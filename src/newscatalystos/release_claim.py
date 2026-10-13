"""Bounded release-time *claim* inspection; not issuer/publication attestation.

An independently pinned hash authenticates bytes only against a caller's pin.
It does NOT authenticate the claimed official URL, a timestamp, or an issuer.
Do not promote this candidate to a RawEvent without a separately verified
official publication proof. This module never makes HTTP calls or writes files.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from .official_normalization import OfficialEvidenceCandidate
from .source_share import SourceShareError, _json, _must_id, _must_sha, _when

SCHEMA = "newscatalyst.release_claim.v1"
STATUS = "PINNED_CLAIM_UNAUTHENTICATED"
MAX_CLAIM_BYTES = 8192
CLAIM_KEYS = frozenset({
    "schema", "provider_id", "source_id", "source_document_id",
    "issuer_id", "revision_id", "revision_kind", "supersedes_document_id",
    "claimed_published_at", "observed_at", "official_url",
})


@dataclass(frozen=True)
class ReleaseClaim:
    schema_version: str
    evidence_id: str
    provider_id: str
    source_document_id: str
    issuer_id: str
    revision_id: str
    revision_kind: str
    supersedes_document_id: str | None
    claimed_published_at: datetime
    observed_at: datetime
    first_seen_at: datetime
    official_url: str
    claim_sha256: str
    source_sha256: str
    source_receipt_sha256: str
    verification_status: str = STATUS

    def to_raw_event(self) -> None:
        raise SourceShareError(
            "RawEvent promotion blocked: source URL and metadata claim do not "
            "authenticate issuer, publication time or correction history"
        )


def _official_url(provider: str, document_id: str, url: object) -> str:
    if not isinstance(url, str) or len(url) > 2048 or any(
        ord(c) <= 32 or ord(c) == 127 for c in url
    ):
        raise SourceShareError("invalid official URL")
    try:
        uri = urlsplit(url)
        host = uri.hostname
        port = uri.port
    except ValueError as exc:
        raise SourceShareError("invalid official URL") from exc
    if (uri.scheme != "https" or uri.username is not None or
        uri.password is not None or uri.fragment or port is not None):
        raise SourceShareError("unsafe official URL")
    if provider == "DART":
        params = parse_qs(uri.query, keep_blank_values=True)
        if (host != "dart.fss.or.kr" or uri.path != "/dsaf001/main.do" or
            params != {"rcpNo": [document_id]}):
            raise SourceShareError("DART URL/document mismatch")
    elif provider == "SEC":
        accession = document_id.replace("-", "")
        if (host != "www.sec.gov" or not
            uri.path.startswith("/Archives/edgar/data/") or
            accession not in uri.path.split("/") or uri.query):
            raise SourceShareError("SEC URL/accession mismatch")
    else:
        raise SourceShareError("source has no disclosure release contract")
    return url


def inspect_release_claim(
    candidate: OfficialEvidenceCandidate,
    claim_bytes: bytes,
    expected_claim_sha256: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> ReleaseClaim:
    """Inspect separately SHA-pinned official *metadata claims*, never certify.

    The expected digest must have been obtained from a separate trusted record;
    hashing the supplied bytes and using that value as the pin is not proof.
    An authoritative page fetch, publisher identity and independent release
    timestamp have NOT been authenticated by this function.
    """
    _must_sha(expected_claim_sha256, "external claim pin")
    if (not isinstance(claim_bytes, bytes) or not 0 < len(claim_bytes) <= MAX_CLAIM_BYTES or
        sha256(claim_bytes).hexdigest() != expected_claim_sha256):
        raise SourceShareError("release claim bytes are not independently pinned")
    if not isinstance(candidate, OfficialEvidenceCandidate) or (
        candidate.provider_id not in ("SEC", "DART") or
        candidate.verified_published_at is not None or
        candidate.classification != "RELEASE_UNVERIFIED_RESEARCH_ONLY"
    ):
        raise SourceShareError("not an unverified disclosure candidate")
    decision = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    instant = _when((now or datetime.now().astimezone()).isoformat(), "now")
    if decision > instant or candidate.first_seen_at > decision:
        raise SourceShareError("future decision or first receipt")
    data = _json(claim_bytes, "release claim")
    if set(data) != CLAIM_KEYS or data["schema"] != SCHEMA:
        raise SourceShareError("unexpected claim schema/fields")
    if (data["provider_id"] != candidate.provider_id or
        data["source_id"] != candidate.source_id or
        data["source_document_id"] != candidate.provider_record_id):
        raise SourceShareError("claim source/document mismatch")
    issuer = _must_id(data["issuer_id"], "issuer_id")
    revision = _must_id(data["revision_id"], "revision_id")
    kind = data["revision_kind"]
    supersedes = data["supersedes_document_id"]
    if kind == "ORIGINAL":
        if supersedes is not None:
            raise SourceShareError("original cannot supersede a document")
    elif kind == "CORRECTION":
        supersedes = _must_id(supersedes, "supersedes_document_id")
        if supersedes == candidate.provider_record_id:
            raise SourceShareError("self-referential correction")
    else:
        raise SourceShareError("invalid revision kind")
    published = _when(data["claimed_published_at"], "claimed_published_at")
    observed = _when(data["observed_at"], "observed_at")
    if (published > candidate.first_seen_at or published > observed or
        observed > decision or published > decision):
        raise SourceShareError("claimed release/observation PIT mismatch")
    if candidate.provider_id == "DART":
        if not candidate.provider_day or (
            published.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
            != candidate.provider_day
        ):
            raise SourceShareError("DART date/claimed release mismatch")
    elif (candidate.provider_acceptance_at is None or
          published < candidate.provider_acceptance_at):
        raise SourceShareError("SEC release predates acceptance")
    url = _official_url(candidate.provider_id, candidate.provider_record_id,
                        data["official_url"])
    return ReleaseClaim(
        schema_version=SCHEMA, evidence_id=candidate.evidence_id,
        provider_id=candidate.provider_id,
        source_document_id=candidate.provider_record_id,
        issuer_id=issuer, revision_id=revision, revision_kind=kind,
        supersedes_document_id=supersedes, claimed_published_at=published,
        observed_at=observed, first_seen_at=candidate.first_seen_at,
        official_url=url, claim_sha256=expected_claim_sha256,
        source_sha256=candidate.source_sha256,
        source_receipt_sha256=candidate.source_receipt_sha256,
    )
