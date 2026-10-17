"""One corporate publisher, two approved RSS categories, one source watermark.

The press-category feed adds metadata versions to the existing newsroom
provider. It never creates a second 'independent' reporting source, circumvents
the original hourly rate limit, or persists licensed article text.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from xml.sax.saxutils import escape

import pytest

from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.incremental_ingest import incremental_poll, state_snapshot
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.provider_registry import ProviderRegistry, parse_provider_registry
from newscatalystos.source_share import SourceShareError

ROOT = Path(__file__).resolve().parent.parent
NAME = "skhynix-newsroom-korea"
TITLE = (
    "SK하이닉스, 용인 Y2 ∙ 청주 M17에 54조 원 투자… "
    "AI 시대 메모리 수요 대응 위한 중장기 생산 기반 확보"
)


def _feeds():
    general = parse_provider_registry(
        (ROOT / "config/semiconductor_company_rss_metadata_registry.json").read_bytes())
    press = parse_provider_registry(
        (ROOT / "config/skhynix_press_rss_same_provider_registry.json").read_bytes())
    original, = (p for p in general.providers if p.provider_id == NAME)
    candidate, = press.providers
    assert candidate.provider_id == original.provider_id
    assert candidate.endpoint == "https://news.skhynix.co.kr/category/press/feed/"
    assert original.endpoint == "https://news.skhynix.co.kr/feed/"
    assert (original.kind == candidate.kind == "COMPANY_IR"
            and original.grant == candidate.grant == "OFFICIAL_TERMS_REVIEWED")
    assert original.rights_reference == candidate.rights_reference
    assert original.hourly_limit == candidate.hourly_limit == 1
    assert not original.allow_full_text_storage and not candidate.allow_full_text_storage
    return original, candidate


def _rss(records):
    rows = []
    for guid, headline, suffix in records:
        rows.append(
            "<item><guid>" + escape(guid) + "</guid><title>" + escape(headline) +
            "</title><link>https://news.skhynix.co.kr/" + suffix + "/</link>" +
            "<description>NONPERSISTED_BODY</description></item>"
        )
    return ("<rss version='2.0'><channel>" + "".join(rows) + "</channel></rss>").encode()


def test_press_variant_keeps_provider_guid_dedup_and_existing_hourly_limit(tmp_path):
    main, extra = _feeds()
    at = datetime(2026, 10, 15, 10, tzinfo=timezone.utc)
    past = at - timedelta(days=1)
    usual = ProviderRegistry((replace(main, reviewed_at=past),))
    press = ProviderRegistry((replace(extra, reviewed_at=past),))
    before = _rss([
        ("shared", "SK하이닉스 HBM 현황 공개", "shared"),
        ("main-only", "메모리 산업 협력 행사", "main"),
    ])
    after = _rss([
        ("shared", "SK하이닉스 HBM 현황 공개", "shared"),
        ("new-press", TITLE, "fab-facility-investment-2026"),
    ])
    # The same publisher GUID must produce the identical SHA across feed URLs.
    first = parse_authorized_feed(usual, NAME, before, observed_at=at)
    second = parse_authorized_feed(press, NAME, after, observed_at=at + timedelta(hours=1,seconds=3))
    assert first[0].event_id == second[0].event_id
    assert "NONPERSISTED_BODY" not in repr(first + second)

    state = tmp_path / "private/state/ingest.sqlite3"
    calls = []

    def reader(feed):
        def read(source, provider_id, *, at):
            calls.append((provider_id, source.active(provider_id, at=at).endpoint))
            return parse_authorized_feed(source, provider_id, feed, observed_at=at)
        return read

    old = incremental_poll(usual, NAME, state, now=at, fetcher=reader(before))
    assert old.new_count == 2 and old.duplicate_count == 0
    with pytest.raises(SourceShareError, match="hourly request budget"):
        incremental_poll(press, NAME, state,
                         now=at + timedelta(minutes=2), fetcher=reader(after))
    assert len(calls) == 1
    later = at + timedelta(hours=1, seconds=3)
    new = incremental_poll(press, NAME, state, now=later, fetcher=reader(after))
    assert new.new_count == new.duplicate_count == 1
    assert len(calls) == 2
    assert new.newly_observed_event_ids == (second[1].event_id,)
    assert state_snapshot(state, NAME)["seen_count"] == 3
    assert state_snapshot(state, NAME)["last_success_at"] == later.isoformat()
    assert "NONPERSISTED_BODY" not in repr(new)

    changes = extract_economic_changes(second[1].headline)
    assert len(changes) == 1
    assert (changes[0]["action"], changes[0]["phase"]) == ("INVESTMENT", "PLANNED")
    assert changes[0]["entity_ids"] == ["SK하이닉스"]
    assert changes[0]["industry_tags"] == ["SEMICONDUCTOR"]
    assert changes[0]["verified_economic_effect"] is False
