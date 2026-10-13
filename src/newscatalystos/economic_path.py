"""4_4 counterfactual economic effect hypotheses, without fictitious figures.

The assessment encodes a demand/supply/CAPEX/earnings/competition transmission
path, plus required contradictory evidence or a plainly labeled unknown.
A hypothesis is never a confirmed beneficiary or predicted security return.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re

from .source_share import SourceShareError, _must_sha, _when

PATHS = frozenset({"DEMAND", "SUPPLY", "CAPEX", "EARNINGS", "COMPETITION"})
DIRECTIONS = frozenset({"INCREASE", "DECREASE", "MIXED", "UNKNOWN"})
CLAIM_TYPES = frozenset({"OBSERVED_SOURCE_CLAIM", "ESTIMATE", "HYPOTHESIS"})
COUNTER_TYPES = frozenset({"CONTRADICTORY_EVIDENCE", "MISSING_INFORMATION"})
SCHEMA = "newscatalyst.analysis_event.v1"


@dataclass(frozen=True)
class ImpactHypothesis:
    path: str
    direction: str
    affected_product: str
    source_claim_sha256: str
    premise: str
    counter_type: str
    counter_argument: str
    claim_type: str = "HYPOTHESIS"


@dataclass(frozen=True)
class AnalysisEvent:
    schema_version: str
    event_sha256: str
    impact_hypotheses: tuple[ImpactHypothesis, ...]
    analyzed_at: datetime
    source_available_at: datetime
    economic_effect_confirmed: bool = False
    estimated_revenue_krw: None = None
    trade_recommendation: None = None

    def as_of(self, when: datetime, *, now: datetime | None = None) -> "AnalysisEvent":
        queried = _when(when.isoformat(), "decision_at")
        current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.analyzed_at <= queried <= current:
            raise SourceShareError("analysis did not exist at historical decision")
        return self


def build_impact_analysis(
    event_sha256: str, hypotheses: tuple[ImpactHypothesis, ...] | list[ImpactHypothesis],
    *, available_at: datetime, decision_at: datetime,
    now: datetime | None = None,
) -> AnalysisEvent:
    event = _must_sha(event_sha256, "source event")
    observed = _when(available_at.isoformat(), "source available at")
    analyzed = _when(decision_at.isoformat(), "decision at")
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not observed <= analyzed <= current:
        raise SourceShareError("future source cannot drive economic analysis")
    if not isinstance(hypotheses, (list,tuple)) or not 0 < len(hypotheses) <= 12:
        raise SourceShareError("bounded counterfactual hypotheses required")
    seen = set()
    for hypothesis in hypotheses:
        if not isinstance(hypothesis,ImpactHypothesis):
            raise SourceShareError("structured counterfactual required")
        if (hypothesis.path not in PATHS or hypothesis.direction not in DIRECTIONS
                or hypothesis.counter_type not in COUNTER_TYPES
                or hypothesis.claim_type not in CLAIM_TYPES):
            raise SourceShareError("unapproved economic effect category")
        if hypothesis.claim_type == "OBSERVED_SOURCE_CLAIM":
            # An economic effect is NOT directly observed merely because a
            # release quotes a contract value. The impact remains an estimate.
            raise SourceShareError("economic transmission cannot claim direct fact certification")
        _must_sha(hypothesis.source_claim_sha256, "hypothesis evidence SHA")
        if (not isinstance(hypothesis.affected_product,str) or
                not 0 < len(hypothesis.affected_product) <= 120 or
                not isinstance(hypothesis.premise,str) or
                not 0 < len(hypothesis.premise) <= 600 or
                not isinstance(hypothesis.counter_argument,str) or
                not 0 < len(hypothesis.counter_argument) <= 600):
            raise SourceShareError("missing economic path/counterexample evidence")
        signature=(hypothesis.path,hypothesis.affected_product,
                   hypothesis.source_claim_sha256)
        if signature in seen:
            raise SourceShareError("duplicate unqualified impact hypothesis")
        seen.add(signature)
    return AnalysisEvent(SCHEMA,event,tuple(hypotheses),analyzed,observed)
