"""2_6 labeled dedup evaluation with honest denominators and miss reporting.

This computes metrics on supplied labels; it does not authenticate who labeled
them or claim the required 95% target has been met on real held-out news.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.filter_evaluation.v1"


@dataclass(frozen=True)
class LabeledDecision:
    case_sha256: str
    true_duplicate: bool
    predicted_duplicate: bool
    important_event: bool
    predicted_excluded: bool
    first_available_at: datetime


@dataclass(frozen=True)
class FilterEvaluation:
    evaluated_at: datetime
    size: int
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    precision: float | None
    recall: float | None
    important_missed_case_ids: tuple[str, ...]
    excluded_case_sample_ids: tuple[str, ...]
    metric_target_reached: bool
    release_gate_verified: bool
    status: str = "METRICS_ONLY_REAL_LABEL_PROVENANCE_UNVERIFIED"
    schema_version: str = SCHEMA


def evaluate_labeled_decisions(
    cases: tuple[LabeledDecision, ...] | list[LabeledDecision],
    decision_at: datetime, *, now: datetime | None = None,
    required_precision: float = .95, review_sample_size: int = 20,
) -> FilterEvaluation:
    decision = _when(decision_at.isoformat(), "decision_at")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if decision > present or not 0 < len(cases) <= 10000:
        raise SourceShareError("empty/future or unbounded evaluation")
    if not (0 < required_precision <= 1.0) or type(review_sample_size) is not int or not 0 < review_sample_size <= 500:
        raise SourceShareError("invalid evaluation requirements")
    seen = set()
    tp=fp=fn=tn=0
    missed=[]
    excluded=[]
    for row in cases:
        if not isinstance(row, LabeledDecision):
            raise SourceShareError("typed labels required")
        _must_sha(row.case_sha256,"label case ID")
        if row.case_sha256 in seen:
            raise SourceShareError("duplicate evaluation case")
        seen.add(row.case_sha256)
        if any(type(flag) is not bool for flag in (
            row.true_duplicate, row.predicted_duplicate,
            row.important_event, row.predicted_excluded,
        )):
            raise SourceShareError("boolean ground truth/predictions required")
        available=_when(row.first_available_at.isoformat(),"case available at")
        if available > decision:
            raise SourceShareError("future item used in evaluation")
        if row.true_duplicate and row.predicted_duplicate:
            tp+=1
        elif not row.true_duplicate and row.predicted_duplicate:
            fp+=1
        elif row.true_duplicate and not row.predicted_duplicate:
            fn+=1
        else:
            tn+=1
        if row.important_event and row.predicted_excluded:
            missed.append(row.case_sha256)
        if row.predicted_excluded:
            excluded.append(row.case_sha256)
    precision=(tp/(tp+fp)) if tp+fp else None
    recall=(tp/(tp+fn)) if tp+fn else None
    # Deterministic audit sample, not convenience selection by model score.
    audited=sorted(excluded,key=lambda x:sha256(x.encode()).hexdigest())[:review_sample_size]
    target=(precision is not None and precision >= required_precision and not missed)
    return FilterEvaluation(
        evaluated_at=decision,size=len(cases),
        true_positive=tp,false_positive=fp,false_negative=fn,true_negative=tn,
        precision=precision,recall=recall,
        important_missed_case_ids=tuple(sorted(missed)),
        excluded_case_sample_ids=tuple(audited),
        metric_target_reached=target,
        release_gate_verified=False,
    )
