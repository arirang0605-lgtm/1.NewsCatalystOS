"""4_4 paths must include counter-arguments and never invent beneficiary ROI."""
from dataclasses import replace
from datetime import timedelta

import pytest

from newscatalystos.economic_path import ImpactHypothesis, build_impact_analysis
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def hypothesis():
    return ImpactHypothesis(
        path="CAPEX", direction="INCREASE", affected_product="HBM equipment",
        source_claim_sha256="b"*64,
        premise="Reported capacity expansion may increase equipment procurement",
        counter_type="MISSING_INFORMATION",
        counter_argument="Supplier award and timing have not been independently validated",
    )


def build(rows=None, at=NOW, observed=NOW):
    return build_impact_analysis("a"*64, [hypothesis()] if rows is None else rows,
                                 available_at=observed, decision_at=at, now=at)


def test_impact_path_is_hypothesis_not_verified_beneficiary():
    output=build()
    assert output.impact_hypotheses[0].path=="CAPEX"
    assert output.impact_hypotheses[0].counter_argument
    assert output.economic_effect_confirmed is False
    assert output.estimated_revenue_krw is None
    assert output.trade_recommendation is None


@pytest.mark.parametrize("category,direction", [
    ("DEMAND","INCREASE"),("SUPPLY","DECREASE"),("CAPEX","MIXED"),
    ("EARNINGS","UNKNOWN"),("COMPETITION","INCREASE"),
])
def test_distinct_effect_transmission_paths(category,direction):
    output=build([replace(hypothesis(),path=category,direction=direction)])
    assert output.impact_hypotheses[0].path==category
    assert not output.economic_effect_confirmed


def test_missing_counter_argument_is_rejected():
    with pytest.raises(SourceShareError,match="counterexample"):
        build([replace(hypothesis(),counter_argument="")])


def test_model_attempt_to_claim_direct_verified_impact_fails():
    with pytest.raises(SourceShareError,match="direct fact"):
        build([replace(hypothesis(),claim_type="OBSERVED_SOURCE_CLAIM")])


def test_malformed_evidence_sha_does_not_pass():
    with pytest.raises(SourceShareError,match="SHA"):
        build([replace(hypothesis(),source_claim_sha256="wrong")])


def test_future_economic_source_does_not_leak():
    with pytest.raises(SourceShareError,match="future"):
        build(at=NOW,observed=NOW+timedelta(seconds=1))


def test_replay_before_impact_review_is_blocked():
    result=build(at=NOW+timedelta(seconds=2))
    with pytest.raises(SourceShareError,match="historical"):
        result.as_of(NOW,now=NOW+timedelta(seconds=2))
