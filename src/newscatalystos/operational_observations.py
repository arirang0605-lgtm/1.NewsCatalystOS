"""PIT-safe observation-only bridge for published official snapshots.

A verified local observation is usable for new analysis *after* this consumer
has checked the complete private publication. It is NOT a claim about when
the issuer made the document public. Certified RawEvent remains separate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .published_observations import PublishedResearchObservations, read_published_observations
from .source_share import SourceShareError, _when

SCHEMA = "newscatalyst.operational_observation.v1"
DISCLOSURE = frozenset({"sec-submissions", "dart-disclosures"})
STATUS = "VERIFIED_LOCAL_OBSERVATION_RELEASE_UNKNOWN"


@dataclass(frozen=True)
class OperationalObservation:
    """Official record metadata observed locally, never independently released."""
    schema_version: str
    source_id: str
    provider_id: str
    evidence_id: str
    source_document_id: str
    first_seen_at: datetime
    available_at: datetime
    verified_at: datetime
    original_sha256: str
    receipt_sha256: str
    source_quality: str
    data_kind: str
    published_at: None = None
    issuer_verified: bool = False
    release_certified: bool = False
    status: str = STATUS

    def to_raw_event(self) -> None:
        raise SourceShareError("observed metadata is not independently certified RawEvent")


@dataclass(frozen=True)
class OperationalObservationSet:
    """PIT-only operational observations; past retrieval is never backfilled."""
    verified_at: datetime
    source_count: int
    coverage_verified: bool
    observations: tuple[OperationalObservation, ...]
    status: str = STATUS

    def as_of(self, decision_at: datetime, *, now: datetime | None = None
              ) -> tuple[OperationalObservation, ...]:
        decision = _when(
            decision_at.isoformat() if isinstance(decision_at, datetime) else None,
            "decision_at",
        )
        current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if decision < self.verified_at or decision > current:
            raise SourceShareError("operational observation unavailable at decision")
        return tuple(row for row in self.observations if row.available_at <= decision)


def project_operational_observations(
    published: PublishedResearchObservations, decision_at: datetime, *,
    now: datetime | None = None,
) -> OperationalObservationSet:
    """Project previously validated v2 private records without reusing old PIT."""
    decision = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    verified_at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if (not isinstance(published, PublishedResearchObservations)
            or published.research_only is not True
            or published.coverage_verified is not True):
        raise SourceShareError("complete v2 source coverage is required")
    if decision < verified_at:
        raise SourceShareError("cannot backdate a newly validated official observation")
    if decision < published.local_published_at or decision < published.batch_decision_at:
        raise SourceShareError("observation did not exist at decision")
    if decision > verified_at:
        raise SourceShareError("future decision")
    # Only v2 source coverage permits safe classification (including zero-row
    # SEC facts). A single source may have PARTIAL scope and is never promoted
    # to a verified full-day history.
    source_quality = {s.source_id: s.source_quality for s in published.source_coverage}
    if len(source_quality) != published.source_count:
        raise SourceShareError("source coverage incomplete")
    result = []
    seen = set()
    for row in published.rows:
        if row.source_id not in source_quality or row.source_quality != source_quality[row.source_id]:
            raise SourceShareError("observation differs from verified source coverage")
        if row.published_at is not None or row.issuer_verified:
            raise SourceShareError("unverified public release masquerading as certified")
        identifier = (row.source_id, row.evidence_id)
        if identifier in seen:
            raise SourceShareError("duplicate official observation")
        seen.add(identifier)
        available = max(row.first_seen_at, row.usable_from,
                        published.local_published_at, verified_at)
        if available > decision:
            raise SourceShareError("observation was not available at decision")
        result.append(OperationalObservation(
            schema_version=SCHEMA, source_id=row.source_id,
            provider_id=row.provider_id, evidence_id=row.evidence_id,
            source_document_id=row.provider_record_id,
            first_seen_at=row.first_seen_at, available_at=available,
            verified_at=verified_at, original_sha256=row.original_sha256,
            receipt_sha256=row.receipt_sha256,
            source_quality=row.source_quality,
            data_kind=("DISCLOSURE_OBSERVED" if row.source_id in DISCLOSURE
                       else "MARKET_CONTEXT_NOT_NEWS"),
        ))
    return OperationalObservationSet(
        verified_at=verified_at, source_count=published.source_count,
        coverage_verified=True, observations=tuple(result),
    )


def load_operational_observations(
    publication: Path, root: Path, expected_payload_sha256: str,
    *, now: datetime | None = None,
) -> OperationalObservationSet:
    """One-shot verification. The caller-provided SHA is NOT self-certified."""
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    published = read_published_observations(
        publication, root, expected_payload_sha256, instant, now=instant
    )
    return project_operational_observations(published, instant, now=instant)
