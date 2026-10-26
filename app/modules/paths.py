# Helpers for building filesystem paths from user supplied names
# without letting them escape the media directories.
from pathlib import Path

# Staging directory (inside sounds_path) for uploads that have not been confirmed yet.
# It lives on the same filesystem as the sounds so a confirmed upload is a single os.replace().
INCOMING_DIR = ".incoming"


class UnsafePath(ValueError):
    pass


def safe_child(root, *parts):
    """
    Join parts under root and guarantee the result stays inside root.

    Raises UnsafePath for empty parts, NUL bytes, absolute parts, or anything
    that resolves (including through symlinks) outside of root.
    """
    root_resolved = Path(root).resolve()
    for part in parts:
        if not part or "\x00" in part or Path(part).is_absolute():
            raise UnsafePath(repr(part))
    candidate = root_resolved.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise UnsafePath("/".join(parts))
    return candidate
