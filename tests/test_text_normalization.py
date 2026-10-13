"""2_1 deterministic normalization of only licensed/authorized metadata."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from newscatalystos.text_normalization import (
    canonicalize_url, normalize_feed_metadata, normalize_text,
)
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import RSS, NOW, registry
from newscatalystos.new_source_adapter import parse_authorized_feed


def observed():
    return parse_authorized_feed(
        registry(), "synthetic-government-feed", RSS, observed_at=NOW
    )[0]


def test_unicode_html_title_is_deterministic_and_source_is_unchanged():
    raw = "<b>ＳＫ  하이닉스</b> &amp; <i>HBM</i>\n  출시"
    before = raw
    result1, digest1 = normalize_text(raw)
    result2, digest2 = normalize_text(raw)
    assert result1 == result2 == "SK 하이닉스 & HBM 출시"
    assert digest1 == digest2 == sha256(raw.encode()).hexdigest()
    assert raw == before


def test_embedded_scripts_are_discarded_without_running():
    title, digest = normalize_text(
        "<h2>Export controls</h2><script>steal_secret()</script>"
        "<style>.hidden {display:none}</style><b>relaxed</b>"
    )
    assert title == "Export controls relaxed"
    assert "secret" not in title


def test_canonical_url_discards_tracking_but_preserves_document_identity():
    url = ("https://WWW.MSS.GO.KR/site/smba/View.do?utm_source=X"
           "&bcIdx=1234&cbIdx=86&fbclid=abc#page2")
    canonical = canonicalize_url(url)
    assert canonical.startswith("https://www.mss.go.kr/")
    assert canonical.endswith("bcIdx=1234&cbIdx=86")
    assert "utm_" not in canonical
    assert "fbclid" not in canonical


def test_feed_contract_unknown_issuer_and_asof_pit():
    row = observed()
    at = NOW + timedelta(minutes=1)
    converted = normalize_feed_metadata(row, verified_at=at, now=at)
    assert converted.company_id is None
    assert converted.published_at is None
    assert converted.event_id == row.event_id
    assert converted.observed_at == NOW
    assert converted.available_at == at
    with pytest.raises(SourceShareError, match="not yet usable"):
        converted.as_of(NOW, now=at)
    assert converted.as_of(at, now=at) is converted


@pytest.mark.parametrize("raw", [b"\xff\xfe", b"", b"hello\x00world", b"x"*8193])
def test_invalid_title_never_trusted(raw):
    with pytest.raises(SourceShareError):
        normalize_text(raw)


@pytest.mark.parametrize("url", [
    "http://example.org/articles",
    "https://user:secret@example.org/p",
    "https://example.org/p?token=SUPERSECRET",
    "https://127.0.0.1/private",
    "https://example.org/../secret",
])
def test_unsafe_urls_rejected(url):
    with pytest.raises(SourceShareError):
        canonicalize_url(url)


def test_future_verification_rejected():
    row = observed()
    with pytest.raises(SourceShareError, match="future"):
        normalize_feed_metadata(row, verified_at=NOW+timedelta(days=1), now=NOW)


def test_forged_published_time_rejected():
    row = observed()
    with pytest.raises(SourceShareError):
        normalize_feed_metadata(
            replace(row, reported_published_at=NOW),
            verified_at=NOW, now=NOW,
        )
