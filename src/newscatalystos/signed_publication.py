"""Offline verification of a separately trusted witness' signed release proof.

No self-issued trust roots, no public-source fetches and no EraLeader writes.
An Ed25519 signature proves endorsement by the pre-approved witness key,
not independently that the witness's real-world claims are true. Deployers
must establish authority and keep the public-key SHA pin outside input data.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from .release_claim import ReleaseClaim, STATUS as UNVERIFIED_STATUS
from .source_share import (
    EVENT_SCHEMA, RawEvent, SourceShareError, _json, _must_id, _must_sha, _when,
)

SCHEMA = "newscatalyst.publication_attestation.v2"
VERIFIED = "EXTERNAL_WITNESS_SIGNED_RELEASE"
REQUIRED = frozenset({
    "schema", "claim_sha256", "provider_id", "source_id",
    "source_document_id", "issuer_id", "revision_id", "revision_kind",
    "supersedes_document_id", "official_url", "publisher_released_at",
    "witness_id", "witness_verified_at",
    "source_sha256", "source_receipt_sha256", "first_seen_at",
})
MAX_ASSERTION = 8192


@dataclass(frozen=True)
class SignedPublication:
    _sealed_event: RawEvent
    claim_sha256: str
    revision_id: str
    revision_kind: str
    supersedes_document_id: str | None
    witness_id: str
    witness_verified_at: datetime
    usable_from: datetime
    witness_public_key_sha256: str
    source_capture_first_seen_at: datetime
    verification_status: str = VERIFIED

    def as_of(self, decision_at: datetime) -> RawEvent:
        decision = _when(
            decision_at.isoformat() if isinstance(decision_at, datetime) else None,
            "decision_at",
        )
        if decision < self.usable_from or decision > datetime.now(timezone.utc):
            raise SourceShareError("attested event not available at decision")
        # Never export a certified RawEvent with a first_seen_at that predates
        # the signed witness evidence. The original capture time remains
        # separately available via source_capture_first_seen_at.
        return replace(self._sealed_event, first_seen_at=self.usable_from)


def _verify_ed25519(statement: bytes, signature: bytes, key: bytes) -> None:
    if len(signature) != 64 or not key.startswith(b"-----BEGIN PUBLIC KEY-----"):
        raise SourceShareError("invalid Ed25519 witness signature/key encoding")
    binary = shutil.which("openssl")
    if binary is None:
        raise SourceShareError("openssl signature verifier unavailable")
    # The temporary files are owned by NewsCatalystOS, never EraLeader.
    with tempfile.TemporaryDirectory(prefix="newscatalyst-proof-") as temp:
        root = Path(temp)
        pub, message, sig = (root / name for name in ("key.pem", "message.json", "signature.bin"))
        pub.write_bytes(key)
        message.write_bytes(statement)
        sig.write_bytes(signature)
        try:
            key_check = subprocess.run(
                [binary, "pkey", "-pubin", "-in", str(pub), "-text_pub", "-noout"],
                capture_output=True, timeout=5, check=False,
            )
            if key_check.returncode or b"ED25519" not in key_check.stdout.upper():
                raise SourceShareError("witness key is not Ed25519")
            result = subprocess.run(
                [binary, "pkeyutl", "-verify", "-pubin", "-inkey", str(pub),
                 "-rawin", "-in", str(message), "-sigfile", str(sig)],
                capture_output=True, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SourceShareError("witness signature verification unavailable") from exc
        if result.returncode != 0:
            raise SourceShareError("invalid external witness signature")


def authenticate_publication(
    claim: ReleaseClaim,
    statement: bytes,
    signature: bytes,
    witness_public_key_pem: bytes,
    trusted_public_key_sha256: str,
    trusted_witness_id: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> SignedPublication:
    """Trust only out-of-band configured witness identity/key, not JSON claims.

    The attestation must have existed by the requested decision time and be
    signed by an independently enrolled release-time verifier. Retrospective
    validation must not rewrite the original first receipt or backfill a past
    decision. The publication timestamp itself is a witnessed assertion.
    """
    if not isinstance(claim, ReleaseClaim) or claim.verification_status != UNVERIFIED_STATUS:
        raise SourceShareError("expected unverified pinned official release claim")
    expected = _must_sha(trusted_public_key_sha256, "trusted witness key pin")
    if (not isinstance(witness_public_key_pem, bytes) or
        sha256(witness_public_key_pem).hexdigest() != expected):
        raise SourceShareError("witness key not in independent trust store")
    witness = _must_id(trusted_witness_id, "trusted_witness_id")
    if witness in ("eraleader", "newscatalystos"):
        raise SourceShareError("witness must be independent of both projects")
    if (not isinstance(statement, bytes) or not 0 < len(statement) <= MAX_ASSERTION or
        not isinstance(signature, bytes)):
        raise SourceShareError("bounded attestation/signature required")
    assertion = _json(statement, "signed attestation")
    if set(assertion) != REQUIRED or assertion["schema"] != SCHEMA:
        raise SourceShareError("unexpected attestation schema/fields")
    same = {
        "claim_sha256": claim.claim_sha256,
        "provider_id": claim.provider_id,
        "source_id": claim.source_id,
        "source_document_id": claim.source_document_id,
        "issuer_id": claim.issuer_id,
        "revision_id": claim.revision_id,
        "revision_kind": claim.revision_kind,
        "supersedes_document_id": claim.supersedes_document_id,
        "official_url": claim.official_url,
        "witness_id": witness,
        "source_sha256": claim.source_sha256,
        "source_receipt_sha256": claim.source_receipt_sha256,
    }
    if any(assertion[k] != v for k, v in same.items()):
        raise SourceShareError("signed evidence differs from pinned candidate")
    claimed_first_seen = _when(assertion["first_seen_at"], "first_seen_at")
    if claimed_first_seen != claim.first_seen_at:
        raise SourceShareError("witness first receipt differs from pinned capture")
    released = _when(assertion["publisher_released_at"], "publisher_released_at")
    if released != claim.claimed_published_at:
        raise SourceShareError("signed publication time differs from claim")
    attested = _when(assertion["witness_verified_at"], "witness_verified_at")
    decision = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if (attested < claim.observed_at or released > claim.first_seen_at or
        attested > decision or decision > present or released > attested):
        raise SourceShareError("attestation unavailable at decision / invalid PIT")
    _verify_ed25519(statement, signature, witness_public_key_pem)
    event_id = sha256((
        claim.provider_id + "\x00" + claim.source_document_id + "\x00"
        + claim.revision_id
    ).encode("utf-8")).hexdigest()
    event = RawEvent(
        schema_version=EVENT_SCHEMA,
        event_id=event_id,
        source_id=assertion["source_id"],
        provider_id=claim.provider_id,
        source_document_id=claim.source_document_id,
        company_id=claim.issuer_id,
        published_at=released,
        first_seen_at=claim.first_seen_at,
        source_sha256=claim.source_sha256,
        source_receipt_sha256=claim.source_receipt_sha256,
    )
    return SignedPublication(
        _sealed_event=event, claim_sha256=claim.claim_sha256,
        revision_id=claim.revision_id, revision_kind=claim.revision_kind,
        supersedes_document_id=claim.supersedes_document_id, witness_id=witness,
        witness_verified_at=attested,
        usable_from=max(claim.first_seen_at, attested),
        witness_public_key_sha256=expected,
        source_capture_first_seen_at=claim.first_seen_at,
    )
