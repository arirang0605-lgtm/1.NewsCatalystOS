"""5_4 beneficiary/risk candidate labels from two separately reviewed claims.

A source-reported relationship + hypothetical economic path is not confirmed
sales or a verified beneficial exposure. Missing sales percentages remain N/A.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .semiconductor_impact import SemiconductorTransmission
from .supply_chain_graph import SupplyChainEdge
from .source_share import SourceShareError, _when

SCHEMA="newscatalyst.beneficiary_candidate.v1"


@dataclass(frozen=True)
class BeneficiaryCandidate:
    schema_version: str
    supplier_id: str
    customer_id: str
    supply_edge_sha256: str
    economic_source_sha256: str
    category: str
    reason: str
    available_at: datetime
    reviewed_at: datetime
    verified_real_benefit: bool = False
    annual_sales_share: None = None
    realized_revenue_krw: None = None


def classify_semiconductor_beneficiary(
    edge: SupplyChainEdge, impact: SemiconductorTransmission, *,
    reviewed_at: datetime, now: datetime | None = None,
) -> BeneficiaryCandidate:
    at=_when(reviewed_at.isoformat(),"reviewed at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not isinstance(edge,SupplyChainEdge) or not isinstance(impact,SemiconductorTransmission):
        raise SourceShareError("evidence-bound edge and impact hypothesis required")
    if edge.verified_real_transaction is not False:
        raise SourceShareError("cannot self-certify commercial transaction")
    ready=max(_when(edge.available_at.isoformat(),"edge available"),
              _when(impact.reviewed_at.isoformat(),"economic path reviewed"))
    if not ready<=at<=current:
        raise SourceShareError("future beneficiary evidence not available")
    if edge.product_stage not in impact.stages:
        category="UNKNOWN_RELATIONSHIP"
        reason="Supply-chain stage does not match this impact hypothesis"
    elif edge.relation_kind=="THEMATIC_ASSOCIATION":
        category="THEMATIC_ONLY"
        reason="Thematic relation is not a direct contract"
    elif edge.relation_kind=="ANNOUNCED_SUPPLY_PLAN":
        category="ANNOUNCED_SUPPLY_PLAN_UNVERIFIED"
        reason="A future supply plan is not evidence of active shipments or realized revenue"
    elif impact.direction=="POSITIVE":
        category="POTENTIAL_BENEFICIARY_UNVERIFIED"
        reason="Reported direct link, hypothetical positive economic effect"
    elif impact.direction=="NEGATIVE":
        category="POTENTIAL_DAMAGE_UNVERIFIED"
        reason="Reported direct link, hypothetical negative economic effect"
    else:
        category="EFFECT_DIRECTION_UNKNOWN"
        reason="Reported direct link, unknown economic effect"
    return BeneficiaryCandidate(
        SCHEMA,edge.supplier_id,edge.customer_id,
        edge.edge_sha256,impact.event_sha256,category,reason,ready,at,
    )
