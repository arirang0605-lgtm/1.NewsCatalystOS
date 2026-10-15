"""Synthetic saved RSS -> scheduled analysis -> existing PIT theme store."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.source_share import SourceShareError
from newscatalystos.standard_delivery import build_theme_bundle, read_theme_bundle
from newscatalystos.theme_emergence import ThemeStore
from scripts import run_feed_analysis, run_scheduled_triage
from test_federated_news_search import setup_workspace, collect, fingerprint, GOV
from test_new_source_adapter import registry, NOW
from test_scheduled_feed_analysis import opts, no_call
from hashlib import sha256


def test_saved_titles_reach_shared_theme_with_replay_and_pit(tmp_path):
    source = setup_workspace(tmp_path, "source", registry())
    work = tmp_path / "analyses" / "core"
    themes = tmp_path / "shared_themes"
    params = opts(source, work, operation="--replay-only")
    params.analysis_theme_root = themes
    collect(source, registry(), GOV, [
        ("a", "가상전자, 신형냉각 수요 증가에 대응해 공급계약 체결", "https://gov.example.org/a")
    ], at=NOW)
    first_decision = datetime.now(timezone.utc) + timedelta(minutes=1)
    at = first_decision
    def analyze(args):
        return run_feed_analysis.evaluate(args, opener=no_call, now=at)
    def tick():
        return run_scheduled_triage.execute(params,
            feed_runner=lambda _: (0, {"status":"NO_PENDING_REPLAY"}), analysis_runner=analyze)
    original = fingerprint(source.inbox_root.parent)
    code, first = tick()
    detail = first["providers"][0]["analysis"]
    assert code == 0 and detail["economic_changes_count"] == 1
    assert detail["theme_versions_created"] == 1
    assert fingerprint(source.inbox_root.parent) == original
    store = ThemeStore(themes)
    earliest = store.search(now=at)
    assert len(earliest) == 1 and earliest[0]["status"] == "CANDIDATE"
    assert earliest[0]["first_detected_at"] == at.isoformat()
    assert earliest[0]["entity_ids"] == ["가상전자"]
    assert not store.search(as_of=NOW, now=at)

    collect(source, registry(), GOV, [
        ("b", "예시소재, 신형냉각 수요 확대에 대응해 생산 시작", "https://gov.example.org/b"),
        ("c", "새빛장비, 신형냉각 수요 증가에 따라 신규 투자 결정", "https://gov.example.org/c"),
        ("d", "가상기업, ‘혁신 플랫폼’ 출시", "https://gov.example.org/d"),
        ("e", "신형냉각 기술 소개 행사 개최", "https://gov.example.org/e"),
    ], at=NOW + timedelta(hours=2))
    at = first_decision + timedelta(hours=3)
    code, second = tick()
    assert code == 0 and second["ai_call_count"] == 0
    detail = second["providers"][0]["analysis"]
    assert detail["economic_changes_count"] == 3 and detail["theme_versions_created"] == 1
    found = store.search(query="신형냉각", now=at)
    assert len(found) == 1 and found[0]["status"] == "EMERGING"
    assert found[0]["scores"]["distinct_economic_events"] == 3
    assert found[0]["scores"]["official_events"] == 0
    assert found[0]["verified_beneficiary_count"] == 0
    assert store.search(as_of=first_decision, now=at) == earliest
    assert {ref["content_scope"] for ref in found[0]["source_refs"]} == {"RSS_TITLE_METADATA"}
    assert {ref["evidence_level"] for ref in found[0]["source_refs"]} == {"REPORTED"}
    raw = build_theme_bundle(found, decision_at=at, now=at)
    assert read_theme_bundle(raw, sha256(raw).hexdigest(), decision_at=at, now=at)["ThemeCandidates"] == found
    rows, stats = scan_saved_analysis(work.parent, now=at)
    assert stats["saved_reports_skipped"] == 0
    assert sum(len(row["economic_changes"]) for row in rows) == 3
    assert all(row["content_scope"] == "RSS_TITLE_METADATA" for row in rows)
    original = fingerprint(source.inbox_root.parent)
    at += timedelta(hours=1)
    code, replay = tick()
    assert code == 0 and replay["providers"][0]["analysis"]["theme_versions_created"] == 0
    assert store.search(now=at) == found
    assert fingerprint(source.inbox_root.parent) == original


def test_title_evidence_cannot_be_upgraded_or_changed_and_old_reports_still_read(tmp_path):
    from test_feed_analysis import setup, run
    report = run(setup(tmp_path, "HBM 공급계약 체결"))
    assert len(report["results"][0]["economic_changes"]) == 1
    for field, value in (("evidence_level", "OFFICIAL_SOURCE"),
                         ("source_paragraph_sha256", "f" * 64)):
        modified = deepcopy(report)
        modified["results"][0]["economic_changes"][0][field] = value
        path, digest = publish_feed_analysis(modified, tmp_path / "reports")
        with pytest.raises(SourceShareError, match="title evidence"):
            consume_feed_analysis(path, path.parent, digest)
    old = deepcopy(report)
    del old["results"][0]["economic_changes"]
    path, digest = publish_feed_analysis(old, tmp_path / "reports")
    assert consume_feed_analysis(path, path.parent, digest)["results"] == old["results"]


@pytest.mark.parametrize("title", [
    "광고: HBM 공급계약 체결", "루머: HBM 공급계약 체결",
    "HBM 공급계약 체결 부인", "HBM 공급계약 체결 취소",
    "가상회사, ‘신형냉각’ 출시", "HBM 가격 상승",
])
def test_non_actions_and_blocked_titles_do_not_make_theme_events(tmp_path, title):
    from test_feed_analysis import setup, run
    assert run(setup(tmp_path, title))["results"][0]["economic_changes"] == []


def test_reported_production_plan_preserves_its_phase(tmp_path):
    from test_feed_analysis import setup, run
    row = run(setup(tmp_path, "가상전자, HBM 양산 개시 예정"))["results"][0]
    assert len(row["economic_changes"]) == 1
    assert row["economic_changes"][0]["phase"] == "PLANNED"
    assert row["economic_changes"][0]["evidence_level"] == "REPORTED"


@pytest.mark.parametrize("driver_phrase", ["신형냉각 수요 증가에 대응해", "HBM"])
def test_same_title_at_three_urls_does_not_multiply_events_or_themes(tmp_path, driver_phrase):
    from newscatalystos.theme_emergence import economic_observation
    from test_feed_analysis import setup, run
    title = "가상전자와 예시소재, 새빛장비 " + driver_phrase + " 공급계약 체결"
    # Use an explicit unambiguous topic for this exact-claim dedup test.
    if driver_phrase.startswith("신형"):
        title = "신형냉각 수요 증가에 대응해 가상전자와 예시소재 및 새빛장비 공급계약 체결"
    row = run(setup(tmp_path, title))["results"][0]
    assert len(row["economic_changes"]) == 1
    observations = [economic_observation(row["economic_changes"][0],
        origin_reference=f"https://example.org/{n}", source_url=f"https://example.org/{n}",
        source_id=f"publisher-{n}", source_available_at=row["source_available_at"],
        content_scope="RSS_TITLE_METADATA") for n in range(3)]
    store = ThemeStore(tmp_path / "themes")
    candidates = store.ingest(observations)
    assert len(candidates) == 1
    assert candidates[0]["status"] == "CANDIDATE"
    assert candidates[0]["scores"]["distinct_economic_events"] == 1
    assert len(candidates[0]["source_refs"]) == 3
    assert store.ingest(observations) == []


def test_actor_comma_is_not_confused_with_a_coordinated_demand_topic():
    from newscatalystos.economic_changes import extract_economic_changes
    assert not extract_economic_changes("양자냉각, 광자유체 수요 증가에 대응해 공급계약 체결")
    changes = extract_economic_changes("다온, 광자유체 수요 증가에 대응해 공급계약 체결", company_names=["다온"])
    assert len(changes) == 1 and changes[0]["topic"] == "광자유체"
    assert changes[0]["entity_ids"] == ["다온"]
