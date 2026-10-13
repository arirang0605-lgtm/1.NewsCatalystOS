"""3_3 factual barrier-removal *candidate*, never inferred from headlines.

A prior observed obstacle must have been recorded and available at decision;
a new claim of relief or approval can then be compared without retroactively
erasing the obstacle or automatically proving economic benefit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .prior_fact_state import FactInput, PriorState
from .source_share import SourceShareError, _when, _must_sha

TYPES = frozenset({
    "REGULATORY_HOLD", "SUPPLY_BOTTLENECK", "PERMIT_DELAY",
    "TRADE_RESTRICTION", "PRODUCTION_STOP", "COURT_INJUNCTION",
})


@dataclass(frozen=True)
class BarrierAssessment:
    reviewed_subject_id: str
    barrier_key: str
    barrier_kind: str
    prior_barrier_value_sha256: str | None
    relief_claim_value_sha256: str
    source_event_sha256: str
    status: str
    fact_verified: bool
    decision_at: datetime
    available_at: datetime

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> "BarrierAssessment":
        requested=_when(decision_at.isoformat(),"decision_at")
        present=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
        if not self.decision_at<=requested<=present:
            raise SourceShareError("barrier claim unavailable at decision")
        return self


def detect_barrier_relief(
    prior: PriorState, relief: FactInput, kind: str,
    decision_at: datetime, *, now: datetime | None = None,
) -> BarrierAssessment:
    decision=_when(decision_at.isoformat(),"decision_at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if kind not in TYPES or decision>current:
        raise SourceShareError("unknown barrier type or future decision")
    if not isinstance(prior,PriorState) or not isinstance(relief,FactInput):
        raise SourceShareError("prior state and typed relief claim required")
    if prior.reviewed_subject_id!=relief.reviewed_subject_id:
        raise SourceShareError("relief subject does not match prior obstacle")
    if _when(prior.decision_at.isoformat(),"baseline decision")!=decision:
        raise SourceShareError("stale PIT baseline for barrier assessment")
    available=_when(relief.available_at.isoformat(),"relief observed")
    if available>decision:
        raise SourceShareError("future relief not yet available")
    source=_must_sha(relief.source_event_sha256,"source SHA")
    proposed=_must_sha(relief.value_sha256,"relief value SHA")
    history=[
        x for x in prior.facts
        if x.fact_key==relief.fact_key
    ]
    if any(x.recorded_at>decision or x.available_at>decision or
           x.reviewed_subject_id!=prior.reviewed_subject_id for x in prior.facts):
        raise SourceShareError("invalid prior obstacle PIT")
    latest=history[-1] if history else None
    if latest is None:
        status="NO_PRIOR_OBSTACLE_RECORDED"
    elif latest.value_sha256==proposed:
        status="NO_ECONOMIC_BARRIER_CHANGE"
    elif latest.evidence_status=="FACT_REFUTED":
        status="PREVIOUS_OBSTACLE_REFUTED_REVIEW"
    else:
        status="BARRIER_REMOVED_CANDIDATE_NOT_FACT_CERTIFIED"
    return BarrierAssessment(
        relief.reviewed_subject_id,relief.fact_key,kind,
        latest.value_sha256 if latest else None,proposed,source,
        status,False,decision,decision,
    )
