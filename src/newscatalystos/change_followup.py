"""3_4 previously observed deal/forecast evolution, without inferred truth.

Explicit typed milestone/revision claims are compared to an as-of prior
version; the original stays immutable and unverified source claims never
automatically become confirmed realized revenue.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .prior_fact_state import FactInput, PriorState
from .source_share import SourceShareError, _when, _must_sha

KINDS={
    "ORDER_FULFILLED":"STRENGTHENED_CANDIDATE",
    "CAPACITY_EXPANDED":"STRENGTHENED_CANDIDATE",
    "DATE_DELAYED":"WEAKENED_CANDIDATE",
    "CONTRACT_REDUCED":"WEAKENED_CANDIDATE",
    "BUSINESS_CANCELLED":"INVALIDATED_CANDIDATE",
    "SOURCE_CORRECTED":"CORRECTION_PENDING_VERIFICATION",
}

@dataclass(frozen=True)
class FollowupChange:
    reviewed_subject_id: str
    fact_key: str
    source_event_sha256: str
    previous_fact_sha256: str | None
    previous_value_sha256: str | None
    new_value_sha256: str
    change_kind: str
    status: str
    available_at: datetime
    decision_at: datetime
    is_realization_confirmed: bool = False

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> "FollowupChange":
        at=_when(decision_at.isoformat(),"decision_at")
        current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
        if not self.decision_at<=at<=current:
            raise SourceShareError("followup result not yet available")
        return self


def assess_followup(
    prior: PriorState, claim: FactInput, kind: str, decision_at: datetime,
    *, now: datetime | None = None,
) -> FollowupChange:
    decision=_when(decision_at.isoformat(),"decision_at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if kind not in KINDS or decision>current:
        raise SourceShareError("unsupported followup kind or future decision")
    if not isinstance(prior,PriorState) or not isinstance(claim,FactInput):
        raise SourceShareError("typed prior and new claim required")
    if prior.reviewed_subject_id!=claim.reviewed_subject_id:
        raise SourceShareError("followup subject does not match baseline")
    if _when(prior.decision_at.isoformat(),"prior decision")!=decision:
        raise SourceShareError("stale PIT baseline cannot classify followup")
    if _when(claim.available_at.isoformat(),"claim available")>decision:
        raise SourceShareError("future followup claim")
    source=_must_sha(claim.source_event_sha256,"followup source")
    value=_must_sha(claim.value_sha256,"followup value")
    history=[x for x in prior.facts if x.fact_key==claim.fact_key]
    if any(x.recorded_at>decision or x.available_at>decision
           or x.reviewed_subject_id!=prior.reviewed_subject_id for x in prior.facts):
        raise SourceShareError("unsafe future prior version")
    latest=history[-1] if history else None
    if latest is None:
        status="NO_PRIOR_EVENT_HOLD"
    elif latest.value_sha256==value:
        status="NO_NEW_VERIFIED_CHANGE"
    elif latest.evidence_status=="FACT_REFUTED":
        status="REFUTED_OLD_CLAIM_HOLD"
    else:
        status=KINDS[kind]
    return FollowupChange(
        reviewed_subject_id=claim.reviewed_subject_id,
        fact_key=claim.fact_key, source_event_sha256=source,
        previous_fact_sha256=latest.fact_sha256 if latest else None,
        previous_value_sha256=latest.value_sha256 if latest else None,
        new_value_sha256=value,change_kind=kind,status=status,
        available_at=decision,decision_at=decision,
    )
