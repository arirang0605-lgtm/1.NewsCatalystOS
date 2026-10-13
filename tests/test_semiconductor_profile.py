"""5_1 one-industry taxonomy; not inferred stock or supplier relationships."""
from dataclasses import replace
import pytest

from newscatalystos.semiconductor_profile import (
    SCHEMA, STAGES, CAUSES, build_semiconductor_profile, validate_profile,
)
from newscatalystos.source_share import SourceShareError


def test_all_nine_semiconductor_stages_present():
    profile=build_semiconductor_profile()
    assert profile.industry_id=="SEMICONDUCTOR"
    assert profile.schema_version==SCHEMA
    assert {x.stage for x in profile.nodes}==set(STAGES)
    assert len(profile.nodes)==9
    assert len(profile.taxonomy_sha256)==64
    validate_profile(profile)


def test_price_volume_capex_packaging_testing_are_distinct():
    profile=build_semiconductor_profile()
    assert {r.trigger for r in profile.routes}==set(CAUSES)
    assert "MEMORY_HBM" in profile.route_for("PACKAGING_CAPACITY").candidate_stages
    assert "FAB_EQUIPMENT" in profile.route_for("EQUIPMENT_CAPEX").candidate_stages
    assert "TESTING" in profile.route_for("TESTING_DEMAND").candidate_stages


def test_taxonomy_is_deterministic_without_external_calls():
    first=build_semiconductor_profile()
    assert first==build_semiconductor_profile()
    assert first.taxonomy_sha256==build_semiconductor_profile().taxonomy_sha256


def test_no_unsubstantiated_beneficiary_or_sales():
    profile=build_semiconductor_profile()
    assert profile.verified_beneficiary_count==0
    assert profile.unverified_relationship_count==0
    assert profile.annual_revenue_inference_allowed is False


def test_other_industries_cannot_be_smuggled_in():
    profile=build_semiconductor_profile()
    with pytest.raises(SourceShareError,match="only supports"):
        validate_profile(replace(profile,industry_id="BIOTECH"))


def test_unauthorized_supplier_edges_not_accepted_in_taxonomy():
    profile=build_semiconductor_profile()
    with pytest.raises(SourceShareError,match="unreviewed"):
        validate_profile(replace(profile,verified_beneficiary_count=100))


def test_unknown_trigger_does_not_produce_beneficiaries():
    with pytest.raises(SourceShareError,match="non-semiconductor"):
        build_semiconductor_profile().route_for("ROBOTICS")
