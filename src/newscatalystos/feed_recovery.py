"""6_5 durable, private retry inbox for approved feed metadata triage.

A pre-commit checkpoint protects title/link metadata if analysis fails after
1_3 successfully commits seen IDs. Only a checkpoint corroborated by committed
SQLite watermark/seen IDs can be replayed, without another HTTP request.
Original article bodies, provider credentials and EraLeader data are excluded.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import stat
import tempfile

from .evidence_archive import _private_root, _write_new
from .incremental_ingest import IncrementalResult, _connect
from .new_source_adapter import FeedObservation, STATUS as FEED_STATUS, _text
from .provider_registry import ProviderRegistry, _safe_https_endpoint
from .source_share import SourceShareError, _json, _must_sha, _read_regular, _when

SCHEMA = "newscatalyst.feed_retry_checkpoint.v1"
MARKER_SCHEMA = "newscatalyst.feed_retry_marker.v1"
ACK_SCHEMA = "newscatalyst.feed_retry_ack.v1"
MAX_BYTES = 512_000
FOLDER = re.compile(r"^pending_([a-f0-9]{64})$")


@dataclass(frozen=True)
class RetryCheckpoint:
    location: Path
    payload_sha256: str
    poll: IncrementalResult


def _encoded(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _validate_poll(poll: IncrementalResult) -> None:
    if (not isinstance(poll, IncrementalResult)
            or poll.status not in ("SUCCESS_NEW", "SUCCESS_UNCHANGED")
            or type(poll.new_count) is not int or type(poll.duplicate_count) is not int
            or not 0 <= poll.new_count <= 100 or not 0 <= poll.duplicate_count <= 100
            or len(poll.observations) == 0 or len(poll.observations) > 100
            or len(poll.observations) != poll.new_count + poll.duplicate_count
            or poll.certified_raw_event_count != 0
            or len(poll.newly_observed_event_ids) != poll.new_count):
        raise SourceShareError("invalid bounded ingestion checkpoint")
    stamp = _when(poll.usable_from.isoformat(), "checkpoint usable_from")
    if _when(poll.watermark.isoformat(), "checkpoint watermark") != stamp:
        raise SourceShareError("inconsistent checkpoint watermark")
    seen: set[str] = set()
    fresh = set(poll.newly_observed_event_ids)
    if len(fresh) != poll.new_count:
        raise SourceShareError("duplicated new checkpoint event IDs")
    for row in poll.observations:
        if not isinstance(row, FeedObservation) or row.provider_id != poll.provider_id:
            raise SourceShareError("invalid feed checkpoint source")
        _text(row.document_id, "checkpoint document ID", 512)
        _text(row.headline, "checkpoint title", 256)
        _safe_https_endpoint(row.source_url)
        if (row.reported_published_at is not None
                or row.verification_status != FEED_STATUS
                or _when(row.first_seen_at.isoformat(), "checkpoint first_seen") > stamp):
            raise SourceShareError("unsafe checkpoint time/classification")
        expected = sha256((row.provider_id + "\0" + row.document_id).encode()).hexdigest()
        if _must_sha(row.event_id, "checkpoint event id") != expected:
            raise SourceShareError("feed checkpoint event identity mismatch")
        if row.event_id in seen:
            raise SourceShareError("duplicate feed checkpoint event")
        seen.add(row.event_id)
    if not fresh.issubset(seen):
        raise SourceShareError("new checkpoint identity absent from receipt")


def save_retry_checkpoint(root: Path, poll: IncrementalResult) -> RetryCheckpoint:
    """Write before SQLite marks a feed seen/successful. Never overwrite."""
    _validate_poll(poll)
    private = _private_root(root)
    data = {
        "schema": SCHEMA, "provider_id": poll.provider_id,
        "status": poll.status, "new_count": poll.new_count,
        "duplicate_count": poll.duplicate_count,
        "usable_from": poll.usable_from.isoformat(),
        "watermark": poll.watermark.isoformat(),
        "newly_observed_event_ids": list(poll.newly_observed_event_ids),
        "records": [{
            "provider_id": r.provider_id, "event_id": r.event_id,
            "document_id": r.document_id, "headline": r.headline,
            "source_url": r.source_url,
            "first_seen_at": r.first_seen_at.isoformat(),
            "verification_status": r.verification_status,
            "reported_published_at": None,
        } for r in poll.observations],
    }
    payload = _encoded(data)
    if len(payload) > MAX_BYTES:
        raise SourceShareError("feed metadata checkpoint too large")
    digest = sha256(payload).hexdigest()
    folder = private / ("pending_" + digest)
    if folder.exists() or folder.is_symlink():
        # A replay retry of identical metadata can reuse the immutable checkpoint.
        existing = read_retry_checkpoint(folder, private, digest)
        if existing.poll != poll:
            raise SourceShareError("feed retry checkpoint digest collision")
        return existing
    stage = Path(tempfile.mkdtemp(prefix=".retry_staging_", dir=private))
    try:
        stage.chmod(0o700)
        marker = {
            "schema": MARKER_SCHEMA, "status": "COMPLETE_METADATA_ONLY",
            "payload_file": "feed.json", "payload_sha256": digest,
            "record_count": len(poll.observations),
            "verified_economic_fact_count": 0, "source_body_stored": False,
        }
        _write_new(stage / "feed.json", payload)
        _write_new(stage / "publication.json", _encoded(marker))
        fd = os.open(stage, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(stage, folder)
        fd = os.open(private, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise SourceShareError("durable feed checkpoint unavailable") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return RetryCheckpoint(folder, digest, poll)


def read_retry_checkpoint(folder: Path, root: Path, digest: str) -> RetryCheckpoint:
    """Validate all stored metadata; a file marker cannot self-pin."""
    root = _private_root(root)
    folder = Path(folder)
    sha = _must_sha(digest, "independently expected checkpoint SHA")
    if (folder.parent != root or folder.name != "pending_" + sha
            or FOLDER.fullmatch(folder.name) is None):
        raise SourceShareError("feed retry folder outside private root")
    info = folder.lstat()
    if (not stat.S_ISDIR(info.st_mode) or folder.is_symlink()
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("unsafe feed retry folder")
    marker = _json(_read_regular(folder / "publication.json", 8192),
                   "retry marker")
    if (set(marker) != {"schema", "status", "payload_file", "payload_sha256",
                        "record_count", "verified_economic_fact_count", "source_body_stored"}
            or marker["schema"] != MARKER_SCHEMA
            or marker["status"] != "COMPLETE_METADATA_ONLY"
            or marker["payload_file"] != "feed.json"
            or marker["payload_sha256"] != sha
            or type(marker["record_count"]) is not int
            or not 1 <= marker["record_count"] <= 100
            or marker["verified_economic_fact_count"] != 0
            or marker["source_body_stored"] is not False):
        raise SourceShareError("untrusted retry publication marker")
    raw = _read_regular(folder / "feed.json", MAX_BYTES)
    if sha256(raw).hexdigest() != sha:
        raise SourceShareError("retry payload SHA differs from pin")
    doc = _json(raw, "retry payload")
    if (set(doc) != {"schema", "provider_id", "status", "new_count",
                     "duplicate_count", "usable_from", "watermark",
                     "newly_observed_event_ids", "records"}
            or doc["schema"] != SCHEMA or not isinstance(doc["records"], list)
            or len(doc["records"]) != marker["record_count"]):
        raise SourceShareError("invalid retry payload schema")
    rows = []
    for item in doc["records"]:
        if (not isinstance(item, dict)
                or set(item) != {"provider_id", "event_id", "document_id",
                                "headline", "source_url", "first_seen_at",
                                "verification_status", "reported_published_at"}):
            raise SourceShareError("unexpected retry feed metadata fields")
        if item["reported_published_at"] is not None:
            raise SourceShareError("feed reported timestamp not certified")
        rows.append(FeedObservation(
            item["provider_id"], item["event_id"], item["document_id"],
            item["headline"], item["source_url"],
            _when(item["first_seen_at"], "first_seen_at"), None,
            item["verification_status"],
        ))
    if not isinstance(doc["newly_observed_event_ids"], list):
        raise SourceShareError("retry new identities malformed")
    restored = IncrementalResult(
        provider_id=doc["provider_id"], status=doc["status"],
        new_count=doc["new_count"], duplicate_count=doc["duplicate_count"],
        watermark=_when(doc["watermark"], "watermark"),
        usable_from=_when(doc["usable_from"], "usable_from"),
        observations=tuple(rows),
        newly_observed_event_ids=tuple(doc["newly_observed_event_ids"]),
    )
    _validate_poll(restored)
    if _encoded(doc) != raw:
        raise SourceShareError("retry payload not canonical")
    return RetryCheckpoint(folder, sha, restored)


def check_committed_ingest(state: Path, poll: IncrementalResult, *,
                           now: datetime | None = None) -> None:
    """Reject an orphan written before a rolled-back ingestion transaction."""
    _validate_poll(poll)
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if poll.usable_from > current:
        raise SourceShareError("future checkpoint cannot be replayed")
    conn = _connect(state)
    try:
        record = conn.execute("SELECT last_success_at FROM source_state WHERE provider_id=?",
                              (poll.provider_id,)).fetchone()
        if (record is None or record[0] is None
                or _when(record[0], "last success") < poll.watermark):
            raise SourceShareError("retry checkpoint has no committed watermark")
        ids = set(poll.newly_observed_event_ids)
        for item in poll.observations:
            row = conn.execute(
                "SELECT first_verified_at FROM seen_events WHERE provider_id=? AND event_id=?",
                (poll.provider_id, item.event_id),
            ).fetchone()
            if (row is None or _when(row[0], "first verified") > poll.watermark
                    or (item.event_id in ids and
                        _when(row[0], "first verified") != poll.watermark)):
                raise SourceShareError("retry feed event is not durably committed")
    finally:
        conn.close()


def _ack_is_valid(private: Path, digest: str, at: datetime) -> bool:
    path = private / "acked" / (digest + ".json")
    if not path.exists() and not path.is_symlink():
        return False
    ackdir = _private_root(path.parent)
    record = _json(_read_regular(ackdir / path.name, 4096), "retry acknowledgment")
    if (set(record) != {"schema", "checkpoint_sha256", "triage_sha256",
                        "provider_id", "poll_verified_at", "confirmed_at",
                        "record_count", "triage_folder"}
            or record["schema"] != ACK_SCHEMA
            or record["checkpoint_sha256"] != digest):
        raise SourceShareError("invalid retry completion acknowledgment")
    triage_pin = _must_sha(record["triage_sha256"], "acknowledged triage SHA")
    folder = Path(record["triage_folder"])
    if (not folder.is_absolute() or folder.is_symlink()
            or folder.name != "feed_triage_" + triage_pin):
        raise SourceShareError("operation receipt points outside verified triage")
    _private_root(folder.parent)
    triage_bytes = _read_regular(folder / "triage.json", 150_000)
    triage_doc = _json(triage_bytes, "acknowledged triage report")
    triage_marker = _json(_read_regular(folder / "publication.json", 8192),
                          "acknowledged triage marker")
    original = read_retry_checkpoint(private / ("pending_" + digest), private, digest)
    if (sha256(triage_bytes).hexdigest() != triage_pin
            or triage_marker.get("status") != "COMPLETE_METADATA_ONLY"
            or triage_marker.get("payload_sha256") != triage_pin
            or record["provider_id"] != original.poll.provider_id
            or record["poll_verified_at"] != original.poll.usable_from.isoformat()
            or record["record_count"] != len(original.poll.observations)
            or triage_doc.get("provider_id") != original.poll.provider_id
            or triage_doc.get("observed_count") != len(original.poll.observations)):
        raise SourceShareError("acknowledged triage payload unavailable or corrupted")
    completed = _when(record["confirmed_at"], "retry completion")
    polled = _when(record["poll_verified_at"], "retry poll watermark")
    if (completed > at or polled > completed
            or type(record["record_count"]) is not int
            or not 1 <= record["record_count"] <= 100
            or not isinstance(record["provider_id"], str)):
        raise SourceShareError("invalid or future recovery completion acknowledgment")
    return True


def pending_retry_checkpoints(root: Path, state: Path,
                              registry: ProviderRegistry, provider_id: str,
                              *, now: datetime | None = None) -> tuple[RetryCheckpoint, ...]:
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    registry.active(provider_id, at=at)
    private = _private_root(root)
    results = []
    for path in sorted(private.iterdir()):
        if not path.name.startswith("pending_"):
            continue
        match = FOLDER.fullmatch(path.name)
        if match is None:
            raise SourceShareError("unexpected feed retry checkpoint path")
        if _ack_is_valid(private, match[1], at):
            continue
        receipt = read_retry_checkpoint(path, private, match[1])
        if receipt.poll.provider_id != provider_id:
            continue
        check_committed_ingest(state, receipt.poll, now=at)
        results.append(receipt)
    results.sort(key=lambda x: (x.poll.usable_from, x.payload_sha256))
    return tuple(results)


def acknowledge_retry_checkpoint(root: Path, receipt: RetryCheckpoint,
                                 triage_folder: Path, triage_sha256: str) -> Path:
    """Acknowledge only after fully published private triage payload is rechecked."""
    private = _private_root(root)
    if not isinstance(receipt, RetryCheckpoint):
        raise SourceShareError("verified retry receipt required")
    _must_sha(receipt.payload_sha256, "checkpoint digest")
    confirmed = read_retry_checkpoint(
        receipt.location, private, receipt.payload_sha256
    )
    if confirmed != receipt:
        raise SourceShareError("retry receipt differs from completed checkpoint")
    triage_sha = _must_sha(triage_sha256, "triage SHA")
    folder = Path(triage_folder)
    if folder.name != "feed_triage_" + triage_sha or folder.is_symlink():
        raise SourceShareError("unexpected triage output")
    raw = _read_regular(folder / "triage.json", 150_000)
    marker = _json(_read_regular(folder / "publication.json", 8192), "triage marker")
    report = _json(raw, "triage report")
    if (sha256(raw).hexdigest() != triage_sha
            or marker.get("payload_sha256") != triage_sha
            or marker.get("status") != "COMPLETE_METADATA_ONLY"
            or report.get("provider_id") != receipt.poll.provider_id
            or report.get("observed_count") != len(receipt.poll.observations)
            or report.get("source_body_count") != 0
            or report.get("verified_new_economic_fact_count") != 0):
        raise SourceShareError("cannot acknowledge unverified triage output")
    ack_dir = _private_root(private / "acked")
    target = ack_dir / (receipt.payload_sha256 + ".json")
    body = _encoded({
        "schema": ACK_SCHEMA,
        "checkpoint_sha256": receipt.payload_sha256,
        "triage_sha256": triage_sha,
        "provider_id": receipt.poll.provider_id,
        "record_count": len(receipt.poll.observations),
        "poll_verified_at": receipt.poll.usable_from.isoformat(),
        "triage_folder": str(folder),
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        _write_new(target, body)
        fd = os.open(ack_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except FileExistsError as exc:
        raise SourceShareError("retry checkpoint already acknowledged") from exc
    return target
