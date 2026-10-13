"""2_5 quoted release reprints never multiply independent fact evidence."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import pytest

from newscatalystos.origin_provenance import Citation, assess_origins
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW

GROUP="a"*64


def cite(provider="media-a", origin="press-original-123",
         stance="SUPPORT", sec=0, role="INDEPENDENT_NEWS"):
    return Citation(
        source_id=provider, event_id=sha256(provider.encode()).hexdigest(),
        observed_at=NOW+timedelta(seconds=sec),
        publisher_role=role, stance=stance, attributed_origin_id=origin,
        origin_reference_sha256=("b"*64 if origin else None),
    )


def test_many_reprints_one_root_not_multiple_independent_sources():
    sources=[cite("media-a"),cite("media-b",role="DISTRIBUTOR"),
             cite("media-c"),cite("media-d")]
    decision=NOW+timedelta(minutes=1)
    result=assess_origins(GROUP,sources,decision,now=decision)
    assert result.citation_count==4
    assert result.claimed_root_count==1
    assert result.independently_verified_fact_count==0
    assert result.claimed_roots==("press-original-123",)
    assert not result.fact_verified
    assert result.hold_reason is None


def test_separate_claim_roots_do_not_automatically_confirm_truth():
    at=NOW+timedelta(seconds=2)
    rows=[cite("media-a",origin="primary-1"),
          cite("media-b",origin="primary-2")]
    result=assess_origins(GROUP,rows,at,now=at)
    assert result.claimed_root_count==2
    assert result.independently_verified_fact_count==0
    assert not result.fact_verified


def test_unknown_social_origin_does_not_add_independent_proof():
    at=NOW+timedelta(seconds=1)
    result=assess_origins(GROUP,[cite("sns-1",origin=None,role="SOCIAL"),
                                 cite("sns-2",origin=None,role="SOCIAL")],at,now=at)
    assert result.claimed_root_count==0
    assert result.unknown_origin_count==2
    assert result.hold_reason=="UNTRACED_ORIGIN_NEEDS_REVIEW"


def test_official_refutation_forces_conflict_hold():
    at=NOW+timedelta(seconds=10)
    result=assess_origins(
        GROUP, [cite("media-a"),cite("regulator",origin="regulator-actual",
                                   stance="REFUTE",role="OFFICIAL_PRIMARY")],
        at,now=at)
    assert result.hold_reason=="CONTRADICTORY_SOURCES_HOLD"
    assert not result.fact_verified


def test_source_correction_forces_review_and_keeps_history():
    at=NOW+timedelta(seconds=10)
    result=assess_origins(
        GROUP,[cite("media-a"),cite("media-b",stance="CORRECT")],at,now=at)
    assert result.hold_reason=="CORRECTION_PENDING_PRIMARY_REVIEW"
    assert result.citation_count==2


def test_future_source_is_not_allowed_to_change_past_verdict():
    at=NOW+timedelta(seconds=2)
    with pytest.raises(SourceShareError,match="future citation"):
        assess_origins(GROUP,[cite(sec=10)],at,now=at)


def test_repeated_same_document_is_not_new_independent_root():
    at=NOW+timedelta(seconds=10)
    a=cite()
    assessed=assess_origins(GROUP,[a,a],at,now=at)
    assert assessed.citation_count==1
    with pytest.raises(SourceShareError,match="conflicting duplicate"):
        assess_origins(GROUP,[a,replace(a,stance="REFUTE")],at,now=at)


def test_invalid_root_digest_or_url_is_denied():
    at=NOW+timedelta(seconds=1)
    with pytest.raises(SourceShareError):
        assess_origins(GROUP,[replace(cite(),attributed_origin_id="../secret")],at,now=at)
    with pytest.raises(SourceShareError):
        assess_origins(GROUP,[replace(cite(),origin_reference_sha256="fake")],at,now=at)


def test_assessment_is_not_replayed_before_its_creation():
    later=NOW+timedelta(seconds=1)
    r=assess_origins(GROUP,[cite()],later,now=later)
    with pytest.raises(SourceShareError,match="not available"):
        r.as_of(NOW,now=later)
