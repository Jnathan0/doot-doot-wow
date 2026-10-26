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


# ---------------------------------------------------------------------------
# Real SQLite fixtures (used by the SQL injection / path traversal tests)
#
# modules.database is stubbed above, so the real GetDB class is loaded from
# its file under a private name. Tests patch it into the modules they exercise.
# ---------------------------------------------------------------------------

import importlib.util  # noqa: E402
import sqlite3  # noqa: E402
from pathlib import Path  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1]


def load_real_module(name, relative_path):
    """Load an app module from disk, bypassing the MagicMock stub registered in sys.modules."""
    spec = importlib.util.spec_from_file_location(name, APP_DIR / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RealGetDB = load_real_module("modules._real_database", "modules/database.py").GetDB

SEED_SOUNDS = [
    ("airhorn", "airhorn", "root", 111, 10, "2024-01-01"),
    ("#teamwork", "#teamwork", "root", 111, 3, "2024-01-02"),
    ("effects bang", "bang", "effects", 222, 5, "2024-01-03"),
    ("Marc Rebillet yeah", "yeah", "Marc Rebillet", 222, 7, "2024-01-04"),
]
SEED_IMAGES = [
    ("airhorn", "img1.png", "images"),
    ("effects bang", "img2.gif", "gifs"),
    ("#teamwork", "img3.png", "images"),
]


def db_rows(db_file, query, params=()):
    conn = sqlite3.connect(db_file)
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


@pytest.fixture
def sounds_db(tmp_path, mocker):
    """
    A real sounds.db built from db/sounds.sql at <tmp>/db/sounds.db, seeded with a few rows.
    config.database_path points at it and the helper/alias modules use the real GetDB.
    """
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db_file = db_dir / "sounds.db"
    conn = sqlite3.connect(db_file)
    conn.executescript((APP_DIR / "db" / "sounds.sql").read_text())
    conn.executemany("INSERT INTO categories (category_id) VALUES (?)", [("root",), ("effects",), ("Marc Rebillet",)])
    conn.executemany("INSERT INTO sounds VALUES (?, ?, ?, ?, ?, ?)", SEED_SOUNDS)
    conn.executemany("INSERT INTO images VALUES (?, ?, ?)", SEED_IMAGES)
    conn.execute("INSERT INTO quicksounds VALUES ('airhorn', 111, 1)")
    conn.commit()
    conn.close()

    mocker.patch.object(_mock_config, "database_path", str(db_file))
    mocker.patch("modules.helper_functions.GetDB", RealGetDB)
    mocker.patch("modules.aliases.GetDB", RealGetDB)
    return db_file


@pytest.fixture
def sounds_catalog(mocker):
    """Point the shared `sounds` catalog at a fixed set of sounds and folders matching SEED_SOUNDS."""
    from modules.aliases import sounds

    airhorn = Sound(sound_id="airhorn", path="/sounds/airhorn.mp3")
    teamwork = Sound(sound_id="#teamwork", path="/sounds/#teamwork.mp3")
    bang = Sound(sound_id="effects bang", path="/sounds/effects/bang.mp3")
    yeah = Sound(sound_id="Marc Rebillet yeah", path="/sounds/Marc Rebillet/yeah.mp3")
    alias_dict = {
        "airhorn": airhorn,
        "#teamwork": teamwork,
        "effects": [bang],
        "effects bang": bang,
        "Marc Rebillet": [yeah],
        "Marc Rebillet yeah": yeah,
    }
    mocker.patch.object(sounds, "alias_dict", alias_dict)
    mocker.patch.object(sounds, "category_list", ["effects", "Marc Rebillet"])
    mocker.patch.object(sounds, "aliases", list(alias_dict))
    return sounds


def make_interaction(user_id=999):
    """Fake discord.Interaction with async response helpers."""
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.user.name = "tester"
    interaction.user.mention = f"<@{user_id}>"
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def sent_text(send_mock):
    """Concatenated positional/content text of every call made to an AsyncMock sender."""
    parts = []
    for call in send_mock.call_args_list:
        parts.extend(str(a) for a in call.args)
        if "content" in call.kwargs:
            parts.append(str(call.kwargs["content"]))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Anti-spam fixtures
#
# The shared modules.antispam.guard is never loaded in tests, so it stays inert
# (nothing blocked or counted). Tests that need a working guard build their own
# SoundGuard over a real metadata.db in tmp with a fake clock.
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402


class FakeClock:
    """Callable clock used for both the monotonic and the wall clock of a SoundGuard."""
    def __init__(self, start=1_700_000_000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def antispam_store(tmp_path):
    from modules.antispam import TimeoutStore
    store = TimeoutStore(str(tmp_path / "metadata.db"), db_factory=RealGetDB)
    store.ensure_schema()
    return store


@pytest.fixture
async def antispam_guard(antispam_store, clock):
    from modules.antispam import SoundGuard
    guard = SoundGuard(antispam_store, clock=clock, wall_clock=clock)
    await guard.load()
    return guard


def make_member(user_id=1, guild_id=10, admin=False, role_ids=()):
    """Fake discord.Member with what the guard and the AntiSpam cog use."""
    member = MagicMock()
    member.id = user_id
    member.guild.id = guild_id
    member.guild_permissions.administrator = admin
    member.roles = [SimpleNamespace(id=role_id) for role_id in role_ids]
    member.mention = f"<@{user_id}>"
    member.bot = False
    member.send = AsyncMock()
    member.timeout = AsyncMock()
    member.is_timed_out = MagicMock(return_value=False)
    member.__str__ = MagicMock(return_value=f"member{user_id}")
    return member
