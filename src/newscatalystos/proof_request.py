"""Prepare a bounded external-witness request from already pinned captures.

Research metadata only. This is an audit request, NEVER publication evidence,
a certified RawEvent, a newly collected SEC/DART record or a trust enrollment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .official_normalization import normalize_official_capture
from .pin_anchor import LocalReferenceAnchor, TRUST_LEVEL, read_local_reference_anchor
from .source_share import SourceShareError, _must_id, _when
from .verified_reference import VerifiedOfficialSources, verify_official_research_reference

SCHEMA = "newscatalyst.external_proof_request.v1"
STATUS = "EXTERNAL_EVIDENCE_REQUIRED_NOT_CERTIFIED"
DISCLOSURES = frozenset({"dart-disclosures", "sec-submissions"})


def build_official_proof_request(
    verified: VerifiedOfficialSources,
    anchor: LocalReferenceAnchor,
    source_id: str,
    document_id: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> dict:
    """Produce one non-certifying request; only metadata from a pinned capture."""
    decision = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    _must_id(document_id, "document_id")
    if decision > instant:
        raise SourceShareError("future proof request decision")
    if source_id not in DISCLOSURES:
        raise SourceShareError("not an eligible disclosure source")
    if (not isinstance(verified, VerifiedOfficialSources)
        or verified.research_only is not True
        or not isinstance(anchor, LocalReferenceAnchor)
        or anchor.trust_level != TRUST_LEVEL
        or verified.report_sha256 != anchor.report_sha256):
        raise SourceShareError("untrusted research reference or anchor")
    if anchor.observed_at > decision or anchor.observed_at > instant:
        raise SourceShareError("anchor not available at request decision")
    matches = [c for c in verified.captures if c.source_id == source_id]
    if len(matches) != 1:
        raise SourceShareError("source unavailable or ambiguous in pinned captures")
    capture = matches[0]
    if capture.first_seen_at > anchor.observed_at:
        raise SourceShareError("capture first received after anchor")
    records = normalize_official_capture(capture, decision)
    candidates = [r for r in records if r.provider_record_id == document_id]
    if len(candidates) != 1:
        raise SourceShareError("document unavailable or ambiguous in pinned capture")
    item = candidates[0]
    return {
        "schema": SCHEMA,
        "status": STATUS,
        "certified_raw_event_count": 0,
        "source_id": item.source_id,
        "provider_id": item.provider_id,
        "source_document_id": item.provider_record_id,
        "source_sha256": item.source_sha256,
        "source_receipt_sha256": item.source_receipt_sha256,
        "research_reference_sha256": verified.report_sha256,
        "capture_first_seen_at": item.first_seen_at.isoformat(),
        "local_anchor_observed_at": anchor.observed_at.isoformat(),
        "provider_acceptance_at": (
            item.provider_acceptance_at.isoformat()
            if item.provider_acceptance_at else None
        ),
        "provider_day": item.provider_day,
        "publisher_released_at": None,
        "issuer_id": None,
        "revision_id": None,
        "supersedes_document_id": None,
        "missing_external_evidence": [
            "authority_verified_issuer_identity",
            "independently_observed_public_release_time",
            "version_and_correction_lineage",
            "independent_witness_identity_and_prior_enrollment",
            "signed_attestation_and_actual_first_evidence_observation",
        ],
        "request_created_at": instant.isoformat(),
    }


def request_from_era_readonly(
    era_root: Path,
    research_reference: Path,
    private_anchor: Path,
    source_id: str,
    document_id: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> dict:
    """The single real-file entrypoint. No requests to providers or writes."""
    anchor = read_local_reference_anchor(
        era_root, research_reference, private_anchor, decision_at
    )
    verified = verify_official_research_reference(
        era_root, research_reference, anchor.report_sha256, decision_at, now=now
    )
    return build_official_proof_request(
        verified, anchor, source_id, document_id, decision_at, now=now
    )
