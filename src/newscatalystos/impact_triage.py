"""3_5 rules-only preliminary importance, no fabricated revenue contribution.

A score ranks *review priority*, never expected stock returns, verified sales
impact, valuation or a buy recommendation. Unknown evidence stays unknown.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .source_share import SourceShareError, _when, _must_sha

SCALE={"SMALL":1,"MEDIUM":2,"LARGE":3,"UNKNOWN":None}
SCOPE={"SINGLE_FIRM":1,"INDUSTRY":2,"GLOBAL":3,"UNKNOWN":None}
REPEAT={"ONE_OFF":0,"RECURRING":2,"UNKNOWN":None}
NOVELTY={"NEW_FACT_CANDIDATE":2,"MATERIAL_REVISION":1,"ALREADY_KNOWN":0,"UNKNOWN":None}
EXPECT={"SURPRISE":2,"PRICED_IN":0,"UNKNOWN":None}


@dataclass(frozen=True)
class ImpactInputs:
    event_sha256: str
    available_at: datetime
    scale: str
    affected_scope: str
    repeatability: str
    novelty: str
    market_expectation: str


@dataclass(frozen=True)
class PreliminaryImportance:
    event_sha256: str
    numeric_score: int | None
    priority: str
    known_dimensions: tuple[str, ...]
    unknown_dimensions: tuple[str, ...]
    verified_economic_impact: bool
    estimated_revenue_krw: None
    decision_at: datetime

    def as_of(self, at: datetime, *, now: datetime | None = None) -> "PreliminaryImportance":
        moment=_when(at.isoformat(),"decision_at")
        current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
        if not self.decision_at<=moment<=current:
            raise SourceShareError("priority did not exist at past decision")
        return self


def triage_importance(
    inputs: ImpactInputs, decision_at: datetime, *,
    now: datetime | None = None,
) -> PreliminaryImportance:
    at=_when(decision_at.isoformat(),"decision_at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not isinstance(inputs,ImpactInputs) or at>current:
        raise SourceShareError("valid event dimensions/current decision required")
    ready=_when(inputs.available_at.isoformat(),"available_at")
    if ready>at:
        raise SourceShareError("future evidence unavailable for triage")
    event=_must_sha(inputs.event_sha256,"event SHA")
    choices={
        "scale":(inputs.scale,SCALE),
        "affected_scope":(inputs.affected_scope,SCOPE),
        "repeatability":(inputs.repeatability,REPEAT),
        "novelty":(inputs.novelty,NOVELTY),
        "market_expectation":(inputs.market_expectation,EXPECT),
    }
    known={}
    unknown=[]
    for key,(name,mapping) in choices.items():
        if name not in mapping:
            raise SourceShareError("unreviewed impact field/category")
        weight=mapping[name]
        if weight is None:
            unknown.append(key)
        else:
            known[key]=weight
    score=sum(known.values()) if not unknown else None
    priority=("INSUFFICIENT_EVIDENCE_REVIEW" if score is None
              else "HIGH_PRIORITY_REVIEW" if score>=8
              else "STANDARD_REVIEW")
    return PreliminaryImportance(
        event_sha256=event,numeric_score=score,priority=priority,
        known_dimensions=tuple(sorted(known)),unknown_dimensions=tuple(sorted(unknown)),
        verified_economic_impact=False,estimated_revenue_krw=None,decision_at=at,
    )
