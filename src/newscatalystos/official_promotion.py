"""Join a signed release proof to an independently anchored EraLeader capture.

All proofs remain contingent on an independently enrolled authoritative witness.
Never uses the collector, HTTP, EraLeader writes, or a made-up publication time.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .official_normalization import normalize_official_capture
from .pin_anchor import (
    LocalReferenceAnchor, TRUST_LEVEL, read_local_reference_anchor,
)
from .release_claim import inspect_release_claim
from .signed_publication import SignedPublication, authenticate_publication
from .source_share import RawEvent, SourceShareError, _when
from .verified_reference import (
    VerifiedOfficialSources, verify_official_research_reference,
)


@dataclass(frozen=True)
class AnchoredOfficialPublication:
    """A proof whose usable time is no earlier than ALL trusted observations."""
    attestation: SignedPublication
    reference_sha256: str
    anchor_first_observed_at: datetime
    usable_from: datetime

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> RawEvent:
        decision = _when(
            decision_at.isoformat() if isinstance(decision_at, datetime) else None,
            "decision_at",
        )
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.usable_from <= decision <= present:
            raise SourceShareError("anchored official proof unavailable at decision")
        event = self.attestation.as_of(decision)
        # The independent anchor may have been recorded after the witness:
        # the downstream event must not become usable before *both* exist.
        return replace(event, first_seen_at=self.usable_from)


def authenticate_anchored_official_record(
    verified: VerifiedOfficialSources,
    anchor: LocalReferenceAnchor,
    source_id: str,
    provider_document_id: str,
    claim_bytes: bytes,
    expected_claim_sha256: str,
    statement: bytes,
    signature: bytes,
    witness_public_key_pem: bytes,
    trusted_public_key_sha256: str,
    trusted_witness_id: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> AnchoredOfficialPublication:
    """Connect three independently verified contracts, never self-pin.

    The caller MUST have loaded verified/anchor from the independent-pin reader.
    The filesystem-enforcing wrapper below is for real usage. A signed witness
    statement is a claim by its signer; trusted issuance/publication authority
    and historical timestamp accuracy are external deployment requirements.
    """
    decision = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if decision > instant:
        raise SourceShareError("future decision")
    if not isinstance(verified, VerifiedOfficialSources) or not verified.research_only:
        raise SourceShareError("only verified research reference is allowed")
    if not isinstance(anchor, LocalReferenceAnchor) or anchor.trust_level != TRUST_LEVEL:
        raise SourceShareError("independently stored local anchor required")
    if verified.report_sha256 != anchor.report_sha256:
        raise SourceShareError("report reference differs from anchor pin")
    anchored_at = _when(anchor.observed_at.isoformat(), "anchor observed at")
    if anchored_at > decision or anchored_at > instant:
        raise SourceShareError("anchor not available at decision")
    matches = [capture for capture in verified.captures
               if capture.source_id == source_id]
    if len(matches) != 1:
        raise SourceShareError("exactly one pinned official source required")
    capture = matches[0]
    if source_id not in ("dart-disclosures", "sec-submissions"):
        raise SourceShareError("not a disclosure source")
    if capture.first_seen_at > anchored_at:
        raise SourceShareError("capture received after anchor was sealed")
    if (capture.release_time_verified or capture.historical_pit_certified or
            capture.completeness_certified):
        raise SourceShareError("unsupported capture certification")
    records = normalize_official_capture(capture, decision)
    candidates = [item for item in records
                  if item.provider_record_id == provider_document_id]
    if len(candidates) != 1:
        raise SourceShareError("official document missing or ambiguous in pinned capture")
    candidate = candidates[0]
    claim = inspect_release_claim(
        candidate, claim_bytes, expected_claim_sha256, decision, now=instant
    )
    # SEC request CIK is bound to the pinned receipt AND validated raw JSON.
    # Matching a URL to its own claimed issuer is not enough to prove lineage.
    if (capture.provider_id == "SEC" and
            (not capture.source_request_value.isdecimal() or
             not claim.issuer_id.isdecimal() or
             int(claim.issuer_id) != int(capture.source_request_value))):
        raise SourceShareError("SEC issuer mismatches original pinned request CIK")
    attestation = authenticate_publication(
        claim, statement, signature, witness_public_key_pem,
        trusted_public_key_sha256, trusted_witness_id, decision, now=instant
    )
    sealed_event = attestation.as_of(decision)
    if (sealed_event.source_sha256 != capture.raw_sha256 or
            sealed_event.source_receipt_sha256 != capture.first_receipt_sha256 or
            sealed_event.source_document_id != provider_document_id or
            attestation.source_capture_first_seen_at != capture.first_seen_at):
        raise SourceShareError("signed event differs from original pinned capture")
    usable_from = max(anchored_at, attestation.usable_from)
    if decision < usable_from:
        raise SourceShareError("signed proof not usable at decision")
    return AnchoredOfficialPublication(
        attestation=attestation, reference_sha256=verified.report_sha256,
        anchor_first_observed_at=anchored_at, usable_from=usable_from
    )


def authenticate_from_era_readonly(
    era_root: Path,
    research_reference: Path,
    private_anchor: Path,
    source_id: str,
    provider_document_id: str,
    claim_bytes: bytes,
    expected_claim_sha256: str,
    statement: bytes,
    signature: bytes,
    witness_public_key_pem: bytes,
    trusted_public_key_sha256: str,
    trusted_witness_id: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> AnchoredOfficialPublication:
    """Production entry: independent pin -> verified immutable source -> proof.

    File reads only; no EraLeader API invocation, no source/DB/Git mutation.
    """
    anchor = read_local_reference_anchor(
        era_root, research_reference, private_anchor, decision_at
    )
    reference = verify_official_research_reference(
        era_root, research_reference, anchor.report_sha256, decision_at, now=now
    )
    return authenticate_anchored_official_record(
        reference, anchor, source_id, provider_document_id,
        claim_bytes, expected_claim_sha256, statement, signature,
        witness_public_key_pem, trusted_public_key_sha256,
        trusted_witness_id, decision_at, now=now
    )
