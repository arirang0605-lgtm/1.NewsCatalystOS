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
from .operational_observations import OperationalObservationSet
from .source_share import SourceShareError, _must_sha, _when
from .supply_chain_graph import SupplyChainEdge, observed_supply_edge

RELATION_STATUS = "OFFICIAL_DOCUMENT_REVIEWED_RELATION_NOT_TRANSACTION_VERIFIED"
_RELATION_TERMS = (
    "supply", "supplies", "supplier", "purchase", "sold", "contract",
    "manufactur", "foundry", "공급", "계약", "납품", "판매", "제조",
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
    if (max(source.available_at, source.verified_at, observed, pinned)
            > reviewed or reviewed > decision):
        raise SourceShareError("document/pin/review unavailable at decision")
    if not isinstance(review.reviewer_code, str) or not re.fullmatch(
        r"[A-Z0-9_-]{3,32}", review.reviewer_code
    ):
        raise SourceShareError("operator reviewer code required")
    names = (review.supplier_name, review.customer_name)
    statement = review.evidence_statement
    if (any(not isinstance(n, str) or not 2 <= len(n) <= 140 for n in names)
            or names[0].casefold() == names[1].casefold()
            or not isinstance(statement, str) or not 20 <= len(statement) <= 1400
            or statement not in full_text
            or any(n.casefold() not in statement.casefold() for n in names)
            or not any(term in statement.casefold() for term in _RELATION_TERMS)):
        raise SourceShareError("explicit supplier/customer transaction statement required")
    edge = observed_supply_edge(
        source, supplier, customer, product_stage=review.product_stage,
        relation_kind="REPORTED_DIRECT_TRANSACTION",
        reviewed_at=reviewed, now=current,
    )
    review_metadata = {
        "source_evidence_id":source.evidence_id,
        "document_sha256":expected,
        "pin_observed_at":pinned.isoformat(),
        "reviewed_at":reviewed.isoformat(),
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
        evidence_status=RELATION_STATUS, available_at=reviewed,
        document_sha256=expected, review_proof_sha256=proof_sha,
    )
