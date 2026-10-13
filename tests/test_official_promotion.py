"""Synthetic proof-to-pinned-capture joining; not a live official witness."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.era_capture_share import read_official_capture
from newscatalystos.official_promotion import authenticate_anchored_official_record
from newscatalystos.pin_anchor import LocalReferenceAnchor
from newscatalystos.release_claim import SCHEMA as CLAIM_SCHEMA
from newscatalystos.source_share import SourceShareError
from newscatalystos.verified_reference import VerifiedOfficialSources
from test_signed_publication import signed, witness
from test_era_capture_share import NOW

REPORT_SHA = "a" * 64
ANCHOR_AT = datetime(2026, 10, 12, 12, 10, tzinfo=timezone.utc)
BEFORE_ANCHOR = datetime(2026, 10, 12, 12, 5, tzinfo=timezone.utc)


def scenario(tmp_path, witness, provider="SEC"):
    claim, statement, signature, public, original, folder = signed(
        tmp_path, witness, provider
    )
    era = folder.parents[2]
    receipt = sha256((folder / "first_receipt.json").read_bytes()).hexdigest()
    capture = read_official_capture(folder, era, receipt, NOW, now=NOW)
    sources = VerifiedOfficialSources(
        report_sha256=REPORT_SHA, captures=(capture,)
    )
    anchor = LocalReferenceAnchor(REPORT_SHA, ANCHOR_AT)
    raw_claim = {
        "schema": CLAIM_SCHEMA,
        "provider_id": claim.provider_id,
        "source_id": claim.source_id,
        "source_document_id": claim.source_document_id,
        "issuer_id": claim.issuer_id,
        "revision_id": claim.revision_id,
        "revision_kind": claim.revision_kind,
        "supersedes_document_id": claim.supersedes_document_id,
        "claimed_published_at": (
            "2026-10-12T09:05:00Z" if provider == "SEC" else "2026-10-08T01:00:00Z"
        ),
        "observed_at": "2026-10-12T12:00:00Z",
        "official_url": claim.official_url,
    }
    claim_bytes = json.dumps(raw_claim, sort_keys=True).encode()
    assert sha256(claim_bytes).hexdigest() == claim.claim_sha256
    values = {
        "verified": sources,
        "anchor": anchor,
        "source_id": claim.source_id,
        "provider_document_id": claim.source_document_id,
        "claim_bytes": claim_bytes,
        "expected_claim_sha256": claim.claim_sha256,
        "statement": statement,
        "signature": signature,
        "witness_public_key_pem": public,
        "trusted_public_key_sha256": sha256(public).hexdigest(),
        "trusted_witness_id": "thirdparty-release-notary",
        "decision_at": NOW,
        "now": NOW,
    }
    return values, folder, original


@pytest.mark.parametrize("provider", ["SEC", "DART"])
def test_pinned_capture_signed_claim_anchor_join_as_of(tmp_path, witness, provider):
    values, folder, original = scenario(tmp_path, witness, provider)
    bound = authenticate_anchored_official_record(**values)
    event = bound.as_of(NOW, now=NOW)
    assert event.source_sha256 == values["verified"].captures[0].raw_sha256
    assert event.source_receipt_sha256 == values["verified"].captures[0].first_receipt_sha256
    assert event.source_document_id == values["provider_document_id"]
    assert event.first_seen_at == bound.usable_from
    assert bound.attestation.source_capture_first_seen_at < bound.usable_from
    assert bound.usable_from == ANCHOR_AT
    with pytest.raises(SourceShareError, match="unavailable"):
        bound.as_of(BEFORE_ANCHOR, now=NOW)
    assert (folder / "raw_response.json").read_bytes() == original


@pytest.mark.parametrize("field,wrong,expected", [
    ("source_id", "dart-disclosures", "one pinned official source"),
    ("provider_document_id", "0000320193-26-999999", "missing or ambiguous"),
    ("expected_claim_sha256", "0" * 64, "independently pinned"),
    ("trusted_public_key_sha256", "0" * 64, "independent trust"),
    ("trusted_witness_id", "newscatalystos", "independent"),
])
def test_wrong_evidence_binding_fails(tmp_path, witness, field, wrong, expected):
    values, _, _ = scenario(tmp_path, witness)
    values[field] = wrong
    with pytest.raises(SourceShareError, match=expected):
        authenticate_anchored_official_record(**values)


def test_reference_pin_and_anchor_time_cannot_be_forged(tmp_path, witness):
    values, _, _ = scenario(tmp_path, witness)
    values["anchor"] = replace(values["anchor"], report_sha256="f" * 64)
    with pytest.raises(SourceShareError, match="differs from anchor"):
        authenticate_anchored_official_record(**values)
    values, _, _ = scenario(tmp_path / "another", witness)
    values["anchor"] = replace(values["anchor"], observed_at=NOW + timedelta(seconds=1))
    with pytest.raises(SourceShareError, match="not available"):
        authenticate_anchored_official_record(**values)
    values["anchor"] = replace(values["anchor"], trust_level="FAKE_EXTERNAL_ATTESTATION")
    with pytest.raises(SourceShareError, match="independently stored"):
        authenticate_anchored_official_record(**values)


def test_original_capture_swap_or_wrong_sha_cannot_promote(tmp_path, witness):
    values, _, _ = scenario(tmp_path, witness)
    source = values["verified"].captures[0]
    changed = replace(source, raw_sha256="b" * 64)
    values["verified"] = replace(values["verified"], captures=(changed,))
    with pytest.raises(SourceShareError, match="differs from pinned candidate|differs from original"):
        authenticate_anchored_official_record(**values)


def test_research_sources_never_pretend_to_be_certified(tmp_path, witness):
    values, _, _ = scenario(tmp_path, witness)
    values["verified"] = replace(values["verified"], research_only=False)
    with pytest.raises(SourceShareError, match="verified research"):
        authenticate_anchored_official_record(**values)
    values, _, _ = scenario(tmp_path / "untrusted", witness)
    changed = replace(values["verified"].captures[0], release_time_verified=True)
    values["verified"] = replace(values["verified"], captures=(changed,))
    with pytest.raises(SourceShareError, match="unsupported capture certification"):
        authenticate_anchored_official_record(**values)


def test_no_actual_signer_is_never_substituted_by_local_anchor(tmp_path, witness):
    values, _, _ = scenario(tmp_path, witness)
    values["signature"] = b"\x00" * 64
    with pytest.raises(SourceShareError, match="signature"):
        authenticate_anchored_official_record(**values)
    values, _, _ = scenario(tmp_path / "late", witness)
    values["decision_at"] = BEFORE_ANCHOR
    with pytest.raises(SourceShareError, match="anchor not available"):
        authenticate_anchored_official_record(**values)


def test_sec_issuer_must_match_signed_and_pinned_original_request_cik(tmp_path, witness):
    values, _, _ = scenario(tmp_path, witness)
    capture = values["verified"].captures[0]
    assert capture.source_request_value == "320193"
    bad = replace(capture, source_request_value="999999")
    values["verified"] = replace(values["verified"], captures=(bad,))
    with pytest.raises(SourceShareError, match="issuer mismatches original pinned request CIK"):
        authenticate_anchored_official_record(**values)


def test_downstream_event_first_seen_never_predates_late_anchor(tmp_path, witness):
    """The public RawEvent cannot masquerade as certified at source receipt."""
    from dataclasses import asdict
    values, _, _ = scenario(tmp_path, witness)
    proof = authenticate_anchored_official_record(**values)
    event = proof.as_of(NOW, now=NOW)
    assert proof.attestation.usable_from < proof.usable_from
    assert proof.attestation.source_capture_first_seen_at < proof.usable_from
    assert event.first_seen_at == proof.usable_from
    assert asdict(event)["first_seen_at"] == proof.usable_from
    assert event.published_at < event.first_seen_at
    with pytest.raises(SourceShareError, match="unavailable"):
        proof.as_of(proof.usable_from - timedelta(microseconds=1), now=NOW)

def test_late_witness_enrollment_blocks_historical_event(tmp_path, witness):
    values, _, _ = scenario(tmp_path, witness)
    enrolled = ANCHOR_AT + timedelta(minutes=5)
    values["witness_enrolled_at"] = enrolled
    proof = authenticate_anchored_official_record(**values)
    assert proof.usable_from == enrolled
    assert proof.as_of(NOW, now=NOW).first_seen_at == enrolled
    with pytest.raises(SourceShareError, match="unavailable"):
        proof.as_of(ANCHOR_AT, now=NOW)

def test_late_arriving_witness_bytes_never_certify_prior_decision(tmp_path, witness):
    values, _, _ = scenario(tmp_path, witness)
    arrived = ANCHOR_AT + timedelta(minutes=7)
    values["proof_observed_at"] = arrived
    proof = authenticate_anchored_official_record(**values)
    assert proof.usable_from == arrived
    assert proof.as_of(NOW, now=NOW).first_seen_at == arrived
    with pytest.raises(SourceShareError, match="unavailable"):
        proof.as_of(ANCHOR_AT, now=NOW)
    values["decision_at"] = arrived - timedelta(microseconds=1)
    with pytest.raises(SourceShareError, match="proof.*decision"):
        authenticate_anchored_official_record(**values)


def test_production_wrapper_requires_observed_proof_before_source_reads(monkeypatch, tmp_path):
    from newscatalystos import official_promotion as mod

    def no_reads(*args, **kwargs):
        raise AssertionError("source read before confirming evidence arrival")
    monkeypatch.setattr(mod, "read_local_reference_anchor", no_reads)
    with pytest.raises(SourceShareError, match="proof.*decision"):
        mod.authenticate_from_era_readonly(
            tmp_path, tmp_path / "research", tmp_path / "pin",
            "sec-submissions", "doc1", b"{}", "a" * 64,
            b"{}", b"x" * 64, b"public key", "b" * 64,
            "registered-external-witness", ANCHOR_AT,
            proof_observed_at=NOW, now=NOW,
        )
