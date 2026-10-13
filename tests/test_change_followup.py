"""3_4 changed economic claims do not overwrite prior PIT history."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.change_followup import assess_followup
from newscatalystos.prior_fact_state import FactInput,record_prior_fact,prior_state_as_of
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def fact(value="b"*64,at=NOW):
    return FactInput("reviewed-company","contract-delivery","a"*64,value,at)


def setup(tmp_path):
    db=tmp_path/"p"/"fact.sqlite3"
    older=record_prior_fact(db,fact(),now=NOW)
    when=NOW+timedelta(seconds=10)
    before=prior_state_as_of(db,"reviewed-company",when,now=when)
    return older,db,when,before


@pytest.mark.parametrize("kind,result",[
    ("ORDER_FULFILLED","STRENGTHENED_CANDIDATE"),
    ("CAPACITY_EXPANDED","STRENGTHENED_CANDIDATE"),
    ("DATE_DELAYED","WEAKENED_CANDIDATE"),
    ("CONTRACT_REDUCED","WEAKENED_CANDIDATE"),
    ("BUSINESS_CANCELLED","INVALIDATED_CANDIDATE"),
    ("SOURCE_CORRECTED","CORRECTION_PENDING_VERIFICATION"),
])
def test_revisions_are_candidates_and_original_is_unchanged(tmp_path,kind,result):
    old,db,when,history=setup(tmp_path)
    later=fact("c"*64,when)
    outcome=assess_followup(history,later,kind,when,now=when)
    assert outcome.status==result
    assert outcome.previous_fact_sha256==old.fact_sha256
    assert outcome.previous_value_sha256=="b"*64
    assert outcome.new_value_sha256=="c"*64
    assert not outcome.is_realization_confirmed
    assert prior_state_as_of(db,"reviewed-company",NOW,now=when).facts[0]==old


def test_new_headline_with_same_claim_value_is_not_material_change(tmp_path):
    old,db,when,history=setup(tmp_path)
    result=assess_followup(history,fact(at=when),"ORDER_FULFILLED",when,now=when)
    assert result.status=="NO_NEW_VERIFIED_CHANGE"


def test_no_old_contract_cannot_claim_implementation(tmp_path):
    db=tmp_path/"p"/"fact.sqlite3"
    history=prior_state_as_of(db,"reviewed-company",NOW,now=NOW)
    result=assess_followup(history,fact(),"ORDER_FULFILLED",NOW,now=NOW)
    assert result.status=="NO_PRIOR_EVENT_HOLD"


def test_future_revision_and_stale_baseline_denied(tmp_path):
    old,db,when,history=setup(tmp_path)
    with pytest.raises(SourceShareError,match="future followup"):
        assess_followup(history,fact(at=when+timedelta(seconds=1)),
                        "DATE_DELAYED",when,now=when)
    with pytest.raises(SourceShareError,match="stale"):
        assess_followup(history,fact(),"DATE_DELAYED",
                        when+timedelta(seconds=1),now=when+timedelta(seconds=1))


def test_invalid_kind_or_wrong_company_rejected(tmp_path):
    old,db,when,history=setup(tmp_path)
    with pytest.raises(SourceShareError,match="kind"):
        assess_followup(history,fact(),"PRICE_PREDICTION",when,now=when)
    with pytest.raises(SourceShareError,match="subject"):
        assess_followup(history,replace(fact(),reviewed_subject_id="other"),
                        "BUSINESS_CANCELLED",when,now=when)
