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


class FeedTransportError(SourceShareError):
    """Classifiable failure; caller may schedule later retry, never inline retry."""

    def __init__(self, reason: str, *, http_code: int | None = None):
        super().__init__(reason)
        self.http_code = http_code
        self.retryable = http_code in (408, 429) or (http_code is not None and 500 <= http_code <= 599)


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
    at: datetime | None = None, timeout_seconds: float = MAX_TIMEOUT_SECONDS,
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
    # Existing providers remain GET. The official MOTIR press RSS form
    # explicitly submits an empty POST; the registry restricts this method
    # to its exact approved HTTPS endpoint so unrelated hosts never receive
    # an unplanned POST or any credentials.
    post = provider.method == "RSS_POST"
    request = Request(
        endpoint, data=b"" if post else None,
        method="POST" if post else "GET",
        headers={"Accept": ("text/html" if provider.method == "HTML_METADATA" else
                            "application/rss+xml,application/xml,text/xml,application/json"),
                 "User-Agent": "NewsCatalystOS/1.0 (authorized metadata feed reader)"},
    )
    try:
        with getter.open(request, timeout=timeout_seconds) as response:
            if response.getcode() != 200:
                raise SourceShareError("official feed HTTP response not successful")
            if response.geturl() != endpoint:
                raise SourceShareError("feed redirected to an unapproved endpoint")
            expected = ({"text/html"} if provider.method == "HTML_METADATA" else
                        RSS_MEDIA if provider.method in ("RSS", "RSS_POST") else JSON_MEDIA)
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
        raise FeedTransportError(f"provider HTTP status {exc.code}; no inline retry",
                                 http_code=exc.code) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise FeedTransportError("provider feed transport unavailable",
                                 http_code=503) from None
    if not raw or len(raw) > MAX_FEED_BYTES:
        raise SourceShareError("feed missing or exceeds size limit")
    # Delivery, not claimed publication time, is the earliest PIT signal.
    verified_at = _when((at or datetime.now(timezone.utc)).isoformat(), "verified_at")
    return parse_authorized_feed(registry, provider_id, raw, observed_at=verified_at)
