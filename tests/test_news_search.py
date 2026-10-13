"""Private live-like RSS headline search; no external API, unverified facts only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from newscatalystos.news_search import sync_completed_titles, search_titles
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from test_feed_operations import completed
from test_feed_recovery import paths
from test_new_source_adapter import registry


def sample(tmp_path):
    state, inbox, output, receipt, ack, folder = completed(tmp_path)
    index = tmp_path / "private_derived" / "news_search.sqlite3"
    return state, inbox, output, receipt, ack, folder, index


def test_real_pipeline_ack_index_full_text_and_semiconductor_review(tmp_path):
    state, inbox, output, receipt, ack, folder, index = sample(tmp_path)
    current = datetime.now(timezone.utc)
    checked = sync_completed_titles(inbox, state, index, registry(), now=current)
    assert checked.processed_receipts == 1
    assert checked.inserted_versions == checked.unique_documents == 3
    assert checked.confirmed_sources == 1
    matches = search_titles(index, "반도체", registry=registry(), now=current)
    assert len(matches) == 2
    assert all("반도체" in item["headline"] for item in matches)
    assert all(not item["verified_economic_fact"]
               and not item["verified_supply_transaction"]
               and not item["confirmed_beneficiary"]
               and not item["article_body_included"]
               for item in matches)
    screened = search_titles(index, "반도체", registry=registry(),
                             semiconductor_only=True, now=current)
    assert len(screened) == 1
    assert screened[0]["needs_human_review"]
    assert screened[0]["semiconductor_keyword_candidate"]
    assert screened[0]["event_id"] in {r.event_id for r in receipt.poll.observations}
    assert screened[0]["first_searchable_at"] == current.isoformat()
    assert screened[0]["source_available_at"] < screened[0]["first_searchable_at"]
    assert len(screened[0]["triage_evidence_sha256"]) == 64
    assert b"FULL ARTICLE BODY MUST NOT" not in index.read_bytes()


def test_two_character_korean_substring_and_english_term(tmp_path):
    state, inbox, _, _, _, _, index = sample(tmp_path)
    now = datetime.now(timezone.utc)
    sync_completed_titles(inbox, state, index, registry(), now=now)
    assert search_titles(index, "공급", registry=registry(), now=now)
    assert search_titles(index, "HBM", registry=registry(), now=now)
    assert not search_titles(index, "NOT_IN_NEWS_SOURCE", registry=registry(), now=now)


def test_sync_is_idempotent_and_search_sorted_deterministically(tmp_path):
    state, inbox, _, _, _, _, index = sample(tmp_path)
    now = datetime.now(timezone.utc)
    first = sync_completed_titles(inbox, state, index, registry(), now=now)
    second = sync_completed_titles(inbox, state, index, registry(), now=now)
    assert second.processed_receipts == 1
    assert second.inserted_versions == 0
    assert second.unique_documents == first.unique_documents
    one = search_titles(index, "반도체", registry=registry(), now=now)
    two = search_titles(index, "반도체", registry=registry(), now=now)
    assert one == two
    assert len(search_titles(index, "반도체", registry=registry(),
                             limit=1, now=now)) == 1


def test_search_asof_cannot_precede_first_actual_index_time(tmp_path):
    state, inbox, _, _, _, _, index = sample(tmp_path)
    created = datetime.now(timezone.utc)
    sync_completed_titles(inbox, state, index, registry(), now=created)
    old = search_titles(index, "반도체", registry=registry(),
                        now=created - timedelta(microseconds=1))
    assert old == ()
    assert search_titles(index, "반도체", registry=registry(), now=created)


def test_revoked_source_cannot_be_searched_from_old_local_cache(tmp_path):
    state, inbox, _, _, _, _, index = sample(tmp_path)
    now = datetime.now(timezone.utc)
    sync_completed_titles(inbox, state, index, registry(), now=now)
    revoked = ProviderRegistry((
        replace(registry().providers[0], approved=False),
    ))
    assert search_titles(index, "반도체", registry=revoked, now=now) == ()
    with pytest.raises(SourceShareError, match="unapproved"):
        search_titles(index, "반도체", registry=revoked,
                      source_id="synthetic-government-feed", now=now)


def test_source_tampering_rejected_before_index_is_created(tmp_path):
    state, inbox, _, _, ack, folder, index = sample(tmp_path)
    article = folder / "triage.json"
    article.write_bytes(article.read_bytes() + b'\nFAKE PAID ARTICLE BODY')
    with pytest.raises(SourceShareError, match="invalid JSON|SHA|corrupt"):
        sync_completed_titles(inbox, state, index, registry())
    assert not index.exists()


def test_forged_matching_sha_and_ack_cannot_inject_paid_body(tmp_path):
    state, inbox, _, _, ack, folder, index = sample(tmp_path)
    doc = json.loads((folder / "triage.json").read_bytes())
    doc["items"][0]["article_body"] = "POTENTIALLY LICENSED CONTENT"
    raw = (json.dumps(doc, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False) + "\n").encode()
    (folder / "triage.json").write_bytes(raw)
    # A rewritten payload cannot be smuggled into an already acknowledged
    # publication, even when its local hash is easy for an attacker to recalc.
    with pytest.raises(SourceShareError, match="corrupt|mismatch|invalid"):
        sync_completed_titles(inbox, state, index, registry())


@pytest.mark.parametrize("phrase", ["", "a", " " * 5, "\x00X"])
def test_short_or_control_query_rejected(tmp_path, phrase):
    with pytest.raises(SourceShareError, match="invalid"):
        search_titles(tmp_path / "search.sqlite3", phrase, registry=registry())


def test_search_no_api_or_era_read_and_index_contains_only_header(tmp_path, monkeypatch):
    state, inbox, _, _, _, _, index = sample(tmp_path)
    import newscatalystos.feed_transport as transport
    def denied(*a, **k):
        raise AssertionError("attempted unexpected API call")
    monkeypatch.setattr(transport, "fetch_authorized_once", denied)
    synced = sync_completed_titles(inbox, state, index, registry())
    assert synced.inserted_versions == 3
    assert search_titles(index, "중소", registry=registry())
    assert b"FULL ARTICLE BODY MUST NOT" not in index.read_bytes()
    assert b"synthetic-government-feed" in index.read_bytes()


def test_search_cli_syncs_approved_titles_without_fetch(tmp_path, monkeypatch):
    import argparse
    from scripts import search_news
    state, inbox, _, _, _, _, index = sample(tmp_path)
    monkeypatch.setattr(search_news, "_registry", lambda path: registry())
    args = argparse.Namespace(
        registry=tmp_path / "approved.json", query="반도체",
        source_id=None, semiconductor_only=True, limit=10,
        state=state, inbox_root=inbox, index=index,
    )
    code, report = search_news.evaluate(args)
    assert code == 0 and report["status"] == "LOCAL_APPROVED_METADATA_SEARCH"
    assert report["indexed_document_versions"] == 3
    assert report["acknowledged_triage_receipts_checked"] == 1
    assert report["keyword_hits"] == 1
    assert report["results"][0]["verified_economic_fact"] is False
    assert report["network_calls"] == report["ai_calls"] == 0
    assert report["original_article_body_stored"] is False


def test_search_cli_invalid_source_fails_without_returning_titles(tmp_path, monkeypatch):
    import argparse
    from scripts import search_news
    state, inbox, _, _, _, _, index = sample(tmp_path)
    monkeypatch.setattr(search_news, "_registry", lambda path: registry())
    args = argparse.Namespace(
        registry=tmp_path / "approved.json", query="반도체",
        source_id="sec-submissions", semiconductor_only=False, limit=20,
        state=state, inbox_root=inbox, index=index,
    )
    code, report = search_news.evaluate(args)
    assert code == 4 and report["status"] == "SEARCH_DATA_UNAVAILABLE"
    assert "results" not in report
    assert report["network_calls"] == report["ai_calls"] == 0
