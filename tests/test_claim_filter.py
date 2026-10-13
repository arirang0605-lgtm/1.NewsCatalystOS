"""2_4 sponsored/anonymous/rumor cannot be promoted to verified fact."""
from dataclasses import replace
from datetime import timedelta

import pytest

from newscatalystos.claim_filter import classify_claim
from newscatalystos.source_share import SourceShareError
from newscatalystos.text_normalization import normalize_text
from test_exact_dedup import feed
from test_new_source_adapter import NOW


def item(title: str):
    base = feed()
    return replace(base, text=title, raw_title_sha256=normalize_text(title)[1])


@pytest.mark.parametrize("kind", ["OFFICIAL_AGENCY", "COMPANY_IR", "PRESS_RELEASE",
                                   "INDEPENDENT_NEWS"])
def test_sources_without_fact_attestation_remain_unverified(kind):
    result=classify_claim(item("HBM 신규 공장 착공"),kind,decision_at=NOW,now=NOW)
    assert result.eligible_for_review
    assert not result.is_verified_fact
    assert "OBSERVED_NOT_FACT" in result.classification or "NOT_INDEPENDENT" in result.classification


@pytest.mark.parametrize("title,kind,expected", [
    ("광고: 100% 수익 보장", "INDEPENDENT_NEWS", "BLOCK_AD_SPAM"),
    ("협찬 HBM 투자 전략", "COMPANY_IR", "BLOCK_AD_SPAM"),
    ("sponsored AI future", "PRESS_RELEASE", "BLOCK_AD_SPAM"),
    ("익명 제보에 의한 HBM 투자 소문", "INDEPENDENT_NEWS", "UNVERIFIED_RUMOR"),
    ("HBM 사업 신규계약", "SOCIAL", "UNVERIFIED_RUMOR"),
    ("국가기관 발표", "ANONYMOUS", "UNVERIFIED_RUMOR"),
])
def test_high_risk_ads_and_rumors_are_never_actionable(title,kind,expected):
    v=classify_claim(item(title),kind,decision_at=NOW,now=NOW)
    assert v.classification==expected
    assert not v.eligible_for_review
    assert v.reason_codes
    assert not v.is_verified_fact


def test_false_official_label_in_headline_not_authority():
    v=classify_claim(item("공식 보도자료 확정 공급망 뉴스"),"SOCIAL",
                     decision_at=NOW,now=NOW)
    assert not v.is_verified_fact
    assert not v.eligible_for_review


def test_late_pit_document_cannot_backfill():
    source=replace(item("정책 발표"),available_at=NOW+timedelta(seconds=1))
    with pytest.raises(SourceShareError,match="future"):
        classify_claim(source,"OFFICIAL_AGENCY",decision_at=NOW,now=NOW)


def test_invalid_source_role_and_false_ad_type_are_rejected():
    with pytest.raises(SourceShareError):
        classify_claim(item("HBM"),"FAKE_OFFICIAL",decision_at=NOW,now=NOW)
    with pytest.raises(SourceShareError):
        classify_claim(item("HBM"),"OFFICIAL_AGENCY",decision_at=NOW,now=NOW,
                       is_advertisement="false")


def test_filter_result_not_replayable_before_its_availability():
    source=replace(item("공장 증설"),available_at=NOW+timedelta(seconds=3))
    later=NOW+timedelta(seconds=3)
    result=classify_claim(source,"COMPANY_IR",decision_at=later,now=later)
    with pytest.raises(SourceShareError,match="unavailable"):
        result.as_of(NOW,now=later)
