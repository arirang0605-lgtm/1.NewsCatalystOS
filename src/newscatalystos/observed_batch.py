"""PIT-safe research observations from verified EraLeader official captures.

This is a usable metadata consumer, NOT a generator of certified RawEvents.
Publication time and issuer identity remain unknown until separately proved.
No EraLeader import, network collection, filesystem write, or API call.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

from .official_normalization import normalize_official_capture
from .source_share import SourceShareError, _must_sha, _when
from .verified_reference import VerifiedOfficialSources

SCHEMA = "newscatalyst.observed_official_batch.v1"
STATUS = "RESEARCH_ONLY_RELEASE_UNVERIFIED"


@dataclass(frozen=True)
class ObservedOfficialRow:
    source_id: str
    provider_id: str
    evidence_id: str
    provider_record_id: str
    provider_day: str | None
    provider_acceptance_at: datetime | None
    first_seen_at: datetime
    usable_from: datetime
    original_sha256: str
    receipt_sha256: str
    source_quality: str
    published_at: None = None
    issuer_verified: bool = False
    classification: str = STATUS


@dataclass(frozen=True)
class ObservedOfficialBatch:
    schema_version: str
    reference_sha256: str
    independent_anchor_observed_at: datetime
    decision_at: datetime
    rows: tuple[ObservedOfficialRow, ...]
    source_count: int
    research_only: bool = True

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> tuple[ObservedOfficialRow, ...]:
        moment = _when(
            decision_at.isoformat() if isinstance(decision_at, datetime) else None,
            "decision_at",
        )
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if (moment < self.decision_at or moment < self.independent_anchor_observed_at
                or moment > present):
            raise SourceShareError("observed batch not available at decision")
        return self.rows

    def to_json_bytes(self) -> bytes:
        """Deterministic, private-safe *metadata*, never copyrighted raw bodies."""
        data = {
            "schema": SCHEMA,
            "status": STATUS,
            "reference_sha256": self.reference_sha256,
            "anchor_first_observed_at": self.independent_anchor_observed_at.isoformat(),
            "decision_at": self.decision_at.isoformat(),
            "source_count": self.source_count,
            "row_count": len(self.rows),
            "research_only": True,
            "certified_raw_event_count": 0,
            "rows": [{
                "source_id": row.source_id,
                "provider_id": row.provider_id,
                "evidence_id": row.evidence_id,
                "provider_record_id": row.provider_record_id,
                "provider_day": row.provider_day,
                "provider_acceptance_at": (row.provider_acceptance_at.isoformat()
                                           if row.provider_acceptance_at else None),
                "first_seen_at": row.first_seen_at.isoformat(),
                "usable_from": row.usable_from.isoformat(),
                "original_sha256": row.original_sha256,
                "receipt_sha256": row.receipt_sha256,
                "source_quality": row.source_quality,
                "published_at": None,
                "issuer_verified": False,
                "classification": STATUS,
            } for row in self.rows],
        }
        return (json.dumps(data, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode("utf-8")


def build_observed_official_batch(
    sources: VerifiedOfficialSources,
    independent_anchor_observed_at: datetime,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> ObservedOfficialBatch:
    """Only expose source captures already SHA/PIT checked by verified_reference.

    The trusted pin's first independent observation also gates historical use:
    an earlier raw receipt does not mean the independent pin existed then.
    """
    if not isinstance(sources, VerifiedOfficialSources) or not sources.research_only:
        raise SourceShareError("official verified research sources required")
    report_sha = _must_sha(sources.report_sha256, "report SHA")
    anchored = _when(
        independent_anchor_observed_at.isoformat()
        if isinstance(independent_anchor_observed_at, datetime) else None,
        "anchor observed_at",
    )
    moment = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if moment < anchored or moment > present or anchored > present:
        raise SourceShareError("research anchor unavailable at decision")
    rows = []
    seen_sources = set()
    seen_evidence = set()
    for capture in sources.captures:
        if capture.source_id in seen_sources:
            raise SourceShareError("duplicate research source")
        seen_sources.add(capture.source_id)
        if capture.release_time_verified or capture.historical_pit_certified:
            raise SourceShareError("research source falsely certified")
        if capture.first_seen_at > anchored:
            raise SourceShareError("source first receipt after independent reference anchor")
        for candidate in normalize_official_capture(capture, moment):
            identity = (capture.source_id, candidate.evidence_id)
            if identity in seen_evidence:
                raise SourceShareError("duplicate official evidence")
            seen_evidence.add(identity)
            rows.append(ObservedOfficialRow(
                source_id=candidate.source_id,
                provider_id=candidate.provider_id,
                evidence_id=candidate.evidence_id,
                provider_record_id=candidate.provider_record_id,
                provider_day=candidate.provider_day,
                provider_acceptance_at=candidate.provider_acceptance_at,
                first_seen_at=candidate.first_seen_at,
                usable_from=max(anchored, candidate.first_seen_at),
                original_sha256=candidate.source_sha256,
                receipt_sha256=candidate.source_receipt_sha256,
                source_quality=capture.quality,
            ))
    return ObservedOfficialBatch(
        schema_version=SCHEMA, reference_sha256=report_sha,
        independent_anchor_observed_at=anchored, decision_at=moment,
        rows=tuple(rows), source_count=len(seen_sources),
    )
