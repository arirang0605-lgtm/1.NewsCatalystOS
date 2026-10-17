"""1_2 bounded, offline metadata adapters for explicitly authorized new feeds.

Parsing supplied RSS/JSON bytes is NOT evidence that their original claim is
true, or an authorization to fetch/store licensed articles. No network calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import xml.etree.ElementTree as ET

from .provider_registry import ProviderRegistry, _safe_https_endpoint
from .source_share import SourceShareError, _json, _when

# Official MSIT RSS includes embedded content:encoded for ~50 entries.
# Read a bounded 1 MiB response, but persist ONLY title, ID and source URL.
MAX_FEED_BYTES = 1024 * 1024
MAX_ITEMS = 100
STATUS = "FEED_METADATA_OBSERVED_SOURCE_CLAIMS_UNVERIFIED"


@dataclass(frozen=True)
class FeedObservation:
    provider_id: str
    event_id: str
    document_id: str
    headline: str
    source_url: str
    first_seen_at: datetime
    reported_published_at: None
    verification_status: str = STATUS


def _text(value: object, label: str, limit: int) -> str:
    if (not isinstance(value, str) or not 0 < len(value) <= limit or
            any(ord(x) < 32 and x not in "\n\t" for x in value)):
        raise SourceShareError(f"invalid {label}")
    clean = value.strip()
    if not clean:
        raise SourceShareError(f"empty {label}")
    return clean


def parse_authorized_feed(
    registry: ProviderRegistry, provider_id: str, feed: bytes,
    *, observed_at: datetime | None = None,
) -> tuple[FeedObservation, ...]:
    """Process only metadata; no article body/summary/full-text persistence."""
    moment = _when((observed_at or datetime.now(timezone.utc)).isoformat(), "observed_at")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved provider registry required")
    provider = registry.active(provider_id, at=moment)
    if not isinstance(feed, bytes) or not 0 < len(feed) <= MAX_FEED_BYTES:
        raise SourceShareError("feed missing or too large")
    results: list[tuple[str, str, str]] = []
    if provider.method in ("RSS", "RSS_POST"):
        # Do not allow DTD/entity expansion, external references or XML fetches.
        upper = feed.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise SourceShareError("XML entity declaration not allowed")
        try:
            root = ET.fromstring(feed)
        except ET.ParseError as exc:
            raise SourceShareError("invalid RSS feed") from exc
        if root.tag != "rss" or root.find("channel") is None:
            raise SourceShareError("unsupported RSS metadata feed")
        items = root.findall("channel/item")
        if len(items) > MAX_ITEMS:
            raise SourceShareError("feed item count exceeded")
        for item in items:
            results.append((
                item.findtext("guid") or item.findtext("link") or "",
                item.findtext("title") or "",
                item.findtext("link") or "",
            ))
    elif provider.method == "JSON_API":
        data = _json(feed, "JSON source feed")
        if set(data) != {"items"} or not isinstance(data["items"], list):
            raise SourceShareError("invalid JSON metadata structure")
        if len(data["items"]) > MAX_ITEMS:
            raise SourceShareError("feed item count exceeded")
        for row in data["items"]:
            if not isinstance(row, dict) or set(row) != {"id", "title", "url"}:
                raise SourceShareError("unrecognized JSON metadata fields")
            results.append((row["id"], row["title"], row["url"]))
    else:
        raise SourceShareError("unsupported provider adapter")
    parsed = []
    seen = set()
    for doc_id, headline, url in results:
        identity = _text(doc_id, "feed document_id", 512)
        headline = _text(headline, "headline", 256)
        url = _safe_https_endpoint(url)
        event_id = sha256((provider_id + "\0" + identity).encode()).hexdigest()
        if event_id in seen:
            continue  # same feed id repeated; no duplicate novelty
        seen.add(event_id)
        parsed.append(FeedObservation(
            provider_id=provider_id, event_id=event_id,
            document_id=identity, headline=headline, source_url=url,
            first_seen_at=moment, reported_published_at=None,
        ))
    return tuple(parsed)
