"""Synthetic licensed input -> actual private files -> separate v2 consumer.

These fixtures are not real publisher permissions or human gold labels.
"""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest

from newscatalystos.reviewed_beneficiary_delivery import (
    GRAPH_SCHEMAS, MARKERS, DELIVERY_SCHEMAS, _validate_reviewed_graph,
    prepare_publisher_beneficiary_graph, publish_reviewed_beneficiary_graph,
    consume_reviewed_beneficiary_graph,
)
from newscatalystos.official_relation_review import PUBLISHER_RELATION_STATUS
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from scripts import publish_reviewed_beneficiaries as publish_cli
from scripts import consume_reviewed_beneficiaries as consume_cli
from test_publisher_relation_intake import fixture, fingerprint, SENTENCE


def prepare(info, *, direction="POSITIVE", trigger="PACKAGING_CAPACITY", registry=None):
    root, archive, review, original_registry, _, at = info
    return prepare_publisher_beneficiary_graph(
        root, archive.version_id, archive.receipt_sha256, review,
        archive.payload_sha256, registry or original_registry,
        trigger=trigger, direction=direction, now=at,
    )


def publish(info, tmp_path, **kwargs):
    delivery = prepare(info, **kwargs)
    out = tmp_path / "outbox"
    result = publish_reviewed_beneficiary_graph(delivery, out, now=info[-1])
    return delivery, out, result


def consume(out, result, at):
    return consume_reviewed_beneficiary_graph(
        result.folder, out, result.payload_sha256, now=at, graph_version="v2",
    )


@pytest.mark.parametrize("kind", ["COMPANY_IR", "GOVERNMENT_POLICY"])
@pytest.mark.parametrize("relation", ["REPORTED_DIRECT_TRANSACTION", "ANNOUNCED_SUPPLY_PLAN"])
def test_full_publisher_path_preserves_origin_identity_plan_and_uncertainty(tmp_path, kind, relation):
    info = fixture(tmp_path, kind=kind, relation_kind=relation)
    inputs = fingerprint(tmp_path)
    delivery, out, publication = publish(info, tmp_path)
    after_publish = fingerprint(tmp_path)
    result = consume(out, publication, info[-1])
    assert fingerprint(tmp_path) == after_publish  # consumer is read-only
    assert all(after_publish[name] == digest for name, digest in inputs.items())
    assert delivery.graph.schema_version == GRAPH_SCHEMAS["v2"]
    marker = json.loads((publication.folder / "publication.json").read_bytes())
    assert marker["schema"] == MARKERS["v2"]
    assert result["schema"] == DELIVERY_SCHEMAS["v2"]
    assert result["status"] == "PUBLISHER_RELATION_CANDIDATE_NOT_COMMERCIALLY_VERIFIED"
    assert result["source_impact_direction"] == "POSITIVE"
    assert result["impact_evidence_level"] == "IMPACT_HYPOTHESIS_NOT_VERIFIED"
    row = result["candidate_edges"][0]
    assert row["source_kind"] == kind
    assert row["source_id"] == "synthetic-publisher"
    assert row["source_document_id"] == "press-1"
    assert (row["supplier_namespace"], row["supplier_id"]) == ("SEC_CIK", "111111")
    assert (row["customer_namespace"], row["customer_id"]) == ("SEC_CIK", "222222")
    assert row["relation_kind"] == relation and row["product_stage"] == "ADVANCED_PACKAGING"
    assert row["relation_proof_status"] == PUBLISHER_RELATION_STATUS
    assert row["document_sha256"] == info[1].payload_sha256
    assert row["source_available_at"] == result["available_at"] == info[-1].isoformat()
    assert row["candidate_category"] == (
        "ANNOUNCED_SUPPLY_PLAN_UNVERIFIED" if relation == "ANNOUNCED_SUPPLY_PLAN"
        else "POTENTIAL_BENEFICIARY_UNVERIFIED")
    assert not row["verified_real_transaction"] and not row["verified_real_benefit"]
    assert row["estimated_revenue_krw"] is None and result["market_action"] is None
    assert SENTENCE not in json.dumps(result)
    assert all(SENTENCE.encode() not in p.read_bytes() for p in publication.folder.iterdir())


