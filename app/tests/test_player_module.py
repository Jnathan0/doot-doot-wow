import pytest
import discord
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call
import modules.player as player_module
from modules.player import _make_source, _maybe_send_media, Player


# ---------------------------------------------------------------------------
# _make_source tests
# ---------------------------------------------------------------------------


@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
def test_make_source_normal(mock_ffmpeg, mock_randint, mock_sound):
    """Non-rickroll, non-reverse: FFmpegOpusAudio called with sound path and '-vn'."""
    _make_source(mock_sound, reverse=False)

    mock_ffmpeg.assert_called_once_with(
        mock_sound.path,
        before_options="-nostdin -hide_banner -loglevel error",
        options="-vn",
    )


@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
def test_make_source_reverse(mock_ffmpeg, mock_randint, mock_sound):
    """Reverse flag: FFmpegOpusAudio called with sound path and opts containing 'areverse'."""
    _make_source(mock_sound, reverse=True)

    _, kwargs = mock_ffmpeg.call_args
    assert mock_ffmpeg.call_args[0][0] == mock_sound.path
    assert "areverse" in kwargs["options"]


@patch("modules.player.random.randint", return_value=1)
@patch("modules.player.discord.FFmpegOpusAudio")
def test_make_source_rickroll(mock_ffmpeg, mock_randint, mock_sound):
    """randint returns 1: FFmpegOpusAudio called with the rickroll path."""
    _make_source(mock_sound, reverse=False)

    args, _ = mock_ffmpeg.call_args
    assert "rickroll.mp3" in args[0]


# ---------------------------------------------------------------------------
# _maybe_send_media tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("modules.player.discord.File")
async def test_maybe_send_media_with_media(mock_file, mock_ctx, mock_sound_with_media):
    """Sound with media: discord.File constructed and ctx.send called."""
    await _maybe_send_media(mock_ctx, mock_sound_with_media)

    mock_file.assert_called_once()
    mock_ctx.send.assert_called_once()
    _, kwargs = mock_ctx.send.call_args
    assert kwargs.get("delete_after") == 10


@pytest.mark.asyncio
async def test_maybe_send_media_no_media(mock_ctx, mock_sound):
    """Sound with no media: ctx.send is never called."""
    await _maybe_send_media(mock_ctx, mock_sound)

    mock_ctx.send.assert_not_called()


@pytest.mark.asyncio
@patch("modules.player.discord.File")
async def test_maybe_send_media_exception_swallowed(mock_file, mock_ctx, mock_sound_with_media):
    """Exception inside _maybe_send_media is swallowed — nothing propagates."""
    mock_ctx.send.side_effect = Exception("fail")

    # Should not raise
    await _maybe_send_media(mock_ctx, mock_sound_with_media)


# ---------------------------------------------------------------------------
# Player.play tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_user_not_in_voice(mock_ctx, mock_sound):
    """Author is not in a voice channel: send called with warning; connect never called."""
    mock_ctx.author.voice = None

    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "not in a voice channel" in mock_ctx.send.call_args[0][0]
    mock_ctx.author.voice  # still None — connect was never set up, no need to assert separately


@pytest.mark.asyncio
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio", side_effect=FileNotFoundError)
async def test_play_file_not_found(mock_ffmpeg, mock_randint, mock_ctx, mock_sound):
    """FFmpegOpusAudio raises FileNotFoundError: send called with file-not-found message."""
    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "File Not Found" in mock_ctx.send.call_args[0][0]
    mock_ctx.author.voice.channel.connect.assert_not_called()


@pytest.mark.asyncio
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
async def test_play_forbidden_on_connect(mock_ffmpeg, mock_randint, mock_ctx, mock_sound):
    """connect() raises discord.Forbidden: send called with 403 message."""
    mock_ctx.author.voice.channel.connect.side_effect = discord.Forbidden(
        MagicMock(), "Forbidden"
    )

    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "403 Forbidden" in mock_ctx.send.call_args[0][0]


