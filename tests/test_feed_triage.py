"""An authorized 1_3 poll produces first-stage review, not confirmed news."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.feed_triage import (
    SCHEMA, triage_committed_feed, publish_feed_triage,
)
from newscatalystos.incremental_ingest import incremental_poll
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW, registry


NAME = "synthetic-government-feed"
RSS = """<rss version="2.0"><channel>
<item><guid>one</guid><title>HBM 반도체 설비공급 확대 계획</title>
<link>https://gov.example.org/hbm/1</link><description>FULL ARTICLE BODY MUST NOT BE PERSISTED</description></item>
<item><guid>two</guid><title>광고: 반도체 투자 100% 수익 보장</title>
<link>https://gov.example.org/hbm/2</link></item>
<item><guid>three</guid><title>중소기업 세제 안내 개정</title>
<link>https://gov.example.org/policy/3</link></item>
</channel></rss>""".encode()


def sample_rows(at=NOW):
    return parse_authorized_feed(registry(), NAME, RSS, observed_at=at)


def poll(tmp_path, rows=None, *, at=NOW, reg=None):
    reg = reg or registry()
    calls = []
    def fetch(_registry, provider_id, *, at):
        calls.append((provider_id, at))
        return sample_rows(at) if rows is None else rows
    return reg, incremental_poll(reg, NAME,
                                 tmp_path / "feed" / "poll.sqlite3",
                                 now=at, fetcher=fetch), calls


def screen(tmp_path, observation, reg, *, at=NOW):
    return triage_committed_feed(
        reg, observation, tmp_path / "dedup" / "exact.sqlite3",
        decision_at=at, now=at,
    )


def test_first_poll_can_be_screened_without_second_api_call(tmp_path):
    provider, committed, calls = poll(tmp_path)
    assert committed.new_count == 3
    assert len(committed.observations) == 3
    assert len(committed.newly_observed_event_ids) == 3
    screened = screen(tmp_path, committed, provider)
    assert len(calls) == 1
    doc = json.loads(screened.payload)
    assert doc["schema"] == SCHEMA
    assert doc["observed_count"] == 3
    assert doc["new_identity_count"] == 3
    assert doc["keyword_review_count"] == 1
    assert doc["ai_call_count"] == 0
    assert doc["source_body_count"] == 0
    assert doc["verified_new_economic_fact_count"] == 0
    assert doc["conservative_cluster_count"] == 2
    items = {x["document_id"]: x for x in doc["items"]}
    assert items["one"]["needs_human_review"]
    assert "hbm" in items["one"]["matching_tokens"]
    assert items["one"]["importance_priority"] == "INSUFFICIENT_EVIDENCE_REVIEW"
    assert not items["one"]["verified_fact"]
    assert items["one"]["source_new_identity"]
    assert items["one"]["exact_index_status"] == "NEW"
    assert not items["two"]["needs_human_review"]
    assert items["two"]["claim_classification"] == "BLOCK_AD_SPAM"
    assert not items["three"]["needs_human_review"]
    assert "FULL ARTICLE BODY" not in screened.payload.decode()
    assert b"HBM" not in (tmp_path / "feed" / "poll.sqlite3").read_bytes()
    assert b"FULL ARTICLE BODY" not in (tmp_path / "feed" / "poll.sqlite3").read_bytes()
    assert b"HBM" not in (tmp_path / "dedup" / "exact.sqlite3").read_bytes()


def test_repeated_feed_ids_are_not_treated_as_new_economic_facts(tmp_path):
    provider, first, _ = poll(tmp_path)
    screen(tmp_path, first, provider)
    later = NOW + timedelta(minutes=10)
    _, second, _ = poll(tmp_path, at=later)
    assert second.new_count == 0
    assert second.duplicate_count == 3
    screened = screen(tmp_path, second, provider, at=later)
    doc = json.loads(screened.payload)
    assert doc["new_identity_count"] == 0
    assert doc["verified_new_economic_fact_count"] == 0
    assert all(x["exact_index_status"] == "DUPLICATE" for x in doc["items"])
    assert not any(x["source_new_identity"] for x in doc["items"])
    # Existing headlines are still available for manual review without AI.
    assert doc["keyword_review_count"] == 1


def test_revised_title_same_feed_id_is_never_certified_or_lost(tmp_path):
    provider, first, _ = poll(tmp_path)
    screen(tmp_path, first, provider)
    later = NOW + timedelta(minutes=10)
    updated = list(sample_rows(later))
    updated[0] = replace(updated[0], headline="HBM 반도체 설비투자 변경 250억원")
    _, second, _ = poll(tmp_path, rows=tuple(updated), at=later)
    screened = screen(tmp_path, second, provider, at=later)
    doc = json.loads(screened.payload)
    node = next(x for x in doc["items"] if x["document_id"] == "one")
    assert node["exact_index_status"] == "REVISED"
    assert node["source_new_identity"] is False
    assert node["needs_human_review"] is True
    assert node["verified_fact"] is False
    assert doc["ai_call_count"] == 0


def test_licensed_news_wire_is_not_mislabelled_independent_press(tmp_path):
    basic = registry()
    provider = ProviderRegistry((
        replace(basic.providers[0], kind="LICENSED_NEWS"),
    ))
    provider, committed, _ = poll(tmp_path, reg=provider)
    report = screen(tmp_path, committed, provider)
    doc = json.loads(report.payload)
    assert doc["source_kind"] == "PRESS_RELEASE"
    assert all(item["source_kind"] == "PRESS_RELEASE" for item in doc["items"])


def test_uncommitted_future_or_inconsistent_poll_is_rejected(tmp_path):
    reg, committed, _ = poll(tmp_path)
    with pytest.raises(SourceShareError, match="committed"):
        screen(tmp_path, replace(committed, status="FAILED"), reg)
    with pytest.raises(SourceShareError, match="committed"):
        screen(tmp_path, committed, reg, at=NOW-timedelta(seconds=1))
    with pytest.raises(SourceShareError, match="disagree"):
        screen(tmp_path, replace(committed, newly_observed_event_ids=()), reg)
    with pytest.raises(SourceShareError, match="ungrounded"):
        screen(tmp_path, replace(committed,
             newly_observed_event_ids=("b"*64, "c"*64, "d"*64)), reg)


def test_private_atomic_screening_publishes_metadata_only(tmp_path):
    reg, committed, _ = poll(tmp_path)
    report = screen(tmp_path, committed, reg)
    out = tmp_path / "private-output"
    folder = publish_feed_triage(report, out)
    assert folder.is_dir()
    assert (folder / "triage.json").read_bytes() == report.payload
    marker = json.loads((folder / "publication.json").read_bytes())
    assert marker["payload_sha256"] == sha256(report.payload).hexdigest()
    assert marker["verified_fact_count"] == 0
    assert (folder.stat().st_mode & 0o077) == 0
    assert not any(p.name.startswith(".triage_staging") for p in out.iterdir())
    with pytest.raises(SourceShareError, match="immutable"):
        publish_feed_triage(report, out)
    assert b"FULL ARTICLE BODY" not in b"".join(
        p.read_bytes() for p in folder.iterdir() if p.is_file())


def test_unapproved_provider_does_not_triage(tmp_path):
    reg, committed, _ = poll(tmp_path)
    disabled = ProviderRegistry((
        replace(reg.providers[0], approved=False),
    ))
    with pytest.raises(SourceShareError, match="not approved"):
        screen(tmp_path, committed, disabled)


def test_first_triage_of_previously_ingested_rows_is_not_called_new_news(tmp_path):
    # Existing 1_3 ingest may predate deployment of the triage SHA index.
    reg, original, _ = poll(tmp_path)
    later = NOW + timedelta(minutes=10)
    _, same, _ = poll(tmp_path, at=later)
    assert same.new_count == 0
    screened = screen(tmp_path, same, reg, at=later)
    body = json.loads(screened.payload)
    assert body["new_identity_count"] == 0
    assert all(x["exact_index_status"] == "INDEX_BOOTSTRAP_PRIOR_SEEN_ID"
               for x in body["items"])
    assert body["verified_new_economic_fact_count"] == 0
    assert body["ai_call_count"] == 0
