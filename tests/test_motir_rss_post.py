"""New public ministry RSS uses explicitly reviewed form POST (not generic POST).

Synthetic network transport: never hit the ministry in automated unit tests.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from io import BytesIO
import json

import pytest

from newscatalystos.provider_registry import SCHEMA, parse_provider_registry
from newscatalystos.feed_transport import fetch_authorized_once
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 14, 7, 0, tzinfo=timezone.utc)
URL = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/rss"
RSS_BODY = ("""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>반도체 산업 신규 정책 검토</title>
<link>https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172287/view</link>
<description>DO NOT STORE ANY ARTICLE BODY</description></item>
</channel></rss>""").encode()


def raw(*, method="RSS_POST", endpoint=URL, grant="OFFICIAL_TERMS_REVIEWED",
        approved=True, kind="GOVERNMENT_POLICY"):
    return {"schema": SCHEMA, "providers": [{
        "provider_id": "motir-official-press", "kind": kind,
        "method": method, "endpoint": endpoint,
        "grant": grant, "rights_reference": (
            "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c"
            if grant != "NOT_REVIEWED" else None),
        "reviewed_at": NOW.isoformat() if grant != "NOT_REVIEWED" else None,
        "expires_at": None, "approved": approved,
        "allow_full_text_storage": False, "hourly_limit": 1,
    }]}


def registry(**kwargs):
    return parse_provider_registry(
        json.dumps(raw(**kwargs)).encode(), now=NOW,
    )


class Response:
    def __init__(self, data=RSS_BODY, mime="text/xml; charset=UTF-8",
                 url=URL, code=200):
        self.data = BytesIO(data)
        self.headers = {"Content-Type": mime}
        self.url, self.code = url, code

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.data.close()

    def read(self, n):
        return self.data.read(n)

    def getcode(self):
        return self.code

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response=None):
        self.calls, self.last_request = 0, None
        self.response = response or Response()

    def open(self, request, timeout):
        self.calls += 1
        self.last_request = request
        assert request.get_method() == "POST"
        assert request.full_url == URL and request.data == b""
        assert 0 < timeout <= 10
        assert request.get_header("Authorization") is None
        return self.response


def test_approved_official_motir_post_is_one_empty_post_and_metadata_only():
    r, transport = registry(), Opener()
    result = fetch_authorized_once(r, "motir-official-press",
                                   at=NOW, opener=transport)
    assert transport.calls == 1 and len(result) == 1
    assert result[0].headline == "반도체 산업 신규 정책 검토"
    assert result[0].source_url.startswith("https://www.motir.go.kr/")
    assert result[0].first_seen_at == NOW
    assert result[0].reported_published_at is None
    assert "DO NOT STORE" not in str(result)


@pytest.mark.parametrize("changes", [
    {"endpoint": "https://news.skhynix.com/en/feed/"},
    {"endpoint": "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/rss?other=1"},
    {"endpoint": "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c"},
    {"kind": "COMPANY_IR"},
])
def test_post_cannot_be_sent_to_any_other_feed_or_era_collector(changes):
    with pytest.raises(SourceShareError, match="RSS_POST allowed"):
        registry(**changes)


def test_not_reviewed_permission_fails_before_http():
    r = registry(grant="NOT_REVIEWED", approved=False)
    opener = Opener()
    with pytest.raises(SourceShareError, match="not approved"):
        fetch_authorized_once(r, "motir-official-press",
                              at=NOW, opener=opener)
    assert opener.calls == 0


def test_post_malformed_or_non_xml_is_rejected_no_retry():
    r = registry()
    for invalid in (
        Response(data=b"<html>not RSS</html>"),
        Response(url="https://other.example.org/rss"),
        Response(mime="text/html"),
    ):
        opener = Opener(invalid)
        with pytest.raises(SourceShareError):
            fetch_authorized_once(r,"motir-official-press",
                                  at=NOW, opener=opener)
        assert opener.calls == 1


def test_existing_get_registry_method_unaffected():
    from test_new_source_adapter import registry as existing, RSS as SAMPLE
    class GetOpener:
        def __init__(self):
            self.calls = 0
        def open(self, request, timeout):
            self.calls += 1
            assert request.get_method() == "GET"
            assert request.data is None
            return Response(data=SAMPLE,
                url=existing().providers[0].endpoint,
                mime="application/rss+xml")
    opener = GetOpener()
    records = fetch_authorized_once(
        existing(), "synthetic-government-feed",
        at=NOW, opener=opener,
    )
    assert len(records) == 1 and opener.calls == 1
