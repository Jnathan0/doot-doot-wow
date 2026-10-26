"""
Permission tiers for privileged commands. Higher tiers include the lower ones:

    BOT_OWNER   - the application owner (or team), or OWNER_IDS when configured
    GUILD_ADMIN - members with the Administrator permission, plus BOT_OWNER
    OWB_ROLE    - members with the OWB_ID role, plus GUILD_ADMIN and BOT_OWNER
    EVERYONE    - no check

The checks run when the command is invoked and fail closed. default_permissions only
hides commands in the client (server admins can override it), so it is never the only guard.

Use bot_owner_only() / guild_admin_only() / owb_role_required() on app commands,
owb_role_required_prefix() on prefix commands, and ADMIN_DEFAULT for groups.
"""
import asyncio
import logging
import time
import discord
from discord import app_commands, Interaction, Permissions
from discord.ext import commands
from .app_config import config
from .config_parsing import normalize_owb_id
from .helper_functions import format_markdown

_log = logging.getLogger("doot-doot")

ADMIN_DEFAULT = Permissions(administrator=True)

# one "tried to use" line per user per 5 minutes in the log channel
DENIAL_LOG_INTERVAL = 300
_last_denial_log = {}

# on_denied hooks run in the background so the denial reply isn't held up, keep references until they finish
_background_tasks = set()


class NotBotOwner(app_commands.CheckFailure):
    pass


class NotGuildAdmin(app_commands.CheckFailure):
    pass


class MissingOWBRole(app_commands.CheckFailure):
    pass


class MissingOWBRolePrefix(commands.CheckFailure):
    pass


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

def guild_owb_role(guild):
    """The guild's OWB role (OWB_ID as a role id, or as a role name), or None if unset or not in this guild."""
    owb_id = normalize_owb_id(config.owb_id)
    if owb_id is None or guild is None:
        return None
    if isinstance(owb_id, int):
        return guild.get_role(owb_id)
    return discord.utils.get(guild.roles, name=owb_id)


def resolve_owb_role(member):
    """The member's OWB role (OWB_ID as a role id, or as a role name), or None."""
    owb_id = normalize_owb_id(config.owb_id)
    if owb_id is None or not isinstance(member, discord.Member):
        return None
    if isinstance(owb_id, int):
        return member.get_role(owb_id)
    return discord.utils.get(member.roles, name=owb_id)


async def is_bot_owner(interaction: Interaction) -> bool:
    return await interaction.client.is_owner(interaction.user)


async def is_guild_admin(interaction: Interaction) -> bool:
    if await is_bot_owner(interaction):
        return True
    return interaction.guild is not None and interaction.permissions.administrator


async def has_owb_role(interaction: Interaction) -> bool:
    if await is_guild_admin(interaction):
        return True
    return interaction.guild is not None and resolve_owb_role(interaction.user) is not None


# ---------------------------------------------------------------------------
# Check decorators
# ---------------------------------------------------------------------------

def bot_owner_only():
    async def predicate(interaction: Interaction) -> bool:
        if not await is_bot_owner(interaction):
            await audit_denial(interaction)
            raise NotBotOwner("Only the bot owner can use this command.")
        return True
    return app_commands.check(predicate)


def guild_admin_only():
    async def predicate(interaction: Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if not await is_guild_admin(interaction):
            raise NotGuildAdmin("Administrator permission required.")
        return True
    return app_commands.check(predicate)


def owb_role_required(message="This command requires the OWB role.", on_denied=None):
    """
    on_denied: optional coroutine function called with the interaction when a member is refused,
    run in the background (it can't delay the reply) and errors in it are only printed.
    """
    async def predicate(interaction: Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if not await has_owb_role(interaction):
            if on_denied is not None:
                _run_in_background(on_denied(interaction))
            raise MissingOWBRole(message)
        return True
    return app_commands.check(predicate)


def _run_in_background(coro):
    async def runner():
        try:
            await coro
        except Exception as e:
            print(f"permissions: denial hook failed: {e}")
    task = asyncio.create_task(runner())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def owb_role_required_prefix():
    """owb_role_required() for prefix commands (ext.commands)."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if await ctx.bot.is_owner(ctx.author):
            return True
        if ctx.author.guild_permissions.administrator:
            return True
        if resolve_owb_role(ctx.author) is not None:
            return True
        raise MissingOWBRolePrefix("This command requires the OWB role.")
    return commands.check(predicate)


# ---------------------------------------------------------------------------
# Audit trail (LOG_CHANNEL)
# ---------------------------------------------------------------------------

def _command_name(interaction: Interaction) -> str:
    command = interaction.command
    return f"/{command.qualified_name}" if command is not None else "an unknown command"


async def _log_to_channel(interaction: Interaction, message: str, level="INFO"):
    from utils import Logger  # imported here, utils.Logger imports the modules package
    try:
        await Logger.log(message, interaction.client, level)
    except Exception as e:
        print(f"permissions: could not write to the log channel: {e}")


async def audit(interaction: Interaction, action=None, detail=""):
    """Logs a privileged action to LOG_CHANNEL, call it before acting."""
    action = action or _command_name(interaction)
    message = f"🔐 {interaction.user} (`{interaction.user.id}`) ran {action}"
    if detail:
        message += f": {detail}"
    await _log_to_channel(interaction, message)


async def audit_denial(interaction: Interaction, action=None):
    """Logs a refused privileged command, at most once per user every DENIAL_LOG_INTERVAL seconds."""
    now = time.monotonic()
    last = _last_denial_log.get(interaction.user.id)
    if last is not None and now - last < DENIAL_LOG_INTERVAL:
        return
    _last_denial_log[interaction.user.id] = now
    action = action or _command_name(interaction)
    await _log_to_channel(interaction, f"⛔ {interaction.user} (`{interaction.user.id}`) tried {action}", "WARNING")


# ---------------------------------------------------------------------------
# Global error handlers, registered in main.py
# ---------------------------------------------------------------------------

async def on_app_command_error(interaction: Interaction, error: app_commands.AppCommandError):
    """
    CommandTree.on_error: answers every failed app command so users never see
    "The application did not respond". Commands, groups and cogs with their own
    error handler are left to it, like discord.py's default handler does.
    """
    command = interaction.command
    if command is not None and command._has_any_error_handlers():
        return
    if isinstance(error, app_commands.CheckFailure):
        message = str(error) or "You don't have permission to use this command."
    else:
        _log.error("Unhandled app command error in %s", _command_name(interaction), exc_info=error)
        message = "Something went wrong running that command."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(format_markdown(message), ephemeral=True)
        else:
            await interaction.response.send_message(format_markdown(message), ephemeral=True)
    except discord.HTTPException as e:
        print(f"permissions: could not send the error reply: {e}")


async def on_prefix_command_error(ctx: commands.Context, error: commands.CommandError):
    """on_command_error listener: short reply when a prefix command is refused by owb_role_required_prefix()."""
    if isinstance(error, MissingOWBRolePrefix):
        try:
            await ctx.send(format_markdown(str(error)), delete_after=10)
        except discord.HTTPException:
            pass
