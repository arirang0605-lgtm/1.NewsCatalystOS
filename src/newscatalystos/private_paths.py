"""Read-only validation of existing private directories."""
from pathlib import Path
import os
import stat
from .source_share import SourceShareError

def _existing_private_dir(path: Path) -> Path:
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts or path.is_symlink()
            or any(part.casefold() == "eraleader" for part in path.parts)):
        raise SourceShareError("private existing directory required")
    try:
        info = path.lstat()
    except OSError as exc:
        raise SourceShareError("existing private directory unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or path.resolve(strict=True) != path):
        raise SourceShareError("unsafe private directory")
    return path
