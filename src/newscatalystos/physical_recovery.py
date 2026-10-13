"""6_5 restore NewsCatalystOS SQLite on a physically distinct backup device.

Existing backup_sqlite/restore_to_new_dir remain the single implementation
of consistency and SHA tests. This adapter checks OS device boundaries and
runs a real isolated restore, without modifying active DBs or EraLeader.
Local cross-device recovery is NOT independently witnessed/off-site recovery.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import plistlib
import re
import sqlite3
import subprocess

from .backup_recovery import (
    _private_dir, _regular_owner, backup_sqlite, restore_to_new_dir,
)
from .source_share import SourceShareError, _when

ALLOWED = {
    "incremental_feeds.sqlite3": {"source_state", "requests", "seen_events"},
    "triage_exact_index.sqlite3": {"document_versions"},
}


@dataclass(frozen=True)
class PhysicalRecoveryCheck:
    source_name: str
    backup_id: str
    snapshot_bytes: int
    source_and_backup_on_different_devices: bool
    restored_to_separate_directory: bool
    restored_sqlite_integrity: bool
    backup_manifest_sha256: str
    snapshot_sha256: str
    backup_created_at: datetime


def _whole_disk(path: Path) -> str:
    """Mac diskutil parent disk, not merely a different APFS volume."""
    try:
        mounted = subprocess.run(
            ["df", "-P", str(path)], capture_output=True, text=True,
            timeout=8, check=True,
        )
        lines = mounted.stdout.splitlines()
        if len(lines) < 2:
            raise SourceShareError("physical backup device not identifiable")
        device = lines[-1].split()[0]
        if not re.fullmatch(r"/dev/disk[0-9]+(?:s[0-9]+)?", device):
            raise SourceShareError("physical backup device not locally identifiable")
        detail = subprocess.run(
            ["diskutil", "info", "-plist", device],
            capture_output=True, timeout=8, check=True,
        )
        parent = plistlib.loads(detail.stdout).get("ParentWholeDisk")
        if not isinstance(parent, str) or not re.fullmatch(r"disk[0-9]+", parent):
            raise SourceShareError("diskutil physical parent not verified")
        return parent
    except (OSError, subprocess.SubprocessError, ValueError, IndexError,
            plistlib.InvalidFileException) as exc:
        raise SourceShareError("physical device verification unavailable") from exc


def _different_disk(active: Path, backup_parent: Path) -> bool:
    return (active.stat().st_dev != backup_parent.stat().st_dev
            and _whole_disk(active) != _whole_disk(backup_parent))


def verify_physical_recovery(
    source: Path, backup_root: Path, restore_parent: Path, *,
    state_root: Path | None = None,
    now: datetime | None = None,
) -> PhysicalRecoveryCheck:
    """Copy one authorized state DB to another device and restore back isolated.

    state_root is injectable by tests only. Production callers must use the
    NewsCatalystOS owner-only internal state directory; do not use an
    arbitrary project, personal file, or EraLeader DB as source.
    """
    base = (Path.home() / "Library/Application Support/NewsCatalystOS/state"
            if state_root is None else Path(state_root))
    source = Path(source)
    backup_root = Path(backup_root)
    restore_parent = Path(restore_parent)
    if (not all(p.is_absolute() and ".." not in p.parts
                for p in (source, backup_root, restore_parent, base))
            or any(part.casefold() == "eraleader"
                   for p in (source, backup_root, restore_parent, base)
                   for part in p.parts)
            or source.name not in ALLOWED
            or source.parent != base
            or backup_root == source.parent
            or restore_parent == source.parent):
        raise SourceShareError("only isolated NewsCatalystOS state recovery supported")
    _private_dir(base)
    _regular_owner(source)
    # Parents must exist and be safe before any backup is written.
    _private_dir(backup_root.parent)
    _private_dir(restore_parent, create=True)
    if backup_root.exists():
        _private_dir(backup_root)
    if (backup_root.is_symlink() or restore_parent.is_symlink()
            or backup_root.resolve() in source.parents
            or source == backup_root
            or not _different_disk(source, backup_root.parent)):
        raise SourceShareError("backup must use a physically separate device")
    if restore_parent.stat().st_dev != source.stat().st_dev:
        raise SourceShareError("restore test must use the active device in an isolated directory")
    timestamp = _when((now or datetime.now(timezone.utc)).isoformat(), "backup start")
    receipt = backup_sqlite(source, backup_root, now=timestamp)
    destination = restore_parent / receipt.backup_id
    recovered = restore_to_new_dir(
        backup_root, receipt, destination,
        expected_manifest_sha256=receipt.manifest_sha256,
    )
    if recovered.parent == source.parent or recovered.stat().st_dev != source.stat().st_dev:
        raise SourceShareError("restored source is not isolated on active device")
    # Existing restore_to_new_dir verified SHA, size and SQLite integrity.
    # Here also verify the actual operational schema survived the transfer.
    with sqlite3.connect(f"file:{recovered}?mode=ro", uri=True) as restored:
        names = {row[0] for row in restored.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not ALLOWED[source.name].issubset(names):
            raise SourceShareError("restored operational schema incomplete")
        if restored.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SourceShareError("restored operational SQLite integrity failed")
    return PhysicalRecoveryCheck(
        source.name, receipt.backup_id, receipt.snapshot_bytes,
        source_and_backup_on_different_devices=True,
        restored_to_separate_directory=True,
        restored_sqlite_integrity=True,
        backup_manifest_sha256=receipt.manifest_sha256,
        snapshot_sha256=receipt.snapshot_sha256,
        backup_created_at=receipt.created_at,
    )
