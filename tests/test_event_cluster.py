"""2_3 source-aware grouping preserves new numeric terms and corrections."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.event_cluster import Story, group_event_stories
from newscatalystos.source_share import SourceShareError
from newscatalystos.text_normalization import normalize_text
from test_exact_dedup import feed
from test_new_source_adapter import NOW


def row(title, source="media-a", seconds=0, code="a"):
    base = feed()
    return replace(base, text=title, source_id=source,
                   event_id=code * 64,
                   raw_title_sha256=normalize_text(title)[1],
                   available_at=NOW + timedelta(seconds=seconds))


def case(title, origin="official-issuer-2026-01", subject="semiconductor-HBM",
         source="media-a", seconds=0, code="a"):
    return Story(row(title, source=source, seconds=seconds, code=code),
                 origin_reference=origin, reviewed_subject=subject)


def test_multiple_accounts_same_economic_event_and_new_amounts_remain():
    a=case("반도체 HBM 증설 투자 100억원 발표")
    b=case("반도체 HBM 증설 투자 200억원 정정 발표",
           source="media-b",seconds=20,code="b")
    at=NOW+timedelta(seconds=30)
    groups=group_event_stories([a,b],at,now=at)
    assert len(groups)==1
    g=groups[0]
    assert len(g.variants)==2
    assert "100억원" in g.variants[0].numeric_facts
    assert "200억원" in g.variants[1].new_numeric_facts
    assert g.variants[1].correction_flag
    assert {x.source_id for x in g.variants} == {"media-a","media-b"}
    assert g.status != "OFFICIALLY_CONFIRMED"
    with pytest.raises(SourceShareError,match="did not exist"):
        g.as_of(NOW+timedelta(seconds=29),now=at)


def test_without_reviewed_same_origin_similar_titles_not_merged():
    a=case("반도체 HBM 증설 투자 100억원 발표",origin=None)
    b=case("반도체 HBM 증설 투자 100억원 발표",
           origin=None,source="media-b",code="b")
    t=NOW+timedelta(seconds=30)
    assert len(group_event_stories([a,b],t,now=t))==2


def test_different_origins_never_merge_even_with_same_headline():
    a=case("반도체 HBM 증설 투자 100억원 발표")
    b=case("반도체 HBM 증설 투자 100억원 발표",
           origin="different-issuer-2026-01",source="media-b",code="b")
    assert len(group_event_stories([a,b],NOW,now=NOW))==2


def test_unrelated_development_is_kept_separate_even_same_origin():
    a=case("반도체 HBM 증설 투자 100억원 발표")
    b=case("바이오 임상 허가 100억원 발표",
           source="media-b",code="b")
    assert len(group_event_stories([a,b],NOW,now=NOW))==2


def test_future_document_is_rejected_entire_batch():
    future=case("HBM 신규 계약 250억원",seconds=1)
    with pytest.raises(SourceShareError,match="future"):
        group_event_stories([future],NOW,now=NOW)


def test_stable_group_id_when_new_revision_arrives():
    first=case("반도체 HBM 증설 투자 100억원 발표")
    second=case("반도체 HBM 증설 투자 200억원 변경 발표",
                source="media-b",seconds=1,code="b")
    one=group_event_stories([first],NOW,now=NOW)[0]
    later=NOW+timedelta(seconds=1)
    combined=group_event_stories([second,first],later,now=later)[0]
    assert combined.cluster_id==one.cluster_id
    assert len(combined.variants)==2


def test_replay_and_repeated_input_deterministic():
    first=case("반도체 HBM 증설 투자 100억원 발표")
    decision=NOW+timedelta(seconds=1)
    a=group_event_stories([first,first],decision,now=decision)
    b=group_event_stories([first],decision,now=decision)
    assert a==b
    assert len(a[0].variants)==1


def test_invalid_origin_or_subject_fails_closed():
    first=case("반도체 HBM 증설 투자 100억원 발표")
    with pytest.raises(SourceShareError):
        group_event_stories([replace(first,origin_reference="../unsafe")],NOW,now=NOW)
    with pytest.raises(SourceShareError):
        group_event_stories([replace(first,reviewed_subject=" ")],NOW,now=NOW)
