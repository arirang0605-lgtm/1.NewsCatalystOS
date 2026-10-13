"""2_2 persistent exact dedup and corrected source-version boundaries."""
from dataclasses import replace
from datetime import timedelta

import pytest

from newscatalystos.exact_dedup import register_exact
from newscatalystos.text_normalization import normalize_feed_metadata, normalize_text
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import RSS, NOW, registry
from newscatalystos.new_source_adapter import parse_authorized_feed


def feed():
    source = parse_authorized_feed(
        registry(), "synthetic-government-feed", RSS, observed_at=NOW
    )[0]
    return normalize_feed_metadata(source, verified_at=NOW, now=NOW)


def state(tmp_path):
    return tmp_path / "private" / "dedup.sqlite3"


def test_same_source_same_document_across_restarts_is_one_new(tmp_path):
    path = state(tmp_path)
    initial = register_exact(path, feed(), "source-doc1", now=NOW)
    second = register_exact(path, feed(), "source-doc1", now=NOW)
    assert initial.status == "NEW"
    assert initial.ai_eligible
    assert second.status == "DUPLICATE"
    assert not second.ai_eligible
    assert initial.canonical_record_sha256 == second.canonical_record_sha256
    assert initial.document_key_sha256 == second.document_key_sha256


def test_changed_document_content_is_revised_not_dropped(tmp_path):
    path = state(tmp_path)
    original = feed()
    initial = register_exact(path, original, "source-doc1", now=NOW)
    new_sha = normalize_text("Changed contract value")[1]
    changed = replace(original, raw_title_sha256=new_sha)
    later = NOW + timedelta(seconds=1)
    revised = register_exact(path, changed, "source-doc1", now=later)
    assert revised.status == "REVISED"
    assert revised.ai_eligible
    assert revised.canonical_record_sha256 != initial.canonical_record_sha256
    assert register_exact(path, changed, "source-doc1",
                          now=later).status == "DUPLICATE"


def test_same_url_and_identical_raw_content_with_alias_id_is_duplicate(tmp_path):
    path = state(tmp_path)
    original = feed()
    register_exact(path, original, "first-id", now=NOW)
    alias = register_exact(path, original, "second-id", now=NOW)
    assert alias.status == "DUPLICATE"
    assert not alias.ai_eligible


def test_independent_sources_not_silently_merged(tmp_path):
    path = state(tmp_path)
    source = feed()
    initial = register_exact(path, source, "one", now=NOW)
    other = replace(source, source_id="independent-provider",
                    event_id="f" * 64)
    second = register_exact(path, other, "one", now=NOW)
    assert initial.status == second.status == "NEW"


def test_replay_before_first_observation_or_future_rejected(tmp_path):
    path = state(tmp_path)
    before = NOW - timedelta(microseconds=1)
    with pytest.raises(SourceShareError, match="precedes"):
        register_exact(path, feed(), "source-doc1", now=before)
    assert not path.exists()


def test_invalid_event_sha_and_document_id_rejected(tmp_path):
    path = state(tmp_path)
    with pytest.raises(SourceShareError, match="SHA"):
        register_exact(path, replace(feed(), raw_title_sha256="evil"),
                       "source-doc1", now=NOW)
    with pytest.raises(SourceShareError, match="document ID"):
        register_exact(path, feed(), "", now=NOW)


def test_hash_index_does_not_store_article_text_or_url(tmp_path):
    path = state(tmp_path)
    title = feed()
    register_exact(path, title, "doc-one", now=NOW)
    raw = path.read_bytes()
    assert b"New factory" not in raw
    assert b"ir.example.org" not in raw
    assert b"doc-one" not in raw
    assert path.stat().st_mode & 0o777 == 0o600
