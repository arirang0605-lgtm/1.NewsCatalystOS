"""Offline 5_2 intake uses a real verified-published *fixture*, not a claim of real trades."""
from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
import argparse
import json

import pytest

from newscatalystos.event_identity import CompanyBinding
from newscatalystos.official_relation_intake import (
    SCHEMA, read_official_relation_intake,
)
from newscatalystos.official_relation_review import OfficialRelationReview, RELATION_STATUS
from newscatalystos.operational_observations import load_operational_observations
from newscatalystos.source_share import SourceShareError
from scripts.review_supply_relation import evaluate
from test_published_observations import published

SENTENCE = (
    "Supplier Alpha agrees to supply advanced packaging components to "
    "Customer Beta under a direct supply contract."
)
BODY = ("Synthetic SEC/DART review fixture only: " + SENTENCE).encode()
PIN = sha256(BODY).hexdigest()


def _plain(record):
    return {k: v.isoformat() if isinstance(v, datetime) else v
            for k, v in asdict(record).items()}


def fixture(tmp_path, source="dart-disclosures"):
    pub, root, payload_sha, at, *_ = published(tmp_path, source)
    observation = load_operational_observations(pub, root, payload_sha, now=at)
    row = observation.observations[0]
    earlier = at - timedelta(minutes=1)
    namespace = "SEC_CIK" if source == "sec-submissions" else "DART_CORP"
    first = "123456" if namespace == "SEC_CIK" else "00000001"
    second = "654321" if namespace == "SEC_CIK" else "00000002"
    supplier = CompanyBinding(row.source_id, row.source_document_id,
                              namespace, first, None, "b" * 64, earlier)
    customer = CompanyBinding(row.source_id, row.source_document_id,
                              namespace, second, None, "c" * 64, earlier)
    review = OfficialRelationReview(
        row.source_id, row.source_document_id, row.evidence_id,
        row.receipt_sha256, PIN, earlier, earlier, at,
        "Supplier Alpha", "Customer Beta", SENTENCE, "ADVANCED_PACKAGING",
    )
    content = {
        "schema": SCHEMA,
        "review": _plain(review),
        "supplier": _plain(supplier),
        "customer": _plain(customer),
    }
    vault = tmp_path / "review-vault"
    vault.mkdir(mode=0o700)
    vault.chmod(0o700)
    review_path = vault / "review.json"
    document_path = vault / "document.txt"
    review_path.write_text(json.dumps(content), encoding="utf-8")
    document_path.write_bytes(BODY)
    review_path.chmod(0o600)
    document_path.chmod(0o600)
    return (pub, root, payload_sha, review_path, document_path, PIN, at)


def run(info, *, now=None, pin=None):
    pub, root, payload_sha, review_path, doc_path, trusted_sha, at = info
    return read_official_relation_intake(
        pub, root, payload_sha, review_path, doc_path,
        trusted_sha if pin is None else pin, now=now or at,
    )


def test_private_offline_review_consumes_completed_v2_publication(tmp_path):
    info = fixture(tmp_path)
    original_document = info[4].read_bytes()
    before = info[0].joinpath("observations.json").read_bytes()
    edge = run(info)
    assert edge.evidence_status == RELATION_STATUS
    assert edge.relation_kind == "REPORTED_DIRECT_TRANSACTION"
    assert edge.document_sha256 == PIN
    assert edge.available_at == info[6]
    assert edge.verified_real_transaction is False
    assert edge.review_proof_sha256 != PIN
    assert info[4].read_bytes() == original_document
    assert info[0].joinpath("observations.json").read_bytes() == before


def test_late_consumer_read_cannot_backdate_prior_human_review(tmp_path):
    info = fixture(tmp_path)
    later = info[6] + timedelta(hours=1)
    edge = run(info, now=later)
    assert edge.available_at == later
    assert edge.last_reviewed_at == later
    with pytest.raises(SourceShareError, match="unavailable"):
        edge.as_of(info[6], now=later)
    assert run(info).edge_sha256 != edge.edge_sha256


