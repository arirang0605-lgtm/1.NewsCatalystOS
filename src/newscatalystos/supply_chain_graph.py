"""5_2 supply-chain relationship candidates with source-bound PIT evidence.

A press/news claim naming two firms is not verified commercial business.
An edge may be stored as reported or merely thematic, but never silently
promoted to a verified real supplier/customer contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from .event_identity import CompanyBinding
from .operational_observations import OperationalObservation
from .new_source_adapter import FeedObservation
from .semiconductor_profile import STAGES
from .source_share import SourceShareError, _when

KINDS = frozenset({"REPORTED_DIRECT_TRANSACTION", "THEMATIC_ASSOCIATION"})


@dataclass(frozen=True)
class SupplyChainEdge:
    edge_sha256: str
    source_id: str
    document_id: str
    source_event_sha256: str
    supplier_namespace: str
    supplier_id: str
    customer_namespace: str
    customer_id: str
    product_stage: str
    relation_kind: str
    evidence_status: str
    evidence_sha256: str
    available_at: datetime
    last_reviewed_at: datetime
    verified_real_transaction: bool = False
    # Populated only for explicit official-document + independent-pin reviews.
    # Optional to preserve existing observed/unverified feed-edge compatibility.
    document_sha256: str | None = None
    review_proof_sha256: str | None = None

    def as_of(self, decision_at: datetime, *, now: datetime | None = None
              ) -> "SupplyChainEdge":
        decision = _when(decision_at.isoformat(), "decision at")
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.available_at <= decision <= present:
            raise SourceShareError("supply relationship unavailable at decision")
        return self


def observed_supply_edge(
    source: OperationalObservation | FeedObservation,
    supplier: CompanyBinding, customer: CompanyBinding, *,
    product_stage: str, relation_kind: str,
    reviewed_at: datetime, now: datetime | None = None,
) -> SupplyChainEdge:
    at = _when(reviewed_at.isoformat(), "reviewed at")
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not at <= current:
        raise SourceShareError("future supply-chain review")
    if product_stage not in STAGES or relation_kind not in KINDS:
        raise SourceShareError("invalid stage or relation directness")
    if not isinstance(supplier,CompanyBinding) or not isinstance(customer,CompanyBinding):
        raise SourceShareError("separately reviewed supplier/customer bindings required")
    supplier_time = supplier.validate()
    customer_time = customer.validate()
    if isinstance(source, OperationalObservation):
        if source.data_kind != "DISCLOSURE_OBSERVED" or source.published_at is not None:
            raise SourceShareError("only uncertified official disclosure observations here")
        source_id,doc,source_event = source.source_id,source.source_document_id,source.evidence_id
        earliest=max(source.available_at,source.verified_at)
        evidence_sha=source.original_sha256
        evidence_status="OFFICIAL_DISCLOSURE_OBSERVED_RELATION_UNVERIFIED"
    elif isinstance(source, FeedObservation):
        source_id,doc,source_event=source.provider_id,source.document_id,source.event_id
        if source.reported_published_at is not None:
            raise SourceShareError("feed publisher timestamp is not independently certified")
        earliest=source.first_seen_at
        evidence_sha=source.event_id
        evidence_status="FEED_CLAIMED_RELATIONSHIP_UNVERIFIED"
    else:
        raise SourceShareError("supported source-bound claim required")
    if any(x.source_id!=source_id or x.source_document_id!=doc for x in (supplier,customer)):
        raise SourceShareError("issuer binding and source-document mismatch")
    if (supplier.id_namespace==customer.id_namespace and
            supplier.company_id==customer.company_id):
        raise SourceShareError("supplier and customer cannot be identical")
    available=max(
        _when(earliest.isoformat(), "source available"),
        supplier_time,customer_time,at,
    )
    if available > at:
        raise SourceShareError("review predates source or company mapping")
    if available > current:
        raise SourceShareError("future mapping cannot create relation")
    identifier=sha256((
        source_id+"\0"+doc+"\0"+source_event+"\0"+supplier.company_id+
        "\0"+customer.company_id+"\0"+product_stage+"\0"+relation_kind
    ).encode()).hexdigest()
    return SupplyChainEdge(
        identifier,source_id,doc,source_event,
        supplier.id_namespace,supplier.company_id,
        customer.id_namespace,customer.company_id,
        product_stage,relation_kind,evidence_status,evidence_sha,
        available,at,
    )
