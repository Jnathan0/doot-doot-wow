"""
Path traversal tests for /add and the shared path / name validators.
/add runs in a tmp sandbox with fake sounds/ and db/ directories next to each other,
mirroring the container layout (/sounds and /db).
"""
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from modules.paths import safe_child, UnsafePath, INCOMING_DIR
from modules.validation import validate_name, validate_sound_upload, InvalidName
from tests.conftest import RealGetDB, db_rows, make_interaction, sent_text


# ---------------------------------------------------------------------------
# safe_child
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("parts", [
    ("../db",),
    ("/db",),
    ("..",),
    ("a/../../b",),
    ("",),
    ("\x00",),
    ("southpark", "../../db/sounds.db"),
    ("southpark", "/etc/passwd"),
])
def test_safe_child_rejects_escapes(tmp_path, parts):
    with pytest.raises(UnsafePath):
        safe_child(tmp_path / "sounds", *parts)


@pytest.mark.parametrize("parts", [("southpark",), ("southpark", "clip.mp3"), ("southpark/clip.mp3",), ("Marc Rebillet",)])
def test_safe_child_accepts_children(tmp_path, parts):
    root = tmp_path / "sounds"
    assert safe_child(root, *parts) == root.resolve().joinpath(*parts)


def test_safe_child_rejects_symlink_escape(tmp_path):
    root = tmp_path / "sounds"
    root.mkdir()
    (tmp_path / "db").mkdir()
    (root / "link").symlink_to(tmp_path / "db")
    with pytest.raises(UnsafePath):
        safe_child(root, "link", "sounds.db")


# ---------------------------------------------------------------------------
# validate_name / validate_sound_upload
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["airhorn", "Air_Horn-2", "a", "x" * 64])
def test_validate_name_accepts(name):
    assert validate_name("sound", name) == name


@pytest.mark.parametrize("name", ["", "x" * 65, "../db", "/db", "a b", "a.b", "#teamwork", 'x" OR 1=1 OR "', "é"])
def test_validate_name_rejects(name):
    with pytest.raises(InvalidName):
        validate_name("sound", name)


@pytest.mark.parametrize("name", ["root", "ROOT", ".incoming"])
def test_validate_name_reserved_folders(name):
    with pytest.raises(InvalidName):
        validate_name("folder", name)
    if name.isalnum():
        # reserved only as a folder name
        assert validate_name("sound", name) == name


@pytest.mark.parametrize("filename,content_type", [
    ("a.mp3", "audio/mpeg"), ("a.MP3", "audio/mpeg"), ("a.wav", "audio/wav"), ("a.ogg", "audio/ogg"),
    ("a.m4a", "audio/mp4"), ("a.mp4", "video/mp4"), ("a.mov", "video/quicktime"),
])
def test_validate_sound_upload_accepts(filename, content_type):
    validate_sound_upload(filename, content_type)


@pytest.mark.parametrize("filename,content_type", [
    ("sounds.db", "application/octet-stream"),
    ("sounds.db", "audio/mpeg"),
    ("a.mp3", "application/octet-stream"),
    ("a.mp3", None),
    ("noextension", "audio/mpeg"),
    ("a.sh", "audio/mpeg"),
])
def test_validate_sound_upload_rejects(filename, content_type):
    with pytest.raises(InvalidName):
        validate_sound_upload(filename, content_type)


# ---------------------------------------------------------------------------
# /add (cogs/Media.py)
# ---------------------------------------------------------------------------

class FakeConfirmation:
    """Stands in for SoundConfirmationDiag; records what was on disk while waiting for the user."""
    def __init__(self, confirmed, sounds_dir):
        self.confirmed = confirmed
        self.sounds_dir = sounds_dir
        self.interaction = MagicMock()
        self.interaction.response.edit_message = AsyncMock()
        self.staged = None

    async def wait(self):
        self.staged = sorted(p.name for p in (self.sounds_dir / INCOMING_DIR).iterdir())


