"""Publish and consume an attributed article claim without human review.

This is a source-backed research candidate, never a verified contract,
customer identity mapping, realized sale, or beneficiary conclusion.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from .evidence_archive import _private_root, _read_once, _write_new, read_archived_evidence
from .provider_registry import ProviderRegistry, permits_document_storage
from .semiconductor_profile import STAGES
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA = "newscatalyst.source_article_supply_claim.v1"
STATUS = "SOURCE_REPORTED_SUPPLY_CANDIDATE_NOT_TRANSACTION_VERIFIED"


def prepare_source_article_claim(
    archive_root: Path, archive_version: str, receipt_sha256: str,
    document_sha256: str, registry: ProviderRegistry, *,
    supplier_name: str, customer_name: str, product_stage: str,
    now: datetime | None = None,
) -> bytes:
    """Match one explicit statement in licensed text and retain only its SHA."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "claim decision")
    pinned_receipt = _must_sha(receipt_sha256, "archive receipt")
    pinned_document = _must_sha(document_sha256, "document")
    text, archived = read_archived_evidence(archive_root, archive_version, now=at)
    if (archived.content_scope != "LICENSED_SOURCE_BYTES"
            or archived.receipt_sha256 != pinned_receipt
            or archived.payload_sha256 != pinned_document):
        raise SourceShareError("source article archive pins mismatch")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved source registry required")
    provider = registry.active(archived.provider_id, at=at)
    if (not permits_document_storage(provider)
            or not provider.enabled_at(archived.first_verified_at)
            or provider.kind != "GOVERNMENT_POLICY"):
        raise SourceShareError("licensed government press text required")
    if (product_stage not in STAGES
            or not all(isinstance(n, str) and 2 <= len(n) <= 100 for n in
                       (supplier_name, customer_name))
            or supplier_name.casefold() == customer_name.casefold()):
        raise SourceShareError("distinct company names and semiconductor stage required")
    try:
        body = text.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceShareError("UTF-8 article text required") from exc
    lines = [line.strip() for line in body.splitlines()]
    direct_supply = re.compile(
        r"공급하고 있|공급했다|공급하였|공급한다|공급 계약|"
        r"납품하고 있|납품했다|납품한다|supplies?\b|supplied\b|supply to\b",
        re.IGNORECASE,
    )
    negations = ("공급하지 않", "납품하지 않", "공급 계약 없음", "거래 관계 없음",
                 "did not supply", "no supply agreement")
    matches = []
    for line in lines:
        folded = line.casefold()
        verb = direct_supply.search(line)
        if (verb and supplier_name.casefold() in folded
                and customer_name.casefold() in folded
                and not any(word in folded for word in negations)
                and folded.index(supplier_name.casefold())
                    < folded.index(customer_name.casefold()) < verb.start()):
            matches.append(line)
    if len(matches) != 1 or not 20 <= len(matches[0]) <= 1400:
        raise SourceShareError("one explicit source-reported supply sentence required")
    statement = matches[0]
    payload = {
        "schema": SCHEMA, "status": STATUS,
        "source_url": provider.endpoint, "provider_id": archived.provider_id,
        "document_id": archived.document_id,
        "archive_version": archived.version_id,
        "archive_receipt_sha256": pinned_receipt,
        "document_sha256": pinned_document,
        "statement_sha256": sha256(statement.encode("utf-8")).hexdigest(),
        "supplier_name": supplier_name, "customer_name": customer_name,
        "company_ids_verified": False, "product_stage": product_stage,
        "first_available_at": max(archived.archived_at, archived.first_verified_at).isoformat(),
        "decision_at": at.isoformat(),
        "verified_real_transaction": False, "verified_real_benefit": False,
        "realized_revenue_krw": None,
    }
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def publish_source_article_claim(payload: bytes, out_root: Path) -> tuple[Path, str]:
    data = _json(payload, "source article claim")
    if data.get("schema") != SCHEMA or data.get("status") != STATUS:
        raise SourceShareError("source article claim schema mismatch")
    digest = sha256(payload).hexdigest()
    root = _private_root(out_root)
    path = root / ("source_claim_" + digest + ".json")
    if path.exists():
        if _read_once(path, 8192) != payload:
            raise SourceShareError("source claim hash collision")
    else:
        _write_new(path, payload)
    return path, digest


def consume_source_article_claim(path: Path, expected_sha256: str, *,
                                 now: datetime | None = None) -> dict:
    """Read only the separately pinned private result, enforcing PIT and status."""
    expected = _must_sha(expected_sha256, "source claim pin")
    payload = _read_once(path, 8192)
    if sha256(payload).hexdigest() != expected:
        raise SourceShareError("source claim payload SHA mismatch")
    data = _json(payload, "source article claim")
    required = {"schema", "status", "source_url", "provider_id", "document_id",
                "archive_version", "archive_receipt_sha256", "document_sha256",
                "statement_sha256", "supplier_name", "customer_name",
                "company_ids_verified", "product_stage", "first_available_at",
                "decision_at", "verified_real_transaction", "verified_real_benefit",
                "realized_revenue_krw"}
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "consumer observation")
    if (set(data) != required or data["schema"] != SCHEMA or data["status"] != STATUS
            or data["company_ids_verified"] is not False
            or data["verified_real_transaction"] is not False
            or data["verified_real_benefit"] is not False
            or data["realized_revenue_krw"] is not None
            or data["product_stage"] not in STAGES
            or _when(data["first_available_at"], "source available") > at
            or _when(data["decision_at"], "claim decision") > at):
        raise SourceShareError("unavailable or overstated source article claim")
    return data
