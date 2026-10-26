"""
Behavioural SQL injection tests: the payloads that worked against the old f-string queries
are replayed through the hardened functions and handlers against a real SQLite database.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from modules.aliases import Sound, SoundsInfo
from modules.helper_functions import checkExists, checkGroup, increment_playcount, update_quicksound
from tests.conftest import RealGetDB, SEED_IMAGES, db_rows, load_real_module, make_interaction, sent_text

PAYLOADS = [
    'x" OR 1=1 OR "',
    "x' OR '1'='1",
    'a" OR sound_id!="',
    '"); DROP TABLE sounds; --',
    'zzz" UNION SELECT name, sql, 1, 1, 1, 1 FROM sqlite_master --',
    'q" OR "1"="1',
    "%",
    "?",
    "“ quoted ”",
]
ENTRANCE_MULTI_ROW = 'airhorn a ",111),("airhorn",222),("x'


def total_plays(db_file):
    return db_rows(db_file, "SELECT SUM(plays) FROM sounds")[0][0]


# ---------------------------------------------------------------------------
# helper_functions
# ---------------------------------------------------------------------------

def test_check_exists_matches_real_sounds(sounds_db):
    assert checkExists("root", "airhorn") is True
    assert checkExists("root", "#teamwork") is True
    assert checkExists("effects", "bang") is True
    assert checkExists("root", "nope") is False


@pytest.mark.parametrize("payload", PAYLOADS)
def test_check_exists_payloads_match_nothing(sounds_db, payload):
    assert checkExists(payload, "airhorn") is False
    assert checkExists("root", payload) is False
    assert checkExists(payload, payload) is False


def test_check_group_matches_real_folders(sounds_db):
    assert checkGroup("effects") is True
    assert checkGroup("Marc Rebillet") is True
    assert checkGroup("nope") is False


@pytest.mark.parametrize("payload", PAYLOADS)
def test_check_group_payloads_match_nothing(sounds_db, payload):
    assert checkGroup(payload) is False


def test_increment_playcount_updates_one_row(sounds_db):
    before = total_plays(sounds_db)
    increment_playcount("airhorn")
    assert total_plays(sounds_db) == before + 1
    assert db_rows(sounds_db, "SELECT plays FROM sounds WHERE sound_id = 'airhorn'") == [(11,)]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_increment_playcount_payloads_change_nothing(sounds_db, payload):
    before = db_rows(sounds_db, "SELECT sound_id, plays FROM sounds ORDER BY sound_id")
    increment_playcount(payload)
    assert db_rows(sounds_db, "SELECT sound_id, plays FROM sounds ORDER BY sound_id") == before
    assert db_rows(sounds_db, "SELECT COUNT(*) FROM sqlite_master WHERE name = 'sounds'") == [(1,)]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_update_quicksound_stores_payload_as_data(sounds_db, payload):
    update_quicksound(222, 2, payload)
    assert db_rows(sounds_db, "SELECT sound_id, user_id, alias FROM quicksounds ORDER BY user_id") == [
        ("airhorn", 111, 1),
        (payload, 222, 2),
    ]


# ---------------------------------------------------------------------------
# aliases: images are bulk loaded with one static query
# ---------------------------------------------------------------------------

def test_alias_images_loaded_from_single_query(sounds_db, tmp_path):
    sounds_dir = tmp_path / "sounds"
    (sounds_dir / "effects").mkdir(parents=True)
    (sounds_dir / ".incoming").mkdir()
    (sounds_dir / "airhorn.mp3").write_bytes(b"")
    (sounds_dir / 'a" OR sound_id!=".mp3').write_bytes(b"")
    (sounds_dir / "effects" / "bang.mp3").write_bytes(b"")
    (sounds_dir / ".incoming" / "tmp123.mp3").write_bytes(b"")

    info = SoundsInfo(str(sounds_dir))

    assert info.alias_dict["airhorn"].media == "img1.png"
    assert info.alias_dict["airhorn"].media_parent_folder == "images"
    assert info.alias_dict["effects bang"].media == "gifs/img2.gif"
    # a hostile on-disk name is just a sound with no image, it does not match other rows
    assert info.alias_dict['a" OR sound_id!="'].media is None
    # staged uploads are not a category
    assert info.category_list == ["effects"]
    assert ".incoming" not in info.alias_dict


# ---------------------------------------------------------------------------
# /stats sound
# ---------------------------------------------------------------------------

@pytest.fixture
def stats_cog(sounds_db, mocker):
    import cogs.Stats as stats_module
    mocker.patch.object(stats_module, "GetDB", RealGetDB)
    bot = MagicMock()
    bot.fetch_user = AsyncMock(return_value=MagicMock(name="user"))
    return stats_module.Stats(bot)


async def test_stats_sound_existing(stats_cog, sounds_catalog):
    interaction = make_interaction()
    await type(stats_cog).stats_sound_command.callback(stats_cog, interaction, "#teamwork")
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert embed.title == "#teamwork"


@pytest.mark.parametrize("payload", PAYLOADS)
async def test_stats_sound_payloads_not_found(stats_cog, sounds_catalog, payload):
    interaction = make_interaction()
    await type(stats_cog).stats_sound_command.callback(stats_cog, interaction, payload)
    assert "not found" in sent_text(interaction.response.send_message)
    stats_cog.bot.fetch_user.assert_not_called()


@pytest.mark.parametrize("payload", PAYLOADS)
async def test_stats_sound_query_is_parameterized(stats_cog, sounds_catalog, mocker, payload):
    """Even if the membership check is bypassed, the query treats the input as data."""
    mocker.patch.object(sounds_catalog, "get_sound", return_value=Sound(sound_id=payload))
    interaction = make_interaction()
    await type(stats_cog).stats_sound_command.callback(stats_cog, interaction, payload)
    assert "not found" in sent_text(interaction.response.send_message)
    stats_cog.bot.fetch_user.assert_not_called()


async def test_stats_sound_autocomplete(stats_cog, sounds_catalog):
    choices = await type(stats_cog).stats_sound_autocomplete(stats_cog, make_interaction(), "bang")
    assert [c.value for c in choices] == ["effects bang"]


# ---------------------------------------------------------------------------
# /entrance set, /quicksounds set, /folders
# ---------------------------------------------------------------------------

@pytest.fixture
def utils_cog(sounds_db, mocker):
    import cogs.SoundsUtils as utils_module
    mocker.patch.object(utils_module, "GetDB", RealGetDB)
    return utils_module.SoundsUtils(MagicMock())


async def call_entrance_set(cog, interaction, sound=None, folder=None):
    await type(cog).entrance_set_command.callback(cog, interaction, sound=sound, folder=folder)


async def test_entrance_set_multi_row_payload_rejected(utils_cog, sounds_catalog, sounds_db):
    # the old code only checked the first word ("airhorn") and then wrote rows for users 111 and 222
    interaction = make_interaction(user_id=999)
    await call_entrance_set(utils_cog, interaction, sound=ENTRANCE_MULTI_ROW)
    assert "does not exist" in sent_text(interaction.response.send_message)
    assert db_rows(sounds_db, "SELECT * FROM entrance") == []


@pytest.mark.parametrize("payload", PAYLOADS)
async def test_entrance_set_payloads_rejected(utils_cog, sounds_catalog, sounds_db, payload):
    await call_entrance_set(utils_cog, make_interaction(), sound=payload)
    await call_entrance_set(utils_cog, make_interaction(), folder=payload)
    assert db_rows(sounds_db, "SELECT * FROM entrance") == []


async def test_entrance_set_valid_sound_and_folder(utils_cog, sounds_catalog, sounds_db):
    await call_entrance_set(utils_cog, make_interaction(user_id=999), sound="#teamwork")
    await call_entrance_set(utils_cog, make_interaction(user_id=555), folder="Marc Rebillet")
    assert db_rows(sounds_db, "SELECT sound_id, user_id, content_type FROM entrance ORDER BY user_id") == [
        ("Marc Rebillet", 555, "folder"),
        ("#teamwork", 999, "sound"),
    ]


async def test_entrance_set_replaces_only_own_row(utils_cog, sounds_catalog, sounds_db):
    await call_entrance_set(utils_cog, make_interaction(user_id=111), sound="airhorn")
    await call_entrance_set(utils_cog, make_interaction(user_id=999), sound="#teamwork")
    await call_entrance_set(utils_cog, make_interaction(user_id=999), sound="effects bang")
    assert db_rows(sounds_db, "SELECT sound_id, user_id FROM entrance ORDER BY user_id") == [
        ("airhorn", 111),
        ("effects bang", 999),
    ]


@pytest.mark.parametrize("payload", PAYLOADS + [ENTRANCE_MULTI_ROW, "effects"])
async def test_quicksounds_set_rejects_unknown_sound(utils_cog, sounds_catalog, payload):
    interaction = make_interaction()
    await type(utils_cog).quicksounds_set_command.callback(utils_cog, interaction, payload)
    assert "does not exist" in sent_text(interaction.response.send_message)
    assert "view" not in interaction.response.send_message.call_args.kwargs


async def test_quicksounds_set_accepts_existing_sound(utils_cog, sounds_catalog, mocker):
    import cogs.SoundsUtils as utils_module
    quicksound = mocker.patch.object(utils_module, "Quicksound")
    mocker.patch.object(utils_module.ui, "View", return_value=MagicMock())
    interaction = make_interaction()
    await type(utils_cog).quicksounds_set_command.callback(utils_cog, interaction, "Marc Rebillet yeah")
    quicksound.assert_called_once_with("Marc Rebillet yeah")


@pytest.mark.parametrize("folder", ["../db", "/db", "..", "../../etc", "effects/../../db", 'x" OR 1=1 OR "'])
async def test_folders_rejects_paths_outside_library(utils_cog, sounds_catalog, mocker, folder):
    import cogs.SoundsUtils as utils_module
    listdir = mocker.patch.object(utils_module.os, "listdir")
    interaction = make_interaction()
    await type(utils_cog).folders_command.callback(utils_cog, interaction, folder)
    assert "not found" in sent_text(interaction.response.send_message)
    listdir.assert_not_called()


async def test_folders_lists_known_folder(utils_cog, sounds_catalog, mocker, tmp_path):
    import cogs.SoundsUtils as utils_module
    sounds_dir = tmp_path / "sounds"
    (sounds_dir / "Marc Rebillet").mkdir(parents=True)
    (sounds_dir / "Marc Rebillet" / "yeah.mp3").write_bytes(b"")
    mocker.patch.object(utils_module.config, "sounds_path", str(sounds_dir))
    interaction = make_interaction()
    await type(utils_cog).folders_command.callback(utils_cog, interaction, "Marc Rebillet")
    text = sent_text(interaction.response.send_message)
    assert "1 sounds in the Marc Rebillet folder" in text
    assert "yeah" in text


# ---------------------------------------------------------------------------
# ImageAttachment (modules/imgprocessing.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def imgprocessing(sounds_db, tmp_path, mocker):
    module = load_real_module("modules._real_imgprocessing", "modules/imgprocessing.py")
    mocker.patch.object(module, "GetDB", RealGetDB)
    for name in ("images", "gifs"):
        (tmp_path / name).mkdir()
    mocker.patch.object(module.config, "images_path", str(tmp_path / "images"))
    mocker.patch.object(module.config, "gifs_path", str(tmp_path / "gifs"))
    return module


def image_attachment(filename="pic.png", content_type="image/png"):
    attachment = MagicMock()
    attachment.filename = filename
    attachment.content_type = content_type
    return attachment


@pytest.mark.parametrize("payload", PAYLOADS)
def test_image_replace_payload_keeps_other_rows(imgprocessing, sounds_db, payload):
    image = imgprocessing.ImageAttachment(image_attachment(), payload)
    image.download_file(b"png")
    rows = db_rows(sounds_db, "SELECT sound_id, image_id, folder FROM images")
    for seeded in SEED_IMAGES:
        assert seeded in rows
    assert len(rows) == len(SEED_IMAGES) + 1


def test_image_replace_swaps_only_its_own_row(imgprocessing, sounds_db):
    image = imgprocessing.ImageAttachment(image_attachment(), "airhorn")
    image.download_file(b"png")
    rows = db_rows(sounds_db, "SELECT sound_id FROM images ORDER BY sound_id")
    assert rows == [("#teamwork",), ("airhorn",), ("effects bang",)]


def test_image_download_ignores_directories_in_filename(imgprocessing, tmp_path):
    image = imgprocessing.ImageAttachment(image_attachment(filename="../../db/evil.png"), "airhorn")
    image.download_file(b"png")
    saved = list((tmp_path / "images").iterdir())
    assert len(saved) == 1 and saved[0].name.endswith("evil.png")
    assert not (tmp_path / "db" / "evil.png").exists()


def test_image_delete_refuses_path_from_database(imgprocessing, sounds_db, tmp_path):
    import sqlite3
    victim = tmp_path / "db" / "keep.txt"
    victim.write_text("important")
    conn = sqlite3.connect(sounds_db)
    conn.execute("UPDATE images SET image_id = '../db/keep.txt' WHERE sound_id = 'airhorn'")
    conn.commit()
    conn.close()

    imgprocessing.ImageAttachment(image_attachment(), "airhorn").delete_existing_image_file()

    assert victim.read_text() == "important"


def test_image_delete_removes_own_file(imgprocessing, tmp_path):
    own = tmp_path / "images" / "img1.png"
    own.write_bytes(b"png")
    imgprocessing.ImageAttachment(image_attachment(), "airhorn").delete_existing_image_file()
    assert not own.exists()
