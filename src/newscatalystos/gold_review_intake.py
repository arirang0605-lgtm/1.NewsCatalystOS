"""2_6/3_6: review-label intake and PIT-safe, *uncertified* metric preview.

This module does not certify that reviewers are independent, predictions were
frozen in external storage, or articles were licensed. No external calls,
content bodies, EraLeader writes, or automatic release-gate promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from .detection_history import DetectionRecall, evaluate_important_detection_recall
from .filter_evaluation import FilterEvaluation, LabeledDecision, evaluate_labeled_decisions
from .release_readiness import REQUIRED_GOLD_CASES
from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.gold_review_intake.v1"
REVIEWER_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]{2,31}\Z")
MAX_CASES = 10_000


def _time(value: datetime, label: str) -> datetime:
    return _when(value.isoformat() if isinstance(value, datetime) else None, label)


def _canonical(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


@dataclass(frozen=True)
class FrozenCasePrediction:
    case_sha256: str
    source_sha256: str
    source_available_at: datetime
    predicted_at: datetime
    pin_first_observed_at: datetime
    predicted_duplicate: bool
    predicted_excluded: bool
    predicted_important: bool
    prediction_sha256: str


def prediction_digest(prediction: FrozenCasePrediction) -> str:
    """Hash declared prediction metadata, NOT independent time certification."""
    if not isinstance(prediction, FrozenCasePrediction):
        raise SourceShareError("typed frozen prediction required")
    return sha256(_canonical({
        "case_sha256": _must_sha(prediction.case_sha256, "case ID"),
        "source_sha256": _must_sha(prediction.source_sha256, "source ID"),
        "source_available_at": _time(prediction.source_available_at, "source available").isoformat(),
        "predicted_at": _time(prediction.predicted_at, "predicted at").isoformat(),
        "pin_first_observed_at": _time(prediction.pin_first_observed_at, "pin observed").isoformat(),
        "predicted_duplicate": prediction.predicted_duplicate,
        "predicted_excluded": prediction.predicted_excluded,
        "predicted_important": prediction.predicted_important,
    })).hexdigest()


@dataclass(frozen=True)
class HumanGoldReview:
    case_sha256: str
    source_sha256: str
    reviewer_code: str
    true_duplicate: bool
    important_event: bool
    review_evidence_sha256: str
    reviewed_at: datetime


@dataclass(frozen=True)
class GoldIntakeReport:
    schema_version: str
    evaluated_at: datetime
    submitted_cases: int
    agreed_cases: int
    missing_case_ids: tuple[str, ...]
    disputed_case_ids: tuple[str, ...]
    manifest_sha256: str
    duplicate_evaluation: FilterEvaluation | None
    important_recall: DetectionRecall | None
    sample_mathematically_eligible: bool
    release_gate_verified: bool = False
    status: str = "REVIEW_METRICS_ONLY_INDEPENDENT_PROVENANCE_UNVERIFIED"


def prepare_gold_review_metrics(
    predictions: tuple[FrozenCasePrediction, ...] | list[FrozenCasePrediction],
    reviews: tuple[HumanGoldReview, ...] | list[HumanGoldReview],
    *, decision_at: datetime, now: datetime | None = None,
) -> GoldIntakeReport:
    """Require two distinct agreeing reviewer codes per case; fail closed on PIT.

    Incomplete or disputed cases are never silently treated as negatives, and
    even 100% calculated metrics do not prove independence, labeling quality,
    source entitlement, or final V1.0 readiness.
    """
    decision = _time(decision_at, "decision at")
    present = _time(now or datetime.now(timezone.utc), "now")
    if decision > present:
        raise SourceShareError("future gold evaluation decision")
    if (not isinstance(predictions, (tuple, list)) or
            not 0 < len(predictions) <= MAX_CASES or
            not isinstance(reviews, (tuple, list)) or
            len(reviews) > 4 * MAX_CASES):
        raise SourceShareError("missing/unbounded gold evaluation inputs")
    cases: dict[str, FrozenCasePrediction] = {}
    for row in predictions:
        digest = prediction_digest(row)
        _must_sha(row.prediction_sha256, "frozen prediction SHA")
        if digest != row.prediction_sha256:
            raise SourceShareError("prediction metadata differs from frozen pin")
        if row.case_sha256 in cases:
            raise SourceShareError("duplicate predicted case ID")
        if any(type(x) is not bool for x in (
            row.predicted_duplicate, row.predicted_excluded, row.predicted_important
        )):
            raise SourceShareError("invalid frozen prediction flags")
        source = _time(row.source_available_at, "source available")
        predicted = _time(row.predicted_at, "predicted at")
        pinned = _time(row.pin_first_observed_at, "pin observed")
        if not source <= predicted <= pinned <= decision:
            raise SourceShareError("prediction/PIT pin unavailable at decision")
        cases[row.case_sha256] = row
    grouped: dict[str, list[HumanGoldReview]] = {case: [] for case in cases}
    reviewers: set[tuple[str, str]] = set()
    independent_review_shas: set[tuple[str, str]] = set()
    for label in reviews:
        if not isinstance(label, HumanGoldReview):
            raise SourceShareError("typed human review required")
        _must_sha(label.case_sha256, "review case ID")
        _must_sha(label.source_sha256, "review source ID")
        _must_sha(label.review_evidence_sha256, "review evidence SHA")
        prediction = cases.get(label.case_sha256)
        if prediction is None or label.source_sha256 != prediction.source_sha256:
            raise SourceShareError("review not bound to a frozen source case")
        if not isinstance(label.reviewer_code, str) or not REVIEWER_PATTERN.fullmatch(label.reviewer_code):
            raise SourceShareError("opaque reviewer code required")
        if any(type(x) is not bool for x in (label.true_duplicate, label.important_event)):
            raise SourceShareError("invalid human review label flags")
        reviewed = _time(label.reviewed_at, "reviewed at")
        if not prediction.pin_first_observed_at <= reviewed <= decision:
            raise SourceShareError("review not available after frozen prediction at decision")
        identity = (label.case_sha256, label.reviewer_code)
        if identity in reviewers:
            raise SourceShareError("duplicate reviewer for one case")
        evidence_identity = (label.case_sha256, label.review_evidence_sha256)
        if evidence_identity in independent_review_shas:
            raise SourceShareError("duplicate review evidence per case")
        reviewers.add(identity)
        independent_review_shas.add(evidence_identity)
        grouped[label.case_sha256].append(label)
    complete: list[LabeledDecision] = []
    detected: list[str] = []
    important: list[str] = []
    missing: list[str] = []
    disputed: list[str] = []
    for case, predicted in sorted(cases.items()):
        labels = grouped[case]
        if len(labels) < 2:
            missing.append(case)
            continue
        truth = {(x.true_duplicate, x.important_event) for x in labels}
        if len(truth) != 1:
            disputed.append(case)
            continue
        duplicate, material = next(iter(truth))
        complete.append(LabeledDecision(
            case_sha256=case, true_duplicate=duplicate,
            predicted_duplicate=predicted.predicted_duplicate,
            important_event=material, predicted_excluded=predicted.predicted_excluded,
            first_available_at=predicted.source_available_at,
        ))
        if material:
            important.append(case)
            if predicted.predicted_important and not predicted.predicted_excluded:
                detected.append(case)
    duplicate_report = (evaluate_labeled_decisions(complete, decision, now=present)
                        if complete else None)
    recall_report = (evaluate_important_detection_recall(important, detected)
                     if complete else None)
    manifest = {
        "schema": SCHEMA, "decision_at": decision.isoformat(),
        "cases": [
            {"case_sha256": case,
             "prediction_sha256": prediction.prediction_sha256,
             "review_evidence": [
                 [x.reviewer_code, x.review_evidence_sha256,
                  x.true_duplicate, x.important_event, _time(x.reviewed_at, "reviewed at").isoformat()]
                 for x in sorted(grouped[case], key=lambda x: x.reviewer_code)
             ]}
            for case, prediction in sorted(cases.items())
        ],
    }
    eligible = (
        len(complete) >= REQUIRED_GOLD_CASES and not missing and not disputed and
        duplicate_report is not None and duplicate_report.metric_target_reached and
        recall_report is not None and recall_report.target_met_on_supplied_labels
    )
    return GoldIntakeReport(
        schema_version=SCHEMA, evaluated_at=decision, submitted_cases=len(cases),
        agreed_cases=len(complete), missing_case_ids=tuple(missing),
        disputed_case_ids=tuple(disputed), manifest_sha256=sha256(_canonical(manifest)).hexdigest(),
        duplicate_evaluation=duplicate_report, important_recall=recall_report,
        sample_mathematically_eligible=bool(eligible),
    )
