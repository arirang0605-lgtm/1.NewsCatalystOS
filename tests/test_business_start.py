"""Synthetic business/service claims through the existing RSS/theme pipeline."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from newscatalystos.economic_changes import business_start_phase, extract_economic_changes
from newscatalystos.feed_analysis import _category
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.theme_emergence import ThemeStore
from scripts import run_feed_analysis
from test_feed_analysis import setup, run
from test_federated_news_search import fingerprint


@pytest.mark.parametrize("title", [
    "가상기업, 맞춤 추천 서비스 출시",
    "가상기업, 신규 사업 개시",
    "가상기업, 서비스가 시작됐다",
    "가상기업은 HBM 검사 서비스를 시작했다",
    "가상기업, 서비스 ‘이웃도움’ 전국 출시",
    "가상기업, ‘신형배송’ 서비스 정식 개시",
    "가상기업, 데이터센터 통합 운영 시작",
])
def test_explicit_starts_are_classified_without_investment_or_sector_terms(tmp_path, title):
    row = run(setup(tmp_path, title))["results"][0]
    assert row["category_candidate"] == "BUSINESS_START"
    assert row["novelty"] == "NEW_FACT_CANDIDATE_NEEDS_EVIDENCE"
    assert not row["reported_plan_only"] and not row["ai_eligible"]
    assert not row["verified_economic_fact"] and not row["verified_beneficiary"]


@pytest.mark.parametrize("title", [
    "가상기업, HBM 검사 서비스 개시 예정",
    "가상기업, ‘신형배송’ 서비스 시작할 계획",
    "가상기업, 데이터센터 통합 운영 나선다",
    "가상기업, HBM 검사 사업에 나설 예정",
])
def test_intention_never_becomes_reported_operation(tmp_path, title):
    row = run(setup(tmp_path, title))["results"][0]
    assert row["category_candidate"] == "BUSINESS_START"
    assert row["reported_plan_only"]
    assert all(c["phase"] == "PLANNED" for c in row["economic_changes"])
    assert business_start_phase(title) == "PLANNED"


@pytest.mark.parametrize("title", [
    "HBM 서비스 개시를 위한 업무협약 체결",
    "HBM 서비스 개시 기념 행사 개최",
    "HBM 서비스 개시 1주년 세미나",
    "HBM 사업 시작하지 않았다",
    "HBM 서비스 개시하지 못했다",
    "HBM 서비스 시작 사실무근",
    "HBM 서비스 개시 취소",
    "지난해 HBM 서비스 개시 성과 발표",
    "HBM 체험 운영 시작",
    "HBM 시범 서비스 개시",
    "HBM 공동사업 추진 업무협약 체결",
    "HBM 서비스 운영 승인 획득",
    "HBM 서비스 개발 중",
    "HBM 서비스 개시 가능성",
    "HBM 서비스 시작 방법 소개",
])
def test_agreements_events_denials_and_old_operation_are_not_starts(title):
    assert business_start_phase(title) is None
    assert _category(title) is None
    assert extract_economic_changes(title) == []


def test_named_service_reaches_saved_report_dashboard_and_individual_theme(tmp_path):
    info = setup(tmp_path, "가상회사, 서비스 ‘이웃도움’ 전국 출시")
    source = info[0]
    before = fingerprint(source.inbox_root.parent)
    work = tmp_path / "reports" / "core"
    themes = tmp_path / "themes"
    opts = run_feed_analysis.parser().parse_args([
        "--registry", str(source.registry_path), "--inbox-root", str(source.inbox_root),
        "--state", str(source.poll_state), "--analysis-root", str(work),
        "--theme-root", str(themes)])
    at = datetime.now(timezone.utc)
    code, report = run_feed_analysis.evaluate(opts, now=at)
    assert code == 0 and report["theme_versions_created"] == 1
    row = report["results"][0]
    assert row["source_matched_fields"][0]["value"] == "이웃도움"
    assert row["economic_changes"][0]["action"] == "BUSINESS_START"
    assert row["economic_changes"][0]["economic_driver"] == "UNKNOWN"
    path = Path(report["private_report_file"])
    assert consume_feed_analysis(path, path.parent, report["report_sha256"], now=at)["results"] == report["results"]
    saved, _ = scan_saved_analysis(work.parent, now=at)
    assert saved[0]["category"] == "BUSINESS_START"
    assert saved[0]["source_products"] == ["이웃도움"]
    store = ThemeStore(themes)
    first = store.search(now=at)
    assert len(first) == 1 and first[0]["status"] == "CANDIDATE"
    assert first[0]["verified_beneficiary_count"] == 0
    assert first[0]["source_refs"][0]["content_scope"] == "RSS_TITLE_METADATA"
    assert not store.search(as_of=at-timedelta(seconds=1), now=at)
    _, again = run_feed_analysis.evaluate(opts, now=at+timedelta(minutes=1))
    assert again["theme_versions_created"] == 0
    assert store.search(now=at+timedelta(minutes=1)) == first
    assert fingerprint(source.inbox_root.parent) == before


def test_explicit_shared_demand_overrides_service_brand_as_topic():
    changes = extract_economic_changes(
        "가상전자는 광자냉각 수요 증가에 대응해 ‘새검사’ 서비스를 개시했다.")
    assert len(changes) == 1
    assert changes[0]["topic"] == "광자냉각"
    assert changes[0]["economic_driver"] == "DEMAND_EXPANSION"
    assert changes[0]["action"] == "BUSINESS_START"


def test_unnamed_generic_business_is_classified_without_inventing_theme():
    assert _category("가상회사, 신규 사업 시작") == "BUSINESS_START"
    assert extract_economic_changes("가상회사, 신규 사업 시작") == []
