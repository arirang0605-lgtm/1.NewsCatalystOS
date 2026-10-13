"""One authorized HTTPS feed fetch per explicit 1_2 invocation; no scheduler.

Do not follow redirects, collect raw article bodies, retry on access denial,
or persist responses. Only pre-reviewed feed metadata reaches the adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)

from .new_source_adapter import (
    MAX_FEED_BYTES, FeedObservation, parse_authorized_feed,
)
from .provider_registry import ProviderRegistry, _safe_https_endpoint
from .source_share import SourceShareError, _when

RSS_MEDIA = frozenset({"application/xml", "application/rss+xml", "text/xml"})
JSON_MEDIA = frozenset({"application/json", "text/json"})
MAX_TIMEOUT_SECONDS = 10


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_opener():
    # Verified TLS; no system proxy or redirects to unreviewed hosts.
    return build_opener(
        ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()),
        _NoRedirect(),
    )


def fetch_authorized_once(
    registry: ProviderRegistry, provider_id: str, *,
    at: datetime | None = None, timeout_seconds: float = 6,
    opener=None,
) -> tuple[FeedObservation, ...]:
    """Fetch one approved feed and return metadata, nothing written anywhere.

    The registry authorization and review evidence are operator-controlled;
    an approval string alone is not a legal license.
    """
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved provider registry required")
    instant = _when((at or datetime.now(timezone.utc)).isoformat(), "at")
    provider = registry.active(provider_id, at=instant)
    endpoint = _safe_https_endpoint(provider.endpoint)
    if (type(timeout_seconds) not in (int, float)
            or not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS):
        raise SourceShareError("invalid bounded feed timeout")
    getter = opener if opener is not None else _default_opener()
    request = Request(
        endpoint, method="GET",
        headers={"Accept": "application/rss+xml,application/xml,text/xml,application/json",
                 "User-Agent": "NewsCatalystOS/1.0 (authorized metadata feed reader)"},
    )
    try:
        with getter.open(request, timeout=timeout_seconds) as response:
            if response.getcode() != 200:
                raise SourceShareError("official feed HTTP response not successful")
            if response.geturl() != endpoint:
                raise SourceShareError("feed redirected to an unapproved endpoint")
            expected = RSS_MEDIA if provider.method == "RSS" else JSON_MEDIA
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if mime not in expected:
                raise SourceShareError("unapproved feed content type")
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    length = int(content_length)
                except ValueError as exc:
                    raise SourceShareError("invalid feed content length") from exc
                if not 0 <= length <= MAX_FEED_BYTES:
                    raise SourceShareError("feed exceeds configured size limit")
            raw = response.read(MAX_FEED_BYTES + 1)
    except HTTPError as exc:
        raise SourceShareError(f"provider HTTP status {exc.code}; no retry") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise SourceShareError("provider feed transport unavailable") from None
    if not raw or len(raw) > MAX_FEED_BYTES:
        raise SourceShareError("feed missing or exceeds size limit")
    # Delivery, not claimed publication time, is the earliest PIT signal.
    verified_at = _when((at or datetime.now(timezone.utc)).isoformat(), "verified_at")
    return parse_authorized_feed(registry, provider_id, raw, observed_at=verified_at)
