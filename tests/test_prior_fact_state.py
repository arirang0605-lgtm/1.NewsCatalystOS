"""3_1 historical snapshots include only facts recorded before decision."""
from dataclasses import replace
from datetime import timedelta

import pytest

from newscatalystos.prior_fact_state import (
    FactInput,record_prior_fact,prior_state_as_of,
)
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW

def fact(event="a"*64,value="b"*64,available=NOW,**changes):
    defaults=dict(
        reviewed_subject_id="company-reviewed-1",fact_key="hbm_capacity",
        source_event_sha256=event,value_sha256=value,available_at=available,
    )
    defaults.update(changes)
    return FactInput(**defaults)


def test_snapshot_excludes_later_correction_and_prior_history(tmp_path):
    path=tmp_path/"private"/"facts.sqlite3"
    initial=record_prior_fact(path,fact(),now=NOW)
    before=prior_state_as_of(path,"company-reviewed-1",NOW,now=NOW)
    assert len(before.facts)==1
    assert before.latest_by_key()[0].fact_sha256==initial.fact_sha256
    later=NOW+timedelta(seconds=10)
    edited=record_prior_fact(path,fact(event="c"*64,value="d"*64,
                                       supersedes_fact_sha256=initial.fact_sha256),
                             now=later)
    older=prior_state_as_of(path,"company-reviewed-1",NOW,now=later)
    assert len(older.facts)==1 and older.facts[0].fact_sha256==initial.fact_sha256
    newer=prior_state_as_of(path,"company-reviewed-1",later,now=later)
    assert len(newer.facts)==2
    assert newer.latest_by_key()[0].fact_sha256==edited.fact_sha256
    assert newer.facts[0].evidence_status=="UNVERIFIED_CLAIM"


def test_backfill_cannot_claim_earlier_storage(tmp_path):
    path=tmp_path/"state"/"facts.sqlite3"
    later=NOW+timedelta(days=1)
    first=record_prior_fact(path,fact(available=NOW),now=later)
    assert first.recorded_at==later
    assert first.available_at==later
    assert not prior_state_as_of(path,"company-reviewed-1",NOW,now=later).facts


def test_exact_same_claim_idempotence(tmp_path):
    path=tmp_path/"state"/"facts.sqlite3"
    a=record_prior_fact(path,fact(),now=NOW)
    b=record_prior_fact(path,fact(),now=NOW)
    assert a==b
    assert len(prior_state_as_of(path,"company-reviewed-1",NOW,now=NOW).facts)==1


def test_unknown_subject_is_not_assumed_joinable(tmp_path):
    path=tmp_path/"state"/"facts.sqlite3"
    with pytest.raises(SourceShareError,match="subject"):
        record_prior_fact(path,fact(reviewed_subject_id=""),now=NOW)
    assert not path.exists()


def test_future_fact_and_future_decision_denied(tmp_path):
    path=tmp_path/"state"/"facts.sqlite3"
    with pytest.raises(SourceShareError,match="future"):
        record_prior_fact(path,fact(available=NOW+timedelta(seconds=1)),now=NOW)
    with pytest.raises(SourceShareError,match="future"):
        prior_state_as_of(path,"company-reviewed-1",
                          NOW+timedelta(days=1),now=NOW)


def test_wrong_subject_revision_chain_and_missing_parent_denied(tmp_path):
    path=tmp_path/"state"/"facts.sqlite3"
    first=record_prior_fact(path,fact(),now=NOW)
    with pytest.raises(SourceShareError,match="correction chain"):
        record_prior_fact(path,fact(event="c"*64,value="d"*64,
             reviewed_subject_id="different-subject",
             supersedes_fact_sha256=first.fact_sha256),now=NOW+timedelta(seconds=1))
    with pytest.raises(SourceShareError,match="correction chain"):
        record_prior_fact(path,fact(event="c"*64,value="d"*64,
             supersedes_fact_sha256="e"*64),now=NOW+timedelta(seconds=1))


def test_status_revision_without_new_sha_cannot_mutate_past(tmp_path):
    path=tmp_path/"state"/"facts.sqlite3"
    record_prior_fact(path,fact(),now=NOW)
    with pytest.raises(SourceShareError,match="immutable"):
        record_prior_fact(path,fact(evidence_status="FACT_REFUTED"),now=NOW)


def test_digest_only_private_database(tmp_path):
    path=tmp_path/"state"/"facts.sqlite3"
    record_prior_fact(path,fact(),now=NOW)
    data=path.read_bytes()
    assert b"company-reviewed-1" in data
    assert b"secret factual original text" not in data
    assert path.stat().st_mode & 0o777 == 0o600
