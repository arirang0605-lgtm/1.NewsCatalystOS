"""2_6 labeled metrics must not turn synthetic high scores into certification."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256

import pytest

from newscatalystos.filter_evaluation import LabeledDecision, evaluate_labeled_decisions
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def row(i, duplicate, predicted, important=False, excluded=False):
    return LabeledDecision(
        case_sha256=sha256(str(i).encode()).hexdigest(),
        true_duplicate=duplicate, predicted_duplicate=predicted,
        important_event=important, predicted_excluded=excluded,
        first_available_at=NOW,
    )


def test_precision_recall_and_fully_shown_important_misses():
    rows=[
        row(1,True,True), row(2,True,False),
        row(3,False,True),row(4,False,False),
        row(5,False,False,important=True,excluded=True),
    ]
    result=evaluate_labeled_decisions(rows,NOW,now=NOW,review_sample_size=2)
    assert (result.true_positive,result.false_positive,
            result.false_negative,result.true_negative)==(1,1,1,2)
    assert result.precision==0.5
    assert result.recall==0.5
    assert len(result.important_missed_case_ids)==1
    assert len(result.excluded_case_sample_ids)==1
    assert not result.metric_target_reached
    assert not result.release_gate_verified


def test_perfect_synthetic_is_not_release_certification():
    sample=[row(i,True,True) for i in range(20)]
    report=evaluate_labeled_decisions(sample,NOW,now=NOW)
    assert report.precision==1.0
    assert report.recall==1.0
    assert report.metric_target_reached
    assert report.release_gate_verified is False
    assert "UNVERIFIED" in report.status


def test_no_duplicate_predicted_precision_is_undefined_not_pass():
    sample=[row(i,False,False) for i in range(5)]
    result=evaluate_labeled_decisions(sample,NOW,now=NOW)
    assert result.precision is None
    assert result.recall is None
    assert not result.metric_target_reached


def test_deterministic_audit_sampling():
    sample=[row(i,True,True,excluded=True) for i in range(50)]
    a=evaluate_labeled_decisions(sample,NOW,now=NOW,review_sample_size=7)
    b=evaluate_labeled_decisions(list(reversed(sample)),NOW,now=NOW,review_sample_size=7)
    assert len(a.excluded_case_sample_ids)==7
    assert a.excluded_case_sample_ids==b.excluded_case_sample_ids


def test_duplicate_gold_id_or_malformed_boolean_rejected():
    sample=[row(1,True,True)]
    with pytest.raises(SourceShareError,match="duplicate"):
        evaluate_labeled_decisions(sample*2,NOW,now=NOW)
    with pytest.raises(SourceShareError,match="boolean"):
        evaluate_labeled_decisions([replace(sample[0],important_event=1)],NOW,now=NOW)


def test_future_case_does_not_leak_into_metrics():
    sample=[replace(row(1,True,True),first_available_at=NOW+timedelta(seconds=1))]
    with pytest.raises(SourceShareError,match="future"):
        evaluate_labeled_decisions(sample,NOW,now=NOW)


@pytest.mark.parametrize("target,sample",[(0.0,2),(1.1,2),(.95,0),(.95,501)])
def test_invalid_evaluation_setup(target,sample):
    with pytest.raises(SourceShareError):
        evaluate_labeled_decisions([row(1,True,True)],NOW,now=NOW,
                                   required_precision=target,review_sample_size=sample)
