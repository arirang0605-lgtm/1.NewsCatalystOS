"""3_5 triage uses bounded qualitative input and never invents financials."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.impact_triage import ImpactInputs,triage_importance
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def item(**kwargs):
    base=dict(event_sha256="a"*64,available_at=NOW,scale="LARGE",
              affected_scope="INDUSTRY",repeatability="RECURRING",
              novelty="NEW_FACT_CANDIDATE",market_expectation="SURPRISE")
    base.update(kwargs)
    return ImpactInputs(**base)


def test_high_rule_priority_is_not_proven_sales_or_advice():
    result=triage_importance(item(),NOW,now=NOW)
    assert result.numeric_score==11
    assert result.priority=="HIGH_PRIORITY_REVIEW"
    assert result.verified_economic_impact is False
    assert result.estimated_revenue_krw is None
    assert not result.unknown_dimensions


def test_unknown_market_expectation_requires_review_not_number():
    result=triage_importance(item(market_expectation="UNKNOWN"),NOW,now=NOW)
    assert result.numeric_score is None
    assert result.priority=="INSUFFICIENT_EVIDENCE_REVIEW"
    assert result.unknown_dimensions==("market_expectation",)
    assert result.estimated_revenue_krw is None


def test_priced_in_known_event_is_lower_review_priority():
    result=triage_importance(item(
        scale="SMALL",affected_scope="SINGLE_FIRM",
        repeatability="ONE_OFF",novelty="ALREADY_KNOWN",
        market_expectation="PRICED_IN"),NOW,now=NOW)
    assert result.numeric_score==2
    assert result.priority=="STANDARD_REVIEW"


def test_bad_dimension_or_future_pit_cannot_receive_signal():
    with pytest.raises(SourceShareError,match="category"):
        triage_importance(item(scale="100 BILLION KRW"),NOW,now=NOW)
    with pytest.raises(SourceShareError,match="future"):
        triage_importance(item(available_at=NOW+timedelta(seconds=1)),NOW,now=NOW)


def test_priority_replay_before_decision_rejected():
    later=NOW+timedelta(seconds=1)
    result=triage_importance(item(),later,now=later)
    with pytest.raises(SourceShareError,match="past decision"):
        result.as_of(NOW,now=later)
