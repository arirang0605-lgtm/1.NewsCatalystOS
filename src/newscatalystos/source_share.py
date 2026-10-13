"""Fail-closed, read-only consumer of EraLeader *published* evidence bundles.

Never imports EraLeader or calls DART/SEC/KRX. A publisher must atomically place
a COMPLETE publication marker last; a separately pinned manifest digest guards
against forged or overwritten metadata. This contract does not create bundles.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import stat

SCHEMA = "newscatalyst.source_manifest.v1"
PUBLICATION_SCHEMA = "newscatalyst.publication.v1"
EVENT_SCHEMA = "newscatalyst.raw_event.v1"
PROVIDERS = frozenset({"DART", "SEC", "KRX"})
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MAX_MANIFEST_BYTES = 32_768
MAX_EVENTS_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 10_000


class SourceShareError(ValueError):
    """Unavailable, malformed, unpinned or future-dated source: fail closed."""


@dataclass(frozen=True)
class SourceManifest:
    schema_version: str
    snapshot_id: str
    provider_id: str
    source_id: str
    source_schema_version: str
    publisher_id: str
    published_at: datetime
    first_seen_at: datetime
    first_receipt_sha256: str
    manifest_sha256: str
    event_count: int


@dataclass(frozen=True)
class RawEvent:
    schema_version: str
    event_id: str
    source_id: str
    provider_id: str
    source_document_id: str
    company_id: str | None
    published_at: datetime
    first_seen_at: datetime
    source_sha256: str
    source_receipt_sha256: str


@dataclass(frozen=True)
class ReadBatch:
    manifest: SourceManifest
    events: tuple[RawEvent, ...]


def _must_id(value: object, name: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise SourceShareError(f"invalid {name}")
    return value


def _must_sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise SourceShareError(f"invalid {name}")
    return value


def _when(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise SourceShareError(f"missing {name}")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceShareError(f"invalid {name}") from exc
    if moment.tzinfo is None or moment.utcoffset() is None or moment.year < 2000:
        raise SourceShareError(f"invalid timezone/year: {name}")
    return moment.astimezone(timezone.utc)


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise SourceShareError("duplicate JSON key")
        obj[key] = value
    return obj


def _json(data: bytes, name: str) -> dict:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                           parse_constant=lambda _: (_ for _ in ()).throw(SourceShareError("nonfinite number")))
    except (UnicodeError, ValueError) as exc:
        raise SourceShareError(f"invalid JSON: {name}") from exc
    if not isinstance(value, dict):
        raise SourceShareError(f"expected object: {name}")
    return value


def _read_regular(path: Path, limit: int) -> bytes:
    # read-only + NOFOLLOW, bounded, and verify descriptor identity before/after.
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path, flags)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise SourceShareError("not a regular bounded evidence file")
            data = b""
            while len(data) <= limit:
                block = os.read(fd, min(65536, limit + 1 - len(data)))
                if not block:
                    break
                data += block
            after = os.fstat(fd)
            if (len(data) > limit or len(data) != after.st_size or
                (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns) !=
                (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns)):
                raise SourceShareError("evidence size changed or exceeds limit")
            return data
        finally:
            os.close(fd)
    except OSError as exc:
        raise SourceShareError("evidence unavailable or unsafe") from exc


def _check_directory(bundle: Path, era_root: Path) -> None:
    if not bundle.is_absolute() or not era_root.is_absolute():
        raise SourceShareError("absolute paths required")
    try:
        rel = bundle.relative_to(era_root)
    except ValueError as exc:
        raise SourceShareError("bundle outside EraLeader root") from exc
    if not rel.parts or rel.parts[0] != "output" or ".." in rel.parts:
        raise SourceShareError("only EraLeader output bundles permitted")
    current = era_root
    for part in rel.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise SourceShareError("missing bundle component") from exc
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise SourceShareError("symlink or nondirectory bundle")
    if era_root.is_symlink() or bundle.resolve(strict=True) != current.resolve(strict=True):
        raise SourceShareError("unsafe parent")


def read_verified_bundle(
    bundle_dir: Path,
    era_root: Path,
    expected_manifest_sha256: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> ReadBatch:
    """Read published event metadata; reject unverified, moving and future sources.

    Caller supplies manifest SHA from an independent trusted channel; NEVER
    discover a 'latest' mutable export and trust its embedded hash alone.
    Nothing is written to either project.
    """
    bundle_dir, era_root = Path(bundle_dir), Path(era_root)
    _check_directory(bundle_dir, era_root)
    _must_sha(expected_manifest_sha256, "expected_manifest_sha256")
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    decision = _when(decision_at.isoformat(), "decision_at") if isinstance(decision_at, datetime) else _when(None, "decision_at")
    if decision > current:
        raise SourceShareError("decision_at is in future")
    marker_bytes = _read_regular(bundle_dir / "publication.json", MAX_MANIFEST_BYTES)
    marker = _json(marker_bytes, "publication")
    if (marker.get("schema") != PUBLICATION_SCHEMA or marker.get("status") != "COMPLETE" or
        marker.get("publisher_id") != "eraleader" or
        marker.get("manifest_sha256") != expected_manifest_sha256):
        raise SourceShareError("publication is not verified COMPLETE")
    marker_time = _when(marker.get("published_at"), "publication.published_at")
    if marker_time > decision:
        raise SourceShareError("publication not available at decision")
    manifest_bytes = _read_regular(bundle_dir / "manifest.json", MAX_MANIFEST_BYTES)
    digest = sha256(manifest_bytes).hexdigest()
    if digest != expected_manifest_sha256:
        raise SourceShareError("manifest digest differs from trusted pin")
    item = _json(manifest_bytes, "manifest")
    if (item.get("schema") != SCHEMA or item.get("status") != "COMPLETE" or
        item.get("publisher_id") != "eraleader" or item.get("quality_status") != "PASS"):
        raise SourceShareError("manifest not complete and quality verified")
    provider = item.get("provider_id")
    if provider not in PROVIDERS:
        raise SourceShareError("unsupported provider")
    count = item.get("event_count")
    size = item.get("events_size_bytes")
    if (type(count) is not int or not 0 <= count <= MAX_EVENTS or
        type(size) is not int or not 0 <= size <= MAX_EVENTS_BYTES):
        raise SourceShareError("invalid events bounds")
    if item.get("events_file") != "events.jsonl":
        raise SourceShareError("unexpected events path")
    first = _when(item.get("first_seen_at"), "manifest.first_seen_at")
    published = _when(item.get("published_at"), "manifest.published_at")
    if first > published or published > marker_time:
        raise SourceShareError("manifest timing inconsistent")
    manifest = SourceManifest(
        schema_version=SCHEMA, snapshot_id=_must_id(item.get("snapshot_id"), "snapshot_id"),
        provider_id=provider, source_id=_must_id(item.get("source_id"), "source_id"),
        source_schema_version=_must_id(item.get("source_schema_version"), "source_schema_version"),
        publisher_id="eraleader", published_at=marker_time, first_seen_at=first,
        first_receipt_sha256=_must_sha(item.get("first_receipt_sha256"), "first_receipt_sha256"),
        manifest_sha256=digest, event_count=count)
    events_bytes = _read_regular(bundle_dir / "events.jsonl", MAX_EVENTS_BYTES)
    if (len(events_bytes) != size or
        sha256(events_bytes).hexdigest() != _must_sha(item.get("events_sha256"), "events_sha256")):
        raise SourceShareError("published events do not match manifest")
    lines = events_bytes.splitlines()
    if len(lines) != count:
        raise SourceShareError("event count mismatch")
    seen = set()
    events = []
    for line in lines:
        event = _json(line, "event")
        if (event.get("schema") != EVENT_SCHEMA or
            event.get("source_id") != manifest.source_id or
            event.get("provider_id") != provider):
            raise SourceShareError("event schema or source mismatch")
        event_id = _must_id(event.get("event_id"), "event_id")
        if event_id in seen:
            raise SourceShareError("duplicate event id")
        seen.add(event_id)
        event_published = _when(event.get("published_at"), "event.published_at")
        event_first = _when(event.get("first_seen_at"), "event.first_seen_at")
        if (event_published > event_first or event_first > first or
            event_first > decision or event_published > decision):
            raise SourceShareError("event future information or impossible chronology")
        company = event.get("company_id")
        if company is not None:
            company = _must_id(company, "company_id")
        if _must_sha(event.get("source_receipt_sha256"), "source_receipt_sha256") != manifest.first_receipt_sha256:
            raise SourceShareError("event receipt not pinned to manifest")
        events.append(RawEvent(
            schema_version=EVENT_SCHEMA, event_id=event_id, source_id=manifest.source_id,
            provider_id=provider,
            source_document_id=_must_id(event.get("source_document_id"), "source_document_id"),
            company_id=company, published_at=event_published, first_seen_at=event_first,
            source_sha256=_must_sha(event.get("source_sha256"), "source_sha256"),
            source_receipt_sha256=_must_sha(event.get("source_receipt_sha256"), "source_receipt_sha256")))
    # Check publication didn't change while metadata/events were read.
    if _read_regular(bundle_dir / "publication.json", MAX_MANIFEST_BYTES) != marker_bytes:
        raise SourceShareError("publication changed during read")
    return ReadBatch(manifest=manifest, events=tuple(events))
