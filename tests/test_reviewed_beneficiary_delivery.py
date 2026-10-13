"""Offline 5_2->5_5 private handoff: synthetic documents only, never trading facts."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import argparse
import json
import stat

import pytest

from newscatalystos.reviewed_beneficiary_delivery import (
    SCHEMA, prepare_reviewed_beneficiary_graph,
    publish_reviewed_beneficiary_graph, consume_reviewed_beneficiary_graph,
)
from newscatalystos.source_share import SourceShareError
from scripts.consume_reviewed_beneficiaries import evaluate as consumer_cli
from test_official_relation_intake import fixture


def prepare(info, *, now=None, direction="UNKNOWN", trigger="PACKAGING_CAPACITY"):
    pub, root, payload_sha, review, document, document_pin, at = info
    return prepare_reviewed_beneficiary_graph(
        pub, root, payload_sha, review, document, document_pin,
        trigger=trigger, direction=direction,
        evidence_note="Reviewer suspects a possible stage effect; actual volume/sales unknown",
        now=now or at,
    )


def test_official_review_to_graph_is_candidate_only_with_exact_review_shas(tmp_path):
    info = fixture(tmp_path)
    report = prepare(info)
    assert report.graph.items_count == 1
    data = json.loads(report.graph.JSON_bytes)
    assert data["schema"] == "newscatalyst.beneficiary_graph.v1"
    assert data["industry_id"] == "SEMICONDUCTOR"
    assert data["certified_beneficiary_count"] == 0
    assert data["source_impact_trigger"] == "PACKAGING_CAPACITY"
    relation = data["edges"][0]
    assert relation["relation_evidence_status"].startswith("OFFICIAL_DOCUMENT_REVIEWED")
    assert relation["candidate_category"] == "EFFECT_DIRECTION_UNKNOWN"
    assert relation["document_sha256"] == info[5]
    assert relation["evidence_sha256"] == relation["document_sha256"]
    assert len(relation["review_proof_sha256"]) == 64
    assert relation["verified_real_benefit"] is False
    assert relation["revenue_contribution_krw"] is None
    assert "Supplier Alpha" not in report.graph.JSON_bytes.decode()


def test_positive_impact_is_still_only_unverified_hypothesis(tmp_path):
    report = prepare(fixture(tmp_path), direction="POSITIVE")
    data = json.loads(report.graph.JSON_bytes)
    assert data["edges"][0]["candidate_category"] == "POTENTIAL_BENEFICIARY_UNVERIFIED"
    assert data["edges"][0]["verified_real_benefit"] is False
    assert data["certified_beneficiary_count"] == 0


@pytest.mark.parametrize("source", ["dart-disclosures", "sec-submissions"])
def test_publish_and_consume_from_unmodified_private_outbox(tmp_path, source):
    info = fixture(tmp_path, source)
    report = prepare(info)
    outbox = tmp_path / "outbox"
    pub = publish_reviewed_beneficiary_graph(report, outbox, now=info[6])
    assert pub.folder.name == "reviewed_candidate_" + report.publication_sha256
    assert pub.candidate_count == 1
    assert stat.S_IMODE(pub.folder.stat().st_mode) == 0o700
    assert stat.S_IMODE((pub.folder / "beneficiary_graph.json").stat().st_mode) == 0o600
    mark = json.loads((pub.folder / "publication.json").read_bytes())
    assert mark["schema"] == "newscatalyst.reviewed_beneficiary_publication.v1"
    assert mark["verified_real_benefit_count"] == 0
    assert mark["source_document_text_included"] is False
    delivered = consume_reviewed_beneficiary_graph(
        pub.folder, outbox, pub.payload_sha256, now=info[6], decision_at=info[6],
    )
    assert delivered["status"] == "OFFICIAL_RELATION_CANDIDATE_NOT_COMMERCIALLY_VERIFIED"
    assert delivered["schema"] == SCHEMA
    assert delivered["reviewed_candidate_count"] == 1
    assert delivered["verified_real_transaction_count"] == 0
    assert delivered["verified_real_benefit_count"] == 0
    assert delivered["market_action"] is None
    assert len(delivered["candidate_edges"]) == 1
    identity = delivered["candidate_edges"][0]
    assert identity["supplier_namespace"] == (
        "SEC_CIK" if source == "sec-submissions" else "DART_CORP"
    )
    assert identity["supplier_id"] != identity["customer_id"]
    assert identity["relation_kind"] == "REPORTED_DIRECT_TRANSACTION"
    assert identity["product_stage"] == "ADVANCED_PACKAGING"
    assert identity["verified_real_transaction"] is False
    assert identity["verified_real_benefit"] is False
    assert identity["estimated_revenue_krw"] is None
    assert "Supplier Alpha" not in json.dumps(delivered)
    # Publication directory and original official text remain immutable.
    assert info[4].exists() and b"Supplier Alpha" in info[4].read_bytes()
    assert not any(".reviewed_staging_" in p.name for p in outbox.iterdir())


def test_immutable_outbox_cannot_be_overwritten_or_backdated(tmp_path):
    info = fixture(tmp_path)
    report = prepare(info)
    outbox = tmp_path / "outbox"
    original = publish_reviewed_beneficiary_graph(report, outbox, now=info[6])
    with pytest.raises(SourceShareError, match="already published"):
        publish_reviewed_beneficiary_graph(report, outbox, now=info[6])
    past = info[6] - timedelta(seconds=1)
    with pytest.raises(SourceShareError, match="PIT available"):
        consume_reviewed_beneficiary_graph(
            original.folder, outbox, report.publication_sha256,
            now=info[6], decision_at=past,
        )


def test_wrong_consumer_pin_and_modified_graph_blocked(tmp_path):
    info = fixture(tmp_path)
    report = prepare(info)
    outbox = tmp_path / "outbox"
    publication = publish_reviewed_beneficiary_graph(report, outbox, now=info[6])
    with pytest.raises(SourceShareError, match="permitted private"):
        consume_reviewed_beneficiary_graph(
            publication.folder, outbox, "f" * 64, now=info[6],
        )
    raw = publication.folder / "beneficiary_graph.json"
    raw.write_bytes(raw.read_bytes() + b"tampered")
    with pytest.raises(SourceShareError, match="differs from independent"):
        consume_reviewed_beneficiary_graph(
            publication.folder, outbox, report.publication_sha256, now=info[6],
        )


def test_missing_real_review_refuses_to_create_output(tmp_path):
    info = fixture(tmp_path)
    args = list(info)
    args[5] = "0" * 64
    with pytest.raises(SourceShareError, match="SHA untrusted"):
        prepare(args)
    outbox = tmp_path / "outbox"
    assert not outbox.exists()


def test_review_graph_stage_not_in_trigger_is_unknown_not_fake_benefit(tmp_path):
    info = fixture(tmp_path)
    graph = prepare(info, trigger="MATERIAL_CONSUMPTION", direction="POSITIVE")
    data = json.loads(graph.graph.JSON_bytes)
    assert data["edges"][0]["candidate_category"] == "UNKNOWN_RELATIONSHIP"
    assert data["certified_beneficiary_count"] == 0


def test_consumer_cli_returns_only_status_and_no_private_names(tmp_path, monkeypatch):
    info = fixture(tmp_path)
    report = prepare(info)
    outbox = tmp_path / "outbox"
    published = publish_reviewed_beneficiary_graph(report, outbox, now=info[6])
    # CLI uses actual clock; the fixture review is safely in the past.
    # Synthetic published() fixtures can be seconds ahead of real wall time.
    # The injected clock stays deterministic and cannot certify real PIT.
    from scripts import consume_reviewed_beneficiaries as cmd
    real_reader = cmd.consume_reviewed_beneficiary_graph
    monkeypatch.setattr(cmd, "consume_reviewed_beneficiary_graph",
        lambda folder, root, pin: real_reader(folder, root, pin, now=info[6]))
    opts = argparse.Namespace(
        folder=published.folder, out_root=outbox,
        expected_sha256=report.publication_sha256,
    )
    code, message = consumer_cli(opts)
    assert code == 0, message
    assert message["reviewed_candidate_count"] == 1
    assert message["verified_real_benefit_count"] == 0
    assert message["candidate_edges"][0]["relation_kind"] == "REPORTED_DIRECT_TRANSACTION"
    assert message["candidate_edges"][0]["verified_real_benefit"] is False
    assert "Supplier Alpha" not in json.dumps(message)
    opts.expected_sha256 = "0" * 64
    code, message = consumer_cli(opts)
    assert code == 4 and message["status"] == "READONLY_CANDIDATE_DELIVERY_UNAVAILABLE"


def test_missing_independent_document_pin_cannot_masquerade_as_real_handoff(tmp_path):
    info = fixture(tmp_path)
    info[4].unlink()
    with pytest.raises(SourceShareError, match="unavailable"):
        prepare(info)
    assert not (tmp_path / "outbox").exists()


def test_missing_consumer_outbox_never_creates_directories(tmp_path):
    missing = tmp_path / "untouched-consumer-outbox"
    assert not missing.exists()
    with pytest.raises(SourceShareError, match="handoff root unavailable"):
        consume_reviewed_beneficiary_graph(
            missing / ("reviewed_candidate_" + "a" * 64),
            missing, "a" * 64,
        )
    assert not missing.exists()


def test_publisher_rejects_cross_project_outbox_before_writing(tmp_path):
    info = fixture(tmp_path)
    graph = prepare(info)
    output = tmp_path / "eraleader" / "output"
    with pytest.raises(SourceShareError, match="NewsCatalystOS private handoff"):
        publish_reviewed_beneficiary_graph(graph, output, now=info[6])
    assert not output.exists()


def test_cli_without_actual_document_fails_closed(tmp_path):
    from scripts.publish_reviewed_beneficiaries import evaluate as publisher_cli
    info = fixture(tmp_path)
    opts = argparse.Namespace(
        publication=info[0], publication_root=info[1], payload_sha256=info[2],
        review_json=info[3], document_text=tmp_path / "no_official_document.txt",
        document_sha256=info[5], trigger="PACKAGING_CAPACITY",
        direction="UNKNOWN",
        evidence_note="Explicitly unverified supply-market impact",
        out_root=tmp_path / "outbox",
    )
    code, report = publisher_cli(opts)
    assert code == 4 and report["status"] == "REVIEWED_CANDIDATE_DATA_UNAVAILABLE"
    assert report["real_beneficiary_verified_count"] == 0
    assert report["network_calls"] == 0
    assert not opts.out_root.exists()


def test_tampered_consumer_company_identity_is_not_accepted(tmp_path):
    info = fixture(tmp_path)
    graph = prepare(info)
    outbox = tmp_path / "outbox"
    published = publish_reviewed_beneficiary_graph(graph, outbox, now=info[6])
    value = json.loads(graph.graph.JSON_bytes)
    value["edges"][0]["supplier_namespace"] = "KRX_STOCK"
    from newscatalystos.reviewed_beneficiary_delivery import _validate_reviewed_graph
    with pytest.raises(SourceShareError, match="roles/stage"):
        _validate_reviewed_graph(value, info[6])
    assert published.folder.exists()
