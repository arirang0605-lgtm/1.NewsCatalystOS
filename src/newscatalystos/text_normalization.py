"""2_1 deterministic text and URL normalization on authorized metadata.

No article fetches, issuer matching, model calls, or mutation of evidence.
Callers retain raw SHA and use the cleaned string only for local filtering.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .new_source_adapter import FeedObservation
from .provider_registry import _safe_https_endpoint
from .source_share import SourceShareError, _when

SCHEMA = "newscatalyst.normalized_text.v1"
TRACKING = frozenset({
    "fbclid", "gclid", "yclid", "mc_cid", "mc_eid",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
})
MAX_TITLE_BYTES = 8192


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg", "iframe"}:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg", "iframe"} and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.parts.append(data)


def normalize_text(raw: str | bytes) -> tuple[str, str]:
    """Return (NFKC collapsed text, SHA of immutable input bytes)."""
    if isinstance(raw, str):
        raw_bytes = raw.encode("utf-8")
    elif isinstance(raw, bytes):
        raw_bytes = raw
    else:
        raise SourceShareError("text must be UTF-8 or str")
    if not 0 < len(raw_bytes) <= MAX_TITLE_BYTES:
        raise SourceShareError("empty or oversized title")
    try:
        decoded = raw_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise SourceShareError("unknown title encoding") from exc
    if "\x00" in decoded:
        raise SourceShareError("embedded NUL in title")
    parser = _TextOnly()
    try:
        parser.feed(decoded)
        parser.close()
    except ValueError as exc:
        raise SourceShareError("malformed title markup") from exc
    normalized = unicodedata.normalize("NFKC", html.unescape(" ".join(parser.parts)))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized or len(normalized) > 2048:
        raise SourceShareError("normalized title empty or excessive")
    return normalized, sha256(raw_bytes).hexdigest()


def canonicalize_url(raw: str) -> str:
    """Strip only known analytics parameters; preserve official document IDs."""
    parsed = urlsplit(raw)
    # Browser fragments are never transmitted to a source; strip before the
    # existing HTTPS/credential/secret-query validator.
    _safe_https_endpoint(urlunsplit(parsed._replace(fragment="")))
    host = parsed.hostname.lower()
    if not host:
        raise SourceShareError("missing URL host")
    if ".." in parsed.path.split("/"):
        raise SourceShareError("ambiguous source path")
    filtered = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING
    ]
    filtered.sort(key=lambda pair: (pair[0], pair[1]))
    return urlunsplit(("https", host, parsed.path or "/", urlencode(filtered), ""))


@dataclass(frozen=True)
class NormalizedText:
    schema_version: str
    source_id: str
    event_id: str
    text: str
    canonical_url: str
    raw_title_sha256: str
    observed_at: datetime
    available_at: datetime
    company_id: None = None
    published_at: None = None

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> "NormalizedText":
        decision = _when(decision_at.isoformat(), "decision_at")
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.available_at <= decision <= present:
            raise SourceShareError("normalized text not yet usable")
        return self


def normalize_feed_metadata(
    observation: FeedObservation, *, verified_at: datetime | None = None,
    now: datetime | None = None,
) -> NormalizedText:
    if not isinstance(observation, FeedObservation) or observation.reported_published_at is not None:
        raise SourceShareError("verified feed metadata only")
    now_time = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    checked = _when((verified_at or now_time).isoformat(), "verified_at")
    observed = _when(observation.first_seen_at.isoformat(), "observed_at")
    if observed > checked or checked > now_time:
        raise SourceShareError("future normalized metadata")
    title, digest = normalize_text(observation.headline)
    return NormalizedText(
        schema_version=SCHEMA, source_id=observation.provider_id,
        event_id=observation.event_id, text=title,
        canonical_url=canonicalize_url(observation.source_url),
        raw_title_sha256=digest, observed_at=observed,
        available_at=checked,
    )
