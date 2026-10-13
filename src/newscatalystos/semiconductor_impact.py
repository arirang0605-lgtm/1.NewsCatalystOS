"""5_3 hypothesis-only transmission of semiconductor economic changes.

Price, capacity, tooling CAPEX, materials, HBM packaging and testing follow
different possible stages; never multiply coefficients into invented revenue.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .semiconductor_profile import SemiconductorProfile, validate_profile
from .source_share import SourceShareError, _must_sha, _when

DIRECTIONS=frozenset({"POSITIVE","NEGATIVE","MIXED","UNKNOWN"})
SCHEMA="newscatalyst.semiconductor_impact.v1"


@dataclass(frozen=True)
class SemiconductorTransmission:
    event_sha256: str
    trigger: str
    direction: str
    stages: tuple[str, ...]
    evidence_note: str
    source_available_at: datetime
    reviewed_at: datetime
    evidence_level: str = "IMPACT_HYPOTHESIS_NOT_VERIFIED"
    revenue_contribution_krw: None = None
    certified_beneficiary_count: int = 0

    def as_of(self, decision_at: datetime, *, now: datetime | None = None
              ) -> "SemiconductorTransmission":
        decision=_when(decision_at.isoformat(),"decision_at")
        current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
        if not self.reviewed_at<=decision<=current:
            raise SourceShareError("transmission not yet available")
        return self


def propagate_semiconductor_claim(
    profile: SemiconductorProfile, source_sha256: str, trigger: str,
    *,
    direction: str, evidence_note: str,
    source_available_at: datetime, reviewed_at: datetime,
    now: datetime | None = None,
) -> SemiconductorTransmission:
    validate_profile(profile)
    digest=_must_sha(source_sha256,"change source SHA")
    at=_when(reviewed_at.isoformat(),"reviewed at")
    present=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    source_seen=_when(source_available_at.isoformat(),"source available")
    if not source_seen<=at<=present:
        raise SourceShareError("future or backdated semiconductor impact evidence")
    if direction not in DIRECTIONS:
        raise SourceShareError("invalid effect direction")
    if not isinstance(evidence_note,str) or not 4<=len(evidence_note)<=500:
        raise SourceShareError("economic hypothesis requires explicit uncertainty context")
    path=profile.route_for(trigger)
    return SemiconductorTransmission(
        digest,trigger,direction,path.candidate_stages,evidence_note,
        source_seen,at,
    )
