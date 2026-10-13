"""Local independent-disk TOFU anchor for an EraLeader research reference.

This records the first *local* observation on another device. It does NOT
attest earlier historical publication, SEC release, or any third-party time.
The anchor is never published in the GitHub repository.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import stat

from .source_share import (
    SourceShareError, _check_directory, _json, _must_sha, _read_regular, _when
)
from .verified_reference import (
    REPORT_SCHEMA, VerifiedOfficialSources, verify_official_research_reference
)

SCHEMA = "newscatalyst.local_research_sha_anchor.v1"
ANCHOR_FILENAME = "official_api_pit_research.pin.json"
TRUST_LEVEL = "LOCAL_TOFU_NOT_EXTERNAL_ATTESTATION"


@dataclass(frozen=True)
class LocalReferenceAnchor:
    report_sha256: str
    observed_at: datetime
    trust_level: str = TRUST_LEVEL


def _device(path: Path) -> int:
    return path.stat().st_dev


def _check_paths(era_root: Path, reference: Path, anchor_path: Path) -> None:
    if not (era_root.is_absolute() and reference.is_absolute() and
            anchor_path.is_absolute()):
        raise SourceShareError("absolute paths required")
    _check_directory(reference.parent, era_root)
    if reference.name != "official_api_pit_research.json":
        raise SourceShareError("unexpected official research index")
    if anchor_path.name != ANCHOR_FILENAME:
        raise SourceShareError("unexpected local anchor filename")
    parent = anchor_path.parent
    try:
        st = parent.lstat()
    except OSError as exc:
        raise SourceShareError("independent anchor directory unavailable") from exc
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or
            stat.S_IMODE(st.st_mode) & 0o077 or parent.is_symlink()):
        raise SourceShareError("anchor directory must be private owner-only")
    if (_device(parent) == _device(era_root) or
            era_root.resolve() in parent.resolve().parents):
        raise SourceShareError("independent anchor must be on another disk")


def _check_reference_schema(content: bytes) -> None:
    obj = _json(content, "official research report")
    if (obj.get("schema") != REPORT_SCHEMA or
            obj.get("watch_type") != "PRICE_ONLY_RESEARCH_NOT_CERTIFIED" or
            obj.get("historic_universe_pit_verified") is not False or
            obj.get("issuer_share_class_verified") is not False or
            obj.get("dart_sec_financial_pit_joined") is not False or
            obj.get("official_leaders") != 0):
        raise SourceShareError("reference is not unpromoted research-only")


def create_local_reference_anchor(
    era_root: Path, reference: Path, anchor_path: Path
) -> LocalReferenceAnchor:
    """Create once with O_EXCL. Never overwrite a pre-existing trust anchor."""
    era_root, reference, anchor_path = map(Path, (era_root, reference, anchor_path))
    _check_paths(era_root, reference, anchor_path)
    report = _read_regular(reference, 2 * 1024 * 1024)
    _check_reference_schema(report)
    observed = datetime.now(timezone.utc)
    digest = sha256(report).hexdigest()
    payload = {
        "schema": SCHEMA, "trust_level": TRUST_LEVEL,
        "reference_name": reference.name,
        "report_sha256": digest, "first_local_observed_at": observed.isoformat(),
    }
    body = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(anchor_path, flags, 0o600)
    except OSError as exc:
        raise SourceShareError("local anchor already exists or cannot be created") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        dir_fd = os.open(anchor_path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except (OSError, ValueError):
        # Failure is never interpreted as a valid initialized anchor.
        raise SourceShareError("could not durably save anchor")
    return LocalReferenceAnchor(digest, observed)


def read_local_reference_anchor(
    era_root: Path, reference: Path, anchor_path: Path, decision_at: datetime
) -> LocalReferenceAnchor:
    era_root, reference, anchor_path = map(Path, (era_root, reference, anchor_path))
    _check_paths(era_root, reference, anchor_path)
    try:
        info = anchor_path.lstat()
    except OSError as exc:
        raise SourceShareError("local SHA anchor unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or
            info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("local anchor not private regular file")
    obj = _json(_read_regular(anchor_path, 4096), "local SHA anchor")
    if (obj.get("schema") != SCHEMA or obj.get("trust_level") != TRUST_LEVEL or
            obj.get("reference_name") != reference.name):
        raise SourceShareError("local SHA anchor schema/trust invalid")
    pinned_at = _when(obj.get("first_local_observed_at"), "anchor observed_at")
    when = _when(decision_at.isoformat() if isinstance(decision_at, datetime) else None,
                 "decision_at")
    if pinned_at > when or pinned_at > datetime.now(timezone.utc):
        raise SourceShareError("anchor unavailable at decision (no historical proof)")
    return LocalReferenceAnchor(
        _must_sha(obj.get("report_sha256"), "report_sha256"), pinned_at)


def verify_with_local_anchor(
    era_root: Path, reference: Path, anchor_path: Path, decision_at: datetime
) -> VerifiedOfficialSources:
    pin = read_local_reference_anchor(era_root, reference, anchor_path, decision_at)
    return verify_official_research_reference(
        era_root, reference, pin.report_sha256, decision_at)
