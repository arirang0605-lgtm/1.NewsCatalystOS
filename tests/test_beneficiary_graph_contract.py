"""5_5 versioned export is deterministic and source-PIT bound."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.beneficiary_graph_contract import build_beneficiary_graph,SCHEMA
from newscatalystos.beneficiary_classification import classify_semiconductor_beneficiary
from newscatalystos.semiconductor_profile import build_semiconductor_profile
from newscatalystos.source_share import SourceShareError
from test_beneficiary_classification import edge,impact
from test_new_source_adapter import NOW


def graph():
    profile=build_semiconductor_profile()
    linked=edge()
    path=impact()
    candidate=classify_semiconductor_beneficiary(linked,path,
                                                   reviewed_at=NOW,now=NOW)
    value=build_beneficiary_graph(profile,path,[linked],[candidate],NOW,now=NOW)
    return value,profile,path,linked,candidate


def test_versioned_json_contract_has_only_unverified_candidate():
    output,*_=graph()
    data=json.loads(output.JSON_bytes)
    assert data["schema"]==SCHEMA
    assert data["industry_id"]=="SEMICONDUCTOR"
    assert data["certified_beneficiary_count"]==0
    assert len(data["edges"])==1
    assert data["edges"][0]["verified_real_benefit"] is False
    assert data["edges"][0]["revenue_contribution_krw"] is None
    assert output.payload_sha256==sha256(output.JSON_bytes).hexdigest()


def test_deterministic_export_with_reordered_input():
    original,profile,impact_path,linked,candidate=graph()
    same=build_beneficiary_graph(profile,impact_path,(linked,),
                                 (candidate,),NOW,now=NOW)
    assert same.JSON_bytes==original.JSON_bytes


def test_unsigned_claim_cannot_be_injected_as_certified_beneficiary():
    value,profile,impact_path,linked,candidate=graph()
    with pytest.raises(SourceShareError,match="source evidence"):
        build_beneficiary_graph(profile,impact_path,[linked],
            [replace(candidate,verified_real_benefit=True)],NOW,now=NOW)


def test_supplier_edges_without_candidate_are_empty_not_fake_positive():
    value,profile,impact_path,linked,candidate=graph()
    zero=build_beneficiary_graph(profile,impact_path,[linked],[],NOW,now=NOW)
    assert zero.items_count==0
    assert json.loads(zero.JSON_bytes)["certified_beneficiary_count"]==0


def test_relation_and_candidate_mismatch_rejected():
    value,profile,impact_path,linked,candidate=graph()
    with pytest.raises(SourceShareError,match="source evidence"):
        build_beneficiary_graph(profile,impact_path,[linked],
            [replace(candidate,supply_edge_sha256="a"*64)],NOW,now=NOW)


def test_future_mapping_does_not_backdate_external_export():
    value,profile,impact_path,linked,candidate=graph()
    late=NOW+timedelta(seconds=2)
    with pytest.raises(SourceShareError,match="source evidence"):
        build_beneficiary_graph(profile,impact_path,[linked],
            [replace(candidate,available_at=late)],NOW,now=late)