def test_document_pin_and_source_payload_pins_are_both_required(tmp_path):
    info = fixture(tmp_path)
    with pytest.raises(SourceShareError, match="SHA untrusted"):
        run(info, pin="0" * 64)
    info[4].write_bytes(BODY + b" tampered")
    with pytest.raises(SourceShareError, match="SHA untrusted"):
        run(info)
    info[4].write_bytes(BODY)
    args = list(info)
    args[2] = "1" * 64
    with pytest.raises(SourceShareError, match="unverified or incomplete"):
        run(args)


def test_bad_private_permissions_missing_document_and_shape_rejected(tmp_path):
    info = fixture(tmp_path)
    info[3].chmod(0o644)
    with pytest.raises(SourceShareError, match="owner-only"):
        run(info)
    info[3].chmod(0o600)
    info[4].unlink()
    with pytest.raises(SourceShareError, match="unavailable"):
        run(info)
    info[4].write_bytes(BODY)
    info[4].chmod(0o600)
    malformed = json.loads(info[3].read_text())
    malformed["review"]["source_document_id"] = "different-filing"
    info[3].write_text(json.dumps(malformed))
    info[3].chmod(0o600)
    with pytest.raises(SourceShareError, match="uniquely verified"):
        run(info)


def test_cli_uses_private_readonly_inputs_and_only_reports_sha(tmp_path):
    info = fixture(tmp_path)
    opts = argparse.Namespace(publication=info[0], publication_root=info[1],
                              payload_sha256=info[2], review_json=info[3],
                              document_text=info[4], document_sha256=info[5])
    code, result = evaluate(opts, now=info[6])
    assert code == 0
    assert result["status"] == "OFFICIAL_DOCUMENT_REVIEW_CANDIDATE_ONLY"
    assert result["verified_real_transaction_count"] == 0
    assert "Supplier Alpha" not in json.dumps(result)
    opts.document_sha256 = "0" * 64
    code, result = evaluate(opts, now=info[6])
    assert code == 4 and result["status"] == "DATA_UNAVAILABLE"
    assert "Supplier Alpha" not in json.dumps(result)


def test_sec_filing_metadata_uses_sec_company_cik_only(tmp_path):
    info = fixture(tmp_path, "sec-submissions")
    linked = run(info)
    assert linked.source_id == "sec-submissions"
    assert linked.supplier_namespace == linked.customer_namespace == "SEC_CIK"
    assert linked.verified_real_transaction is False


def test_intake_edge_flows_into_existing_hypothesis_and_graph_without_sales(tmp_path):
    from newscatalystos.beneficiary_classification import classify_semiconductor_beneficiary
    from newscatalystos.beneficiary_graph_contract import build_beneficiary_graph
    from newscatalystos.semiconductor_impact import propagate_semiconductor_claim
    from newscatalystos.semiconductor_profile import build_semiconductor_profile

    info = fixture(tmp_path)
    linked = run(info)
    profile = build_semiconductor_profile()
    hypothesized = propagate_semiconductor_claim(
        profile, "d" * 64, "PACKAGING_CAPACITY",
        direction="POSITIVE", evidence_note="Synthetic impact hypothesis only",
        source_available_at=linked.available_at, reviewed_at=info[6], now=info[6],
    )
    candidate = classify_semiconductor_beneficiary(
        linked, hypothesized, reviewed_at=info[6], now=info[6],
    )
    graph = build_beneficiary_graph(
        profile, hypothesized, [linked], [candidate], info[6], now=info[6],
    )
    node = json.loads(graph.JSON_bytes)["edges"][0]
    assert node["document_sha256"] == PIN
    assert node["review_proof_sha256"] == linked.review_proof_sha256
    assert node["relation_evidence_status"] == RELATION_STATUS
    assert node["verified_real_benefit"] is False
    assert node["revenue_contribution_krw"] is None
