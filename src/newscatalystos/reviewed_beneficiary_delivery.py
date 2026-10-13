"""5_2->5_5: deliver a human-reviewed official relation as an unverified graph.

No automatic company selection, fabricated revenue, API calls or EraLeader
writes. Official document text stays in owner-private operator input; only
SHA-bound *hypotheses* leave this producer. Read-only downstream consumers
supply their own expected SHA and must respect first-observed PIT.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import stat
import tempfile

from .beneficiary_classification import classify_semiconductor_beneficiary
from .beneficiary_graph_contract import BeneficiaryGraph, build_beneficiary_graph
from .evidence_archive import _private_root, _read_once, _write_new
from .official_relation_intake import read_official_relation_intake
from .official_relation_review import RELATION_STATUS
from .semiconductor_impact import (
    DIRECTIONS, propagate_semiconductor_claim,
)
from .semiconductor_profile import build_semiconductor_profile, CAUSES, STAGES
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA = "newscatalyst.reviewed_beneficiary_delivery.v1"
MARKER = "newscatalyst.reviewed_beneficiary_publication.v1"
MAX_GRAPH_BYTES = 512_000


@dataclass(frozen=True)
class ReviewedDelivery:
    graph: BeneficiaryGraph
    publication_sha256: str
    publisher_decision_at: datetime
    source_evidence_sha256: str


@dataclass(frozen=True)
class ReviewedPublication:
    folder: Path
    payload_sha256: str
    published_at: datetime
    candidate_count: int


def prepare_reviewed_beneficiary_graph(
    publication: Path, publication_root: Path, trusted_payload_sha256: str,
    review_json: Path, document_text: Path, trusted_document_sha256: str,
    *, trigger: str, direction: str = "UNKNOWN",
    evidence_note: str = "Impact direction unverified; independent sales proof missing",
    now: datetime | None = None,
) -> ReviewedDelivery:
    """Consume prior official metadata and human review ONCE; no new DART/SEC."""
    if direction not in DIRECTIONS or direction not in (
        "POSITIVE", "NEGATIVE", "MIXED", "UNKNOWN",
    ):
        raise SourceShareError("unrecognized economic direction")
    edge = read_official_relation_intake(
        publication, publication_root, trusted_payload_sha256,
        review_json, document_text, trusted_document_sha256, now=now,
    )
    checked = _when((now or datetime.now(timezone.utc)).isoformat(),
                    "delivery producer decision")
    if (edge.evidence_status != RELATION_STATUS or edge.verified_real_transaction
            or edge.document_sha256 is None or edge.review_proof_sha256 is None
            or edge.available_at > checked):
        raise SourceShareError("approved human-reviewed official relation required")
    profile = build_semiconductor_profile()
    impact = propagate_semiconductor_claim(
        profile, edge.source_event_sha256, trigger,
        direction=direction, evidence_note=evidence_note,
        source_available_at=edge.available_at, reviewed_at=checked, now=checked,
    )
    beneficiary = classify_semiconductor_beneficiary(
        edge, impact, reviewed_at=checked, now=checked,
    )
    graph = build_beneficiary_graph(
        profile, impact, (edge,), (beneficiary,), checked, now=checked,
    )
    if graph.items_count != 1 or graph.payload_sha256 != sha256(graph.JSON_bytes).hexdigest():
        raise SourceShareError("non-deterministic reviewed relation delivery")
    return ReviewedDelivery(graph, graph.payload_sha256, checked, edge.source_event_sha256)


def _handoff_root(path: Path, *, create: bool) -> Path:
    """Owner-only local publication. Readers cannot create directories."""
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts or path.is_symlink()
            or any(part.casefold() == "eraleader" for part in path.parts)):
        raise SourceShareError("NewsCatalystOS private handoff path required")
    if create:
        return _private_root(path)
    try:
        info = path.lstat()
    except OSError as exc:
        raise SourceShareError("completed handoff root unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or path.resolve(strict=True) != path):
        raise SourceShareError("read-only consumer requires owner-private handoff root")
    return path


def publish_reviewed_beneficiary_graph(
    report: ReviewedDelivery, out_root: Path, *, now: datetime | None = None,
) -> ReviewedPublication:
    """Atomic, immutable owner-only graph delivery; never publish source text."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "delivery published")
    if (not isinstance(report, ReviewedDelivery)
            or report.publisher_decision_at > at
            or report.graph.decision_at > at
            or report.graph.items_count != 1
            or report.graph.source_event_sha256 != report.source_evidence_sha256
            or report.graph.payload_sha256 != report.publication_sha256
            or sha256(report.graph.JSON_bytes).hexdigest() != report.publication_sha256):
        raise SourceShareError("complete reviewed graph and real publication time required")
    data = _json(report.graph.JSON_bytes, "reviewed candidate graph")
    _validate_reviewed_graph(data, at)
    root = _handoff_root(out_root, create=True)
    stage = Path(tempfile.mkdtemp(prefix=".reviewed_staging_", dir=root))
    dest = root / ("reviewed_candidate_" + report.publication_sha256)
    if dest.exists() or dest.is_symlink():
        raise SourceShareError("already published candidate cannot be overwritten")
    try:
        stage.chmod(0o700)
        note = {
            "schema": MARKER,
            "status": "REVIEWED_RELATION_CANDIDATES_UNVERIFIED",
            "payload_file": "beneficiary_graph.json",
            "payload_sha256": report.publication_sha256,
            "source_event_sha256": report.source_evidence_sha256,
            "candidate_count": 1,
            "verified_real_benefit_count": 0,
            "source_document_text_included": False,
            "producer_decision_at": report.publisher_decision_at.isoformat(),
            "prepared_at": at.isoformat(),
        }
        encoded = (json.dumps(note, sort_keys=True, separators=(",", ":"))+"\n").encode()
        _write_new(stage / "beneficiary_graph.json", report.graph.JSON_bytes)
        _write_new(stage / "publication.json", encoded)
        fd = os.open(stage, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(stage, dest)
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise SourceShareError("private reviewed graph publication failed") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    completed = _when((now or datetime.now(timezone.utc)).isoformat(),
                      "publication completed")
    return ReviewedPublication(dest, report.publication_sha256, completed, 1)


def _validate_reviewed_graph(data: dict, available_at: datetime) -> None:
    if (set(data) != {
            "schema", "industry_id", "event_sha256", "profile_sha256",
            "decision_at", "source_impact_trigger", "status", "edges",
            "certified_beneficiary_count",
        } or data.get("schema") != "newscatalyst.beneficiary_graph.v1"
            or data.get("industry_id") != "SEMICONDUCTOR"
            or data.get("status") != "REVIEW_CANDIDATES_NOT_VERIFIED_BENEFICIARIES"
            or data.get("certified_beneficiary_count") != 0
            or not isinstance(data.get("edges"), list)
            or len(data["edges"]) != 1):
        raise SourceShareError("unverified semiconductor graph only")
    event = _must_sha(data.get("event_sha256"), "source event ID")
    profile = build_semiconductor_profile()
    if (data.get("profile_sha256") != profile.taxonomy_sha256
            or data.get("source_impact_trigger") not in CAUSES):
        raise SourceShareError("unsupported semiconductor stage/profile")
    decision = _when(data["decision_at"], "graph decision")
    if decision > available_at:
        raise SourceShareError("future graph cannot be delivered")
    edge = data["edges"][0]
    expected_fields = {
        "relation_sha256", "evidence_source_sha256", "evidence_sha256",
        "relation_kind", "product_stage", "supplier_namespace", "supplier_id",
        "customer_namespace", "customer_id", "source_available_at",
        "candidate_category", "candidate_reviewed_at", "verified_real_benefit",
        "revenue_contribution_krw", "document_sha256",
        "review_proof_sha256", "relation_evidence_status",
    }
    if not isinstance(edge, dict) or set(edge) != expected_fields:
        raise SourceShareError("reviewed official relation fields missing")
    if (edge.get("relation_kind") != "REPORTED_DIRECT_TRANSACTION"
            or edge.get("relation_evidence_status") != RELATION_STATUS
            or edge.get("evidence_source_sha256") != event
            or edge.get("evidence_sha256") != edge.get("document_sha256")
            or edge.get("verified_real_benefit") is not False
            or edge.get("revenue_contribution_krw") is not None):
        raise SourceShareError("reviewed relation cannot certify commercial benefit")
    if (edge.get("product_stage") not in STAGES
            or edge.get("supplier_namespace") not in ("DART_CORP", "SEC_CIK")
            or edge.get("customer_namespace") != edge.get("supplier_namespace")
            or edge.get("supplier_id") == edge.get("customer_id")
            or edge.get("candidate_category") not in (
                "POTENTIAL_BENEFICIARY_UNVERIFIED",
                "POTENTIAL_DAMAGE_UNVERIFIED",
                "UNKNOWN_RELATIONSHIP", "THEMATIC_ONLY",
                "EFFECT_DIRECTION_UNKNOWN",
            )):
        raise SourceShareError("unapproved relationship roles/stage")
    import re
    identifier = (r"[0-9]{8}" if edge["supplier_namespace"] == "DART_CORP"
                  else r"[0-9]{1,10}")
    for party in ("supplier_id", "customer_id"):
        if not isinstance(edge.get(party), str) or not re.fullmatch(identifier, edge[party]):
            raise SourceShareError("invalid reviewed company identifier")
    for key in ("relation_sha256", "document_sha256", "review_proof_sha256"):
        _must_sha(edge.get(key), key)
    if (_when(edge["candidate_reviewed_at"], "candidate reviewed") > decision
            or _when(edge["source_available_at"], "relation first consumed") > decision):
        raise SourceShareError("future reviewed relation cannot enter delivery")


def consume_reviewed_beneficiary_graph(
    folder: Path, out_root: Path, expected_sha256: str,
    *, decision_at: datetime | None = None, now: datetime | None = None,
) -> dict:
    """Reader-only consumer, suitable for ANY chosen downstream project.

    expected_sha256 MUST be independently obtained (out-of-band). This code
    never calls/edits the downstream project or its repository.
    """
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "consumer now")
    decision = _when((decision_at or at).isoformat(), "consumer decision")
    expected = _must_sha(expected_sha256, "trusted delivery payload SHA")
    root = _handoff_root(out_root, create=False)
    folder = Path(folder)
    if (folder.parent != root
            or folder.name != "reviewed_candidate_" + expected
            or folder.is_symlink()):
        raise SourceShareError("candidate outside permitted private handoff root")
    info = folder.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("untrusted private candidate delivery")
    note = _json(_read_once(folder / "publication.json", 8192),
                 "reviewed graph publication")
    if (set(note) != {
            "schema", "status", "payload_file", "payload_sha256",
            "source_event_sha256", "candidate_count",
            "verified_real_benefit_count", "source_document_text_included",
            "producer_decision_at", "prepared_at",
        } or note["schema"] != MARKER
            or note["status"] != "REVIEWED_RELATION_CANDIDATES_UNVERIFIED"
            or note["payload_file"] != "beneficiary_graph.json"
            or note["payload_sha256"] != expected
            or note["candidate_count"] != 1
            or note["verified_real_benefit_count"] != 0
            or note["source_document_text_included"] is not False):
        raise SourceShareError("untrusted reviewed candidate publication")
    raw = _read_once(folder / "beneficiary_graph.json", MAX_GRAPH_BYTES)
    if sha256(raw).hexdigest() != expected:
        raise SourceShareError("candidate payload differs from independent pin")
    value = _json(raw, "reviewed candidate graph")
    if (value.get("event_sha256") != note["source_event_sha256"]
            or _when(note["producer_decision_at"], "producer decision") >
            _when(note["prepared_at"], "publication prepared")):
        raise SourceShareError("reviewed candidate identity/PIT mismatch")
    # The actual completed publication could occur after marker preparation,
    # and a consumer cannot assume immediate historical availability.
    earliest = _when(note["prepared_at"], "publication prepared")
    if (decision < earliest or decision > at
            or _when(note["producer_decision_at"], "producer decision") > decision):
        raise SourceShareError("candidate not PIT available to consumer")
    _validate_reviewed_graph(value, decision)
    return {
        "status": "OFFICIAL_RELATION_CANDIDATE_NOT_COMMERCIALLY_VERIFIED",
        "schema": SCHEMA,
        "consumer_checked_at": at.isoformat(),
        "payload_sha256": expected,
        "industry_id": "SEMICONDUCTOR",
        "source_event_sha256": value["event_sha256"],
        "reviewed_candidate_count": 1,
        # Public corporate IDs and SHA-bound caveats, NOT a trade instruction.
        # A downstream system may use this typed JSON without touching EraLeader.
        "candidate_edges": [{
            "supplier_namespace": value["edges"][0]["supplier_namespace"],
            "supplier_id": value["edges"][0]["supplier_id"],
            "customer_namespace": value["edges"][0]["customer_namespace"],
            "customer_id": value["edges"][0]["customer_id"],
            "product_stage": value["edges"][0]["product_stage"],
            "relation_kind": "REPORTED_DIRECT_TRANSACTION",
            "relation_sha256": value["edges"][0]["relation_sha256"],
            "document_sha256": value["edges"][0]["document_sha256"],
            "review_proof_sha256": value["edges"][0]["review_proof_sha256"],
            "source_available_at": value["edges"][0]["source_available_at"],
            "candidate_category": value["edges"][0]["candidate_category"],
            "relation_proof_status": RELATION_STATUS,
            "verified_real_transaction": False,
            "verified_real_benefit": False,
            "estimated_revenue_krw": None,
        }],
        "verified_real_transaction_count": 0,
        "verified_real_benefit_count": 0,
        "estimated_revenue_krw": None,
        "market_action": None,
    }
