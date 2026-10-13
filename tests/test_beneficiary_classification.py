"""5_4 potential beneficiary/damage is not verified company revenue."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.beneficiary_classification import classify_semiconductor_beneficiary
from newscatalystos.semiconductor_profile import build_semiconductor_profile
from newscatalystos.semiconductor_impact import propagate_semiconductor_claim
from newscatalystos.supply_chain_graph import observed_supply_edge
from newscatalystos.source_share import SourceShareError
from test_supply_chain_graph import source,bind
from test_new_source_adapter import NOW


def edge(kind="REPORTED_DIRECT_TRANSACTION"):
    item=source()
    return observed_supply_edge(
        item,bind(item,"123456"),bind(item,"654321"),
        product_stage="ADVANCED_PACKAGING",
        relation_kind=kind,reviewed_at=NOW,now=NOW,
    )


def impact(direction="POSITIVE",trigger="PACKAGING_CAPACITY"):
    return propagate_semiconductor_claim(
        build_semiconductor_profile(),"a"*64,trigger,direction=direction,
        evidence_note="Only a possible transmission, no verified supply award",
        source_available_at=NOW,reviewed_at=NOW,now=NOW,
    )


def test_positive_direct_report_is_only_potential_not_certified():
    result=classify_semiconductor_beneficiary(edge(),impact(),reviewed_at=NOW,now=NOW)
    assert result.category=="POTENTIAL_BENEFICIARY_UNVERIFIED"
    assert not result.verified_real_benefit
    assert result.annual_sales_share is None
    assert result.realized_revenue_krw is None


def test_negative_impact_preserves_potential_harm():
    r=classify_semiconductor_beneficiary(edge(),impact("NEGATIVE"),reviewed_at=NOW,now=NOW)
    assert r.category=="POTENTIAL_DAMAGE_UNVERIFIED"


def test_thematic_relevance_never_becomes_direct_award():
    r=classify_semiconductor_beneficiary(
        edge("THEMATIC_ASSOCIATION"),impact(),reviewed_at=NOW,now=NOW,
    )
    assert r.category=="THEMATIC_ONLY"


def test_different_product_stage_does_not_forge_exposure():
    r=classify_semiconductor_beneficiary(
        edge(),impact(trigger="MEMORY_PRICE"),reviewed_at=NOW,now=NOW,
    )
    assert r.category=="UNKNOWN_RELATIONSHIP"


def test_future_reviewed_mapping_is_not_usable_at_past():
    at=NOW+timedelta(seconds=2)
    with pytest.raises(SourceShareError,match="future beneficiary"):
        classify_semiconductor_beneficiary(
            edge(),replace(impact(),reviewed_at=at),reviewed_at=NOW,now=at,
        )


def test_forged_verified_commercial_link_rejected():
    with pytest.raises(SourceShareError,match="self-certify"):
        classify_semiconductor_beneficiary(
            replace(edge(),verified_real_transaction=True),
            impact(),reviewed_at=NOW,now=NOW,
        )
