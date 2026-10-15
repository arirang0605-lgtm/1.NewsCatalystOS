"""Offline 5_2 intake: private relation evidence + independent SHA + verified disclosure.

No DART/SEC/KRX network calls, EraLeader writes or official text persistence.
The result is a review *candidate*, never evidence of executed transactions.
All inputs must be already authorized and kept in owner-only local folders.
"""
from __future__ import annotations

from dataclasses import fields
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
import os
import stat

from .event_identity import CompanyBinding
from .evidence_archive import read_archived_evidence
from .provider_registry import ProviderRegistry
from .official_relation_review import (
    MAX_DOCUMENT_BYTES, OfficialRelationReview, review_official_supply_relation,
    PUBLISHER_RELATION_STATUS, _review_bound_document,
)
from .operational_observations import load_operational_observations
from .source_share import SourceShareError, _json, _must_sha, _read_regular, _when
from .supply_chain_graph import SupplyChainEdge

SCHEMA = "newscatalyst.official_relation_intake.v2"
MAX_REVIEW_BYTES = 16_384


def _private_input(path: Path, limit: int) -> bytes:
    """Bounded read, no link endpoint, owner-only leaf and immediate directory."""
    path = Path(path)
    if not path.is_absolute():
        raise SourceShareError("absolute private input path required")
    try:
        directory = path.parent.lstat()
        entry = path.lstat()
        if (not stat.S_ISDIR(directory.st_mode)
                or not stat.S_ISREG(entry.st_mode)
                or directory.st_uid != os.geteuid()
                or entry.st_uid != os.geteuid()
                or stat.S_IMODE(directory.st_mode) & 0o077
                or stat.S_IMODE(entry.st_mode) & 0o077):
            raise SourceShareError("review inputs must be owner-only regular files")
    except OSError as exc:
        raise SourceShareError("private review input unavailable") from exc
    return _read_regular(path, limit)


def _record(value: object, typ, time_fields: frozenset[str]):
    expected = {field.name for field in fields(typ)}
    if not isinstance(value, dict) or set(value) != expected:
        raise SourceShareError("invalid typed review/binding record")
    data = dict(value)
    for key in time_fields:
        data[key] = _when(data[key], key)
    result = typ(**data)
    if isinstance(result, CompanyBinding):
        result.validate()
    return result


def read_official_relation_intake(
    publication: Path, publication_root: Path, trusted_payload_sha256: str,
    private_review_json: Path, private_document_text: Path,
    trusted_document_sha256: str, *,
    now: datetime | None = None,
) -> SupplyChainEdge:
    """Join a completed research publication with an operator-approved document.

    Both expected SHA values must be acquired out of band; a mutable manifest
    or this document's computed digest is NOT proof of independent trust.
    Operational availability starts only after this invocation reads every
    input. A historical review date never backdates its first consumption.
    """
    payload_pin = _must_sha(trusted_payload_sha256, "publication payload pin")
    document_pin = _must_sha(trusted_document_sha256, "out-of-band document pin")
    review_data = _json(_private_input(private_review_json, MAX_REVIEW_BYTES),
                        "private official relation review")
    if (set(review_data) != {"schema", "review", "supplier", "customer"}
            or review_data["schema"] != SCHEMA):
        raise SourceShareError("unknown official relation intake schema")
    review = _record(
        review_data["review"], OfficialRelationReview,
        frozenset({"document_observed_at", "pin_observed_at", "reviewed_at"}),
    )
    supplier = _record(review_data["supplier"], CompanyBinding, frozenset({"observed_at"}))
    customer = _record(review_data["customer"], CompanyBinding, frozenset({"observed_at"}))
    document = _private_input(private_document_text, MAX_DOCUMENT_BYTES)
    checked = _when((now or datetime.now(timezone.utc)).isoformat(), "intake read completed")
    observations = load_operational_observations(
        Path(publication), Path(publication_root), payload_pin, now=checked
    )
    # Re-stamp after all source and review reads for PIT availability.
    completed = _when((now or datetime.now(timezone.utc)).isoformat(),
                      "intake verification completed")
    return review_official_supply_relation(
        observations, supplier, customer, review, document,
        trusted_document_sha256=document_pin,
        decision_at=completed, now=completed, consumer_observed_at=completed,
    )


