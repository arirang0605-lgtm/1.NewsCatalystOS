"""Owner-only Gemini credential file on the Mac internal disk.

The setup form writes this file. Production code only reads it at call time.
No key is included in reports, command arguments, logs, or Git.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import tempfile

from .source_share import SourceShareError

NAME = "GEMINI_API_KEY"
MAX_FILE_BYTES = 512


def credential_path() -> Path:
    return (Path.home() / "Library" / "Application Support" /
            "NewsCatalystOS" / "api-credentials" / "gemini_api.env")


def valid_api_key(value: str) -> bool:
    return (isinstance(value, str) and 20 <= len(value) <= 256
            and value.isascii() and all(33 <= ord(ch) <= 126 for ch in value))


def _private_dir(path: Path, *, create: bool) -> None:
    if not path.is_absolute() or path.name != "gemini_api.env":
        raise SourceShareError("AI credential location invalid")
    parent = path.parent
    if parent.is_symlink() or parent.parent.is_symlink():
        raise SourceShareError("AI credential location invalid")
    if create:
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        info = parent.stat()
    except OSError:
        raise SourceShareError("AI credential unavailable") from None
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise SourceShareError("AI credential directory unsafe")


def read_private_api_key(path: Path | None = None) -> str:
    selected = credential_path() if path is None else Path(path)
    _private_dir(selected, create=False)
    if selected.is_symlink():
        raise SourceShareError("AI credential file unsafe")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(selected, flags)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_size > MAX_FILE_BYTES):
                raise SourceShareError("AI credential file unsafe")
            raw = os.read(fd, MAX_FILE_BYTES + 1)
        finally:
            os.close(fd)
    except OSError:
        raise SourceShareError("AI credential unavailable") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise SourceShareError("AI credential file invalid") from None
    prefix = NAME + "="
    if not text.startswith(prefix) or not text.endswith("\n") or text.count("\n") != 1:
        raise SourceShareError("AI credential file invalid")
    key = text[len(prefix):-1]
    if not valid_api_key(key):
        raise SourceShareError("AI credential file invalid")
    return key


def save_private_api_key(value: str, path: Path | None = None) -> None:
    if not valid_api_key(value):
        raise SourceShareError("AI credential format invalid")
    selected = credential_path() if path is None else Path(path)
    _private_dir(selected, create=True)
    if selected.exists() or selected.is_symlink():
        # Do not replace a link, shared file, or a file owned by someone else.
        read_private_api_key(selected)
    raw = (NAME + "=" + value + "\n").encode("ascii")
    if len(raw) > MAX_FILE_BYTES:
        raise SourceShareError("AI credential format invalid")
    fd, temp_name = tempfile.mkstemp(prefix=".gemini_", dir=selected.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, selected)
        directory_fd = os.open(selected.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
