"""Owner-private, cross-device SHA pin for later independent SQLite restore.

The backup manifest lives on T5DATA and this pin on the Mac's other disk.
It records local integrity/restore evidence, not third-party notarization or
off-site disaster recovery. No EraLeader or public Git data is written.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
import re

from .backup_recovery import (
    BackupReceipt, _private_dir, _regular_owner, restore_to_new_dir,
)
from .evidence_archive import _write_new
from .physical_recovery import ALLOWED, PhysicalRecoveryCheck, _different_disk
from .source_share import SourceShareError, _json, _read_regular, _must_sha, _when

SCHEMA = "newscatalyst.physical_dr_pin.v1"
PIN_LIMIT = 8192
PIN_NAME = re.compile(r"backup_[a-f0-9]{32}\.pin\.json\Z")


@dataclass(frozen=True)
class RecordedRecoveryPin:
    pin_path: Path
    receipt: BackupReceipt
    recorded_at: datetime
    backup_root: Path


def _validate_locations(pin_root: Path, backup_root: Path) -> tuple[Path, Path]:
    pin_root, backup_root = Path(pin_root), Path(backup_root)
    if (not pin_root.is_absolute() or not backup_root.is_absolute()
            or ".." in pin_root.parts or ".." in backup_root.parts
            or any(part.casefold() == "eraleader" for part in (
                *pin_root.parts, *backup_root.parts
            ))):
        raise SourceShareError("only private NewsCatalystOS physical pin locations")
    pin_root = _private_dir(pin_root, create=True)
    backup_root = _private_dir(backup_root)
    if pin_root == backup_root or not _different_disk(pin_root, backup_root):
        raise SourceShareError("physical backup pin must be on the other device")
    return pin_root, backup_root


def record_recovery_pin(
    proof: PhysicalRecoveryCheck, backup_root: Path, pin_root: Path,
    *, now: datetime | None = None,
) -> RecordedRecoveryPin:
    if (not isinstance(proof, PhysicalRecoveryCheck)
            or proof.source_name not in ALLOWED
            or not proof.source_and_backup_on_different_devices
            or not proof.restored_to_separate_directory
            or not proof.restored_sqlite_integrity
            or not re.fullmatch(r"backup_[a-f0-9]{32}", proof.backup_id)):
        raise SourceShareError("actual checked physical restore required")
    pin_root, backup_root = _validate_locations(pin_root, backup_root)
    manifest = backup_root / proof.backup_id / "manifest.json"
    _regular_owner(manifest)
    raw_manifest = _read_regular(manifest, PIN_LIMIT)
    if sha256(raw_manifest).hexdigest() != proof.backup_manifest_sha256:
        raise SourceShareError("backup manifest not verified against DR result")
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "DR pin first stored")
    if proof.backup_created_at > at:
        raise SourceShareError("DR pin cannot predate backup")
    document = {
        "schema": SCHEMA,
        "backup_id": proof.backup_id,
        "source_name": proof.source_name,
        "snapshot_sha256": _must_sha(proof.snapshot_sha256, "snapshot SHA"),
        "manifest_sha256": _must_sha(proof.backup_manifest_sha256, "manifest SHA"),
        "snapshot_bytes": proof.snapshot_bytes,
        "backup_root": str(backup_root),
        "backup_created_at": proof.backup_created_at.isoformat(),
        "pin_recorded_at": at.isoformat(),
    }
    import json
    raw = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    pin = pin_root / (proof.backup_id + ".pin.json")
    _write_new(pin, raw)
    fd = os.open(pin_root, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    receipt = BackupReceipt(
        proof.backup_id, proof.source_name, proof.snapshot_sha256,
        proof.backup_manifest_sha256, proof.backup_created_at,
        proof.snapshot_bytes,
    )
    return RecordedRecoveryPin(pin, receipt, at, backup_root)


def read_recovery_pin(pin_path: Path, pin_root: Path, backup_root: Path,
                      *, now: datetime | None = None) -> RecordedRecoveryPin:
    pin_root, backup_root = _validate_locations(pin_root, backup_root)
    pin_path = Path(pin_path)
    if (pin_path.parent != pin_root or not PIN_NAME.fullmatch(pin_path.name)
            or pin_path.is_symlink()):
        raise SourceShareError("untrusted independent DR pin path")
    _regular_owner(pin_path)
    document = _json(_read_regular(pin_path, PIN_LIMIT), "independent DR pin")
    if (set(document) != {"schema", "backup_id", "source_name",
                          "snapshot_sha256", "manifest_sha256", "snapshot_bytes",
                          "backup_root", "backup_created_at", "pin_recorded_at"}
            or document["schema"] != SCHEMA
            or document["source_name"] not in ALLOWED
            or pin_path.name != document["backup_id"] + ".pin.json"
            or str(backup_root) != document["backup_root"]
            or type(document["snapshot_bytes"]) is not int
            or not 0 < document["snapshot_bytes"] <= 50 * 1024 * 1024):
        raise SourceShareError("invalid cross-device DR pin")
    registered = _when(document["pin_recorded_at"], "pin recorded_at")
    created = _when(document["backup_created_at"], "backup created_at")
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not created <= registered <= current:
        raise SourceShareError("physical DR pin cannot be used retroactively")
    receipt = BackupReceipt(
        document["backup_id"], document["source_name"],
        _must_sha(document["snapshot_sha256"], "snapshot"),
        _must_sha(document["manifest_sha256"], "manifest"),
        created, document["snapshot_bytes"],
    )
    return RecordedRecoveryPin(pin_path, receipt, registered, backup_root)


def verify_recovery_from_pin(pin_path: Path, pin_root: Path,
                             backup_root: Path, restore_parent: Path,
                             *, now: datetime | None = None) -> Path:
    """A later cold-restore uses the SHA from the independently saved Mac pin."""
    pinned = read_recovery_pin(pin_path, pin_root, backup_root, now=now)
    restore_parent = _private_dir(restore_parent, create=True)
    if not _different_disk(restore_parent, pinned.backup_root):
        raise SourceShareError("restore must be on an independent device")
    from uuid import uuid4
    dest = restore_parent / ("pin_verify_" + uuid4().hex)
    restored = restore_to_new_dir(
        pinned.backup_root, pinned.receipt, dest,
        expected_manifest_sha256=pinned.receipt.manifest_sha256,
    )
    return restored


def checked_local_recovery_sources(pin_root: Path,
                                   backup_root: Path) -> frozenset[str]:
    """Read-only status: Mac-side pins and SSD SHA remain recoverable.

    Each pin was created only after an isolated verified restore. This does
    not imply that an off-site copy or five trading days are certified.
    """
    pin_root = Path(pin_root)
    backup_root = Path(backup_root)
    if not pin_root.exists() and not pin_root.is_symlink():
        return frozenset()
    if not backup_root.exists() and not backup_root.is_symlink():
        return frozenset()
    pinned_root, backups = _validate_locations(pin_root, backup_root)
    from .backup_recovery import _file_sha
    sources = set()
    for file in sorted(pinned_root.iterdir()):
        if not file.name.endswith(".pin.json"):
            raise SourceShareError("unexpected DR pin file in private store")
        check = read_recovery_pin(file, pinned_root, backups)
        receipt = check.receipt
        folder = _private_dir(backups / receipt.backup_id)
        manifest = folder / "manifest.json"
        _regular_owner(manifest)
        if sha256(_read_regular(manifest, PIN_LIMIT)).hexdigest() != receipt.manifest_sha256:
            raise SourceShareError("DR backup manifest no longer matches independent pin")
        snapshot = folder / "state.sqlite3"
        _regular_owner(snapshot)
        digest, size = _file_sha(snapshot)
        if digest != receipt.snapshot_sha256 or size != receipt.snapshot_bytes:
            raise SourceShareError("DR snapshot no longer matches independent pin")
        sources.add(receipt.source_name)
    return frozenset(sources)
