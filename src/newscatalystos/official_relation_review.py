"""5_2: an offline, human-reviewed relation claim bound to a verified official receipt.

The five baseline EraLeader snapshots contain filing *metadata*, not contract
body text. Never infer counterparties from a filing ID, ticker or press title.
This accepts separately available official document text only with an
out-of-band pinned SHA and explicit human-reviewed role statement. It returns
a reviewed claim, NOT evidence of a completed commercial transaction.
No collector/network/filesystem access; document bytes are not persisted.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from .event_identity import CompanyBinding
from .evidence_archive import ArchivedEvidence
from .operational_observations import OperationalObservation, OperationalObservationSet
from .source_share import SourceShareError, _must_sha, _when
from .supply_chain_graph import SupplyChainEdge, observed_supply_edge

RELATION_STATUS = "OFFICIAL_DOCUMENT_REVIEWED_RELATION_NOT_TRANSACTION_VERIFIED"
PUBLISHER_RELATION_STATUS = "LICENSED_PUBLISHER_DOCUMENT_REVIEWED_RELATION_NOT_TRANSACTION_VERIFIED"
DOCUMENT_REVIEW_STATUSES = frozenset({RELATION_STATUS, PUBLISHER_RELATION_STATUS})
_RELATION_TERMS = (
    "supply", "supplies", "supplied", "purchase", "purchased", "sold", "contract",
    "manufactures for", "manufactured for", "공급", "계약", "납품", "판매", "위탁생산",
)
MAX_DOCUMENT_BYTES = 1024 * 1024


def _time(value: datetime, field: str) -> datetime:
    return _when(value.isoformat() if isinstance(value, datetime) else None, field)


@dataclass(frozen=True)
class OfficialRelationReview:
    source_id: str
    source_document_id: str
    source_evidence_id: str
    source_receipt_sha256: str
    document_sha256: str
    document_observed_at: datetime
    pin_observed_at: datetime
    reviewed_at: datetime
    reviewer_code: str
    supplier_name: str
    customer_name: str
    evidence_statement: str
    product_stage: str


def review_official_supply_relation(
    observations: OperationalObservationSet,
    supplier: CompanyBinding,
    customer: CompanyBinding,
    review: OfficialRelationReview,
    document_text: bytes,
    *,
    trusted_document_sha256: str,
    decision_at: datetime,
    now: datetime | None = None,
    consumer_observed_at: datetime | None = None,
) -> SupplyChainEdge:
    """Validate the complete metadata-to-document-to-review evidence chain.

    trusted_document_sha256 must originate from an independently kept,
    operator-approved pin (never computed from document_text by the caller).
    Official filing metadata does NOT contain the text of supplier contracts;
    the reviewer's role assertion is separate and remains non-transactional.
    """
    decision = _time(decision_at, "decision_at")
    current = _time(now or datetime.now(timezone.utc), "now")
    if decision > current:
        raise SourceShareError("future supply-chain decision")
    if (not isinstance(observations, OperationalObservationSet)
            or observations.coverage_verified is not True):
        raise SourceShareError("complete official observation coverage required")
    rows = observations.as_of(decision, now=current)
    if not isinstance(review, OfficialRelationReview):
        raise SourceShareError("typed human relation review required")
    matches = [
        r for r in rows
        if (r.source_id, r.source_document_id) ==
        (review.source_id, review.source_document_id)
    ]
    if len(matches) != 1:
        raise SourceShareError("one uniquely verified official document required")
    source = matches[0]
    if (source.data_kind != "DISCLOSURE_OBSERVED"
            or source.provider_id not in ("DART", "SEC")
            or source.issuer_verified or source.release_certified
            or source.published_at is not None):
        raise SourceShareError("source is not an uncertified disclosure observation")
    if (_must_sha(review.source_evidence_id, "source evidence")
            != source.evidence_id
            or _must_sha(review.source_receipt_sha256, "receipt")
            != source.receipt_sha256):
        raise SourceShareError("source evidence/receipt is not the pinned snapshot")
    if (supplier.id_namespace != customer.id_namespace
            or supplier.id_namespace != ("DART_CORP" if source.provider_id == "DART" else "SEC_CIK")):
        raise SourceShareError("official source and both company ID namespaces mismatch")
    return _review_bound_document(
        source, supplier, customer, review, document_text,
        trusted_document_sha256=trusted_document_sha256, decision=decision,
        current=current, consumer_observed_at=consumer_observed_at,
        source_evidence_id=source.evidence_id,
        source_available_at=max(source.available_at, source.verified_at),
        evidence_status=RELATION_STATUS,
    )


def _review_bound_document(
    source: OperationalObservation | ArchivedEvidence,
    supplier: CompanyBinding, customer: CompanyBinding,
    review: OfficialRelationReview, document_text: bytes, *,
    trusted_document_sha256: str, decision: datetime, current: datetime,
    consumer_observed_at: datetime | None, source_evidence_id: str,
    source_available_at: datetime, evidence_status: str,
    relation_kind: str = "REPORTED_DIRECT_TRANSACTION",
) -> SupplyChainEdge:
    """Shared text/PIT review logic; callers keep their distinct source gates."""
    if decision > current or evidence_status not in DOCUMENT_REVIEW_STATUSES:
        raise SourceShareError("invalid document review context")
    expected = _must_sha(trusted_document_sha256, "trusted document pin")
    if (_must_sha(review.document_sha256, "document SHA") != expected
            or not isinstance(document_text, bytes)
            or not 0 < len(document_text) <= MAX_DOCUMENT_BYTES
            or sha256(document_text).hexdigest() != expected):
        raise SourceShareError("document text missing, oversized or SHA untrusted")
    try:
        full_text = document_text.decode("utf-8")
    except UnicodeError as exc:
        raise SourceShareError("official document text must be UTF-8") from exc
    observed = _time(review.document_observed_at, "document observed")
    pinned = _time(review.pin_observed_at, "independent pin observed")
    reviewed = _time(review.reviewed_at, "human review")
    # An offline review may predate this consumer's first validated read.
    # Never expose a relation before the complete evidence actually arrived.
    consumed = (_time(consumer_observed_at, "consumer observation")
                if consumer_observed_at is not None else reviewed)
    if consumed > decision:
        raise SourceShareError("relation evidence unavailable at decision")
    effective = max(reviewed, consumed)
    if (max(observed, pinned) > reviewed or reviewed > decision
            or source_available_at > effective):
        raise SourceShareError("document/pin/review unavailable at decision")
    if (supplier.validate() > reviewed or customer.validate() > reviewed):
        raise SourceShareError("review predates source or company mapping")
    if not isinstance(review.reviewer_code, str) or not re.fullmatch(
        r"[A-Z0-9_-]{3,32}", review.reviewer_code
    ):
        raise SourceShareError("operator reviewer code required")
    names = (review.supplier_name, review.customer_name)
    statement = review.evidence_statement
    # A company named 'Supplier Alpha' or a negated contract mention must
    # never turn mere co-occurrence into a direct commercial relationship.
    if not isinstance(statement, str):
        raise SourceShareError("explicit supplier/customer transaction statement required")
    normalized = statement.casefold()
    relation_context = normalized
    for name in names:
        if isinstance(name, str):
            relation_context = relation_context.replace(name.casefold(), " ")
    negations = ("no business deal", "no contract", "not a supplier",
                 "unrelated", "계약 없음", "공급 계약 없음", "거래 관계 없음",
                 "no supply agreement", "did not supply", "will not supply",
                 "no purchase agreement", "공급하지 않", "계약하지 않", "납품하지 않")
    if (any(not isinstance(n, str) or not 2 <= len(n) <= 140 for n in names)
            or names[0].casefold() == names[1].casefold()
            or not isinstance(statement, str) or not 20 <= len(statement) <= 1400
            or statement not in full_text
            or any(n.casefold() not in statement.casefold() for n in names)
            or any(term in normalized for term in negations)
            or not any(term in relation_context for term in _RELATION_TERMS)):
        raise SourceShareError("explicit supplier/customer transaction statement required")
    edge = observed_supply_edge(
        source, supplier, customer, product_stage=review.product_stage,
        relation_kind=relation_kind,
        reviewed_at=effective, now=current,
    )
    review_metadata = {
        "source_evidence_id":source_evidence_id,
        "document_sha256":expected,
        "pin_observed_at":pinned.isoformat(),
        "reviewed_at":reviewed.isoformat(),
        "consumer_observed_at":consumed.isoformat(),
        "reviewer_code":review.reviewer_code,
        "supplier_name":names[0],
        "customer_name":names[1],
        "statement_sha256":sha256(statement.encode("utf-8")).hexdigest(),
        "product_stage":review.product_stage,
    }
    proof_sha = sha256(json.dumps(
        review_metadata, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    relation_sha = sha256((edge.edge_sha256 + ":" + proof_sha).encode()).hexdigest()
    return replace(
        edge, edge_sha256=relation_sha, evidence_sha256=expected,
        evidence_status=evidence_status, available_at=effective,
        last_reviewed_at=effective,
        document_sha256=expected, review_proof_sha256=proof_sha,
    )
