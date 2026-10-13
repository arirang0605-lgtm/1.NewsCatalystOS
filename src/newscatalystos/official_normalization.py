"""Conservative official-record metadata, never an automatically promoted RawEvent.

Source release time, SEC acceptance, DART filing day and local first receipt
are distinct observations. An EraLeader research receipt cannot certify public
dissemination or issuer identity. No writes or provider API calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .era_capture_share import OfficialCapture
from .source_share import SourceShareError, _when

SCHEMA = "newscatalyst.official_candidate.v1"
BLOCKED = "RELEASE_UNVERIFIED_RESEARCH_ONLY"


@dataclass(frozen=True)
class OfficialEvidenceCandidate:
    schema_version: str
    evidence_id: str
    source_id: str
    provider_id: str
    provider_record_id: str
    provider_day: str | None
    provider_acceptance_at: datetime | None
    first_seen_at: datetime
    verified_published_at: None
    source_sha256: str
    source_receipt_sha256: str
    classification: str = BLOCKED

    def to_raw_event(self) -> None:
        """Fail closed until a separate validated release-proof adapter exists."""
        raise SourceShareError(
            "RawEvent promotion blocked: verified published_at / issuer proof unavailable")


def normalize_official_capture(
    capture: OfficialCapture, decision_at: datetime
) -> tuple[OfficialEvidenceCandidate, ...]:
    """Metadata candidates only; no substitute for verified public release."""
    decision = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    if capture.first_seen_at > decision:
        raise SourceShareError("official capture unavailable at decision")
    if capture.release_time_verified or capture.completeness_certified or capture.historical_pit_certified:
        raise SourceShareError("research capture has unsupported certification")
    candidates = []
    for record in capture.records:
        if record.available_at != capture.first_seen_at or record.available_at > decision:
            raise SourceShareError("official record violates first-receipt PIT")
        if record.release_at is not None or record.issuer_attested:
            raise SourceShareError("unverified research source cannot assert public release/issuer")
        if (record.provider_acceptance_at is not None and
                record.provider_acceptance_at > record.available_at):
            raise SourceShareError("provider acceptance after first receipt")
        if capture.provider_id != "SEC" and record.provider_acceptance_at is not None:
            raise SourceShareError("unexpected non-SEC acceptance timestamp")
        candidates.append(OfficialEvidenceCandidate(
            schema_version=SCHEMA,
            evidence_id=record.record_id,
            source_id=capture.source_id,
            provider_id=capture.provider_id,
            provider_record_id=record.provider_record_id,
            provider_day=record.provider_day,
            provider_acceptance_at=record.provider_acceptance_at,
            first_seen_at=record.available_at,
            verified_published_at=None,
            source_sha256=capture.raw_sha256,
            source_receipt_sha256=capture.first_receipt_sha256,
        ))
    return tuple(candidates)
