import os
import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# ---------------------------------------------------------------------------
# Block dangerous module-level side effects before any app code is imported.
#
# modules/app_config.py ends with:   config = AppConfig()  (Redis + fs checks)
# modules/aliases.py ends with:      sounds = SoundsInfo(config.sounds_path)  (os.scandir)
#
# Strategy:
#   1. Inject a fake `modules.app_config` stub into sys.modules so that
#      `from .app_config import config` inside aliases.py gets our mock.
#   2. Stub every other sub-module that __init__.py re-exports so that
#      importing `modules` never reaches real Redis/filesystem code.
#   3. Temporarily replace os.scandir with a no-op so SoundsInfo.__init__
#      completes without touching the filesystem.
#   4. Import only what tests actually need (Sound, SoundsInfo) directly from
#      the real aliases module, then restore os.scandir.
# ---------------------------------------------------------------------------

# Step 1 – build a concrete mock config
_mock_config = MagicMock()
_mock_config.prefix = "!"
_mock_config.sub_cmd_sep = " "
_mock_config.reverse_char = "-"
_mock_config.sounds_path = "/sounds"
_mock_config.gifs_path = "/gifs"
_mock_config.images_path = "/images"
_mock_config.database_path = "/db/sounds.db"
_mock_config.media_duration_limit = 180
_mock_config.worker_queue = MagicMock()

# Step 2 – inject stubs for every sub-module that carries side effects
_app_config_stub = MagicMock()
_app_config_stub.config = _mock_config

sys.modules.setdefault("modules.app_config", _app_config_stub)

for _mod_name in (
    "modules.errors",
    "modules.metadata",
    "modules.database",
    "modules.redisworkers",
    "modules.quicksounds",
    "modules.imgprocessing",
    "modules.command_help",
    "modules.menus",
    "modules.media",
):
    sys.modules.setdefault(_mod_name, MagicMock())

# Step 3/4 – import Sound and SoundsInfo with os.scandir patched out.
# os.scandir is used as a context manager (`with os.scandir(...) as it:`), so
# the replacement must support __enter__/__exit__ as well as __iter__.
class _EmptyScandir:
    def __enter__(self):
        return iter([])
    def __exit__(self, *_):
        return False
    def __iter__(self):
        return iter([])

_real_scandir = os.scandir
os.scandir = lambda path: _EmptyScandir()

from modules.aliases import Sound, SoundsInfo  # noqa: E402

os.scandir = _real_scandir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ctx():
    """Fake discord.py Context object."""
    ctx = MagicMock()

    # guild voice state – no existing voice client
    ctx.message.guild.voice_client = None

    # author identity
    ctx.message.author.id = 12345
    ctx.message.content = "!test_sound"

    # voice channel – connect() returns a voice_client with play/disconnect
    voice_client = MagicMock()

    def _play(source, *, after=None):
        if after is not None:
            after(None)

    voice_client.play = MagicMock(side_effect=_play)
    voice_client.disconnect = AsyncMock()

    voice_channel = MagicMock()
    voice_channel.connect = AsyncMock(return_value=voice_client)

    ctx.author.voice.channel = voice_channel

    # async helpers
    ctx.send = AsyncMock()
    ctx.message.delete = AsyncMock()

    return ctx


@pytest.fixture
def mock_sound():
    """A plain Sound with no media attachment."""
    return Sound(sound_id="test_sound", path="/sounds/test_sound.mp3", media=None)


@pytest.fixture
def mock_sound_with_media():
    """A Sound that references an image."""
    return Sound(
        sound_id="test_sound",
        path="/sounds/test_sound.mp3",
        media="image.png",
        media_parent_folder="images",
    )


@pytest.fixture
def mock_sounds_info():
    """A MagicMock standing in for a real SoundsInfo instance."""
    info = MagicMock()
    sound = Sound(sound_id="test_sound", path="/sounds/test_sound.mp3")
    category_sound = Sound(sound_id="category test", path="/sounds/category/test.mp3")
    info.alias_dict = {"test_sound": sound, "category": [category_sound]}
    info.aliases = ["test_sound", "category"]
    return info
