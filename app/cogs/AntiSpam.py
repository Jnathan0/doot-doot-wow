"""
This Cog provides the /antispam admin commands for the sound-spam timeout, and the
listeners that notify users when they are timed out (see modules/antispam.py).
"""
import datetime
import logging
import traceback
import discord
from dataclasses import replace
from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands
from modules.antispam import (
    guard, AntiSpamSettings, InvalidSetting, SoundTimeoutActive, TimeoutInfo,
    MAX_TIMEOUT_SECONDS, DISCORD_TIMEOUT_MAX_SECONDS,
)
from modules.durations import DurationUnit, to_seconds, humanize
from modules.helper_functions import format_markdown
from modules.media import SoundConfirmationDiag
from modules.menus import ButtonMenu
from modules.permissions import ADMIN_DEFAULT, NotGuildAdmin, guild_admin_only
from utils import Logger

# same logger discord.py's default on_command_error uses
_command_log = logging.getLogger("discord.ext.commands.bot")

PAGE_SIZE = 10


def _format_value(name, value):
    if name.endswith("_seconds"):
        return humanize(value)
    if name == "exempt_role_ids":
        return ", ".join(str(role_id) for role_id in value) or "none"
    return str(value)


def _describe_trigger(info: TimeoutInfo) -> str:
    if info.reason == "auto" and info.trigger_plays:
        return f"{info.trigger_plays} plays in {humanize(info.trigger_window_s)}"
    return info.note or info.reason