PUBLISHER_SCHEMA = "newscatalyst.publisher_relation_intake.v2"


def read_publisher_relation_intake(
    archive_root: Path, archive_version: str, trusted_receipt_sha256: str,
    private_review_json: Path, trusted_document_sha256: str,
    registry: ProviderRegistry, *, now: datetime | None = None,
) -> SupplyChainEdge:
    """Use a licensed IR/government document, without inventing an SEC filing.

    Existing immutable archive, explicit source permission and source evidence are
    required. This function reads only; it never grants rights, downloads a
    source, creates reviewer answers, or promotes a transaction to verified status.
    External publisher results have their own evidence status and graph schema.
    """
    # Reuse the filesystem-only private directory validator.
    from .private_paths import _existing_private_dir
    from .provider_registry import permits_document_storage
    root = _existing_private_dir(archive_root)
    receipt_pin = _must_sha(trusted_receipt_sha256, "archive receipt pin")
    document_pin = _must_sha(trusted_document_sha256, "publisher document pin")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved publisher registry required")
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "publisher intake started")
    document, archived = read_archived_evidence(root, archive_version, now=at)
    if (archived.content_scope != "LICENSED_SOURCE_BYTES"
            or archived.receipt_sha256 != receipt_pin
            or archived.payload_sha256 != document_pin):
        raise SourceShareError("licensed document and independent archive pins required")
    # Verify archive identity, not an unrelated filing/document reference.
    key = sha256((archived.provider_id + "\0" + archived.document_id).encode()).hexdigest()
    expected_version = sha256((key + "\0" + document_pin).encode()).hexdigest()
    if expected_version != archived.version_id:
        raise SourceShareError("publisher archive identity mismatch")
    provider = registry.active(archived.provider_id, at=at)
    if (provider.kind not in {"COMPANY_IR", "GOVERNMENT_POLICY"}
            or not permits_document_storage(provider)
            or not provider.enabled_at(archived.first_verified_at)):
        raise SourceShareError("publisher document storage permission missing or expired")
    data = _json(_private_input(private_review_json, MAX_REVIEW_BYTES),
                 "publisher document evidence")
    if (set(data) != {"schema", "relation_kind", "review", "supplier", "customer"}
            or data["schema"] != PUBLISHER_SCHEMA
            or data["relation_kind"] not in {"REPORTED_DIRECT_TRANSACTION", "ANNOUNCED_SUPPLY_PLAN"}):
        raise SourceShareError("publisher relation evidence schema required")
    review = _record(data["review"], OfficialRelationReview,
                     frozenset({"document_observed_at", "pin_observed_at", "reviewed_at"}))
    supplier = _record(data["supplier"], CompanyBinding, frozenset({"observed_at"}))
    customer = _record(data["customer"], CompanyBinding, frozenset({"observed_at"}))
    if ((review.source_id, review.source_document_id, review.source_evidence_id,
                review.source_receipt_sha256) !=
               (archived.provider_id, archived.document_id, archived.version_id, receipt_pin)
            or review.document_observed_at != archived.first_verified_at
            or not archived.archived_at <= review.pin_observed_at <= review.reviewed_at):
        raise SourceShareError("publisher evidence does not match archived source")
    completed = _when((now or datetime.now(timezone.utc)).isoformat(), "publisher intake completed")
    # Rights may expire while the document is being read.
    registry.active(archived.provider_id, at=completed)
    return _review_bound_document(
        archived, supplier, customer, review, document,
        trusted_document_sha256=document_pin, decision=completed, current=completed,
        consumer_observed_at=completed, source_evidence_id=archived.version_id,
        source_available_at=max(archived.first_verified_at, archived.archived_at),
        evidence_status=PUBLISHER_RELATION_STATUS, relation_kind=data["relation_kind"],
    )