@pytest.mark.parametrize("direction", ["NEGATIVE", "MIXED", "UNKNOWN"])
def test_plan_remains_plan_for_every_impact_direction(tmp_path, direction):
    info = fixture(tmp_path, relation_kind="ANNOUNCED_SUPPLY_PLAN")
    _, out, pub = publish(info, tmp_path, direction=direction)
    result = consume(out, pub, info[-1])
    assert result["source_impact_direction"] == direction
    assert result["candidate_edges"][0]["candidate_category"] == "ANNOUNCED_SUPPLY_PLAN_UNVERIFIED"


def test_stage_without_matching_impact_is_delivered_as_unknown(tmp_path):
    info = fixture(tmp_path, relation_kind="ANNOUNCED_SUPPLY_PLAN")
    _, out, pub = publish(info, tmp_path, trigger="MATERIAL_CONSUMPTION")
    row = consume(out, pub, info[-1])["candidate_edges"][0]
    assert row["candidate_category"] == "UNKNOWN_RELATIONSHIP"
    assert row["relation_kind"] == "ANNOUNCED_SUPPLY_PLAN"


@pytest.mark.parametrize("namespace,identifier", [("KRX_STOCK", "123456"), ("DART_CORP", "00000012")])
def test_publisher_mixed_company_namespaces_survive_delivery(tmp_path, namespace, identifier):
    info = fixture(tmp_path, kind="GOVERNMENT_POLICY")
    doc = json.loads(info[2].read_bytes())
    doc["customer"].update(id_namespace=namespace, company_id=identifier)
    info[2].write_text(json.dumps(doc))
    _, out, pub = publish(info, tmp_path)
    row = consume(out, pub, info[-1])["candidate_edges"][0]
    assert (row["customer_namespace"], row["customer_id"]) == (namespace, identifier)
    assert row["supplier_namespace"] == "SEC_CIK"


def test_consumer_v2_is_explicit_and_cannot_be_disguised_as_v1(tmp_path):
    info = fixture(tmp_path)
    _, out, pub = publish(info, tmp_path)
    with pytest.raises(SourceShareError, match="publication"):
        consume_reviewed_beneficiary_graph(pub.folder, out, pub.payload_sha256, now=info[-1])
    assert consume(out, pub, info[-1])["reviewed_candidate_count"] == 1
    marker_file = pub.folder / "publication.json"
    marker = json.loads(marker_file.read_bytes())
    marker["schema"] = MARKERS["v1"]
    marker_file.write_text(json.dumps(marker))
    with pytest.raises(SourceShareError, match="publication"):
        consume(out, pub, info[-1])
    with pytest.raises(SourceShareError, match="unverified semiconductor"):
        consume_reviewed_beneficiary_graph(pub.folder, out, pub.payload_sha256, now=info[-1])


@pytest.mark.parametrize("field,value", [
    ("relation_evidence_status", "OFFICIAL_DOCUMENT_REVIEWED_RELATION_NOT_TRANSACTION_VERIFIED"),
    ("candidate_category", "POTENTIAL_BENEFICIARY_UNVERIFIED"),
    ("source_kind", "SNS_TIP"), ("verified_real_benefit", True),
])
def test_invalid_plan_or_source_state_not_accepted(tmp_path, field, value):
    info = fixture(tmp_path, relation_kind="ANNOUNCED_SUPPLY_PLAN")
    delivery = prepare(info)
    data = json.loads(delivery.graph.JSON_bytes)
    data["edges"][0][field] = value
    with pytest.raises(SourceShareError):
        _validate_reviewed_graph(data, info[-1], graph_version="v2")


def test_old_or_modified_delivery_cannot_backdate_or_change_claim(tmp_path):
    info = fixture(tmp_path)
    _, out, pub = publish(info, tmp_path)
    later = info[-1] + timedelta(hours=1)
    result = consume(out, pub, later)
    assert result["available_at"] == later.isoformat()
    assert result["candidate_edges"][0]["source_available_at"] == info[-1].isoformat()
    with pytest.raises(SourceShareError, match="before consumer verification"):
        consume_reviewed_beneficiary_graph(pub.folder, out, pub.payload_sha256,
            now=later, decision_at=info[-1], graph_version="v2")
    payload = pub.folder / "beneficiary_graph.json"
    payload.write_bytes(payload.read_bytes() + b"modified")
    with pytest.raises(SourceShareError, match="SHA|independent pin"):
        consume(out, pub, later)


