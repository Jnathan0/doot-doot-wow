import pytest
from unittest.mock import MagicMock, AsyncMock

import cogs.Player as cog_module
from cogs.Player import Player as PlayerCog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_cog():
    bot = MagicMock()
    cog = PlayerCog(bot)
    # discord.py's Command.__call__ only prepends `self.cog` when cog is set.
    # Without add_cog(), we inject it manually so tests can call commands normally.
    for cmd in cog.__cog_commands__:
        cmd.cog = cog
    return cog


# ---------------------------------------------------------------------------
# master_command tests
# ---------------------------------------------------------------------------


class TestMasterCommand:
    async def test_master_command_direct_sound(self, mock_ctx, mock_sound, mocker):
        """Direct alias -> player.play called with Sound and reverse=False; enqueue direct."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mock_inc = mocker.patch("cogs.Player.increment_playcount")
        mock_enqueue = mocker.patch.object(cog_module.config.worker_queue, "enqueue")

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}

        cog = make_cog()
        await cog.master_command(mock_ctx)

        mock_play.assert_called_once_with(mock_ctx, mock_sound, False)
        mock_inc.assert_called_once_with("test_sound")
        mock_enqueue.assert_called_once()
        # enqueue(update_metadata, user_id, sound_id, call_type) — call_type is args[3]
        args = mock_enqueue.call_args[0]
        assert args[3] == "direct"

    async def test_master_command_category_picks_randomly(self, mock_ctx, mock_sound, mocker):
        """List alias -> secrets.choice picks a Sound; enqueue with call_type='random'."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mock_inc = mocker.patch("cogs.Player.increment_playcount")
        mock_enqueue = mocker.patch.object(cog_module.config.worker_queue, "enqueue")

        sound1 = MagicMock()
        sound1.sound_id = "test_sound"
        sound2 = MagicMock()
        sound2.sound_id = "test_sound_alt"
        sound_list = [sound1, sound2]

        cog_module.sounds.alias_dict = {"test_sound": sound_list}
        mocker.patch("cogs.Player.secrets.choice", return_value=sound1)

        cog = make_cog()
        await cog.master_command(mock_ctx)

        mock_play.assert_called_once_with(mock_ctx, sound1, False)
        mock_inc.assert_called_once_with(sound1.sound_id)
        args = mock_enqueue.call_args[0]
        assert args[3] == "random"

    async def test_master_command_already_in_voice_returns_early(self, mock_ctx, mock_sound, mocker):
        """Existing voice client -> return immediately without playing."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}
        mock_ctx.message.guild.voice_client = MagicMock()

        cog = make_cog()
        await cog.master_command(mock_ctx)

        mock_play.assert_not_called()

    async def test_master_command_reverse_suffix(self, mock_ctx, mock_sound, mocker):
        """Content ending with reverse_char -> player.play called with reverse=True."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}
        mock_ctx.message.content = "!test_sound -"

        cog = make_cog()
        await cog.master_command(mock_ctx)

        mock_play.assert_called_once_with(mock_ctx, mock_sound, True)

    async def test_master_command_no_reverse(self, mock_ctx, mock_sound, mocker):
        """Normal content (no trailing reverse_char) -> player.play called with reverse=False."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}
        mock_ctx.message.content = "!test_sound"

        cog = make_cog()
        await cog.master_command(mock_ctx)

        mock_play.assert_called_once_with(mock_ctx, mock_sound, False)


# ---------------------------------------------------------------------------
# random command tests
# ---------------------------------------------------------------------------


class TestRandomCommand:
    async def test_random_plays_direct_sound(self, mock_ctx, mock_sound, mocker):
        """Single Sound in alias_dict -> player.play called; ctx.send includes sound_id; enqueue 'random'."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mocker.patch("cogs.Player.increment_playcount")
        mock_enqueue = mocker.patch.object(cog_module.config.worker_queue, "enqueue")
        mocker.patch("cogs.Player.asyncio.sleep", new_callable=AsyncMock)

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}
        mocker.patch("cogs.Player.secrets.choice", return_value="test_sound")

        # ctx.send returns an AsyncMock; give its return value a delete method
        msg_mock = AsyncMock()
        mock_ctx.send.return_value = msg_mock

        mock_ctx.message.content = "!random"

        cog = make_cog()
        await cog.random(mock_ctx)

        mock_play.assert_called_once_with(mock_ctx, mock_sound, False)
        mock_ctx.send.assert_called_once()
        send_text = mock_ctx.send.call_args[0][0]
        assert mock_sound.sound_id in send_text

        # In random command, call_type is passed as a keyword argument
        kwargs = mock_enqueue.call_args[1]
        assert kwargs.get("call_type") == "random"

    async def test_random_picks_from_category(self, mock_ctx, mocker):
        """List value in alias_dict -> second secrets.choice picks from the list."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mock_inc = mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")
        mocker.patch("cogs.Player.asyncio.sleep", new_callable=AsyncMock)

        sound1 = MagicMock()
        sound1.sound_id = "cat_sound"
        sound_list = [sound1]

        cog_module.sounds.alias_dict = {"category": sound_list}

        # First call returns the key, second call returns the Sound from the list
        choice_mock = mocker.patch(
            "cogs.Player.secrets.choice",
            side_effect=["category", sound1],
        )

        msg_mock = AsyncMock()
        mock_ctx.send.return_value = msg_mock
        mock_ctx.message.content = "!random"

        cog = make_cog()
        await cog.random(mock_ctx)

        mock_play.assert_called_once_with(mock_ctx, sound1, False)
        mock_inc.assert_called_once_with(sound1.sound_id)

    async def test_random_deletes_calling_message(self, mock_ctx, mock_sound, mocker):
        """ctx.message.delete is called before player.play."""
        call_order = []

        mock_ctx.message.delete = AsyncMock(side_effect=lambda: call_order.append("delete"))

        async def _play(*args, **kwargs):
            call_order.append("play")

        mocker.patch("cogs.Player.player.play", side_effect=_play)
        mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")
        mocker.patch("cogs.Player.asyncio.sleep", new_callable=AsyncMock)

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}
        mocker.patch("cogs.Player.secrets.choice", return_value="test_sound")

        msg_mock = AsyncMock()
        mock_ctx.send.return_value = msg_mock
        mock_ctx.message.content = "!random"

        cog = make_cog()
        await cog.random(mock_ctx)

        mock_ctx.message.delete.assert_called_once()
        assert call_order.index("delete") < call_order.index("play")

    async def test_random_cleanup_message_deleted_after_sleep(self, mock_ctx, mock_sound, mocker):
        """The message sent by ctx.send is deleted after asyncio.sleep."""
        mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")
        mock_sleep = mocker.patch("cogs.Player.asyncio.sleep", new_callable=AsyncMock)

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}
        mocker.patch("cogs.Player.secrets.choice", return_value="test_sound")

        msg_mock = AsyncMock()
        msg_mock.delete = AsyncMock()
        mock_ctx.send.return_value = msg_mock
        mock_ctx.message.content = "!random"

        cog = make_cog()
        await cog.random(mock_ctx)

        mock_sleep.assert_called_once_with(10)
        msg_mock.delete.assert_called_once()

    async def test_random_already_in_voice_returns_early(self, mock_ctx, mock_sound, mocker):
        """Existing voice client -> return after deleting message, without playing."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")
        mocker.patch("cogs.Player.asyncio.sleep", new_callable=AsyncMock)

        cog_module.sounds.alias_dict = {"test_sound": mock_sound}
        mock_ctx.message.guild.voice_client = MagicMock()
        mock_ctx.message.content = "!random"

        cog = make_cog()
        await cog.random(mock_ctx)

        mock_play.assert_not_called()

    async def test_random_reverse_suffix(self, mock_ctx, mock_sound, mocker):
        """Content ending with reverse_char -> player.play called with reverse=True."""
        mock_play = mocker.patch("cogs.Player.player.play", new_callable=AsyncMock)
        mocker.patch("cogs.Player.increment_playcount")
        mocker.patch.object(cog_module.config.worker_queue, "enqueue")
        mocker.patch("cogs.Player.asyncio.sleep", new_callable=AsyncMock)

        cog_module.sounds.alias_dict = {"random": mock_sound}
        mocker.patch("cogs.Player.secrets.choice", return_value="random")

        msg_mock = AsyncMock()
        mock_ctx.send.return_value = msg_mock
        mock_ctx.message.content = "!random -"

        cog = make_cog()
        await cog.random(mock_ctx)

        mock_play.assert_called_once_with(mock_ctx, mock_sound, True)


