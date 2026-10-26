"""Permission tiers, OWB_ID parsing and the global error handlers (modules/permissions.py)."""
import discord
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock
from discord import app_commands
from discord.ext import commands

import modules.permissions as permissions
from modules.config_parsing import normalize_owb_id, parse_id_list
from modules.permissions import (
    NotBotOwner, NotGuildAdmin, MissingOWBRole, MissingOWBRolePrefix,
    bot_owner_only, guild_admin_only, owb_role_required, owb_role_required_prefix,
    resolve_owb_role, on_app_command_error, on_prefix_command_error,
)
from tests.conftest import _mock_config, sent_text

OWB_ROLE = SimpleNamespace(id=123, name="OWB")
OTHER_ROLE = SimpleNamespace(id=456, name="Members")


@pytest.fixture(autouse=True)
def setup(mocker):
    mocker.patch.object(_mock_config, "owb_id", 123)
    mocker.patch.dict(permissions._last_denial_log, clear=True)


@pytest.fixture
def log(mocker):
    import utils.Logger
    return mocker.patch.object(utils.Logger, "log", new_callable=AsyncMock)


def make_member(roles=(), admin=False):
    member = MagicMock(spec=discord.Member)
    member.id = 42
    member.roles = list(roles)
    member.get_role = MagicMock(side_effect=lambda role_id: next((r for r in member.roles if r.id == role_id), None))
    member.guild_permissions = MagicMock(administrator=admin)
    member.__str__ = MagicMock(return_value="someone")
    return member


USERS = {
    "owner": dict(owner=True, admin=False, roles=()),
    "admin": dict(owner=False, admin=True, roles=()),
    "owb": dict(owner=False, admin=False, roles=(OWB_ROLE,)),
    "member": dict(owner=False, admin=False, roles=(OTHER_ROLE,)),
}


def make_interaction(kind="member", dm=False, command="admin shutdown"):
    user = USERS[kind]
    interaction = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=user["owner"])
    interaction.user = make_member(user["roles"], admin=user["admin"])
    interaction.guild = None if dm else MagicMock()
    interaction.permissions = MagicMock(administrator=user["admin"] and not dm)
    interaction.command.qualified_name = command
    interaction.command._has_any_error_handlers = MagicMock(return_value=False)
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def predicate_of(decorator):
    async def command(interaction):
        pass
    decorator(command)
    return command.__discord_app_commands_checks__[0]


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

EXPECTED = {
    # decorator: (users who pass, error for the others)
    "bot_owner_only": ({"owner"}, NotBotOwner),
    "guild_admin_only": ({"owner", "admin"}, NotGuildAdmin),
    "owb_role_required": ({"owner", "admin", "owb"}, MissingOWBRole),
}
DECORATORS = {"bot_owner_only": bot_owner_only, "guild_admin_only": guild_admin_only, "owb_role_required": owb_role_required}


@pytest.mark.parametrize("tier", list(EXPECTED))
@pytest.mark.parametrize("kind", list(USERS))
async def test_tier_matrix(tier, kind, log):
    allowed, error = EXPECTED[tier]
    predicate = predicate_of(DECORATORS[tier]())
    interaction = make_interaction(kind)
    if kind in allowed:
        assert await predicate(interaction) is True
    else:
        with pytest.raises(error):
            await predicate(interaction)


@pytest.mark.parametrize("tier", ["guild_admin_only", "owb_role_required"])
@pytest.mark.parametrize("kind", list(USERS))
async def test_guild_tiers_refuse_dms(tier, kind):
    with pytest.raises(app_commands.NoPrivateMessage):
        await predicate_of(DECORATORS[tier]())(make_interaction(kind, dm=True))


async def test_owner_passes_bot_owner_check_in_dm():
    assert await predicate_of(bot_owner_only())(make_interaction("owner", dm=True)) is True


async def test_error_messages_are_user_facing(log):
    with pytest.raises(NotBotOwner, match="Only the bot owner can use this command."):
        await predicate_of(bot_owner_only())(make_interaction("admin"))
    with pytest.raises(NotGuildAdmin, match="Administrator permission required."):
        await predicate_of(guild_admin_only())(make_interaction("owb"))
    with pytest.raises(MissingOWBRole, match="requires the OWB role"):
        await predicate_of(owb_role_required())(make_interaction("member"))


# ---------------------------------------------------------------------------
# OWB_ID resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("owb_id,has_role", [
    ("123", True), (123, True), (" 123 ", True), ("OWB", True),
    ("999", False), (999, False), ("owb", False), (None, False), (" ", False), ("", False),
])
async def test_owb_id_forms(mocker, owb_id, has_role):
    mocker.patch.object(_mock_config, "owb_id", owb_id)
    member = make_member([OTHER_ROLE, OWB_ROLE])
    assert (resolve_owb_role(member) is OWB_ROLE) is has_role
    predicate = predicate_of(owb_role_required())
    interaction = make_interaction("owb")
    if has_role:
        assert await predicate(interaction) is True
    else:
        with pytest.raises(MissingOWBRole):
            await predicate(interaction)


async def test_unset_owb_id_still_lets_admins_and_owner_in(mocker):
    mocker.patch.object(_mock_config, "owb_id", None)
    predicate = predicate_of(owb_role_required())
    assert await predicate(make_interaction("admin")) is True
    assert await predicate(make_interaction("owner")) is True


def test_resolve_owb_role_needs_a_member():
    user = MagicMock(spec=discord.User)
    assert resolve_owb_role(user) is None


