"""
Command-tree audit: loads every cog the bot loads and checks each command's permission tier,
so a privileged command can't ship without its check.

When you add a command on purpose, add it to PRIVILEGED or PUBLIC below.
"""
import ast
import discord
import pytest
from discord import app_commands
from discord.ext import commands

from tests.conftest import APP_DIR

# full command name -> the modules.permissions helper that must guard it
PRIVILEGED = {
    "admin shutdown": "bot_owner_only",
    "admin presence": "bot_owner_only",
    "admin stats": "bot_owner_only",
    "admin avatar": "bot_owner_only",
    "restart": "owb_role_required",
    "add": "owb_role_required",
}
# every command under these groups needs the helper (new subcommands included)
PRIVILEGED_GROUPS = {
    "admin": "bot_owner_only",
    "antispam": "guild_admin_only",
    "reports": "guild_admin_only",
}
PUBLIC = {
    "ping", "github", "help", "sounds", "folders",
    "stats top", "stats sound", "stats user", "stats new", "stats hour", "stats day", "stats week", "stats month",
    "entrance set", "entrance info", "entrance remove",
    "quicksounds set", "quicksounds info",
}
# top-level commands and groups that must not be offered in DMs
GUILD_ONLY = {"admin", "antispam", "restart", "add", "stats", "sounds"}
PREFIX_PRIVILEGED = {"mod": "owb_role_required_prefix"}


def configured_extensions():
    """__extensions__ from modules/app_config.py (the real module can't be imported in tests)."""
    tree = ast.parse((APP_DIR / "modules" / "app_config.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "__extensions__":
            return ast.literal_eval(node.value)
    raise AssertionError("__extensions__ not found")


def has_helper_check(command, helper):
    return any(getattr(check, "__module__", "") == "modules.permissions"
               and check.__qualname__.startswith(helper + ".") for check in command.checks)


def permission_problems(bot):
    problems = []
    for command in bot.tree.walk_commands():
        name = command.qualified_name
        # ext.commands checks (e.g. commands.is_owner) on an app command are silently ignored
        callback = getattr(command, "callback", None)
        if callback is not None and getattr(callback, "__commands_checks__", None):
            problems.append(f"/{name}: uses discord.ext.commands checks, which app commands ignore")
        if any(getattr(check, "__module__", "").startswith("discord.ext.commands") for check in getattr(command, "checks", [])):
            problems.append(f"/{name}: has a discord.ext.commands check")
        if isinstance(command, app_commands.Group):
            continue

        root = command.root_parent.name if command.root_parent else None
        if name in PRIVILEGED:
            helper = PRIVILEGED[name]
        elif root in PRIVILEGED_GROUPS:
            helper = PRIVILEGED_GROUPS[root]
        elif name in PUBLIC:
            continue
        else:
            problems.append(f"/{name}: not classified, add it to PRIVILEGED or PUBLIC in this test")
            continue
        if not has_helper_check(command, helper):
            problems.append(f"/{name}: missing the {helper}() check")

    for command in bot.tree.get_commands():
        if command.name in PRIVILEGED_GROUPS:
            if not (command.default_permissions and command.default_permissions.administrator):
                problems.append(f"/{command.name}: group should default to Administrator (ADMIN_DEFAULT)")
        if command.name in GUILD_ONLY and not command.guild_only:
            problems.append(f"/{command.name}: should be guild_only")

    for command in bot.walk_commands():
        helper = PREFIX_PRIVILEGED.get(command.qualified_name)
        if helper and not any(check.__qualname__.startswith(helper + ".") for check in command.checks):
            problems.append(f"'{command.qualified_name}: missing the {helper}() check")
    return problems


@pytest.fixture
async def bot(antispam_guard, mocker):
    import cogs.AntiSpam
    mocker.patch.object(cogs.AntiSpam, "guard", antispam_guard)
    bot = commands.Bot(command_prefix="'", intents=discord.Intents.default())
    for name in configured_extensions():
        module = __import__(f"cogs.{name}", fromlist=["setup"])
        await module.setup(bot)
    return bot


async def test_every_cog_loads(bot):
    assert set(bot.cogs) == set(configured_extensions())


async def test_command_tree_permissions(bot):
    assert permission_problems(bot) == []


async def test_every_classified_command_exists(bot):
    names = {command.qualified_name for command in bot.tree.walk_commands()}
    stale = (set(PRIVILEGED) | PUBLIC) - names
    assert stale == set(), f"commands listed here no longer exist: {stale}"


async def test_admin_group_is_hidden_and_guild_only(bot):
    group = bot.tree.get_command("admin")
    assert group.default_permissions.administrator is True
    assert group.guild_only is True
    payload = group.to_dict(bot.tree)
    assert int(payload["default_member_permissions"]) == discord.Permissions(administrator=True).value
    # discord only honours default permissions on top-level commands, not subcommands
    assert all(sub.default_permissions is None for sub in group.commands)


async def test_registration_payload_builds(bot):
    [command.to_dict(bot.tree) for command in bot.tree.get_commands()]


# ---------------------------------------------------------------------------
# The audit catches the mistakes it is meant to catch
# ---------------------------------------------------------------------------

async def test_audit_flags_ext_commands_checks_on_app_commands():
    class Broken(commands.Cog):
        group = app_commands.Group(name="admin", description="x")

        @group.command(name="shutdown")
        @commands.is_owner()
        async def shutdown(self, interaction: discord.Interaction):
            pass

    bot = commands.Bot(command_prefix="'", intents=discord.Intents.none())
    await bot.add_cog(Broken())
    problems = permission_problems(bot)
    assert "/admin shutdown: uses discord.ext.commands checks, which app commands ignore" in problems
    assert "/admin shutdown: missing the bot_owner_only() check" in problems
    assert "/admin: group should default to Administrator (ADMIN_DEFAULT)" in problems
    assert "/admin: should be guild_only" in problems


async def test_audit_flags_new_unchecked_subcommand_in_privileged_group():
    from modules.permissions import ADMIN_DEFAULT, guild_admin_only

    class Reports(commands.Cog):
        group = app_commands.Group(name="reports", description="x", default_permissions=ADMIN_DEFAULT, guild_only=True)

        @group.command(name="weekly")
        @guild_admin_only()
        async def weekly(self, interaction: discord.Interaction):
            pass

        @group.command(name="forgot")
        async def forgot(self, interaction: discord.Interaction):
            pass

    bot = commands.Bot(command_prefix="'", intents=discord.Intents.none())
    await bot.add_cog(Reports())
    assert permission_problems(bot) == ["/reports forgot: missing the guild_admin_only() check"]


async def test_audit_flags_unclassified_commands():
    class New(commands.Cog):
        @app_commands.command(name="brand-new")
        async def brand_new(self, interaction: discord.Interaction):
            pass

    bot = commands.Bot(command_prefix="'", intents=discord.Intents.none())
    await bot.add_cog(New())
    assert permission_problems(bot) == ["/brand-new: not classified, add it to PRIVILEGED or PUBLIC in this test"]


async def test_audit_rejects_lookalike_checks():
    def bot_owner_only():
        async def predicate(interaction):
            return True
        return app_commands.check(predicate)

    class Fake(commands.Cog):
        @app_commands.command(name="restart")
        @app_commands.guild_only()
        @bot_owner_only()
        async def restart(self, interaction: discord.Interaction):
            pass

    bot = commands.Bot(command_prefix="'", intents=discord.Intents.none())
    await bot.add_cog(Fake())
    assert permission_problems(bot) == ["/restart: missing the owb_role_required() check"]
