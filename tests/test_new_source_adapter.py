"""Offline feed adapters; operator permission data here is synthetic."""
from datetime import datetime, timezone
import json

import pytest

from newscatalystos.new_source_adapter import parse_authorized_feed, STATUS
from newscatalystos.provider_registry import SCHEMA, parse_provider_registry
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><guid>id-1</guid><title>New factory</title>
<link>https://ir.example.org/news/1</link><description>PRIVATE BODY NEVER STORED</description></item>
<item><guid>id-1</guid><title>Repeated</title>
<link>https://ir.example.org/news/1</link></item>
</channel></rss>"""


def registry(approved=True, method="RSS"):
    doc = {"schema": SCHEMA, "providers": [{
        "provider_id": "synthetic-government-feed", "kind": "GOVERNMENT_POLICY",
        "method": method, "endpoint": "https://gov.example.org/feed",
        "grant": "OFFICIAL_TERMS_REVIEWED" if approved else "NOT_REVIEWED",
        "rights_reference": "synthetic-review" if approved else None,
        "reviewed_at": NOW.isoformat() if approved else None,
        "expires_at": None, "approved": approved,
        "allow_full_text_storage": False, "hourly_limit": 10,
    }]}
    return parse_provider_registry(json.dumps(doc).encode(), now=NOW)


def test_rss_metadata_deduplicates_without_body():
    rows = parse_authorized_feed(registry(), "synthetic-government-feed", RSS, observed_at=NOW)
    assert len(rows) == 1
    assert rows[0].headline == "New factory"
    assert rows[0].first_seen_at == NOW
    assert rows[0].reported_published_at is None
    assert rows[0].verification_status == STATUS
    assert "PRIVATE BODY" not in str(rows)


def test_unapproved_license_blocks_even_malformed_payload():
    with pytest.raises(SourceShareError, match="not approved"):
        parse_authorized_feed(registry(False), "synthetic-government-feed", b"bad", observed_at=NOW)


def test_json_api_header_only():
    data = json.dumps({"items": [{"id": "a1", "title": "Policy notice",
                                  "url": "https://gov.example.org/a1"}]}).encode()
    rows = parse_authorized_feed(registry(method="JSON_API"),
                                 "synthetic-government-feed", data, observed_at=NOW)
    assert len(rows) == 1 and rows[0].reported_published_at is None


@pytest.mark.parametrize("bad", [
    b'<!DOCTYPE rss [ <!ENTITY x "y"> ]><rss><channel></channel></rss>',
    b"<body>not RSS</body>",
    b"<rss><channel><item><title>no link</title></item></channel></rss>",
    b"<rss><channel><item><guid>e</guid><title>bad</title><link>http://localhost/x</link></item></channel></rss>",
    b"<rss><channel><item><guid>e</guid><title> </title><link>https://ir.example.org/x</link></item></channel></rss>",
])
def test_invalid_or_unsafe_rss_is_rejected(bad):
    with pytest.raises(SourceShareError):
        parse_authorized_feed(registry(), "synthetic-government-feed", bad, observed_at=NOW)


def test_json_article_body_not_stored():
    data = json.dumps({"items": [{
        "id": "x", "title": "Headline", "url": "https://gov.example.org/x",
        "body": "paid full text",
    }]}).encode()
    with pytest.raises(SourceShareError, match="fields"):
        parse_authorized_feed(registry(method="JSON_API"),
                              "synthetic-government-feed", data, observed_at=NOW)


def test_large_feed_rejected():
    with pytest.raises(SourceShareError, match="too large"):
        parse_authorized_feed(registry(), "synthetic-government-feed",
                              b"x" * (1024 * 1024 + 1), observed_at=NOW)


def test_official_rss_document_links_support_nonsecret_query_ids():
    payload = b"""<rss version="2.0"><channel>
    <item><title>Official policy update</title>
    <link>https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=86&amp;bcIdx=1234</link>
    </item></channel></rss>"""
    rows = parse_authorized_feed(
        registry(), "synthetic-government-feed", payload, observed_at=NOW
    )
    assert len(rows) == 1
    assert rows[0].document_id == rows[0].source_url
    assert "cbIdx=86" in rows[0].source_url
