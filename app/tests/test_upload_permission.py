"""/add is limited to the OWB role, refused uploads DM the server admins with how to allow them."""
import asyncio
import discord
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

import cogs.Media as media_module
import modules.permissions as permissions
from modules.permissions import MissingOWBRole, owb_role_required
from tests.conftest import _mock_config, sent_text

OWB_ROLE = SimpleNamespace(id=123, name="Sound Uploaders")


def make_member(user_id, admin=False, bot=False, roles=(), name=None):
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.bot = bot
    member.display_name = name or f"user{user_id}"
    member.mention = f"<@{user_id}>"
    member.roles = list(roles)
    member.get_role = MagicMock(side_effect=lambda role_id: next((r for r in member.roles if r.id == role_id), None))
    member.guild_permissions = MagicMock(administrator=admin)
    member.send = AsyncMock()
    member.__str__ = MagicMock(return_value=member.display_name)
    return member


@pytest.fixture(autouse=True)
def setup(mocker):
    mocker.patch.object(_mock_config, "owb_id", 123)
    mocker.patch.dict(media_module._last_upload_request, clear=True)
    mocker.patch.dict(permissions._last_denial_log, clear=True)


@pytest.fixture
def log(mocker):
    import utils.Logger
    return mocker.patch.object(utils.Logger, "log", new_callable=AsyncMock)


@pytest.fixture
def guild():
    guild = MagicMock()
    guild.id = 10
    guild.name = "The Server"
    guild.roles = [OWB_ROLE]
    guild.get_role = MagicMock(side_effect=lambda role_id: OWB_ROLE if role_id == OWB_ROLE.id else None)
    guild.owner = make_member(1, admin=True, name="owner")
    guild.members = [
        guild.owner,
        make_member(2, admin=True, name="admin"),
        make_member(3, name="uploader", roles=[OWB_ROLE]),
        make_member(4, admin=True, bot=True, name="somebot"),
        make_member(5, name="newbie"),
    ]
    return guild


def make_interaction(guild, user, filename="airhorn.mp3"):
    interaction = MagicMock()
    interaction.guild = guild
    interaction.user = user
    interaction.client.is_owner = AsyncMock(return_value=False)
    interaction.permissions = MagicMock(administrator=user.guild_permissions.administrator)
    interaction.namespace = SimpleNamespace(attachment=SimpleNamespace(filename=filename))
    interaction.command.qualified_name = "add"
    return interaction


def member(guild, user_id):
    return next(m for m in guild.members if m.id == user_id)


async def check_add(interaction):
    """Runs /add's checks like discord.py does before the command, then waits for the background DMs."""
    try:
        return await media_module.Media.add_command._check_can_run(interaction)
    finally:
        await asyncio.gather(*list(permissions._background_tasks))


async def test_member_without_role_is_refused_and_admins_are_dmd(guild, log):
    newbie = member(guild, 5)
    with pytest.raises(MissingOWBRole, match="Uploading sounds requires the OWB role. The server admins have been told"):
        await check_add(make_interaction(guild, newbie))

    for admin_id in (1, 2):
        dm = sent_text(member(guild, admin_id).send)
        assert "**newbie** (<@5>) tried to upload `airhorn.mp3` with `/add` in **The Server**" in dm
        assert "right-click newbie → Roles → tick **Sound Uploaders**" in dm
    # bots, non-admins and the person themselves aren't DM'd
    for other_id in (3, 4, 5):
        member(guild, other_id).send.assert_not_called()
    assert "tried /add" in log.call_args.args[0]


@pytest.mark.parametrize("user_id", [1, 2, 3])
async def test_role_holders_and_admins_can_upload(guild, user_id):
    assert await check_add(make_interaction(guild, member(guild, user_id))) is True
    assert not any(m.send.called for m in guild.members)


async def test_admin_dms_are_throttled_per_member(guild, log, mocker):
    clock = mocker.patch.object(media_module.time, "monotonic", return_value=1000.0)
    newbie = member(guild, 5)
    for _ in range(3):
        with pytest.raises(MissingOWBRole):
            await check_add(make_interaction(guild, newbie))
    assert member(guild, 1).send.await_count == 1

    other = make_member(6, name="other")
    guild.members.append(other)
    with pytest.raises(MissingOWBRole):
        await check_add(make_interaction(guild, other))
    assert member(guild, 1).send.await_count == 2

    clock.return_value = 1000.0 + media_module.UPLOAD_REQUEST_INTERVAL
    with pytest.raises(MissingOWBRole):
        await check_add(make_interaction(guild, newbie))
    assert member(guild, 1).send.await_count == 3


async def test_closed_dms_dont_stop_the_others(guild, log):
    member(guild, 1).send.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "Cannot send messages to this user")
    with pytest.raises(MissingOWBRole):
        await check_add(make_interaction(guild, member(guild, 5)))
    member(guild, 2).send.assert_awaited_once()


async def test_refusal_is_not_delayed_by_the_dms(guild, log):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_send(text):
        started.set()
        await release.wait()

    member(guild, 1).send.side_effect = slow_send
    with pytest.raises(MissingOWBRole):
        # the check raises straight away while the DM is still being sent
        await media_module.Media.add_command._check_can_run(make_interaction(guild, member(guild, 5)))
    await started.wait()
    release.set()
    await asyncio.gather(*list(permissions._background_tasks))


def test_message_when_owb_id_is_not_set(guild, mocker):
    mocker.patch.object(_mock_config, "owb_id", None)
    text = media_module.upload_request_message(guild, member(guild, 5), "airhorn.mp3")
    assert "needs the OWB role" in text
    assert "set `OWB_ID` in the bot's `.env`" in text and "only server admins can upload" in text


def test_message_when_owb_id_matches_no_role(guild, mocker):
    mocker.patch.object(_mock_config, "owb_id", "999")
    text = media_module.upload_request_message(guild, member(guild, 5), None)
    assert "`OWB_ID` (`999`) doesn't match a role in this server" in text
    assert "tried to upload with `/add`" in text


def test_message_with_role_name_config(guild, mocker):
    mocker.patch.object(_mock_config, "owb_id", "Sound Uploaders")
    text = media_module.upload_request_message(guild, member(guild, 5), "a.mp3")
    assert "tick **Sound Uploaders**" in text


async def test_failing_hook_does_not_change_the_refusal(guild):
    async def broken(interaction):
        raise RuntimeError("boom")

    async def command(interaction):
        pass
    owb_role_required(on_denied=broken)(command)
    with pytest.raises(MissingOWBRole):
        await command.__discord_app_commands_checks__[0](make_interaction(guild, member(guild, 5)))
    await asyncio.gather(*list(permissions._background_tasks))


async def test_hook_not_called_when_allowed(guild):
    hook = AsyncMock()

    async def command(interaction):
        pass
    owb_role_required(on_denied=hook)(command)
    assert await command.__discord_app_commands_checks__[0](make_interaction(guild, member(guild, 3))) is True
    hook.assert_not_called()
