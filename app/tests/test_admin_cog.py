"""/admin commands (cogs/Admin.py): audit logging, ephemeral stats and avatar validation."""
import pytest
from unittest.mock import MagicMock, AsyncMock

import cogs.Admin as module
from tests.conftest import sent_text


@pytest.fixture
def log(mocker):
    import utils.Logger
    return mocker.patch.object(utils.Logger, "log", new_callable=AsyncMock)


@pytest.fixture
def cog():
    bot = MagicMock()
    bot.close = AsyncMock()
    bot.change_presence = AsyncMock()
    bot.user.edit = AsyncMock()
    return module.Admin(bot)


def make_interaction(command="admin shutdown"):
    interaction = MagicMock()
    interaction.user.id = 42
    interaction.user.__str__ = MagicMock(return_value="owner")
    interaction.command.qualified_name = command
    interaction.response.send_message = AsyncMock()
    return interaction


def attachment(content_type="image/png", size=1000, filename="face.png"):
    file = MagicMock()
    file.content_type = content_type
    file.size = size
    file.filename = filename
    file.read = AsyncMock(return_value=b"\x89PNG data")
    return file


async def run(cog, name, interaction, *args):
    await getattr(type(cog), name).callback(cog, interaction, *args)


async def test_shutdown_is_audited_before_closing(cog, log):
    order = []
    log.side_effect = lambda *a, **k: order.append("audit")
    cog.bot.close.side_effect = lambda: order.append("close")
    await run(cog, "admin_shutdown_command", make_interaction())
    assert order == ["audit", "close"]
    assert "ran /admin shutdown" in log.call_args.args[0]


async def test_presence_is_audited(cog, log):
    interaction = make_interaction("admin presence")
    await run(cog, "admin_setpresence_command", interaction, "hello world")
    cog.bot.change_presence.assert_awaited_once()
    assert "/admin presence: hello world" in log.call_args.args[0]


async def test_stats_reply_is_ephemeral(cog):
    interaction = make_interaction("admin stats")
    await run(cog, "admin_stats_command", interaction)
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


async def test_avatar_uploads_the_image(cog, log):
    interaction = make_interaction("admin avatar")
    await run(cog, "admin_avatar_command", interaction, attachment())
    cog.bot.user.edit.assert_awaited_once_with(avatar=b"\x89PNG data")
    assert "/admin avatar: face.png" in log.call_args.args[0]
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.parametrize("file,text", [
    (attachment(content_type="application/pdf"), "must be an image"),
    (attachment(content_type=None), "must be an image"),
    (attachment(size=module.AVATAR_SIZE_LIMIT + 1), "at most 8 MB"),
])
async def test_avatar_validation(cog, log, file, text):
    interaction = make_interaction("admin avatar")
    await run(cog, "admin_avatar_command", interaction, file)
    cog.bot.user.edit.assert_not_called()
    assert text in sent_text(interaction.response.send_message)
    log.assert_not_called()


def test_avatar_and_stats_are_separate_methods():
    assert module.Admin.admin_stats_command.name == "stats"
    assert module.Admin.admin_avatar_command.name == "avatar"
