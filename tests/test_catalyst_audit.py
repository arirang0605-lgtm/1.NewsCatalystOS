"""6_3 trace source/transition/model/prompt hashes at historical decision."""
from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from newscatalystos.catalyst_audit import AuditInput,append_catalyst_audit,audit_as_of
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW

EVENT="a"*64
SOURCE="b"*64


def database(tmp_path):
    return tmp_path/"private"/"catalyst_audit.sqlite3"


def new(kind="SOURCE_OBSERVED",**change):
    fields=dict(event_sha256=EVENT,source_evidence_sha256=SOURCE,
                transition_sha256=None,analysis_sha256=None,
                model_sha256=None,prompt_sha256=None,
                kind=kind,first_seen_at=NOW,
                source_available_at=NOW)
    fields.update(change)
    return AuditInput(**fields)


def test_first_evidence_and_immutable_repeated_ingestion(tmp_path):
    path=database(tmp_path)
    first=append_catalyst_audit(path,new(),now=NOW)
    again=append_catalyst_audit(path,new(),now=NOW)
    assert first==again
    assert first.externally_certified_release_at is None
    assert len(audit_as_of(path,EVENT,NOW,now=NOW))==1
    assert path.stat().st_mode & 0o777 == 0o600


def test_lifecycle_and_model_version_links_survive_replay(tmp_path):
    path=database(tmp_path)
    one=append_catalyst_audit(path,new(),now=NOW)
    later=NOW+timedelta(seconds=2)
    change=append_catalyst_audit(path,new(
        "LIFECYCLE_CHANGED",transition_sha256="c"*64,
        supersedes_audit_sha256=one.audit_sha256,
    ),now=later)
    analysis=append_catalyst_audit(path,new(
        "AI_ANALYZED",analysis_sha256="d"*64,model_sha256="e"*64,
        prompt_sha256="f"*64,supersedes_audit_sha256=change.audit_sha256,
    ),now=later)
    assert len(audit_as_of(path,EVENT,NOW,now=later))==1
    historical=audit_as_of(path,EVENT,later,now=later)
    assert len(historical)==3
    assert historical[-1].model_sha256=="e"*64
    assert historical[-1].prompt_sha256=="f"*64
    assert historical[-1].supersedes_audit_sha256==change.audit_sha256
    assert historical[0]==one


def test_missing_model_or_lifecycle_evidence_denied(tmp_path):
    with pytest.raises(SourceShareError,match="missing model"):
        append_catalyst_audit(database(tmp_path),
                              new("AI_ANALYZED",analysis_sha256="c"*64),now=NOW)
    with pytest.raises(SourceShareError,match="missing lifecycle"):
        append_catalyst_audit(database(tmp_path),
                              new("LIFECYCLE_CHANGED"),now=NOW)


def test_future_source_and_backfilled_timestamps_not_allowed(tmp_path):
    path=database(tmp_path)
    with pytest.raises(SourceShareError,match="future"):
        append_catalyst_audit(path,new(
            source_available_at=NOW+timedelta(seconds=1)
        ),now=NOW)
    later=NOW+timedelta(seconds=2)
    append_catalyst_audit(path,new(),now=later)
    assert audit_as_of(path,EVENT,NOW,now=later)==()


def test_tampering_same_sha_with_different_claim_time_denied(tmp_path):
    path=database(tmp_path)
    append_catalyst_audit(path,new(),now=NOW)
    with pytest.raises(SourceShareError,match="immutable"):
        append_catalyst_audit(path,new(first_seen_at=NOW-timedelta(seconds=1)),now=NOW)


def test_wrong_event_correction_chain_is_rejected(tmp_path):
    path=database(tmp_path)
    prior=append_catalyst_audit(path,new(),now=NOW)
    with pytest.raises(SourceShareError,match="prior audit chain"):
        append_catalyst_audit(path,new(
            "LIFECYCLE_CHANGED",transition_sha256="c"*64,
            event_sha256="f"*64,supersedes_audit_sha256=prior.audit_sha256
        ),now=NOW)


def test_database_does_not_store_source_article_or_secret_prompt(tmp_path):
    path=database(tmp_path)
    append_catalyst_audit(path,new(),now=NOW)
    payload=path.read_bytes()
    assert b"article paid full text" not in payload
    assert b"PROMPT_BODY_PRIVATE" not in payload
