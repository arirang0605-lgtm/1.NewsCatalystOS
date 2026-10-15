"""Synthetic licensed documents and extracted evidence; no live permissions."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.beneficiary_classification import classify_semiconductor_beneficiary
from newscatalystos.beneficiary_graph_contract import build_beneficiary_graph, PUBLISHER_GRAPH_SCHEMA
from newscatalystos.evidence_archive import archive_evidence
from newscatalystos.event_identity import CompanyBinding
from newscatalystos.official_relation_intake import PUBLISHER_SCHEMA, read_publisher_relation_intake
from newscatalystos.official_relation_review import OfficialRelationReview, PUBLISHER_RELATION_STATUS
from newscatalystos.provider_registry import ProviderRegistry, SCHEMA as REGISTRY_SCHEMA
from newscatalystos.reviewed_beneficiary_delivery import _validate_reviewed_graph
from newscatalystos.semiconductor_impact import propagate_semiconductor_claim
from newscatalystos.semiconductor_profile import build_semiconductor_profile
from newscatalystos.source_share import SourceShareError
from scripts.review_supply_relation import parser, evaluate
from test_new_source_adapter import NOW, registry

SENTENCE = "Alpha Devices will supply advanced packaging services to Beta Systems under the announced supply contract."
BODY = ("SYNTHETIC LICENSED DOCUMENT FOR TESTS ONLY. " + SENTENCE).encode()


def plain(value):
    return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in asdict(value).items()}


def fixture(tmp_path, *, kind="COMPANY_IR", relation_kind="REPORTED_DIRECT_TRANSACTION"):
    provider = replace(registry().providers[0], provider_id="synthetic-publisher",
                       kind=kind, grant="WRITTEN_LICENSE", allow_full_text_storage=True)
    reg = ProviderRegistry((provider,))
    root = tmp_path / "private_archive"
    archive = archive_evidence(root, provider, "press-1", BODY,
                               scope="LICENSED_SOURCE_BYTES", now=NOW)
    reviewed = NOW + timedelta(seconds=2)
    supplier = CompanyBinding(provider.provider_id, "press-1", "SEC_CIK", "111111",
                              None, "a"*64, NOW)
    customer = CompanyBinding(provider.provider_id, "press-1", "SEC_CIK", "222222",
                              None, "b"*64, NOW)
    review = OfficialRelationReview(
        provider.provider_id, "press-1", archive.version_id, archive.receipt_sha256,
        archive.payload_sha256, NOW, NOW + timedelta(seconds=1), reviewed,
        "Alpha Devices", "Beta Systems", SENTENCE, "ADVANCED_PACKAGING",
    )
    data = {"schema": PUBLISHER_SCHEMA,
            "relation_kind": relation_kind, "review": plain(review),
            "supplier": plain(supplier), "customer": plain(customer)}
    vault = tmp_path / "private_review"; vault.mkdir(mode=0o700)
    path = vault / "review.json"; path.write_text(json.dumps(data)); path.chmod(0o600)
    regpath = vault / "registry.json"
    regpath.write_text(json.dumps({"schema": REGISTRY_SCHEMA, "providers": [plain(provider)]}))
    regpath.chmod(0o600)
    return root, archive, path, reg, regpath, reviewed + timedelta(seconds=1)


def run(info, *, reg=None, now=None, receipt=None, document=None):
    root, archive, review, original, _, at = info
    return read_publisher_relation_intake(root, archive.version_id,
        receipt or archive.receipt_sha256, review, document or archive.payload_sha256,
        reg or original, now=now or at)


def graph(edge, at, direction="POSITIVE"):
    profile = build_semiconductor_profile()
    impact = propagate_semiconductor_claim(profile, edge.source_event_sha256,
        "PACKAGING_CAPACITY", direction=direction, evidence_note="Synthetic hypothesis only",
        source_available_at=edge.available_at, reviewed_at=at, now=at)
    candidate = classify_semiconductor_beneficiary(edge, impact, reviewed_at=at, now=at)
    result = build_beneficiary_graph(profile, impact, (edge,), (candidate,), at, now=at)
    return candidate, result


def fingerprint(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("kind", ["COMPANY_IR", "GOVERNMENT_POLICY"])
def test_licensed_publisher_enters_existing_graph_without_filing_substitution(tmp_path, kind):
    info = fixture(tmp_path, kind=kind)
    before = fingerprint(tmp_path)
    edge = run(info)
    candidate, result = graph(edge, info[-1])
    assert edge.source_id == "synthetic-publisher" and edge.document_id == "press-1"
    assert edge.evidence_status == PUBLISHER_RELATION_STATUS
    assert edge.document_sha256 == info[1].payload_sha256
    assert edge.source_event_sha256 == info[1].version_id
    assert not edge.verified_real_transaction and not candidate.verified_real_benefit
    payload = json.loads(result.JSON_bytes)
    assert result.schema_version == payload["schema"] == PUBLISHER_GRAPH_SCHEMA
    assert payload["edges"][0]["relation_evidence_status"] == PUBLISHER_RELATION_STATUS
    assert payload["edges"][0]["revenue_contribution_krw"] is None
    assert SENTENCE not in result.JSON_bytes.decode()
    assert fingerprint(tmp_path) == before
    with pytest.raises(SourceShareError, match="unverified semiconductor"):
        _validate_reviewed_graph(payload, info[-1])


@pytest.mark.parametrize("direction", ["POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN"])
def test_future_supply_plan_is_distinct_from_active_transaction(tmp_path, direction):
    info = fixture(tmp_path, relation_kind="ANNOUNCED_SUPPLY_PLAN")
    edge = run(info)
    candidate, result = graph(edge, info[-1], direction)
    assert candidate.category == "ANNOUNCED_SUPPLY_PLAN_UNVERIFIED"
    assert edge.relation_kind == "ANNOUNCED_SUPPLY_PLAN"
    assert candidate.realized_revenue_krw is None
    assert json.loads(result.JSON_bytes)["edges"][0]["relation_kind"] == "ANNOUNCED_SUPPLY_PLAN"


@pytest.mark.parametrize("patch", [
    {"approved": False}, {"allow_full_text_storage": False},
    {"grant": "OFFICIAL_TERMS_REVIEWED"}, {"expires_at": NOW + timedelta(seconds=1)},
    {"kind": "LICENSED_NEWS"},
])
def test_absent_revoked_or_inadequate_storage_rights_block_input(tmp_path, patch):
    info = fixture(tmp_path)
    changed = ProviderRegistry((replace(info[3].providers[0], **patch),))
    with pytest.raises(SourceShareError):
        run(info, reg=changed)


@pytest.mark.parametrize("field,value", [
    ("review_origin", "REMOVED_FIELD"),
    ("review_origin", "UNASSIGNED"), ("relation_kind", "THEMATIC_ASSOCIATION"),
    ("schema", "newscatalyst.public_relation_reference.v1"),
])
def test_unexpected_fields_and_invalid_evidence_schema_are_rejected(tmp_path, field, value):
    info = fixture(tmp_path)
    data = json.loads(info[2].read_text()); data[field] = value
    info[2].write_text(json.dumps(data))
    with pytest.raises(SourceShareError, match="evidence schema"):
        run(info)


@pytest.mark.parametrize("field,value", [
    ("source_document_id", "unrelated-sec-filing"),
    ("source_evidence_id", "f"*64), ("source_receipt_sha256", "e"*64),
])
def test_source_review_must_match_the_actual_document_archive(tmp_path, field, value):
    info = fixture(tmp_path)
    data = json.loads(info[2].read_text()); data["review"][field] = value
    info[2].write_text(json.dumps(data))
    with pytest.raises(SourceShareError, match="evidence does not match"):
        run(info)


def test_late_consumption_cannot_backdate_licensed_document(tmp_path):
    info = fixture(tmp_path); later = info[-1] + timedelta(hours=2)
    edge = run(info, now=later)
    assert edge.available_at == later
    with pytest.raises(SourceShareError, match="unavailable"):
        edge.as_of(info[-1], now=later)
    with pytest.raises(SourceShareError):
        run(info, now=NOW)


def test_independent_document_and_receipt_pins_required(tmp_path):
    info = fixture(tmp_path)
    for kw in ({"receipt": "a"*64}, {"document": "b"*64}):
        with pytest.raises(SourceShareError, match="independent archive pins"):
            run(info, **kw)
    body = info[0] / info[1].version_id / "payload.bin"
    body.write_bytes(BODY + b" MODIFIED")
    with pytest.raises(SourceShareError, match="SHA"):
        run(info)


def test_missing_archive_not_created(tmp_path):
    info = fixture(tmp_path)
    absent = tmp_path / "not_an_archive"
    with pytest.raises(SourceShareError):
        read_publisher_relation_intake(absent, info[1].version_id,
            info[1].receipt_sha256, info[2], info[1].payload_sha256, info[3], now=info[-1])
    assert not absent.exists()


def test_mixed_company_namespaces_are_bound_to_publisher_not_sec_format(tmp_path):
    info = fixture(tmp_path, kind="GOVERNMENT_POLICY")
    data = json.loads(info[2].read_text())
    data["customer"].update(id_namespace="KRX_STOCK", company_id="123456")
    info[2].write_text(json.dumps(data))
    edge = run(info)
    assert (edge.supplier_namespace, edge.customer_namespace) == ("SEC_CIK", "KRX_STOCK")
    assert graph(edge, info[-1])[1].schema_version == PUBLISHER_GRAPH_SCHEMA


def cli(info):
    root, archive, review, _, reg, _ = info
    return parser().parse_args([
        "--input-kind", "publisher", "--archive-root", str(root),
        "--archive-version", archive.version_id,
        "--archive-receipt-sha256", archive.receipt_sha256,
        "--registry", str(reg), "--review-json", str(review),
        "--document-sha256", archive.payload_sha256,
    ])


def test_existing_review_cli_routes_explicit_publisher_type(tmp_path):
    info = fixture(tmp_path, relation_kind="ANNOUNCED_SUPPLY_PLAN")
    opts = cli(info); code, output = evaluate(opts, now=info[-1])
    assert code == 0 and output["status"] == "PUBLISHER_DOCUMENT_REVIEW_CANDIDATE_ONLY"
    assert output["relation_kind"] == "ANNOUNCED_SUPPLY_PLAN"
    assert output["verified_real_transaction_count"] == 0
    assert SENTENCE not in json.dumps(output)
    opts.publication = tmp_path / "fake-sec"
    assert evaluate(opts, now=info[-1])[0] == 4


def test_official_mode_does_not_accept_publisher_archive_flags(tmp_path):
    info = fixture(tmp_path); opts = cli(info); opts.input_kind = "official"
    assert evaluate(opts, now=info[-1])[0] == 4


def test_metadata_only_archive_cannot_stand_in_for_licensed_document(tmp_path):
    info = fixture(tmp_path)
    meta = json.dumps({"event_id": "f"*64, "source_id": "synthetic-publisher",
                       "source_url": "https://ir.example.org/press", "headline": "Reference only"}).encode()
    archived = archive_evidence(info[0], info[3].providers[0], "meta-1", meta, now=NOW)
    with pytest.raises(SourceShareError, match="licensed document"):
        read_publisher_relation_intake(info[0], archived.version_id, archived.receipt_sha256,
            info[2], archived.payload_sha256, info[3], now=info[-1])


def test_corrected_relation_uses_new_archive_version_without_overwriting_plan(tmp_path):
    info = fixture(tmp_path, relation_kind="ANNOUNCED_SUPPLY_PLAN")
    first = run(info)
    saved_body = (info[0] / info[1].version_id / "payload.bin").read_bytes()
    later = NOW + timedelta(hours=1)
    sentence = "Alpha Devices supplied advanced packaging services to Beta Systems under the supply contract."
    revised = archive_evidence(info[0], info[3].providers[0], "press-1", sentence.encode(),
        scope="LICENSED_SOURCE_BYTES", supersedes_version_id=info[1].version_id, now=later)
    data = json.loads(info[2].read_text())
    data["relation_kind"] = "REPORTED_DIRECT_TRANSACTION"
    data["review"].update(source_evidence_id=revised.version_id,
        source_receipt_sha256=revised.receipt_sha256, document_sha256=revised.payload_sha256,
        document_observed_at=later.isoformat(), pin_observed_at=later.isoformat(),
        reviewed_at=later.isoformat(), evidence_statement=sentence)
    new_review = info[2].parent / "revised.json"
    new_review.write_text(json.dumps(data)); new_review.chmod(0o600)
    second = read_publisher_relation_intake(info[0], revised.version_id,
        revised.receipt_sha256, new_review, revised.payload_sha256, info[3], now=later)
    assert first.edge_sha256 != second.edge_sha256
    assert second.document_sha256 != first.document_sha256
    assert first.relation_kind == "ANNOUNCED_SUPPLY_PLAN"
    assert second.relation_kind == "REPORTED_DIRECT_TRANSACTION"
    assert not second.verified_real_transaction
    assert (info[0] / info[1].version_id / "payload.bin").read_bytes() == saved_body
    assert revised.supersedes_version_id == info[1].version_id


def test_intake_and_graph_do_not_call_any_network(tmp_path, monkeypatch):
    import socket
    info = fixture(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("document review must be offline")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert graph(run(info), info[-1])[1].items_count == 1
