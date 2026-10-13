"""5_5 stable, evidence-linked beneficiary candidate JSON for read-only consumers.

No automatic distribution to EraLeader, no source excerpt or article body, no
false confirmed beneficiary claims. Consumers check the payload SHA out of band.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json

from .beneficiary_classification import BeneficiaryCandidate
from .semiconductor_impact import SemiconductorTransmission
from .semiconductor_profile import SemiconductorProfile, validate_profile
from .official_relation_review import RELATION_STATUS
from .supply_chain_graph import SupplyChainEdge
from .source_share import SourceShareError, _must_sha, _when

SCHEMA="newscatalyst.beneficiary_graph.v1"


@dataclass(frozen=True)
class BeneficiaryGraph:
    schema_version: str
    source_event_sha256: str
    profile_sha256: str
    decision_at: datetime
    items_count: int
    JSON_bytes: bytes
    payload_sha256: str
    status: str = "REVIEW_CANDIDATES_NOT_VERIFIED_BENEFICIARIES"


def build_beneficiary_graph(
    profile: SemiconductorProfile,
    impact: SemiconductorTransmission,
    relations: tuple[SupplyChainEdge, ...] | list[SupplyChainEdge],
    candidates: tuple[BeneficiaryCandidate, ...] | list[BeneficiaryCandidate],
    decision_at: datetime,
    *, now: datetime | None = None,
) -> BeneficiaryGraph:
    validate_profile(profile)
    at=_when(decision_at.isoformat(),"decision_at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not impact.reviewed_at<=at<=current:
        raise SourceShareError("impact information unavailable for export")
    if not isinstance(relations,(tuple,list)) or not isinstance(candidates,(tuple,list)):
        raise SourceShareError("typed verified metadata required")
    if len(relations)>1000 or len(candidates)>1000:
        raise SourceShareError("unbounded graph size")
    edge_by_id={}
    for edge in relations:
        if not isinstance(edge,SupplyChainEdge) or edge.available_at>at:
            raise SourceShareError("future or invalid graph relation")
        if edge.verified_real_transaction:
            raise SourceShareError("unsigned relationship cannot become verified commercial fact")
        if edge.edge_sha256 in edge_by_id:
            raise SourceShareError("duplicate relation ID")
        edge_by_id[edge.edge_sha256]=edge
    rendered=[]
    for candidate in candidates:
        if not isinstance(candidate,BeneficiaryCandidate):
            raise SourceShareError("typed beneficiary candidate required")
        edge=edge_by_id.get(candidate.supply_edge_sha256)
        if (edge is None or candidate.reviewed_at>at or
                candidate.available_at>at or candidate.verified_real_benefit or
                candidate.annual_sales_share is not None or
                candidate.realized_revenue_krw is not None or
                candidate.economic_source_sha256!=impact.event_sha256 or
                (candidate.supplier_id,candidate.customer_id)!=(edge.supplier_id,edge.customer_id)):
            raise SourceShareError("beneficiary lacks consistent source evidence")
        rendered.append({
            "relation_sha256":edge.edge_sha256,
            "evidence_source_sha256":edge.source_event_sha256,
            "evidence_sha256":edge.evidence_sha256,
            "relation_kind":edge.relation_kind,
            "product_stage":edge.product_stage,
            "supplier_namespace":edge.supplier_namespace,
            "supplier_id":edge.supplier_id,
            "customer_namespace":edge.customer_namespace,
            "customer_id":edge.customer_id,
            "source_available_at":edge.available_at.isoformat(),
            "candidate_category":candidate.category,
            "candidate_reviewed_at":candidate.reviewed_at.isoformat(),
            "verified_real_benefit":False,
            "revenue_contribution_krw":None,
        })
        if edge.document_sha256 is not None or edge.review_proof_sha256 is not None:
            if (edge.document_sha256 is None or edge.review_proof_sha256 is None
                    or edge.evidence_status != RELATION_STATUS
                    or edge.evidence_sha256 != edge.document_sha256
                    or candidate.available_at < edge.available_at):
                raise SourceShareError("inconsistent official relation document proof")
            rendered[-1].update({
                "document_sha256": _must_sha(edge.document_sha256, "document proof"),
                "review_proof_sha256": _must_sha(edge.review_proof_sha256, "review proof"),
                "relation_evidence_status": RELATION_STATUS,
            })
    rendered.sort(key=lambda x:x["relation_sha256"])
    if len({x["relation_sha256"] for x in rendered})!=len(rendered):
        raise SourceShareError("same relation cannot be counted twice")
    data={
        "schema":SCHEMA,"industry_id":"SEMICONDUCTOR",
        "event_sha256":impact.event_sha256,
        "profile_sha256":profile.taxonomy_sha256,
        "decision_at":at.isoformat(),
        "source_impact_trigger":impact.trigger,
        "status":"REVIEW_CANDIDATES_NOT_VERIFIED_BENEFICIARIES",
        "edges":rendered,"certified_beneficiary_count":0,
    }
    raw=(json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
    return BeneficiaryGraph(
        SCHEMA,impact.event_sha256,profile.taxonomy_sha256,at,len(rendered),
        raw,sha256(raw).hexdigest()
    )
