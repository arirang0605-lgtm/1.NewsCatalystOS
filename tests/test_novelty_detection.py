"""3_2 economic newness requires a PIT baseline, not a new news headline."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.novelty_detection import detect_new_economic_claim
from newscatalystos.prior_fact_state import FactInput, PriorState, record_prior_fact, prior_state_as_of
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def candidate(value="b"*64, event="a"*64, available=NOW):
    return FactInput(reviewed_subject_id="company-reviewed-1",fact_key="new_hbm_contract",
                     source_event_sha256=event,value_sha256=value,available_at=available)


def baseline(tmp_path, moment=NOW):
    return prior_state_as_of(tmp_path/"private"/"facts.sqlite3",
                             "company-reviewed-1",moment,now=moment)


def test_no_prior_economic_claim_is_new_candidate_not_certified_truth(tmp_path):
    past=baseline(tmp_path)
    outcome=detect_new_economic_claim(
        past,candidate(),"NEW_CONTRACT",NOW,now=NOW
    )
    assert outcome.novelty=="NEW_FACT_CANDIDATE_NEEDS_EVIDENCE"
    assert outcome.fact_verified is False
    assert outcome.prior_value_sha256s==()


def test_repeated_headline_facts_not_misclassified_as_new(tmp_path):
    path=tmp_path/"private"/"facts.sqlite3"
    record_prior_fact(path,candidate(),now=NOW)
    later=NOW+timedelta(seconds=1)
    prior=prior_state_as_of(path,"company-reviewed-1",later,now=later)
    result=detect_new_economic_claim(prior,candidate(),"NEW_CONTRACT",
                                     later,now=later)
    assert result.novelty=="EXISTING_ECONOMIC_CLAIM"
    assert len(result.prior_value_sha256s)==1


def test_changed_contract_value_is_preserved_as_revision(tmp_path):
    path=tmp_path/"private"/"facts.sqlite3"
    record_prior_fact(path,candidate(),now=NOW)
    later=NOW+timedelta(seconds=1)
    prior=prior_state_as_of(path,"company-reviewed-1",later,now=later)
    changed=candidate(value="c"*64,event="d"*64,available=later)
    result=detect_new_economic_claim(prior,changed,"NEW_CONTRACT",later,now=later)
    assert result.novelty=="CHANGED_ECONOMIC_CLAIM_REVIEW"
    assert result.prior_value_sha256s==("b"*64,)
    assert result.proposed_value_sha256=="c"*64
    assert result.fact_verified is False


def test_inappropriate_stale_baseline_fails_closed(tmp_path):
    old=baseline(tmp_path)
    later=NOW+timedelta(seconds=1)
    with pytest.raises(SourceShareError,match="stale"):
        detect_new_economic_claim(old,candidate(),"NEW_CONTRACT",later,now=later)


def test_mismatched_subject_cannot_be_cross_labeled(tmp_path):
    past=baseline(tmp_path)
    wrong=replace(candidate(),reviewed_subject_id="other-company")
    with pytest.raises(SourceShareError,match="subject differs"):
        detect_new_economic_claim(past,wrong,"NEW_CONTRACT",NOW,now=NOW)


def test_future_observation_or_decision_cannot_leak():
    at=NOW+timedelta(seconds=1)
    prior=PriorState("company-reviewed-1",NOW,())
    with pytest.raises(SourceShareError,match="future economic"):
        detect_new_economic_claim(prior,candidate(available=at),"NEW_CONTRACT",NOW,now=NOW)
    with pytest.raises(SourceShareError):
        detect_new_economic_claim(prior,candidate(),"NEW_CONTRACT",at,now=NOW)


def test_unsupported_fact_type_and_ambiguous_industry_are_not_guessed(tmp_path):
    old=baseline(tmp_path)
    with pytest.raises(SourceShareError,match="category"):
        detect_new_economic_claim(old,candidate(),"NEW_HEADLINE",NOW,now=NOW)


def test_newness_after_refutation_remains_for_manual_review(tmp_path):
    path=tmp_path/"private"/"facts.sqlite3"
    historic=replace(candidate(),evidence_status="FACT_REFUTED")
    record_prior_fact(path,historic,now=NOW)
    later=NOW+timedelta(seconds=1)
    result=detect_new_economic_claim(
        prior_state_as_of(path,"company-reviewed-1",later,now=later),
        candidate(value="c"*64,available=later),"NEW_CONTRACT",later,now=later
    )
    assert result.novelty=="REFUTED_CLAIM_REOPENED_REVIEW"
    assert not result.fact_verified
