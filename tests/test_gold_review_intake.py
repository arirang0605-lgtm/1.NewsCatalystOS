"""Gold intake regression: synthetic labels never imply certified real-world scores."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from newscatalystos.gold_review_intake import (
    FrozenCasePrediction, HumanGoldReview, prediction_digest,
    prepare_gold_review_metrics,
)
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 13, 13, 0, tzinfo=timezone.utc)


def sha(s):
    return sha256(str(s).encode()).hexdigest()


def case(n=1, *, excluded=False, predicted_important=True):
    prediction = FrozenCasePrediction(
        sha(n), sha("source"+str(n)), NOW-timedelta(hours=2),
        NOW-timedelta(hours=1), NOW-timedelta(minutes=50),
        False, excluded, predicted_important, "0"*64,
    )
    return replace(prediction, prediction_sha256=prediction_digest(prediction))


def reviews(p, *, truth=False, important=True, second_truth=None):
    return [
        HumanGoldReview(p.case_sha256, p.source_sha256, "REVIEWER_A",
                        truth, important, sha("a"+p.case_sha256), NOW-timedelta(minutes=20)),
        HumanGoldReview(p.case_sha256, p.source_sha256, "REVIEWER_B",
                        truth if second_truth is None else second_truth,
                        important, sha("b"+p.case_sha256), NOW-timedelta(minutes=10)),
    ]


def run(predictions, labels, decision=NOW):
    return prepare_gold_review_metrics(predictions, labels, decision_at=decision, now=NOW)


def test_two_agreeing_reviewers_are_metrics_only():
    p=case()
    report=run([p],reviews(p))
    assert report.agreed_cases==1
    assert report.duplicate_evaluation is not None
    assert report.important_recall.measured_recall==1.0
    assert not report.release_gate_verified
    assert not report.sample_mathematically_eligible


def test_missing_and_disputed_reviews_never_count_as_negative():
    a,b=case(1),case(2)
    report=run([a,b],reviews(a,second_truth=True))
    assert report.agreed_cases==0
    assert report.duplicate_evaluation is None
    assert report.missing_case_ids==(b.case_sha256,)
    assert report.disputed_case_ids==(a.case_sha256,)


def test_prediction_digest_tampering_rejected():
    p=case()
    with pytest.raises(SourceShareError,match="frozen pin"):
        run([replace(p,predicted_excluded=True)],reviews(p))


def test_future_pin_and_review_rejected():
    p=case()
    with pytest.raises(SourceShareError,match="PIT pin"):
        future=replace(p,pin_first_observed_at=NOW+timedelta(seconds=1))
        run([replace(future,prediction_sha256=prediction_digest(future))],reviews(p))
    bad=replace(reviews(p)[0],reviewed_at=NOW+timedelta(seconds=1))
    with pytest.raises(SourceShareError,match="review not available"):
        run([p],[bad,reviews(p)[1]])


def test_duplicate_reviewer_and_evidence_rejected():
    p=case()
    labels=reviews(p)
    with pytest.raises(SourceShareError,match="duplicate reviewer"):
        run([p],labels+[labels[0]])
    with pytest.raises(SourceShareError,match="duplicate review evidence"):
        run([p],[labels[0],replace(labels[1],review_evidence_sha256=labels[0].review_evidence_sha256)])


def test_important_exclusion_counts_as_missed_event():
    p=case(excluded=True)
    report=run([p],reviews(p))
    assert report.important_recall.measured_recall==0.0
    assert report.duplicate_evaluation.important_missed_case_ids==(p.case_sha256,)


def test_wrong_source_review_and_duplicate_prediction_rejected():
    p=case()
    with pytest.raises(SourceShareError,match="source case"):
        run([p],[replace(reviews(p)[0],source_sha256=sha("other")),reviews(p)[1]])
    with pytest.raises(SourceShareError,match="duplicate predicted"):
        run([p,p],reviews(p))


def test_review_cannot_precede_frozen_prediction_pin():
    p=case()
    with pytest.raises(SourceShareError,match="review not available"):
        run([p],[replace(reviews(p)[0],reviewed_at=NOW-timedelta(hours=2)),reviews(p)[1]])


def test_500_synthetic_agreements_still_not_independent_certification():
    predictions=[case(i) for i in range(500)]
    # Include true duplicates so precision has a nonzero denominator.
    predictions=[replace(p,predicted_duplicate=True,prediction_sha256="0"*64) for p in predictions]
    predictions=[replace(p,prediction_sha256=prediction_digest(p)) for p in predictions]
    labels=[r for p in predictions for r in reviews(p,truth=True) ]
    report=run(predictions,labels)
    assert report.agreed_cases==500
    assert report.sample_mathematically_eligible
    assert not report.release_gate_verified
