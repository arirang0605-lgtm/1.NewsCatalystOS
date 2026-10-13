"""4_3 separate provenance, explicit evidence and AI hypotheses.

The classification records what has been OBSERVED, not legal issuer identity,
profitability or commercial impact. A claimed official-looking headline is not
enough to establish a verified official source.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit

from .source_share import SourceShareError, _must_sha, _when
from .official_promotion import AnchoredOfficialPublication
from .provider_registry import _safe_https_endpoint

KINDS = frozenset({
    "OFFICIAL_CHANNEL", "DISTRIBUTED_RELEASE", "INDEPENDENT_NEWS",
    "SOCIAL_RUMOR", "AI_HYPOTHESIS",
})


@dataclass(frozen=True)
class ClaimBoundary:
    source_event_sha256: str
    claim_sha256: str
    origin_kind: str
    source_url: str | None
    evidence_quote_sha256: str | None
    first_usable_at: datetime
    reviewed_at: datetime
    evidence_status: str
    issuer_verified: bool
    independent_confirmation: bool
    inference_only: bool
    verified_economic_fact: bool = False

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> "ClaimBoundary":
        decision = _when(decision_at.isoformat(), "decision_at")
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.reviewed_at <= decision <= present:
            raise SourceShareError("claim boundary not available at decision")
        return self


def classify_evidence_claim(
    event_sha256: str, claim_text: str, kind: str,
    *,
    source_url: str | None,
    evidence_quote: str | None,
    first_usable_at: datetime,
    reviewed_at: datetime,
    now: datetime | None = None,
    anchored_publication: AnchoredOfficialPublication | None = None,
    independent_source_reviewed: bool = False,
) -> ClaimBoundary:
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    first = _when(first_usable_at.isoformat(), "first usable")
    reviewed = _when(reviewed_at.isoformat(), "reviewed at")
    if not first <= reviewed <= current:
        raise SourceShareError("future claim review")
    event = _must_sha(event_sha256, "source event id")
    if kind not in KINDS or not isinstance(claim_text, str) or not 0 < len(claim_text) <= 700:
        raise SourceShareError("invalid claim text/origin kind")
    if type(independent_source_reviewed) is not bool:
        raise SourceShareError("invalid independence review flag")
    signed_issuer_certificate = False
    if anchored_publication is not None:
        if kind != "OFFICIAL_CHANNEL" or not isinstance(
            anchored_publication, AnchoredOfficialPublication
        ):
            raise SourceShareError("verified anchored publication required for issuer certification")
        signed_event = anchored_publication.as_of(reviewed, now=current)
        if signed_event.event_id != event:
            raise SourceShareError("signed source event mismatch")
        signed_issuer_certificate = True
    if source_url is not None:
        _safe_https_endpoint(source_url)
    if evidence_quote is not None and (
        not isinstance(evidence_quote, str) or
        not 0 < len(evidence_quote) <= 400 or
        evidence_quote not in claim_text
    ):
        raise SourceShareError("claim quote is not source-bound")
    if independent_source_reviewed and kind not in ("INDEPENDENT_NEWS",):
        raise SourceShareError("independence review incompatible with origin")
    category = {
        "OFFICIAL_CHANNEL": ("OFFICIAL_ISSUER_CERTIFIED" if signed_issuer_certificate
                             else "OFFICIAL_CHANNEL_OBSERVED_UNCERTIFIED"),
        "DISTRIBUTED_RELEASE": "DISTRIBUTED_UNVERIFIED_CLAIM",
        "INDEPENDENT_NEWS": ("INDEPENDENT_REPORT_REVIEWED_NOT_FACT_ATTESTED"
                             if independent_source_reviewed else "REPORT_SOURCE_UNVERIFIED"),
        "SOCIAL_RUMOR": "RUMOR_UNVERIFIED",
        "AI_HYPOTHESIS": "AI_INFERENCE_UNVERIFIED",
    }[kind]
    return ClaimBoundary(
        event, sha256(claim_text.encode()).hexdigest(), kind, source_url,
        sha256(evidence_quote.encode()).hexdigest() if evidence_quote is not None else None,
        first, reviewed, category,
        signed_issuer_certificate, independent_source_reviewed,
        kind == "AI_HYPOTHESIS", False,
    )
