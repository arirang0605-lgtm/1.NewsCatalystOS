"""3_2 compare a newly observed economic claim with PIT-consistent prior state.

A newly written headline is not automatically a NEW economic fact. The
subject, claim category and source must be explicitly supported elsewhere;
this offline comparator reports novelty *candidates*, not factual truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .prior_fact_state import FactInput, PriorState
from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.novelty_detection.v1"
CATEGORIES = frozenset({
    "NEW_CONTRACT", "NEW_INVESTMENT", "COMMERCIALIZATION", "PRODUCT_LAUNCH",
    "REGULATORY_APPROVAL", "NEW_CUSTOMER", "NEW_FACILITY",
    "CONTRACT_TERMINATION", "CONTRACT_REDUCTION", "CONTRACT_DELAY",  # reported reversals, unverified
})


@dataclass(frozen=True)
class EconomicChange:
    schema_version: str
    reviewed_subject_id: str
    fact_key: str
    category: str
    source_event_sha256: str
    proposed_value_sha256: str
    prior_value_sha256s: tuple[str, ...]
    novelty: str
    evidence_level: str
    fact_verified: bool
    decision_at: datetime
    available_at: datetime

    def as_of(self, decision_at: datetime, *, now: datetime | None = None
              ) -> "EconomicChange":
        decision = _when(decision_at.isoformat(), "decision_at")
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.decision_at <= decision <= present:
            raise SourceShareError("new-fact detection not known at decision")
        return self


def detect_new_economic_claim(
    prior: PriorState, candidate: FactInput, category: str,
    decision_at: datetime, *, now: datetime | None = None,
) -> EconomicChange:
    decision = _when(decision_at.isoformat(), "decision_at")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if category not in CATEGORIES or decision > present:
        raise SourceShareError("invalid new-fact category or future decision")
    if not isinstance(prior, PriorState) or not isinstance(candidate, FactInput):
        raise SourceShareError("PIT prior state and structured economic claim required")
    if candidate.reviewed_subject_id != prior.reviewed_subject_id:
        raise SourceShareError("claim subject differs from PIT baseline")
    if _when(prior.decision_at.isoformat(), "baseline decision") != decision:
        raise SourceShareError("stale or future prior baseline cannot classify novelty")
    observed_at = _when(candidate.available_at.isoformat(), "claim available")
    if observed_at > decision:
        raise SourceShareError("future economic claim is unavailable")
    event_sha = _must_sha(candidate.source_event_sha256, "source SHA")
    proposed_sha = _must_sha(candidate.value_sha256, "proposed value SHA")
    history = [
        x for x in prior.facts if x.fact_key == candidate.fact_key
    ]
    if any(
        x.reviewed_subject_id != prior.reviewed_subject_id
        or x.recorded_at > decision or x.available_at > decision
        for x in prior.facts
    ):
        raise SourceShareError("future or wrong-subject historical facts")
    prior_values = tuple(sorted(set(x.value_sha256 for x in history)))
    if not history:
        novelty = "NEW_FACT_CANDIDATE_NEEDS_EVIDENCE"
    elif any(x.value_sha256 == proposed_sha for x in history):
        novelty = "EXISTING_ECONOMIC_CLAIM"
    elif history[-1].evidence_status == "FACT_REFUTED":
        novelty = "REFUTED_CLAIM_REOPENED_REVIEW"
    else:
        novelty = "CHANGED_ECONOMIC_CLAIM_REVIEW"
    return EconomicChange(
        schema_version=SCHEMA, reviewed_subject_id=prior.reviewed_subject_id,
        fact_key=candidate.fact_key, category=category,
        source_event_sha256=event_sha, proposed_value_sha256=proposed_sha,
        prior_value_sha256s=prior_values,
        novelty=novelty, evidence_level=candidate.evidence_status,
        fact_verified=False, decision_at=decision,
        available_at=decision,
    )
