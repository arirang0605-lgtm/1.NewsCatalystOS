"""1_2 HTTPS one-shot source checks without real network or persistence."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.error import HTTPError, URLError
import json

import pytest

from newscatalystos.feed_transport import fetch_authorized_once
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import registry, RSS, NOW


class _Response:
    def __init__(self, endpoint, body=RSS, code=200, media="application/rss+xml",
                 redirect=None, length=None):
        self.code = code
        self.url = redirect or endpoint
        self.body = BytesIO(body)
        self.headers = {"Content-Type": media}
        if length is not None:
            self.headers["Content-Length"] = str(length)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def getcode(self):
        return self.code

    def geturl(self):
        return self.url

    def read(self, n):
        return self.body.read(n)


class _Opener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def open(self, request, timeout):
        self.calls += 1
        assert request.get_method() == "GET"
        assert timeout == 10  # large official RSS is still bounded, not retried.
        if self.error is not None:
            raise self.error
        return self.response


def test_approved_metadata_only_one_get_and_pit():
    reg = registry()
    url = reg.active("synthetic-government-feed", at=NOW).endpoint
    transport = _Opener(_Response(url))
    result = fetch_authorized_once(
        reg, "synthetic-government-feed", at=NOW, opener=transport
    )
    assert transport.calls == 1 and len(result) == 1
    assert result[0].first_seen_at == NOW
    assert result[0].reported_published_at is None
    assert "PRIVATE BODY" not in str(result)


def test_unapproved_source_never_contacts_network():
    transport = _Opener()
    with pytest.raises(SourceShareError, match="not approved"):
        fetch_authorized_once(
            registry(False), "synthetic-government-feed",
            at=NOW, opener=transport,
        )
    assert transport.calls == 0


@pytest.mark.parametrize("kind", ["http403", "redirect", "oversized", "wrongmime",
                                   "not200", "network_error", "truncated"])
def test_transport_failure_is_redacted_and_does_not_retry(kind):
    reg = registry()
    endpoint = reg.active("synthetic-government-feed", at=NOW).endpoint
    if kind == "http403":
        transport = _Opener(error=HTTPError(endpoint, 403, "Forbidden", {}, None))
    elif kind == "redirect":
        transport = _Opener(_Response(endpoint, redirect="https://evil.example.com/feed"))
    elif kind == "oversized":
        transport = _Opener(_Response(endpoint, length=2 * 1024 * 1024))
    elif kind == "wrongmime":
        transport = _Opener(_Response(endpoint, media="text/html"))
    elif kind == "not200":
        transport = _Opener(_Response(endpoint, code=503))
    elif kind == "network_error":
        transport = _Opener(error=URLError("PRIVATE_PASSWORD_DO_NOT_EXPOSE"))
    else:
        transport = _Opener(_Response(endpoint, body=b"x" * (1024 * 1024 + 1)))
    with pytest.raises(SourceShareError) as caught:
        fetch_authorized_once(
            reg, "synthetic-government-feed", at=NOW, opener=transport
        )
    assert transport.calls == 1
    assert "PRIVATE_PASSWORD" not in str(caught.value)


def test_invalid_timeout_rejected_before_request():
    opener = _Opener()
    with pytest.raises(SourceShareError, match="timeout"):
        fetch_authorized_once(
            registry(), "synthetic-government-feed",
            at=NOW, timeout_seconds=45, opener=opener,
        )
    assert opener.calls == 0


def test_expired_rights_rejected_before_request():
    from newscatalystos.provider_registry import SCHEMA, parse_provider_registry
    source = registry().providers[0]
    from dataclasses import asdict
    data = asdict(source)
    data.update(reviewed_at=(NOW - timedelta(days=4)).isoformat(),
                expires_at=(NOW - timedelta(days=1)).isoformat())
    reviewed = parse_provider_registry(
        json.dumps({"schema": SCHEMA, "providers": [data]}).encode(), now=NOW
    )
    opener = _Opener()
    with pytest.raises(SourceShareError, match="not approved"):
        fetch_authorized_once(
            reviewed, "synthetic-government-feed", at=NOW, opener=opener,
        )
    assert opener.calls == 0


def test_json_feed_only_metadata():
    reg = registry(method="JSON_API")
    endpoint = reg.active("synthetic-government-feed", at=NOW).endpoint
    data = json.dumps({"items": [{
        "id": "doc1", "title": "Approved announcement",
        "url": "https://gov.example.org/post1",
    }]}).encode()
    opener = _Opener(_Response(endpoint, body=data, media="application/json"))
    observed = fetch_authorized_once(
        reg, "synthetic-government-feed", at=NOW, opener=opener
    )
    assert len(observed) == 1 and observed[0].first_seen_at == NOW