# ---------------------------------------------------------------------------
# stop command tests
# ---------------------------------------------------------------------------


class TestStopCommand:
    async def test_stop_in_voice_disconnects(self, mock_ctx):
        """Active voice client -> disconnect is called."""
        voice_client = AsyncMock()
        mock_ctx.message.guild.voice_client = voice_client

        cog = make_cog()
        await cog.stop(mock_ctx)

        voice_client.disconnect.assert_called_once()

    async def test_stop_not_in_voice(self, mock_ctx):
        """No voice client -> disconnect is never called."""
        mock_ctx.message.guild.voice_client = None

        cog = make_cog()
        await cog.stop(mock_ctx)

        # Nothing to assert on disconnect — just verify no AttributeError was raised
        # and message.delete was still called (next test). Passes if no exception.

    async def test_stop_always_deletes_message(self, mock_ctx):
        """ctx.message.delete is called regardless of voice state."""
        # Test with no voice client
        mock_ctx.message.guild.voice_client = None
        cog = make_cog()
        await cog.stop(mock_ctx)
        mock_ctx.message.delete.assert_called_once()

        # Reset and test with active voice client
        mock_ctx.message.delete.reset_mock()
        mock_ctx.message.guild.voice_client = AsyncMock()
        await cog.stop(mock_ctx)
        mock_ctx.message.delete.assert_called_once()
