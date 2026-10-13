"""5_2 never infer real counterparties from news or stock themes."""
from dataclasses import replace
from datetime import timedelta

import pytest

from newscatalystos.event_identity import CompanyBinding
from newscatalystos.supply_chain_graph import observed_supply_edge
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW, RSS, registry
from newscatalystos.new_source_adapter import parse_authorized_feed


def source():
    return parse_authorized_feed(
        registry(),"synthetic-government-feed",RSS,observed_at=NOW
    )[0]


def bind(row, id, at=NOW):
    return CompanyBinding(
        source_id=row.provider_id,
        source_document_id=row.document_id,
        id_namespace="SEC_CIK",
        company_id=id,
        mapped_ticker=None,
        evidence_sha256="b"*64,
        observed_at=at,
    )


def test_supplier_customer_are_explicit_claimed_edges_not_verified_trades():
    row=source()
    edge=observed_supply_edge(
        row,bind(row,"123456"),bind(row,"654321"),
        product_stage="ADVANCED_PACKAGING",
        relation_kind="REPORTED_DIRECT_TRANSACTION",
        reviewed_at=NOW,now=NOW,
    )
    assert edge.supplier_id=="123456"
    assert edge.customer_id=="654321"
    assert edge.product_stage=="ADVANCED_PACKAGING"
    assert edge.verified_real_transaction is False
    assert edge.evidence_status=="FEED_CLAIMED_RELATIONSHIP_UNVERIFIED"
    assert edge.source_event_sha256==row.event_id


def test_themed_association_not_forged_into_contract():
    row=source()
    a=observed_supply_edge(
        row,bind(row,"123456"),bind(row,"654321"),
        product_stage="MEMORY_HBM",relation_kind="THEMATIC_ASSOCIATION",
        reviewed_at=NOW,now=NOW,
    )
    b=observed_supply_edge(
        row,bind(row,"123456"),bind(row,"654321"),
        product_stage="MEMORY_HBM",relation_kind="REPORTED_DIRECT_TRANSACTION",
        reviewed_at=NOW,now=NOW,
    )
    assert a.edge_sha256!=b.edge_sha256
    assert not a.verified_real_transaction and not b.verified_real_transaction


def test_same_entity_or_unreviewed_id_rejected():
    row=source()
    with pytest.raises(SourceShareError,match="identical"):
        observed_supply_edge(
            row,bind(row,"123456"),bind(row,"123456"),
            product_stage="MEMORY_HBM",relation_kind="THEMATIC_ASSOCIATION",
            reviewed_at=NOW,now=NOW,
        )
    with pytest.raises(SourceShareError,match="source-document mismatch"):
        observed_supply_edge(
            row,replace(bind(row,"123456"),source_document_id="wrong"),
            bind(row,"654321"),
            product_stage="MEMORY_HBM",relation_kind="THEMATIC_ASSOCIATION",
            reviewed_at=NOW,now=NOW,
        )


def test_mapping_added_later_does_not_retroactively_change_relation():
    row=source()
    later=NOW+timedelta(minutes=3)
    with pytest.raises(SourceShareError,match="review predates"):
        observed_supply_edge(
            row,bind(row,"123456",later),bind(row,"654321"),
            product_stage="MEMORY_HBM",relation_kind="THEMATIC_ASSOCIATION",
            reviewed_at=NOW,now=later,
        )
    edge=observed_supply_edge(
        row,bind(row,"123456",later),bind(row,"654321"),
        product_stage="MEMORY_HBM",relation_kind="THEMATIC_ASSOCIATION",
        reviewed_at=later,now=later,
    )
    assert edge.available_at==later
    with pytest.raises(SourceShareError,match="unavailable"):
        edge.as_of(NOW,now=later)


def test_invalid_product_and_external_industry_rejected():
    row=source()
    with pytest.raises(SourceShareError,match="invalid stage"):
        observed_supply_edge(
            row,bind(row,"123456"),bind(row,"654321"),
            product_stage="BIOTECH",relation_kind="THEMATIC_ASSOCIATION",
            reviewed_at=NOW,now=NOW,
        )