@pytest.mark.asyncio
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
async def test_play_timeout_on_connect(mock_ffmpeg, mock_randint, mock_ctx, mock_sound):
    """connect() raises TimeoutError: send called with timeout message."""
    mock_ctx.author.voice.channel.connect.side_effect = TimeoutError

    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "Timeout" in mock_ctx.send.call_args[0][0]


@pytest.mark.asyncio
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
async def test_play_client_exception_on_connect(mock_ffmpeg, mock_randint, mock_ctx, mock_sound):
    """connect() raises discord.ClientException: send called with 'already playing' message."""
    mock_ctx.author.voice.channel.connect.side_effect = discord.ClientException("busy")

    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "already playing" in mock_ctx.send.call_args[0][0]


@pytest.mark.asyncio
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
async def test_play_generic_exception_on_connect(mock_ffmpeg, mock_randint, mock_ctx, mock_sound):
    """connect() raises a generic Exception: send called with generic error message."""
    mock_ctx.author.voice.channel.connect.side_effect = Exception("boom")

    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "error processing your request" in mock_ctx.send.call_args[0][0]


@pytest.mark.asyncio
@patch("modules.player.asyncio.create_task", side_effect=lambda coro: coro.close())
@patch("modules.player.asyncio.get_running_loop")
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
async def test_play_forbidden_on_play(
    mock_ffmpeg, mock_randint, mock_get_loop, mock_create_task, mock_ctx, mock_sound
):
    """voice_client.play raises discord.Forbidden: send called with permission error; create_task called for disconnect."""
    voice_client = mock_ctx.author.voice.channel.connect.return_value
    voice_client.play.side_effect = discord.Forbidden(MagicMock(), "Forbidden")

    mock_loop = MagicMock()
    mock_get_loop.return_value = mock_loop

    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "issue playing a sound effect" in mock_ctx.send.call_args[0][0]
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
@patch("modules.player.asyncio.create_task", side_effect=lambda coro: coro.close())
@patch("modules.player.asyncio.get_running_loop")
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
async def test_play_timeout_on_play(
    mock_ffmpeg, mock_randint, mock_get_loop, mock_create_task, mock_ctx, mock_sound
):
    """voice_client.play raises TimeoutError: send called with timeout message; create_task called for disconnect."""
    voice_client = mock_ctx.author.voice.channel.connect.return_value
    voice_client.play.side_effect = TimeoutError

    mock_loop = MagicMock()
    mock_get_loop.return_value = mock_loop

    p = Player()
    await p.play(mock_ctx, mock_sound)

    mock_ctx.send.assert_called_once()
    assert "Timeout" in mock_ctx.send.call_args[0][0]
    mock_create_task.assert_called_once()


@pytest.mark.asyncio
@patch("modules.player.asyncio.create_task", side_effect=lambda coro: coro.close())
@patch("modules.player.asyncio.get_running_loop")
@patch("modules.player.random.randint", return_value=5)
@patch("modules.player.discord.FFmpegOpusAudio")
async def test_play_happy_path(
    mock_ffmpeg, mock_randint, mock_get_loop, mock_create_task, mock_ctx, mock_sound
):
    """Full happy path: playback completes, disconnect task is scheduled via create_task."""
    voice_client = mock_ctx.author.voice.channel.connect.return_value

    # Make get_running_loop return a mock whose call_soon_threadsafe calls its argument
    # immediately, so done.set() is invoked and done.wait() unblocks.
    mock_loop = MagicMock()
    mock_loop.call_soon_threadsafe.side_effect = lambda fn: fn()
    mock_get_loop.return_value = mock_loop

    p = Player()
    await p.play(mock_ctx, mock_sound)

    # play was invoked on the voice client
    voice_client.play.assert_called_once()

    # A disconnect task was scheduled after playback finished
    mock_create_task.assert_called_once()

    # No error messages were sent
    mock_ctx.send.assert_not_called()
