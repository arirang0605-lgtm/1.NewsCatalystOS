"""5_3 stage-specific transmission never invents specific supplier revenue."""
from datetime import timedelta
import pytest

from newscatalystos.semiconductor_profile import build_semiconductor_profile
from newscatalystos.semiconductor_impact import propagate_semiconductor_claim
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def assess(trigger="PACKAGING_CAPACITY", at=NOW, source_seen=NOW, direction="POSITIVE"):
    return propagate_semiconductor_claim(
        build_semiconductor_profile(), "a"*64, trigger,
        direction=direction, evidence_note="Impact is a hypothetical demand path",
        source_available_at=source_seen,reviewed_at=at,now=at,
    )


def test_hbm_packaging_and_testing_have_different_stage_footprints():
    pack=assess("PACKAGING_CAPACITY")
    test=assess("TESTING_DEMAND")
    assert "ADVANCED_PACKAGING" in pack.stages
    assert "TESTING" in test.stages
    assert pack.stages != test.stages
    assert not pack.certified_beneficiary_count
    assert pack.revenue_contribution_krw is None


def test_capex_hypothesis_is_not_proven_sales():
    result=assess("EQUIPMENT_CAPEX")
    assert "FAB_EQUIPMENT" in result.stages
    assert result.evidence_level=="IMPACT_HYPOTHESIS_NOT_VERIFIED"


def test_positive_negative_impacts_do_not_imply_security_returns():
    assert assess(direction="NEGATIVE").direction=="NEGATIVE"
    assert assess(direction="POSITIVE").direction=="POSITIVE"


def test_future_source_cannot_supply_past_company_effect():
    with pytest.raises(SourceShareError,match="future"):
        assess(at=NOW,source_seen=NOW+timedelta(seconds=1))


def test_unknown_non_semiconductor_trigger_fails():
    with pytest.raises(SourceShareError,match="non-semiconductor"):
        assess("AUTOMOTIVE_BATTERY")


def test_historical_impact_not_replayable_before_review():
    later=NOW+timedelta(seconds=2)
    result=assess(at=later)
    with pytest.raises(SourceShareError,match="not yet"):
        result.as_of(NOW,now=later)