def snapshot(root):
    """{relative path: bytes} for every file under root."""
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def media(sounds_db, sounds_catalog, tmp_path, mocker):
    import cogs.Media as media_module

    sounds_dir = tmp_path / "sounds"
    (sounds_dir / "effects").mkdir(parents=True)
    (sounds_dir / "effects" / "bang.mp3").write_bytes(b"existing bang")
    (sounds_dir / "Marc Rebillet").mkdir()
    (tmp_path / "db" / "metadata.db").write_bytes(b"metadata")

    mocker.patch.object(media_module.config, "sounds_path", str(sounds_dir))
    mocker.patch.object(media_module, "GetDB", RealGetDB)
    mocker.patch.object(media_module, "isLoud", return_value=False)
    mocker.patch.object(media_module, "checkExceedsDurationLimit", return_value=False)
    mocker.patch.object(sounds_catalog, "update_sounds")

    bot = MagicMock()
    bot.commands = []
    bot.reload_extension = AsyncMock()
    cog = media_module.Media(bot)
    cog.module = media_module
    cog.sounds_dir = sounds_dir
    cog.tmp_path = tmp_path
    return cog


def sound_attachment(filename, content_type="audio/mpeg", data=b"ID3 fake audio"):
    attachment = MagicMock()
    attachment.filename = filename
    attachment.content_type = content_type
    attachment.read = AsyncMock(return_value=data)
    return attachment


def use_confirmation(media, mocker, confirmed):
    view = FakeConfirmation(confirmed, media.sounds_dir)
    mocker.patch.object(media.module, "SoundConfirmationDiag", return_value=view)
    return view


async def run_add(media, attachment, folder=None):
    interaction = make_interaction()
    await type(media).add_command.callback(media, interaction, attachment, folder)
    return interaction


def outside_sounds(media):
    return {k: v for k, v in snapshot(media.tmp_path).items() if not k.startswith("sounds/")}


@pytest.mark.parametrize("folder,filename,content_type", [
    ("../db", "sounds.db", "application/octet-stream"),
    ("../db", "sounds.mp3", "audio/mpeg"),
    ("/db", "sounds.mp3", "audio/mpeg"),
    ("../../etc", "passwd.mp3", "audio/mpeg"),
    ("effects/../../db", "x.mp3", "audio/mpeg"),
    (".incoming", "x.mp3", "audio/mpeg"),
    ("root", "x.mp3", "audio/mpeg"),
    (None, "sounds.db", "audio/mpeg"),
    (None, "metadata.db", "application/octet-stream"),
    (None, "bad name.mp3", "audio/mpeg"),
    (None, 'x" OR 1=1 OR ".mp3', "audio/mpeg"),
])
async def test_add_rejects_traversal_and_bad_names(media, mocker, folder, filename, content_type):
    view = use_confirmation(media, mocker, confirmed=True)
    before_outside = outside_sounds(media)
    before_db = db_rows(media.tmp_path / "db" / "sounds.db", "SELECT * FROM sounds")

    interaction = await run_add(media, sound_attachment(filename, content_type), folder)

    assert "Error" in sent_text(interaction.response.send_message)
    assert view.staged is None  # never got as far as asking for confirmation
    assert outside_sounds(media) == before_outside
    assert snapshot(media.sounds_dir) == {"effects/bang.mp3": b"existing bang"}
    assert db_rows(media.tmp_path / "db" / "sounds.db", "SELECT * FROM sounds") == before_db


async def test_add_uses_only_the_attachment_basename(media, mocker):
    use_confirmation(media, mocker, confirmed=True)
    before_outside = outside_sounds(media)

    await run_add(media, sound_attachment("../../db/clip.mp3"))

    # sounds.db legitimately changes (new row); nothing is created or overwritten next to it
    after_outside = outside_sounds(media)
    assert after_outside.keys() == before_outside.keys()
    assert after_outside["db/metadata.db"] == before_outside["db/metadata.db"]
    assert (media.sounds_dir / "clip.mp3").read_bytes() == b"ID3 fake audio"


