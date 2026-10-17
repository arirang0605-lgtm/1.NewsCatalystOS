"""4_2 quantitative facts must match authorized source excerpt exactly."""
from datetime import timedelta
import pytest

from newscatalystos.fact_extraction import FactProposal, verify_extracted_facts
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW

EXCERPT = "ABC반도체는 2026-10-13 HBM 장비 공급 계약 320억원을 발표했다. 실제 매출 기여는 미확인."


def proposals():
    return [
        FactProposal("CONTRACT_AMOUNT", "320억원", "HBM 장비 공급 계약 320억원"),
        FactProposal("ANNOUNCEMENT_DATE", "2026-10-13", "2026-10-13 HBM 장비"),
        FactProposal("PRODUCT", "HBM", "HBM 장비"),
    ]


def verify(entries=None, excerpt=EXCERPT):
    return verify_extracted_facts(
        "a"*64, excerpt, proposals() if entries is None else entries,
        observed_at=NOW, checked_at=NOW, now=NOW,
    )


def test_exactly_supported_amount_and_dates():
    result=verify()
    assert {f.field for f in result.supported} == {
        "CONTRACT_AMOUNT", "ANNOUNCEMENT_DATE", "PRODUCT"
    }
    assert result.rejected_fields==()
    assert result.independently_certified_accuracy is False
    assert all(f.evidence_quote_sha256 for f in result.supported)


def test_hallucinated_amount_cannot_become_verified():
    result=verify([FactProposal("CONTRACT_AMOUNT", "900억원",
                                "HBM 장비 공급 계약 900억원")])
    assert result.supported==()
    assert result.rejected_fields==("CONTRACT_AMOUNT",)


def test_unsupported_revenue_contribution_is_unknown():
    result=verify([FactProposal("CONTRACT_AMOUNT", "2000억원", "매출 기여 2000억원")])
    assert not result.supported


def test_invalid_date_or_future_policy_date_rejected():
    source="정부 정책은 2026-02-30 적용으로 표시됐다."
    result=verify([FactProposal("POLICY_EFFECTIVE_DATE", "2026-02-30",
                                "2026-02-30 적용")],excerpt=source)
    assert not result.supported


def test_quote_match_is_mandatory_not_only_value():
    result=verify([FactProposal("PRODUCT","HBM","unrelated citation")])
    assert result.rejected_fields==("PRODUCT",)


def test_future_source_cannot_leak_into_extractor():
    with pytest.raises(SourceShareError,match="cannot precede"):
        verify_extracted_facts("a"*64,EXCERPT,proposals(),
            observed_at=NOW+timedelta(seconds=1),checked_at=NOW,now=NOW)


def test_unsafe_large_source_and_unknown_field():
    with pytest.raises(SourceShareError,match="authorized short"):
        verify_extracted_facts("a"*64,"x"*2049,proposals(),
            observed_at=NOW,checked_at=NOW,now=NOW)
    with pytest.raises(SourceShareError,match="field"):
        verify([FactProposal("STOCK_PRICE_TARGET", "$999", "some made-up quote")])


def test_after_check_as_of_does_not_backdate():
    at=NOW+timedelta(seconds=2)
    rows=verify_extracted_facts("a"*64,EXCERPT,proposals(),
                               observed_at=NOW,checked_at=at,now=at)
    with pytest.raises(SourceShareError,match="unavailable"):
        rows.as_of(NOW,now=at)
    assert rows.as_of(at,now=at) is rows


def test_duplicate_proposals_not_double_counted():
    result=verify(proposals() + [proposals()[0]])
    assert len(result.supported)==3


def test_spaced_large_won_units_keep_exact_source_amount_evidence():
    from newscatalystos.feed_analysis import _krw
    from newscatalystos.fact_extraction import MONEY
    from decimal import Decimal
    title = "가상반도체는 HBM 공급계약 54조 원 체결"
    fragments = [m.group().strip() for m in MONEY.finditer(title)]
    assert fragments == ["54조 원"]
    assert _krw(fragments[0]) == Decimal("54000000000000")
    assert _krw("54조원") == _krw("54조 원")
    facts = verify([FactProposal("CONTRACT_AMOUNT", "54조 원", title)], excerpt=title)
    assert [(row.field,row.value) for row in facts.supported] == [("CONTRACT_AMOUNT", "54조 원")]
    assert not facts.independently_certified_accuracy
    assert _krw("$99billion") is None  # no inferred currency conversion