def test_repeated_publication_preserves_original_and_leaves_no_staging(tmp_path):
    info = fixture(tmp_path)
    delivery, out, pub = publish(info, tmp_path)
    before = fingerprint(out)
    with pytest.raises(SourceShareError, match="already published"):
        publish_reviewed_beneficiary_graph(delivery, out, now=info[-1])
    assert fingerprint(out) == before
    assert not list(out.glob(".reviewed_staging_*"))


def test_missing_rights_blocks_only_this_publisher_input(tmp_path, monkeypatch):
    import socket
    info = fixture(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("offline handoff attempted network access")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    revoked = ProviderRegistry((replace(info[3].providers[0], approved=False),))
    with pytest.raises(SourceShareError):
        prepare(info, registry=revoked)
    assert not (tmp_path / "outbox").exists()
    _, out, pub = publish(info, tmp_path)
    assert consume(out, pub, info[-1])["reviewed_candidate_count"] == 1


def publisher_argv(info, out):
    return ["--input-kind", "publisher", "--archive-root", str(info[0]),
            "--archive-version", info[1].version_id,
            "--archive-receipt-sha256", info[1].receipt_sha256,
            "--review-json", str(info[2]), "--registry", str(info[4]),
            "--document-sha256", info[1].payload_sha256,
            "--trigger", "PACKAGING_CAPACITY", "--direction", "POSITIVE",
            "--out-root", str(out)]


def test_real_separate_python_cli_processes_publish_then_consume(tmp_path):
    info = fixture(tmp_path, relation_kind="ANNOUNCED_SUPPLY_PLAN")
    before = fingerprint(tmp_path)
    project = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(project / "src"), PYTHONDONTWRITEBYTECODE="1")
    out = tmp_path / "subprocess_outbox"
    producer = subprocess.run([sys.executable, str(project / "scripts/publish_reviewed_beneficiaries.py"),
                              *publisher_argv(info, out)], cwd=tmp_path,
                             env=env, capture_output=True, text=True, timeout=20)
    assert producer.returncode == 0, producer.stderr + producer.stdout
    produced = json.loads(producer.stdout)
    assert produced["graph_schema"] == GRAPH_SCHEMAS["v2"]
    assert produced["network_calls"] == 0
    after_publish = fingerprint(tmp_path)
    consumer_args = [sys.executable, str(project / "scripts/consume_reviewed_beneficiaries.py"),
                     "--graph-version", "v2", "--folder", produced["outbox_folder"],
                     "--out-root", str(out), "--expected-sha256", produced["payload_sha256"]]
    consumer = subprocess.run(consumer_args, cwd=tmp_path, env=env,
                             capture_output=True, text=True, timeout=20)
    assert consumer.returncode == 0, consumer.stderr + consumer.stdout
    consumed = json.loads(consumer.stdout)
    assert consumed["payload_sha256"] == produced["payload_sha256"]
    assert consumed["candidate_edges"][0]["relation_kind"] == "ANNOUNCED_SUPPLY_PLAN"
    assert consumed["candidate_edges"][0]["candidate_category"] == "ANNOUNCED_SUPPLY_PLAN_UNVERIFIED"
    assert all(after_publish[k] == v for k, v in before.items())
    assert fingerprint(tmp_path) == after_publish


def test_cli_modes_reject_mixed_inputs_without_creating_output(tmp_path):
    info = fixture(tmp_path)
    out = tmp_path / "outbox"
    opts = publish_cli.parser().parse_args(publisher_argv(info, out))
    opts.publication = tmp_path / "unrelated_filing"
    assert publish_cli.evaluate(opts)[0] == 4
    assert not out.exists()
    opts.publication = None; opts.input_kind = "official"
    assert publish_cli.evaluate(opts)[0] == 4
    assert not out.exists()
    assert consume_cli.parser().parse_args([
        "--folder", str(out), "--out-root", str(out), "--expected-sha256", "a"*64,
    ]).graph_version == "v1"
