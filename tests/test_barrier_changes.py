"""3_3 obstacle removal requires a prior PIT obstacle and a changed claim."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.barrier_changes import detect_barrier_relief
from newscatalystos.prior_fact_state import FactInput, record_prior_fact, prior_state_as_of
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def claim(value="b"*64,event="a"*64,at=NOW):
    return FactInput("company-reviewed-1","export_limit",event,value,at,
                     evidence_status="OFFICIAL_CHANNEL_OBSERVED")


def baseline(path,at):
    return prior_state_as_of(path,"company-reviewed-1",at,now=at)


def test_recorded_obstacle_and_new_claim_of_approval(tmp_path):
    path=tmp_path/"p"/"facts.sqlite3"
    record_prior_fact(path,claim(),now=NOW)
    later=NOW+timedelta(seconds=1)
    result=detect_barrier_relief(
        baseline(path,later),claim(value="c"*64,event="d"*64,at=later),
        "TRADE_RESTRICTION",later,now=later,
    )
    assert result.status=="BARRIER_REMOVED_CANDIDATE_NOT_FACT_CERTIFIED"
    assert result.prior_barrier_value_sha256=="b"*64
    assert result.relief_claim_value_sha256=="c"*64
    assert not result.fact_verified
    with pytest.raises(SourceShareError,match="unavailable"):
        result.as_of(NOW,now=later)


def test_no_known_obstacle_cannot_claim_it_was_removed(tmp_path):
    path=tmp_path/"p"/"facts.sqlite3"
    result=detect_barrier_relief(
        baseline(path,NOW),claim(),"REGULATORY_HOLD",NOW,now=NOW)
    assert result.status=="NO_PRIOR_OBSTACLE_RECORDED"


def test_same_claim_value_is_not_material_change(tmp_path):
    path=tmp_path/"p"/"facts.sqlite3"
    record_prior_fact(path,claim(),now=NOW)
    result=detect_barrier_relief(
        baseline(path,NOW),claim(),"REGULATORY_HOLD",NOW,now=NOW)
    assert result.status=="NO_ECONOMIC_BARRIER_CHANGE"


def test_refuted_old_obstacle_is_not_automatically_removed(tmp_path):
    path=tmp_path/"p"/"facts.sqlite3"
    old=replace(claim(),evidence_status="FACT_REFUTED")
    record_prior_fact(path,old,now=NOW)
    later=NOW+timedelta(seconds=1)
    result=detect_barrier_relief(
        baseline(path,later),claim(value="d"*64,at=later),
        "REGULATORY_HOLD",later,now=later)
    assert result.status=="PREVIOUS_OBSTACLE_REFUTED_REVIEW"


def test_future_relief_or_stale_baseline_cannot_leak(tmp_path):
    path=tmp_path/"p"/"facts.sqlite3"
    with pytest.raises(SourceShareError,match="future relief"):
        detect_barrier_relief(baseline(path,NOW),
                              claim(at=NOW+timedelta(seconds=1)),
                              "PERMIT_DELAY",NOW,now=NOW)
    with pytest.raises(SourceShareError,match="stale"):
        detect_barrier_relief(baseline(path,NOW),claim(),"PERMIT_DELAY",
                              NOW+timedelta(seconds=1),
                              now=NOW+timedelta(seconds=1))


def test_wrong_subject_or_category_fails_closed(tmp_path):
    path=tmp_path/"p"/"facts.sqlite3"
    with pytest.raises(SourceShareError,match="relief subject"):
        detect_barrier_relief(baseline(path,NOW),
                              replace(claim(),reviewed_subject_id="other-company"),
                              "PERMIT_DELAY",NOW,now=NOW)
    with pytest.raises(SourceShareError,match="barrier type"):
        detect_barrier_relief(baseline(path,NOW),claim(),"HEADLINE_CHANGED",NOW,now=NOW)
