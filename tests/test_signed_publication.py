"""Synthetic independent Ed25519 release witness; never a real certification."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import subprocess

import pytest

from newscatalystos.signed_publication import SCHEMA, authenticate_publication
from newscatalystos.source_share import SourceShareError
from test_release_claim import sample, inspect
from test_era_capture_share import NOW


@pytest.fixture
def witness(tmp_path):
    secret, public = tmp_path / "synthetic-private.pem", tmp_path / "synthetic-public.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out",
                    str(secret)], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", str(secret), "-pubout", "-out",
                    str(public)], check=True, capture_output=True)
    return secret, public.read_bytes()


def signed(tmp_path, witness, provider="SEC", changes=None):
    candidate, data, original, directory = sample(tmp_path, provider)
    claim = inspect(candidate, data)
    attestation = {
        "schema": SCHEMA,
        "claim_sha256": claim.claim_sha256,
        "provider_id": claim.provider_id,
        "source_id": claim.source_id,
        "source_document_id": claim.source_document_id,
        "issuer_id": claim.issuer_id,
        "revision_id": claim.revision_id,
        "revision_kind": claim.revision_kind,
        "supersedes_document_id": claim.supersedes_document_id,
        "official_url": claim.official_url,
        "publisher_released_at": claim.claimed_published_at.isoformat(),
        "source_sha256": claim.source_sha256,
        "source_receipt_sha256": claim.source_receipt_sha256,
        "first_seen_at": claim.first_seen_at.isoformat(),
        "witness_id": "thirdparty-release-notary",
        "witness_verified_at": "2026-10-12T12:01:00+00:00",
    }
    attestation.update(changes or {})
    body = json.dumps(attestation, sort_keys=True, separators=(",", ":")).encode()
    private, public = witness
    message = tmp_path / "message"
    sig = tmp_path / "sig"
    message.write_bytes(body)
    subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(private),
                    "-rawin", "-in", str(message), "-out", str(sig)],
                   check=True, capture_output=True)
    return claim, body, sig.read_bytes(), public, original, directory


def check(claim, body, signature, key, **overrides):
    args = {
        "claim": claim, "statement": body, "signature": signature,
        "witness_public_key_pem": key,
        "trusted_public_key_sha256": sha256(key).hexdigest(),
        "trusted_witness_id": "thirdparty-release-notary",
        "decision_at": NOW, "now": NOW,
    }
    args.update(overrides)
    return authenticate_publication(**args)


@pytest.mark.parametrize("provider", ["SEC", "DART"])
def test_genuine_synthetic_witness_promotes_only_at_verified_decision(tmp_path, witness, provider):
    claim, body, sig, key, original, folder = signed(tmp_path, witness, provider)
    proof = check(claim, body, sig, key)
    event = proof.as_of(NOW)
    assert event.source_document_id == claim.source_document_id
    assert event.source_sha256 == claim.source_sha256
    assert event.source_receipt_sha256 == claim.source_receipt_sha256
    assert event.published_at == claim.claimed_published_at
    assert event.first_seen_at == proof.usable_from
    assert proof.source_capture_first_seen_at == claim.first_seen_at
    assert proof.witness_verified_at == event.first_seen_at
    assert proof.revision_id == claim.revision_id
    assert proof.revision_kind == claim.revision_kind
    assert proof.supersedes_document_id == claim.supersedes_document_id
    with pytest.raises(SourceShareError, match="not available"):
        proof.as_of(datetime(2026, 10, 12, 11, tzinfo=timezone.utc))
    assert (folder / "raw_response.json").read_bytes() == original


@pytest.mark.parametrize("changes", [
    {"publisher_released_at": "2026-10-12T09:00:00Z"},
    {"issuer_id": "NOT_THE_SAME_ISSUER"},
    {"claim_sha256": "0" * 64},
    {"source_sha256": "0" * 64},
    {"source_receipt_sha256": "0" * 64},
    {"first_seen_at": "2026-10-01T00:00:00Z"},
    {"provider_id": "DART"},
    {"source_document_id": "FAKE"},
    {"source_id": "dart-disclosures"},
    {"revision_id": "v2"},
    {"revision_kind": "CORRECTION"},
    {"supersedes_document_id": "ANOTHER"},
    {"witness_id": "unknown-witness"},
    {"witness_verified_at": "2026-10-12T11:59:00Z"},
    {"witness_verified_at": "2026-10-14T01:00:00Z"},
    {"schema": "untrusted.v0"},
    {"new_unverified_field": True},
])
def test_mismatched_or_future_signed_statement_fails(tmp_path, witness, changes):
    claim, body, sig, key, _, _ = signed(tmp_path, witness, changes=changes)
    with pytest.raises(SourceShareError):
        check(claim, body, sig, key)


def test_modified_bytes_even_with_same_old_signature_rejected(tmp_path, witness):
    claim, body, sig, key, _, _ = signed(tmp_path, witness)
    changed = body.replace(b"2026-10-12T12:01:00+00:00", b"2026-10-12T12:02:00+00:00")
    with pytest.raises(SourceShareError, match="signature"):
        check(claim, changed, sig, key)


def test_wrong_trust_pin_and_wrong_witness_rejected(tmp_path, witness):
    claim, body, sig, key, _, _ = signed(tmp_path, witness)
    with pytest.raises(SourceShareError, match="independent trust"):
        check(claim, body, sig, key, trusted_public_key_sha256="f" * 64)
    with pytest.raises(SourceShareError, match="differs"):
        check(claim, body, sig, key, trusted_witness_id="another-trust-root")
    with pytest.raises(SourceShareError, match="independent"):
        check(claim, body, sig, key, trusted_witness_id="eraleader")


def test_bad_signature_and_untrusted_claim_state_rejected(tmp_path, witness):
    claim, body, sig, key, _, _ = signed(tmp_path, witness)
    with pytest.raises(SourceShareError, match="signature"):
        check(claim, body, bytes(64), key)
    with pytest.raises(SourceShareError, match="expected unverified"):
        check(replace(claim, verification_status="OFFICIAL_CERTIFIED"), body, sig, key)


def test_proof_must_be_available_at_decision_not_backdated(tmp_path, witness):
    claim, body, sig, key, _, _ = signed(tmp_path, witness)
    with pytest.raises(SourceShareError, match="PIT"):
        check(claim, body, sig, key,
              decision_at=datetime(2026, 10, 12, 11, tzinfo=timezone.utc))
    with pytest.raises(SourceShareError, match="PIT"):
        check(claim, body, sig, key,
              decision_at=datetime(2026, 10, 14, tzinfo=timezone.utc))


def test_late_signer_not_made_available_at_raw_first_receipt(tmp_path, witness):
    claim, body, sig, key, _, _ = signed(tmp_path, witness)
    result = check(claim, body, sig, key)
    assert result.usable_from == datetime(2026, 10, 12, 12, 1, tzinfo=timezone.utc)
    assert result.source_capture_first_seen_at < result.usable_from


def test_legacy_v1_witness_without_capture_lineage_not_accepted(tmp_path, witness):
    claim, body, sig, public, _, _ = signed(
        tmp_path, witness,
        changes={"schema": "newscatalyst.publication_attestation.v1"},
    )
    with pytest.raises(SourceShareError, match="unexpected attestation schema"):
        check(claim, body, sig, public)

def test_witness_enrollment_time_prevents_backdating(tmp_path, witness):
    claim, body, sig, key, _, _ = signed(tmp_path, witness)
    enrolled = datetime(2026, 10, 12, 12, 20, tzinfo=timezone.utc)
    proof = check(claim, body, sig, key, witness_enrolled_at=enrolled)
    assert proof.witness_verified_at < enrolled
    assert proof.usable_from == enrolled
    assert proof.as_of(NOW).first_seen_at == enrolled
    with pytest.raises(SourceShareError, match="not available"):
        proof.as_of(datetime(2026, 10, 12, 12, 19, tzinfo=timezone.utc))
    with pytest.raises(SourceShareError, match="not enrolled at decision"):
        check(claim, body, sig, key,
              witness_enrolled_at=datetime(2026, 10, 14, tzinfo=timezone.utc))
    with pytest.raises(SourceShareError, match="timezone|invalid"):
        check(claim, body, sig, key, witness_enrolled_at=datetime(2026, 10, 12, 12, 20))
