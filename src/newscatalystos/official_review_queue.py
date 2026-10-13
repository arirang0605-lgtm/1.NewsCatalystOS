"""5_2: deterministic review worklist from completed DART/SEC observation metadata.

This is a *screening queue*, not a list of semiconductor companies, verified
supply contracts, or even relevant disclosures. The original shared metadata
has no document body or official counterparty claims. No API calls or Era writes.
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
import uuid

from .operational_observations import OperationalObservationSet
from .source_share import SourceShareError, _when

SCHEMA = "newscatalyst.official_relation_review_queue.v1"
MARKER_SCHEMA = "newscatalyst.review_queue_publication.v1"
SOURCE_IDS = ("dart-disclosures", "sec-submissions")
MAX_ROWS = 2000


@dataclass(frozen=True)
class OfficialReviewQueue:
    decision_at: datetime
    total_eligible: int
    selected_count: int
    payload: bytes
    payload_sha256: str


@dataclass(frozen=True)
class ReviewQueuePublication:
    location: Path
    payload_sha256: str
    published_at: datetime
    item_count: int


def build_official_review_queue(
    observations: OperationalObservationSet, *,
    decision_at: datetime, source_id: str = "ALL",
    offset: int = 0, limit: int = 100,
    document_id: str | None = None,
    now: datetime | None = None,
) -> OfficialReviewQueue:
    """Page stable identifiers; preserve UNKNOWN relevance and relationship."""
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    decision = _when(decision_at.isoformat(), "decision_at")
    if (not isinstance(observations, OperationalObservationSet)
            or observations.coverage_verified is not True):
        raise SourceShareError("complete official observation coverage required")
    if (source_id not in (*SOURCE_IDS, "ALL")
            or (document_id is not None and (not isinstance(document_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", document_id)))
            or type(offset) is not int or type(limit) is not int
            or offset < 0 or not 1 <= limit <= MAX_ROWS):
        raise SourceShareError("invalid review queue pagination or source")
    rows = observations.as_of(decision, now=current)
    eligible = [
        r for r in rows
        if (r.source_id in SOURCE_IDS and r.data_kind == "DISCLOSURE_OBSERVED"
            and (source_id == "ALL" or r.source_id == source_id))
    ]
    if document_id is not None:
        eligible = [r for r in eligible if r.source_document_id == document_id]
        if not eligible:
            raise SourceShareError("requested document absent from verified publication")
    eligible.sort(key=lambda r: (r.source_id, r.source_document_id, r.evidence_id))
    if len({(r.source_id, r.source_document_id) for r in eligible}) != len(eligible):
        raise SourceShareError("ambiguous duplicate official document ID")
    page = eligible[offset:offset + limit]
    items = [{
        "source_id": row.source_id,
        "provider_id": row.provider_id,
        "source_document_id": row.source_document_id,
        "source_evidence_id": row.evidence_id,
        "source_receipt_sha256": row.receipt_sha256,
        "source_available_at": row.available_at.isoformat(),
        "source_quality": row.source_quality,
        "industry_relevance": "UNKNOWN_UNSCREENED",
        "official_document_text_available": False,
        "supply_relation_status": "UNREVIEWED",
        "verified_real_transaction": False,
    } for row in page]
    payload = {
        "schema": SCHEMA,
        "status": "OFFICIAL_METADATA_ONLY_MANUAL_SCREENING_REQUIRED",
        "decision_at": decision.isoformat(),
        "source_filter": source_id,
        "requested_document_id": document_id,
        "sort": "SOURCE_AND_DOCUMENT_ID_NOT_IMPORTANCE",
        "offset": offset, "limit": limit,
        "total_eligible": len(eligible), "selected_count": len(items),
        "has_more": offset + len(items) < len(eligible),
        "verified_supply_relationship_count": 0,
        "semiconductor_relevance_verified_count": 0,
        "items": items,
    }
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")
    return OfficialReviewQueue(decision, len(eligible), len(items),
                               data, sha256(data).hexdigest())


def publish_official_review_queue(
    queue: OfficialReviewQueue, root: Path, *,
    now: datetime | None = None,
) -> ReviewQueuePublication:
    """Owner-only append-only atomic publication; never store article bodies."""
    if not isinstance(queue, OfficialReviewQueue):
        raise SourceShareError("typed official review queue required")
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if queue.decision_at > current or sha256(queue.payload).hexdigest() != queue.payload_sha256:
        raise SourceShareError("future or corrupted review queue")
    root = Path(root)
    if not root.is_absolute():
        raise SourceShareError("absolute review output root required")
    try:
        root.mkdir(mode=0o700, exist_ok=True)
        info = root.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise SourceShareError("review queue root must be owner-only")
    except OSError as exc:
        raise SourceShareError("private review root unavailable") from exc
    identity = uuid.uuid4().hex
    stage = root / (".review_staging_" + identity)
    final = root / ("official_relation_review_queue_" + identity)
    stage.mkdir(mode=0o700, exist_ok=False)
    try:
        marker = {
            "schema": MARKER_SCHEMA,
            "status": "COMPLETE_METADATA_ONLY",
            "payload_file": "queue.json",
            "payload_sha256": queue.payload_sha256,
            "item_count": queue.selected_count,
            "official_text_stored": False,
            "verified_supply_relationship_count": 0,
            "marker_prepared_at": current.isoformat(),
        }
        raw_marker = (json.dumps(marker, sort_keys=True, separators=(",", ":"))
                      + "\n").encode("utf-8")
        for filename, data in (("queue.json", queue.payload),
                               ("publication.json", raw_marker)):
            fd = os.open(stage / filename,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        fd = os.open(stage, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(stage, final)
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        # This is after atomic rename and directory durability, unlike marker time.
        completed = now or datetime.now(timezone.utc)
    except (OSError, SourceShareError) as exc:
        raise SourceShareError("atomic private review publication failed") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return ReviewQueuePublication(final, queue.payload_sha256,
                                  completed, queue.selected_count)
