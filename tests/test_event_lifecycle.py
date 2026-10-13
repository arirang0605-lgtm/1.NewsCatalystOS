"""6_1 lifecycle/PIT/correction tests, including synthetic signed fixture."""
from datetime import timedelta
import pytest

from newscatalystos.event_lifecycle import (
    append_lifecycle,lifecycle_as_of,
)
from newscatalystos.source_share import SourceShareError
from newscatalystos.official_promotion import authenticate_anchored_official_record
from test_official_promotion import scenario, NOW as PROOF_NOW
from test_signed_publication import witness
from test_new_source_adapter import NOW

EVENT = "a"*64
EVIDENCE = "b"*64


def state(tmp_path):
    return tmp_path/"private"/"event_lifecycle.sqlite3"


def test_new_detection_without_signed_proof_is_not_confirmed(tmp_path):
    path=state(tmp_path)
    original=append_lifecycle(path,EVENT,"DETECTED",EVIDENCE,NOW,at=NOW)
    assert original.state=="DETECTED"
    assert original.revision_number==1
    assert original.evidence_status=="UNVERIFIED_SOURCE_CLAIM"
    assert lifecycle_as_of(path,EVENT,NOW,now=NOW).current_state=="DETECTED"
    assert not lifecycle_as_of(path,EVENT,NOW,now=NOW).independently_certified_release
    with pytest.raises(SourceShareError,match="anchored official"):
        append_lifecycle(path,EVENT,"CONFIRMED","c"*64,NOW,at=NOW)
    assert lifecycle_as_of(path,EVENT,NOW,now=NOW).current_state=="DETECTED"


def test_detected_to_invalidated_then_reactivation_preserves_both(tmp_path):
    path=state(tmp_path)
    first=append_lifecycle(path,EVENT,"DETECTED",EVIDENCE,NOW,at=NOW)
    invalid_at=NOW+timedelta(seconds=1)
    dead=append_lifecycle(path,EVENT,"INVALIDATED","c"*64,invalid_at,at=invalid_at)
    restart_at=NOW+timedelta(seconds=2)
    new=append_lifecycle(path,EVENT,"DETECTED","d"*64,restart_at,at=restart_at)
    assert new.previous_version_sha256==dead.version_sha256
    assert dead.previous_version_sha256==first.version_sha256
    assert [x.state for x in lifecycle_as_of(path,EVENT,restart_at,now=restart_at).versions]==[
        "DETECTED","INVALIDATED","DETECTED"
    ]
    assert lifecycle_as_of(path,EVENT,invalid_at,now=restart_at).current_state=="INVALIDATED"
    assert lifecycle_as_of(path,EVENT,NOW,now=restart_at).current_state=="DETECTED"


def test_no_article_does_not_auto_expire_existing_lifecycle(tmp_path):
    path=state(tmp_path)
    append_lifecycle(path,EVENT,"DETECTED",EVIDENCE,NOW,at=NOW)
    later=NOW+timedelta(days=300)
    status=lifecycle_as_of(path,EVENT,later,now=later)
    assert status.current_state=="DETECTED" and len(status.versions)==1


def test_cannot_skip_confirmed_without_actual_proof(tmp_path):
    path=state(tmp_path)
    append_lifecycle(path,EVENT,"DETECTED",EVIDENCE,NOW,at=NOW)
    with pytest.raises(SourceShareError,match="illegal lifecycle"):
        append_lifecycle(path,EVENT,"STRENGTHENED","c"*64,NOW,at=NOW)
    with pytest.raises(SourceShareError,match="illegal lifecycle"):
        append_lifecycle(path,EVENT,"WEAKENED","d"*64,NOW,at=NOW)


def test_future_evidence_and_future_history_denied(tmp_path):
    path=state(tmp_path)
    with pytest.raises(SourceShareError,match="future"):
        append_lifecycle(path,EVENT,"DETECTED",EVIDENCE,NOW+timedelta(seconds=1),at=NOW)
    with pytest.raises(SourceShareError,match="future"):
        lifecycle_as_of(path,EVENT,NOW+timedelta(seconds=1),now=NOW)


def test_signed_synthetic_fixture_allows_typed_confirmed_transition(tmp_path,witness):
    args,folder,original=scenario(tmp_path,witness,"SEC")
    signed=authenticate_anchored_official_record(**args)
    raw=signed.as_of(PROOF_NOW,now=PROOF_NOW)
    path=state(tmp_path)
    append_lifecycle(path,raw.event_id,"DETECTED","b"*64,
                     signed.usable_from,at=PROOF_NOW)
    confirmed=append_lifecycle(path,raw.event_id,"CONFIRMED","c"*64,
                               signed.usable_from,at=PROOF_NOW,
                               anchored_publication=signed)
    assert confirmed.state=="CONFIRMED"
    assert confirmed.evidence_status=="ANCHORED_WITNESS_RELEASE_CLAIM"
    changed=append_lifecycle(path,raw.event_id,"STRENGTHENED","d"*64,
                             signed.usable_from,at=PROOF_NOW)
    weak=append_lifecycle(path,raw.event_id,"WEAKENED","e"*64,
                          signed.usable_from,at=PROOF_NOW)
    stopped=append_lifecycle(path,raw.event_id,"INVALIDATED","f"*64,
                             signed.usable_from,at=PROOF_NOW)
    assert [x.state for x in lifecycle_as_of(path,raw.event_id,PROOF_NOW,now=PROOF_NOW).versions]==[
        "DETECTED","CONFIRMED","STRENGTHENED","WEAKENED","INVALIDATED"
    ]
    assert (folder/"raw_response.json").read_bytes()==original
    assert stopped.previous_version_sha256==weak.version_sha256


def test_synthetic_proof_wrong_event_cannot_confirm(tmp_path,witness):
    args,folder,original=scenario(tmp_path,witness,"SEC")
    signed=authenticate_anchored_official_record(**args)
    path=state(tmp_path)
    append_lifecycle(path,EVENT,"DETECTED",EVIDENCE,
                     signed.usable_from,at=PROOF_NOW)
    with pytest.raises(SourceShareError,match="signed event ID"):
        append_lifecycle(path,EVENT,"CONFIRMED","c"*64,
                         signed.usable_from,at=PROOF_NOW,
                         anchored_publication=signed)
    assert lifecycle_as_of(path,EVENT,PROOF_NOW,now=PROOF_NOW).current_state=="DETECTED"