@app_commands.guild_only()
@app_commands.default_permissions(ADMIN_DEFAULT)
class AntiSpam(commands.GroupCog, group_name="antispam",
               group_description="Configure the sound-spam timeout (admins only)"):
    def __init__(self, bot):
        self.bot = bot

    exempt_role_group = app_commands.Group(name="exempt-role", description="Roles that are never timed out from sounds")

    async def cog_load(self) -> None:
        await guard.load()

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        original = getattr(error, "original", error)
        if isinstance(error, NotGuildAdmin):
            message = str(error)
        elif isinstance(error, app_commands.NoPrivateMessage):
            message = "This command can only be used in a server."
        elif isinstance(original, InvalidSetting):
            message = f"Error: {original}"
        else:
            traceback.print_exception(type(original), original, original.__traceback__)
            message = "An error occoured while processing this command. If this persists please notify an admin."
        await self._reply(interaction, format_markdown(message))

    # -- helpers ------------------------------------------------------------

    async def _reply(self, interaction: discord.Interaction, content=None, **kwargs):
        kwargs.setdefault("ephemeral", True)
        if interaction.response.is_done():
            await interaction.followup.send(content, **kwargs)
        else:
            await interaction.response.send_message(content, **kwargs)

    async def _log(self, message, settings: AntiSpamSettings, force=False):
        if not (settings.log_to_log_channel or force):
            return
        try:
            await Logger.log(message, self.bot, "INFO")
        except Exception as e:
            print(f"antispam: could not write to the log channel: {e}")

    async def _update(self, interaction: discord.Interaction, **changes) -> AntiSpamSettings:
        """Saves changed settings (raises InvalidSetting) and logs the change to LOG_CHANNEL."""
        old = guard.settings_for(interaction.guild_id)
        new = await guard.update_settings(interaction.guild_id, replace(old, **changes), interaction.user.id)
        diff = new.changes_from(old)
        if diff:
            lines = [f"⚙️ antispam: {interaction.user} set {name} {_format_value(name, before)}→{_format_value(name, after)}"
                     for name, before, after in diff]
            await self._log("\n".join(lines), new, force=old.log_to_log_channel)
        return new

    async def _notify(self, member, channel, text, settings: AntiSpamSettings):
        """Tells a member about their timeout, where notify_mode says to."""
        if settings.notify_mode in ("channel", "both") and channel is not None:
            try:
                await channel.send(text, delete_after=15, allowed_mentions=discord.AllowedMentions(users=[member]))
            except discord.HTTPException as e:
                print(f"antispam: could not send timeout notice: {e}")
        if settings.notify_mode in ("dm", "both"):
            try:
                await member.send(text)
            except discord.HTTPException as e:
                print(f"antispam: could not DM timeout notice: {e}")

    async def _discord_timeout(self, member, info: Optional[TimeoutInfo], settings: AntiSpamSettings):
        """Optional server-wide Discord timeout (apply_discord_timeout), info=None removes it."""
        if not settings.apply_discord_timeout:
            return
        try:
            if info is None:
                if member.is_timed_out():
                    await member.timeout(None, reason="Sound spam timeout pardoned")
            else:
                await member.timeout(datetime.timedelta(seconds=info.duration), reason="Sound spam")
        except discord.HTTPException as e:
            await self._log(f"❗ antispam: could not apply a Discord timeout to {member} ({member.id}): {e}", settings)

    def _timeout_cap(self, settings: AntiSpamSettings) -> int:
        return DISCORD_TIMEOUT_MAX_SECONDS if settings.apply_discord_timeout else MAX_TIMEOUT_SECONDS

    # -- listeners ----------------------------------------------------------

    @commands.Cog.listener()
    async def on_sound_timeout(self, ctx, info: TimeoutInfo):
        """Dispatched by modules.antispam.record_play when a play trips the rule."""
        settings = guard.settings_for(info.guild_id)
        member = ctx.author
        text = (f"🔇 {member.mention}, you're timed out from playing sounds for **{humanize(info.duration)}** "
                f"({_describe_trigger(info)}). Ends <t:{info.expires_at}:R>.")
        await self._notify(member, ctx.channel, text, settings)
        await self._discord_timeout(member, info, settings)
        await self._log(f"🔇 antispam: {member} (`{member.id}`) timed out from sounds for {humanize(info.duration)} "
                        f"({_describe_trigger(info)})", settings)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, SoundTimeoutActive):
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            info = error.info
            if guard.should_notify_blocked(info.guild_id, info.user_id):
                text = f"🔇 {ctx.author.mention}, you're still timed out from playing sounds. Ends <t:{info.expires_at}:R>."
                await self._notify(ctx.author, ctx.channel, text, guard.settings_for(info.guild_id))
            return
        # Having any on_command_error listener turns off discord.py's default handler, keep its logging
        command = ctx.command
        if command and command.has_error_handler():
            return
        if ctx.cog and ctx.cog.has_error_handler():
            return
        _command_log.error("Ignoring exception in command %s", command, exc_info=error)

    # -- settings commands --------------------------------------------------

    @app_commands.command(name="status")
    @guild_admin_only()
    async def status_command(self, interaction: discord.Interaction) -> None:
        """Show the anti-spam settings and how many users are timed out."""
        settings = guard.settings_for(interaction.guild_id)
        embed = discord.Embed(
            title="Sound anti-spam",
            colour=discord.Colour.green() if settings.enabled else discord.Colour.light_grey(),
            description=f"**{'Enabled' if settings.enabled else 'Disabled'}**\n{settings.rule_sentence()}.",
        )
        if settings.escalation_enabled:
            escalation = (f"×{settings.escalation_multiplier:g} per repeat offence within "
                          f"{humanize(settings.escalation_lookback_seconds)}, capped at {humanize(settings.max_timeout_seconds)}")
        else:
            escalation = "Off"
        embed.add_field(name="Escalation", value=escalation, inline=False)
        embed.add_field(name="Counted plays", value=(
            "Sound and folder commands: always\n"
            f"Random: {'yes' if settings.count_random else 'no'}\n"
            f"Quicksounds: {'yes' if settings.count_quicksounds else 'no'}\n"
            f"Ignored while the bot is busy: {'yes' if settings.count_ignored_attempts else 'no'}\n"
            "Entrance sounds: never"), inline=True)
        roles = ", ".join(f"<@&{role_id}>" for role_id in settings.exempt_role_ids) or "none"
        embed.add_field(name="Exempt", value=(
            f"Administrators: {'yes' if settings.exempt_administrators else 'no'}\nRoles: {roles}"), inline=True)
        embed.add_field(name="Notifications", value=(
            f"Mode: {settings.notify_mode}\nLog channel: {'yes' if settings.log_to_log_channel else 'no'}"), inline=True)
        embed.add_field(name="Discord timeout", value=(
            "On: also mutes the user server-wide (needs Moderate Members, max 4w)" if settings.apply_discord_timeout
            else "Off (only sound commands are blocked)"), inline=False)
        embed.add_field(name="Active timeouts", value=str(guard.active_count(interaction.guild_id)), inline=False)
        await self._reply(interaction, embed=embed)

    @app_commands.command(name="enable")
    @guild_admin_only()
    async def enable_command(self, interaction: discord.Interaction) -> None:
        """Turn the sound-spam timeout on."""
        settings = await self._update(interaction, enabled=True)
        await self._reply(interaction, f"✅ Anti-spam **enabled**. {settings.rule_sentence()}.")

    @app_commands.command(name="disable")
    @guild_admin_only()
    async def disable_command(self, interaction: discord.Interaction) -> None:
        """Turn the sound-spam timeout off."""
        await self._update(interaction, enabled=False)
        await self._reply(interaction, (
            "Anti-spam **disabled**. Active timeouts are not lifted: they are paused while disabled and "
            "apply again if it is re-enabled before they end. Use `/antispam pardon` to lift one."))

    @app_commands.command(name="rule")
    @guild_admin_only()
    @app_commands.describe(
        max_plays="Number of plays that trips the rule",
        window_amount="Time window the plays have to happen in",
        window_unit="Unit for the window",
        reset_gap_amount="A break this long forgives the streak (0 turns this off)",
        reset_gap_unit="Unit for the reset gap (default seconds)",
    )
    async def rule_command(self, interaction: discord.Interaction,
                           max_plays: app_commands.Range[int, 2, 100],
                           window_amount: app_commands.Range[int, 1, 10_000],
                           window_unit: DurationUnit,
                           reset_gap_amount: Optional[app_commands.Range[int, 0, 10_000]] = None,
                           reset_gap_unit: DurationUnit = "seconds") -> None:
        """Set when a user gets timed out: N plays within a window without a break."""
        changes = {"max_plays": max_plays, "window_seconds": to_seconds(window_amount, window_unit)}
        if reset_gap_amount is not None:
            changes["reset_gap_seconds"] = to_seconds(reset_gap_amount, reset_gap_unit)
        settings = await self._update(interaction, **changes)
        await self._reply(interaction, f"Rule updated: {settings.rule_sentence()}.")

    @app_commands.command(name="duration")
    @guild_admin_only()
    @app_commands.describe(amount="Base timeout length", unit="Unit for the timeout")
    async def duration_command(self, interaction: discord.Interaction,
                               amount: app_commands.Range[int, 1, 10_000], unit: DurationUnit) -> None:
        """Set the base timeout length."""
        seconds = to_seconds(amount, unit)
        old = guard.settings_for(interaction.guild_id)
        # keep the escalation cap at least as long as the base timeout
        settings = await self._update(interaction, timeout_seconds=seconds,
                                      max_timeout_seconds=max(old.max_timeout_seconds, seconds))
        message = f"Base timeout set to **{humanize(settings.timeout_seconds)}**."
        if settings.max_timeout_seconds != old.max_timeout_seconds:
            message += f" Max timeout raised to **{humanize(settings.max_timeout_seconds)}** to match."
        await self._reply(interaction, message)

    @app_commands.command(name="escalation")
    @guild_admin_only()
    @app_commands.describe(
        enabled="Lengthen the timeout for repeat offenders",
        multiplier="Timeout is multiplied by this for each recent offence",
        max_amount="Longest a timeout can get",
        max_unit="Unit for the max timeout (default hours)",
        lookback_amount="How far back previous timeouts count",
        lookback_unit="Unit for the lookback (default hours)",
    )
    async def escalation_command(self, interaction: discord.Interaction, enabled: bool,
                                 multiplier: Optional[app_commands.Range[float, 1.0, 10.0]] = None,
                                 max_amount: Optional[app_commands.Range[int, 1, 10_000]] = None,
                                 max_unit: DurationUnit = "hours",
                                 lookback_amount: Optional[app_commands.Range[int, 1, 10_000]] = None,
                                 lookback_unit: DurationUnit = "hours") -> None:
        """Repeat offender settings."""
        changes = {"escalation_enabled": enabled}
        if multiplier is not None:
            changes["escalation_multiplier"] = float(multiplier)
        if max_amount is not None:
            changes["max_timeout_seconds"] = to_seconds(max_amount, max_unit)
        if lookback_amount is not None:
            changes["escalation_lookback_seconds"] = to_seconds(lookback_amount, lookback_unit)
        settings = await self._update(interaction, **changes)
        if settings.escalation_enabled:
            await self._reply(interaction, (
                f"Escalation **on**: ×{settings.escalation_multiplier:g} per offence within "
                f"{humanize(settings.escalation_lookback_seconds)}, capped at {humanize(settings.max_timeout_seconds)}."))
        else:
            await self._reply(interaction, "Escalation **off**: every timeout is the base length.")

    @app_commands.command(name="counting")
    @guild_admin_only()
    @app_commands.describe(
        random="Count the random command",
        quicksounds="Count quicksounds (1, 2, 3)",
        ignored_attempts="Count commands sent while the bot is already playing",
    )
    async def counting_command(self, interaction: discord.Interaction, random: Optional[bool] = None,
                               quicksounds: Optional[bool] = None, ignored_attempts: Optional[bool] = None) -> None:
        """Choose which kinds of plays count toward the rule."""
        changes = {}
        if random is not None:
            changes["count_random"] = random
        if quicksounds is not None:
            changes["count_quicksounds"] = quicksounds
        if ignored_attempts is not None:
            changes["count_ignored_attempts"] = ignored_attempts
        settings = await self._update(interaction, **changes) if changes else guard.settings_for(interaction.guild_id)
        await self._reply(interaction, (
            f"Counted plays: sound and folder commands always, random **{'yes' if settings.count_random else 'no'}**, "
            f"quicksounds **{'yes' if settings.count_quicksounds else 'no'}**, "
            f"ignored while busy **{'yes' if settings.count_ignored_attempts else 'no'}**."))

    @app_commands.command(name="notify")
    @guild_admin_only()
    @app_commands.describe(mode="Where users are told about their timeout")
    async def notify_command(self, interaction: discord.Interaction,
                             mode: Literal["channel", "dm", "both", "none"]) -> None:
        """Choose how users are told they've been timed out."""
        await self._update(interaction, notify_mode=mode)
        await self._reply(interaction, f"Timeout notices: **{mode}**.")

    @app_commands.command(name="options")
    @guild_admin_only()
    @app_commands.describe(
        exempt_admins="Members with the Administrator permission are never timed out",
        log_channel="Log timeouts, pardons and setting changes to the log channel",
        discord_timeout="Also apply a server-wide Discord timeout (mutes text and voice, max 4 weeks)",
    )
    async def options_command(self, interaction: discord.Interaction, exempt_admins: Optional[bool] = None,
                              log_channel: Optional[bool] = None, discord_timeout: Optional[bool] = None) -> None:
        """Other anti-spam options."""
        changes = {}
        if exempt_admins is not None:
            changes["exempt_administrators"] = exempt_admins
        if log_channel is not None:
            changes["log_to_log_channel"] = log_channel
        if discord_timeout is not None:
            changes["apply_discord_timeout"] = discord_timeout
        settings = await self._update(interaction, **changes) if changes else guard.settings_for(interaction.guild_id)
        message = (f"Exempt administrators **{'yes' if settings.exempt_administrators else 'no'}**, "
                   f"log channel **{'yes' if settings.log_to_log_channel else 'no'}**, "
                   f"Discord timeout **{'on' if settings.apply_discord_timeout else 'off'}**.")
        if settings.apply_discord_timeout:
            message += ("\n⚠️ Discord timeouts mute the user server-wide (text and voice), not just sounds. "
                        "They need the Moderate Members permission and can't apply to members above the bot's role.")
            me = interaction.guild.me if interaction.guild else None
            if me is not None and not me.guild_permissions.moderate_members:
                message += "\n❗ The bot does not have Moderate Members in this server, so they will fail."
        await self._reply(interaction, message)

    @app_commands.command(name="reset-defaults")
    @guild_admin_only()
    async def reset_defaults_command(self, interaction: discord.Interaction) -> None:
        """Restore the default settings (keeps it enabled or disabled)."""
        view = SoundConfirmationDiag()
        await interaction.response.send_message(
            "Reset all anti-spam settings to the defaults? Enabled/disabled is kept.", view=view, ephemeral=True)
        await view.wait()
        if view.confirmed is None:
            await interaction.edit_original_response(content="Timed out, nothing was changed.", view=None)
            return
        if not view.confirmed:
            await view.interaction.response.edit_message(content="Cancelled, nothing was changed.", view=None)
            return
        current = guard.settings_for(interaction.guild_id)
        defaults = AntiSpamSettings(enabled=current.enabled)
        changes = {name: after for name, _, after in defaults.changes_from(current)}
        settings = await self._update(interaction, **changes)
        await view.interaction.response.edit_message(
            content=f"Settings reset to defaults. {settings.rule_sentence()}.", view=None)

    # -- exempt roles -------------------------------------------------------

    @exempt_role_group.command(name="add")
    @guild_admin_only()
    async def exempt_role_add_command(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """Never time out members with this role."""
        settings = guard.settings_for(interaction.guild_id)
        if role.id not in settings.exempt_role_ids:
            settings = await self._update(interaction, exempt_role_ids=settings.exempt_role_ids + (role.id,))
        await self._reply(interaction, f"{role.mention} is exempt from the sound-spam timeout.",
                          allowed_mentions=discord.AllowedMentions.none())

    @exempt_role_group.command(name="remove")
    @guild_admin_only()
    async def exempt_role_remove_command(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """Stop exempting a role."""
        settings = guard.settings_for(interaction.guild_id)
        if role.id in settings.exempt_role_ids:
            await self._update(interaction, exempt_role_ids=tuple(r for r in settings.exempt_role_ids if r != role.id))
            message = f"{role.mention} is no longer exempt."
        else:
            message = f"{role.mention} wasn't exempt."
        await self._reply(interaction, message, allowed_mentions=discord.AllowedMentions.none())

    @exempt_role_group.command(name="list")
    @guild_admin_only()
    async def exempt_role_list_command(self, interaction: discord.Interaction) -> None:
        """List exempt roles."""
        settings = guard.settings_for(interaction.guild_id)
        roles = ", ".join(f"<@&{role_id}>" for role_id in settings.exempt_role_ids) or "none"
        admins = "Administrators are exempt." if settings.exempt_administrators else "Administrators are not exempt."
        await self._reply(interaction, f"Exempt roles: {roles}\n{admins}", allowed_mentions=discord.AllowedMentions.none())

    # -- timeouts -----------------------------------------------------------

    @app_commands.command(name="timeout")
    @guild_admin_only()
    @app_commands.describe(member="Member to time out", amount="Timeout length", unit="Unit for the timeout",
                           reason="(Optional) reason, shown in history")
    async def timeout_command(self, interaction: discord.Interaction, member: discord.Member,
                              amount: app_commands.Range[int, 1, 10_000], unit: DurationUnit,
                              reason: Optional[app_commands.Range[str, 1, 200]] = None) -> None:
        """Manually time a member out of playing sounds."""
        settings = guard.settings_for(interaction.guild_id)
        seconds = to_seconds(amount, unit)
        cap = self._timeout_cap(settings)
        if seconds > cap:
            raise InvalidSetting(f"Timeout can be at most {humanize(cap)}.")
        if member.bot:
            raise InvalidSetting("Bots can't be timed out from sounds.")
        info = await guard.issue(interaction.guild_id, member.id, seconds, "manual",
                                 issued_by=interaction.user.id, note=reason)
        text = (f"🔇 {member.mention}, you've been timed out from playing sounds for **{humanize(info.duration)}**"
                + (f" ({reason})" if reason else "") + f". Ends <t:{info.expires_at}:R>.")
        await self._notify(member, interaction.channel, text, settings)
        await self._discord_timeout(member, info, settings)
        await self._log(f"🔇 antispam: {interaction.user} timed out {member} (`{member.id}`) from sounds for "
                        f"{humanize(info.duration)}" + (f": {reason}" if reason else ""), settings)
        message = f"{member.mention} is timed out from sounds for **{humanize(info.duration)}**, ends <t:{info.expires_at}:R>."
        if not settings.enabled:
            message += "\nNote: anti-spam is disabled, so this isn't enforced unless it's enabled before it ends."
        await self._reply(interaction, message, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="pardon")
    @guild_admin_only()
    @app_commands.describe(member="Member whose timeout to lift")
    async def pardon_command(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Lift a member's sound timeout."""
        settings = guard.settings_for(interaction.guild_id)
        if not await guard.pardon(interaction.guild_id, member.id, interaction.user.id):
            await self._reply(interaction, f"{member.mention} isn't timed out.", allowed_mentions=discord.AllowedMentions.none())
            return
        await self._discord_timeout(member, None, settings)
        await self._log(f"🔊 antispam: {interaction.user} pardoned {member} (`{member.id}`)", settings)
        await self._reply(interaction, f"{member.mention} can play sounds again.", allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="active")
    @guild_admin_only()
    async def active_command(self, interaction: discord.Interaction) -> None:
        """List members who are timed out from sounds."""
        timeouts = await guard.list_active(interaction.guild_id)
        if not timeouts:
            await self._reply(interaction, "No active sound timeouts.")
            return
        lines = [f"• <@{info.user_id}> ends <t:{info.expires_at}:R> ({humanize(info.duration)}, {_describe_trigger(info)})"
                 for info in timeouts]
        pages = [f"**Active sound timeouts ({len(lines)})**\n" + "\n".join(lines[i:i + PAGE_SIZE])
                 for i in range(0, len(lines), PAGE_SIZE)]
        if len(pages) == 1:
            await self._reply(interaction, pages[0], allowed_mentions=discord.AllowedMentions.none())
        else:
            await self._reply(interaction, pages[0], view=ButtonMenu(pages, 600),
                              allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="history")
    @guild_admin_only()
    @app_commands.describe(member="Member to show timeouts for")
    async def history_command(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Last 10 sound timeouts for a member."""
        timeouts = await guard.history(interaction.guild_id, member.id, 10)
        if not timeouts:
            await self._reply(interaction, f"{member.mention} has no sound timeouts.",
                              allowed_mentions=discord.AllowedMentions.none())
            return
        lines = []
        for info in timeouts:
            line = f"• <t:{info.started_at}:f> {humanize(info.duration)}, {info.reason}: {_describe_trigger(info)}"
            if info.issued_by:
                line += f", by <@{info.issued_by}>"
            if info.revoked_at:
                line += f", lifted <t:{info.revoked_at}:R>" + (f" by <@{info.revoked_by}>" if info.revoked_by else "")
            lines.append(line)
        await self._reply(interaction, f"**Sound timeouts for {member.mention}**\n" + "\n".join(lines),
                          allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