@pytest.mark.parametrize("value,expected", [
    ("123456789012345678", 123456789012345678), (123, 123), ("  42 ", 42),
    ("OWB", "OWB"), (" Sound Mods ", "Sound Mods"), (None, None), ("", None), (" ", None), (True, None),
])
def test_normalize_owb_id(value, expected):
    assert normalize_owb_id(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("", []), (None, []), ("1", [1]), ("1, 2,3", [1, 2, 3]), (" 1 ,, 2 ", [1, 2]),
    (5, [5]), ([1, "2"], [1, 2]), ("1, bob, 3", [1, 3]),
])
def test_parse_id_list(value, expected):
    assert parse_id_list(value) == expected


# ---------------------------------------------------------------------------
# Prefix adapter
# ---------------------------------------------------------------------------

def make_ctx(kind="member", dm=False):
    user = USERS[kind]
    ctx = MagicMock()
    ctx.guild = None if dm else MagicMock()
    ctx.bot.is_owner = AsyncMock(return_value=user["owner"])
    ctx.author = make_member(user["roles"], admin=user["admin"])
    ctx.send = AsyncMock()
    return ctx


def prefix_predicate():
    async def command(ctx):
        pass
    owb_role_required_prefix()(command)
    return command.__commands_checks__[0]


@pytest.mark.parametrize("kind,allowed", [("owner", True), ("admin", True), ("owb", True), ("member", False)])
async def test_prefix_adapter(kind, allowed):
    predicate = prefix_predicate()
    if allowed:
        assert await predicate(make_ctx(kind)) is True
    else:
        with pytest.raises(MissingOWBRolePrefix):
            await predicate(make_ctx(kind))


async def test_prefix_adapter_refuses_dms():
    with pytest.raises(commands.NoPrivateMessage):
        await prefix_predicate()(make_ctx("owner", dm=True))


async def test_prefix_error_handler_replies_briefly():
    ctx = make_ctx()
    await on_prefix_command_error(ctx, MissingOWBRolePrefix("This command requires the OWB role."))
    assert "requires the OWB role" in sent_text(ctx.send)
    assert ctx.send.call_args.kwargs["delete_after"] == 10


async def test_prefix_error_handler_ignores_other_errors():
    ctx = make_ctx()
    await on_prefix_command_error(ctx, commands.CommandNotFound("nope"))
    ctx.send.assert_not_called()


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

async def test_audit_logs_privileged_action(log):
    interaction = make_interaction("owner", command="admin presence")
    await permissions.audit(interaction, detail="hello")
    message = log.call_args.args[0]
    assert message.startswith("🔐") and "(`42`)" in message and "/admin presence: hello" in message


async def test_owner_denials_are_logged_and_throttled(log, mocker):
    clock = mocker.patch.object(permissions.time, "monotonic", return_value=1000.0)
    predicate = predicate_of(bot_owner_only())
    for _ in range(3):
        with pytest.raises(NotBotOwner):
            await predicate(make_interaction("admin"))
    log.assert_awaited_once()
    assert "⛔" in log.call_args.args[0] and "tried /admin shutdown" in log.call_args.args[0]
    assert log.call_args.args[2] == "WARNING"

    clock.return_value = 1000.0 + permissions.DENIAL_LOG_INTERVAL
    with pytest.raises(NotBotOwner):
        await predicate(make_interaction("admin"))
    assert log.await_count == 2


async def test_audit_never_raises_when_log_channel_fails(log):
    log.side_effect = TypeError("int() argument must be a string")
    await permissions.audit(make_interaction("owner"))


# ---------------------------------------------------------------------------
# Global app command error handler
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("error,text", [
    (NotBotOwner("Only the bot owner can use this command."), "Only the bot owner"),
    (NotGuildAdmin("Administrator permission required."), "Administrator permission required"),
    (MissingOWBRole("This command requires the OWB role."), "requires the OWB role"),
    (app_commands.NoPrivateMessage(), "cannot be used in direct messages"),
    (app_commands.MissingRole(123), "123"),
    (app_commands.CheckFailure(), "You don't have permission"),
])
async def test_check_failures_get_an_ephemeral_reply(error, text):
    interaction = make_interaction()
    await on_app_command_error(interaction, error)
    assert text in sent_text(interaction.response.send_message)
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


async def test_unexpected_errors_are_logged_and_answered(mocker):
    log = mocker.patch.object(permissions, "_log")
    interaction = make_interaction()
    error = app_commands.CommandInvokeError(MagicMock(), RuntimeError("secret detail"))
    await on_app_command_error(interaction, error)
    text = sent_text(interaction.response.send_message)
    assert "Something went wrong" in text and "secret detail" not in text
    log.error.assert_called_once()


async def test_uses_followup_when_already_responded():
    interaction = make_interaction()
    interaction.response.is_done.return_value = True
    await on_app_command_error(interaction, NotBotOwner("Only the bot owner can use this command."))
    interaction.response.send_message.assert_not_called()
    assert interaction.followup.send.call_args.kwargs["ephemeral"] is True


async def test_commands_with_their_own_handler_are_left_alone():
    interaction = make_interaction()
    interaction.command._has_any_error_handlers.return_value = True
    await on_app_command_error(interaction, NotGuildAdmin("Administrator permission required."))
    interaction.response.send_message.assert_not_called()
    interaction.followup.send.assert_not_called()


async def test_reply_failure_is_swallowed():
    interaction = make_interaction()
    interaction.response.send_message.side_effect = discord.NotFound(MagicMock(status=404, reason="Not Found"), "Unknown interaction")
    await on_app_command_error(interaction, NotBotOwner("x"))


async def test_tree_uses_the_handler():
    bot = commands.Bot(command_prefix="'", intents=discord.Intents.none())
    bot.tree.error(on_app_command_error)
    assert bot.tree.on_error is on_app_command_error
