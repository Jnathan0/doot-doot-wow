# Validation rules for names that users create (folders and sounds via /add).
# Existing names on disk are grandfathered: lookups check membership in
# sounds.alias_dict / sounds.category_list instead of this regex.
import re
from .paths import INCOMING_DIR

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
RESERVED_FOLDER_NAMES = {"root", INCOMING_DIR}
ALLOWED_SOUND_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".mp4", ".mov"}
ALLOWED_SOUND_CONTENT_TYPES = ("audio/", "video/")


class InvalidName(ValueError):
    pass


def validate_name(kind, value):
    """
    Returns value if it is an acceptable new folder or sound name, otherwise raises InvalidName
    with a message that can be shown to the user.
    """
    if not isinstance(value, str) or not NAME_RE.fullmatch(value):
        raise InvalidName(
            f"Error: invalid {kind} name \"{value}\". "
            f"Use 1-64 letters, numbers, '-' or '_' (no spaces, dots or slashes)."
        )
    if kind == "folder" and value.lower() in RESERVED_FOLDER_NAMES:
        raise InvalidName(f"Error: \"{value}\" is a reserved folder name, please choose another.")
    return value


def validate_sound_upload(filename, content_type):
    """
    Checks the extension and content type of an uploaded sound.
    filename must already be reduced to a bare name (no directories).
    Raises InvalidName with a user facing message.
    """
    extension = ("." + filename.rsplit(".", 1)[1].lower()) if "." in filename else ""
    if extension not in ALLOWED_SOUND_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_SOUND_EXTENSIONS))
        raise InvalidName(f"Error: unsupported file type \"{extension or filename}\". Supported types: {allowed}")
    if not (content_type or "").lower().startswith(ALLOWED_SOUND_CONTENT_TYPES):
        raise InvalidName(f"Error: uploaded file is not audio or video (content type \"{content_type}\").")
    return extension
