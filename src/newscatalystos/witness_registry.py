"""Offline private trust registry reader for official publication witnesses.

The registry must be provisioned by the operator through an independently
reviewed enrollment process BEFORE the decision time. This module NEVER
creates trust records or accepts a proof-supplied key fingerprint as trust.
Local metadata is not a third-party timestamp notary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
import stat

from .source_share import SourceShareError, _json, _must_id, _must_sha, _read_regular, _when

SCHEMA = "newscatalyst.official_witness_registry.v1"
TRUST = "OPERATOR_APPROVED_EXTERNAL_WITNESS"
REGISTRY_NAME = "official_witness_registry.json"
MAX_BYTES = 16 * 1024
ALLOWED = frozenset({"sec-submissions", "dart-disclosures"})
FIELDS = frozenset({"schema", "trust_level", "witnesses"})
WITNESS_FIELDS = frozenset({
    "witness_id", "public_key_sha256", "enrolled_at", "allowed_sources",
})


@dataclass(frozen=True)
class TrustedWitness:
    witness_id: str
    public_key_sha256: str
    enrolled_at: datetime
    allowed_sources: frozenset[str]
    trust_level: str = TRUST


def parse_operator_witness_registry(
    document: bytes, witness_id: str, source_id: str, decision_at: datetime,
    *, now: datetime | None = None,
) -> TrustedWitness:
    """Validate content, even if an out-of-band trust path was already checked.

    Merely self-issuing these bytes is NOT proof of external authority.
    """
    _must_id(witness_id, "witness_id")
    decision = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if decision > instant:
        raise SourceShareError("decision in future")
    if source_id not in ALLOWED:
        raise SourceShareError("witness authorization source invalid")
    if not isinstance(document, bytes) or not 0 < len(document) <= MAX_BYTES:
        raise SourceShareError("unavailable independent witness registry")
    record = _json(document, "witness registry")
    if (set(record) != FIELDS or record["schema"] != SCHEMA or
            record["trust_level"] != TRUST):
        raise SourceShareError("witness registry not operator approved")
    items = record["witnesses"]
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise SourceShareError("invalid witness registry size")
    by_id: dict[str, TrustedWitness] = {}
    for row in items:
        if not isinstance(row, dict) or set(row) != WITNESS_FIELDS:
            raise SourceShareError("invalid witness enrollment fields")
        identity = _must_id(row["witness_id"], "enrolled witness_id")
        if identity in by_id or identity in ("eraleader", "newscatalystos"):
            raise SourceShareError("duplicate or project-operated witness")
        allowed = row["allowed_sources"]
        if (not isinstance(allowed, list) or not allowed or len(allowed) > 2 or
                any(not isinstance(x, str) or x not in ALLOWED for x in allowed) or
                len(set(allowed)) != len(allowed)):
            raise SourceShareError("invalid witness source scope")
        enrolled_at = _when(row["enrolled_at"], "witness enrolled_at")
        if enrolled_at > instant:
            raise SourceShareError("future witness enrollment")
        by_id[identity] = TrustedWitness(
            identity,
            _must_sha(row["public_key_sha256"], "witness public key fingerprint"),
            enrolled_at, frozenset(allowed),
        )
    trusted = by_id.get(witness_id)
    if trusted is None:
        raise SourceShareError("witness not in independent operator registry")
    if decision < trusted.enrolled_at:
        raise SourceShareError("witness was not enrolled at decision")
    if source_id not in trusted.allowed_sources:
        raise SourceShareError("witness has no provider authorization")
    return trusted


def private_registry_path() -> Path:
    """Fixed private path, never accepted from a proof package or CLI flag."""
    return Path.home() / "Library" / "Application Support" / "NewsCatalystOS" / "trust" / REGISTRY_NAME


def load_operator_witness(
    era_root: Path,
    witness_id: str,
    source_id: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> TrustedWitness:
    """Use a private owner-controlled registry on a device other than T5DATA."""
    path = private_registry_path()
    directory = path.parent
    for parent in (directory,):
        try:
            info = parent.lstat()
        except OSError as exc:
            raise SourceShareError("independent operator witness registry missing") from exc
        if (not stat.S_ISDIR(info.st_mode) or
                info.st_uid != os.geteuid() or
                stat.S_IMODE(info.st_mode) & 0o077):
            raise SourceShareError("operator witness registry is not owner-private")
    try:
        info = path.lstat()
    except OSError as exc:
        raise SourceShareError("independent operator witness registry missing") from exc
    if (not Path(era_root).is_absolute() or directory.stat().st_dev ==
            Path(era_root).stat().st_dev):
        raise SourceShareError("operator witness registry must use independent disk")
    if (not stat.S_ISREG(info.st_mode) or
            info.st_uid != os.geteuid() or
            stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("operator witness registry file not owner-private")
    return parse_operator_witness_registry(
        _read_regular(path, MAX_BYTES), witness_id, source_id,
        decision_at, now=now,
    )