async def test_add_confirm_moves_staged_file_into_library(media, mocker):
    view = use_confirmation(media, mocker, confirmed=True)

    await run_add(media, sound_attachment("clip.mp3"), "newfolder")

    # while waiting for confirmation the upload only existed as a staged temp file
    assert len(view.staged) == 1 and view.staged[0].endswith(".mp3")
    assert (media.sounds_dir / "newfolder" / "clip.mp3").read_bytes() == b"ID3 fake audio"
    assert list((media.sounds_dir / INCOMING_DIR).iterdir()) == []
    db_file = media.tmp_path / "db" / "sounds.db"
    assert db_rows(db_file, "SELECT category_id FROM categories WHERE category_id = 'newfolder'") == [("newfolder",)]
    assert db_rows(db_file, "SELECT sound_id, sound_name, category_id, author_id, plays FROM sounds WHERE sound_id = 'newfolder clip'") == [
        ("newfolder clip", "clip", "newfolder", 999, 0)
    ]
    media.bot.reload_extension.assert_awaited_once_with("cogs.Player")


async def test_add_existing_category_is_not_duplicated(media, mocker):
    use_confirmation(media, mocker, confirmed=True)
    await run_add(media, sound_attachment("boom.mp3"), "effects")
    db_file = media.tmp_path / "db" / "sounds.db"
    assert db_rows(db_file, "SELECT COUNT(*) FROM categories WHERE category_id = 'effects'") == [(1,)]
    assert (media.sounds_dir / "effects" / "boom.mp3").exists()


async def test_add_to_grandfathered_folder(media, mocker):
    use_confirmation(media, mocker, confirmed=True)
    await run_add(media, sound_attachment("again.mp3"), "Marc Rebillet")
    assert (media.sounds_dir / "Marc Rebillet" / "again.mp3").exists()


async def test_add_cancel_deletes_only_the_temp_file(media, mocker):
    view = use_confirmation(media, mocker, confirmed=False)
    before = snapshot(media.tmp_path)

    await run_add(media, sound_attachment("clip.mp3"), "effects")

    assert len(view.staged) == 1
    assert snapshot(media.tmp_path) == before
    assert list((media.sounds_dir / INCOMING_DIR).iterdir()) == []
    assert "Process cancelled" in sent_text(view.interaction.response.edit_message)


async def test_add_timeout_deletes_only_the_temp_file(media, mocker):
    use_confirmation(media, mocker, confirmed=None)
    before = snapshot(media.tmp_path)

    interaction = await run_add(media, sound_attachment("clip.mp3"))

    assert snapshot(media.tmp_path) == before
    interaction.edit_original_response.assert_awaited_once()


async def test_add_rejects_existing_sound(media, mocker):
    view = use_confirmation(media, mocker, confirmed=True)
    interaction = await run_add(media, sound_attachment("bang.mp3"), "effects")
    assert "already exists" in sent_text(interaction.response.send_message)
    assert view.staged is None
    assert (media.sounds_dir / "effects" / "bang.mp3").read_bytes() == b"existing bang"


async def test_add_rejects_folder_named_like_a_sound(media, mocker):
    use_confirmation(media, mocker, confirmed=True)
    interaction = await run_add(media, sound_attachment("clip.mp3"), "airhorn")
    assert "already a sound name" in sent_text(interaction.response.send_message)


async def test_add_ffmpeg_error_is_rejected_cleanly(media, mocker):
    view = use_confirmation(media, mocker, confirmed=True)
    mocker.patch.object(media.module, "isLoud", side_effect=Exception("ffmpeg: invalid data"))
    before = snapshot(media.tmp_path)

    interaction = await run_add(media, sound_attachment("clip.mp3"))

    assert "Could not read that file" in sent_text(interaction.response.send_message)
    assert view.staged is None
    assert snapshot(media.tmp_path) == before


async def test_add_too_loud_is_rejected(media, mocker):
    use_confirmation(media, mocker, confirmed=True)
    mocker.patch.object(media.module, "isLoud", return_value=True)
    before = snapshot(media.tmp_path)

    interaction = await run_add(media, sound_attachment("clip.mp3"))

    assert "too loud" in sent_text(interaction.response.send_message)
    assert snapshot(media.tmp_path) == before
