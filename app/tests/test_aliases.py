import pytest
import os
from unittest.mock import MagicMock, patch, call
from modules.aliases import Sound, SoundsInfo


# ---------------------------------------------------------------------------
# Helpers — build fake DirEntry-like mocks and context manager wrappers
# ---------------------------------------------------------------------------

def make_file_entry(name, path):
    entry = MagicMock()
    entry.is_file.return_value = True
    entry.is_dir.return_value = False
    entry.name = name
    entry.path = path
    return entry


def make_dir_entry(name, path):
    entry = MagicMock()
    entry.is_file.return_value = False
    entry.is_dir.return_value = True
    entry.name = name
    entry.path = path
    return entry


def scandir_returning(entries):
    ctx = MagicMock()
    ctx.__enter__.return_value = iter(entries)
    ctx.__exit__.return_value = False
    return ctx


# ---------------------------------------------------------------------------
# Sound tests
# ---------------------------------------------------------------------------

def test_sound_with_all_args():
    s = Sound(sound_id="s", path="/p", media="img.png", media_parent_folder="images")
    assert s.sound_id == "s"
    assert s.path == "/p"
    assert s.media == "img.png"
    assert s.media_parent_folder == "images"


def test_sound_defaults():
    s = Sound()
    assert s.sound_id is None
    assert s.path is None
    assert s.media is None
    assert s.media_parent_folder is None


# ---------------------------------------------------------------------------
# SoundsInfo.getAliasInfo tests
# ---------------------------------------------------------------------------

def test_get_alias_info_flat_dir(mocker):
    """Two flat file entries, no media — alias_dict has 2 Sound objects, category_list empty."""
    file1 = make_file_entry("beep.mp3", "/sounds/beep.mp3")
    file2 = make_file_entry("boop.mp3", "/sounds/boop.mp3")

    mock_GetDB = mocker.patch("modules.aliases.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchone.return_value = None

    mocker.patch("os.scandir", return_value=scandir_returning([file1, file2]))

    si = SoundsInfo("/sounds")

    assert len(si.alias_dict) == 2
    assert "beep" in si.alias_dict
    assert "boop" in si.alias_dict
    assert isinstance(si.alias_dict["beep"], Sound)
    assert isinstance(si.alias_dict["boop"], Sound)
    assert si.category_list == []


def test_get_alias_info_with_subdir(mocker):
    """Root has 1 file + 1 dir; subdir has 2 files."""
    root_file = make_file_entry("solo.mp3", "/sounds/solo.mp3")
    subdir = make_dir_entry("effects", "/sounds/effects")

    sub_file1 = make_file_entry("bang.mp3", "/sounds/effects/bang.mp3")
    sub_file2 = make_file_entry("crash.mp3", "/sounds/effects/crash.mp3")

    root_ctx = scandir_returning([root_file, subdir])
    sub_ctx = scandir_returning([sub_file1, sub_file2])

    mock_GetDB = mocker.patch("modules.aliases.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchone.return_value = None

    mocker.patch("os.scandir", side_effect=[root_ctx, sub_ctx])

    si = SoundsInfo("/sounds")

    # flat sound
    assert "solo" in si.alias_dict
    assert isinstance(si.alias_dict["solo"], Sound)

    # category key maps to a list of 2 Sounds
    assert "effects" in si.alias_dict
    assert isinstance(si.alias_dict["effects"], list)
    assert len(si.alias_dict["effects"]) == 2

    # sub-sounds are individually addressable too
    assert "effects bang" in si.alias_dict
    assert "effects crash" in si.alias_dict

    assert si.category_list == ["effects"]


def test_get_alias_info_empty_dir(mocker):
    """Empty scandir — alias_dict and category_list are both empty."""
    mock_GetDB = mocker.patch("modules.aliases.GetDB")

    mocker.patch("os.scandir", return_value=scandir_returning([]))

    si = SoundsInfo("/sounds")

    assert si.alias_dict == {}
    assert si.category_list == []


def test_get_alias_info_sound_with_media(mocker):
    """File entry where DB returns media row — Sound has media + media_parent_folder."""
    file_entry = make_file_entry("bark.mp3", "/sounds/bark.mp3")

    mock_GetDB = mocker.patch("modules.aliases.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    # DB returns (image_id, folder)
    mock_db.cursor.execute.return_value.fetchone.return_value = ("img.png", "images")

    mocker.patch("os.scandir", return_value=scandir_returning([file_entry]))

    si = SoundsInfo("/sounds")

    sound = si.alias_dict["bark"]
    assert sound.media == "img.png"
    assert sound.media_parent_folder == "images"


def test_get_alias_info_sound_no_media(mocker):
    """File entry where DB returns None — Sound has media=None."""
    file_entry = make_file_entry("bark.mp3", "/sounds/bark.mp3")

    mock_GetDB = mocker.patch("modules.aliases.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchone.return_value = None

    mocker.patch("os.scandir", return_value=scandir_returning([file_entry]))

    si = SoundsInfo("/sounds")

    sound = si.alias_dict["bark"]
    assert sound.media is None


# ---------------------------------------------------------------------------
# SoundsInfo.update_sounds test
# ---------------------------------------------------------------------------

def test_update_sounds(mocker):
    """update_sounds refreshes alias_dict and aliases from a new scandir result."""
    mock_GetDB = mocker.patch("modules.aliases.GetDB")
    mock_db = MagicMock()
    mock_GetDB.return_value = mock_db
    mock_db.cursor.execute.return_value.fetchone.return_value = None

    # First call (during __init__): empty dir
    mock_scandir = mocker.patch("os.scandir", return_value=scandir_returning([]))
    si = SoundsInfo("/sounds")

    assert si.alias_dict == {}
    assert si.aliases == []

    # Second call (during update_sounds): one file
    new_file = make_file_entry("ding.mp3", "/sounds/ding.mp3")
    mock_scandir.return_value = scandir_returning([new_file])

    si.update_sounds()

    assert len(si.alias_dict) == 1
    assert "ding" in si.alias_dict
    assert len(si.aliases) == 1
    assert "ding" in si.aliases
