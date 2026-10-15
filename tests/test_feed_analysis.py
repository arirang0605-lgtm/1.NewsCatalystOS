"""Actual checkpoint -> analysis -> adapter/cache/report, SYNTHETIC news and AI only."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from newscatalystos.feed_analysis import analyze_completed_feed, publish_feed_analysis
from newscatalystos.source_share import SourceShareError
from scripts import run_feed_analysis
from test_federated_news_search import setup_workspace, collect, fingerprint, GOV
from test_new_source_adapter import registry, NOW
from test_ai_provider import config
from test_ai_openai_transport import LocalOpener, packet

TITLE = "반도체 업계 HBM 1조원 공급계약 체결, 3년간 공급"
URL = "https://gov.example.org/semiconductor/contract-1"


def setup(tmp_path, title=TITLE):
    reg = registry()
    workspace = setup_workspace(tmp_path, "source", reg)
    folder, ack = collect(workspace, reg, GOV, [("contract-1", title, URL)])
    work = tmp_path / "derived_analysis"
    return workspace, reg, folder, ack, work


def run(info, **kwargs):
    source, reg, _, _, work = info
    return analyze_completed_feed(reg, source.inbox_root, source.poll_state, work, **kwargs)


@pytest.fixture
def fake_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-material-not-real-abcdef0123456789")


def test_complete_path_uses_source_evidence_budgeted_adapter_then_cache(tmp_path, fake_key):
    info = setup(tmp_path)
    before = fingerprint(info[0].inbox_root.parent)
    opener = LocalOpener(packet())
    first = run(info, model=config(), allow_paid=True, opener=opener)
    row = first["results"][0]
    assert row["ai_eligible"] and row["known_dimension_score_lower_bound"] == 9
    assert row["complete_importance_score"] is None
    assert row["unknown_dimensions"] == ["market_expectation"]
    assert row["dimensions"]["market_expectation"] == "UNKNOWN"
    assert row["category_candidate"] == "NEW_CONTRACT"
    assert row["novelty"] == "NEW_FACT_CANDIDATE_NEEDS_EVIDENCE"
    assert row["ai_status"] == "ANALYZED_UNVERIFIED"
    assert {v["value"] for v in row["source_matched_fields"]} >= {"HBM", "1조원"}
    ai = row["ai_analysis"]
    assert ai["is_verified_market_fact"] is False
    assert ai["classification"].startswith("UNVERIFIED")
    assert ai["event_sha256"] == row["analysis_event_sha256"]
    assert ai["available_at"] <= row["analysis_available_at"]
    second = run(info, model=config(), allow_paid=True, opener=opener)
    assert second["cache_hits"] == 1 and second["new_ai_results"] == 0
    assert second["results"][0]["ai_analysis"] == ai
    assert second["results"][0]["already_recorded_source_version"]
    assert opener.calls == 1
    with sqlite3.connect(info[-1] / "ai_costs.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM ai_invocations").fetchone()[0] == 1
        assert db.execute("SELECT settled_krw FROM ai_invocations").fetchone()[0] == pytest.approx(.09)
    assert fingerprint(info[0].inbox_root.parent) == before
    assert not row["verified_economic_fact"] and row["revenue_estimate_krw"] is None
    assert first["source_fetch_calls"] == 0
    assert "FULL ARTICLE BODY" not in json.dumps(first)


def test_rules_only_then_authorized_run_does_not_lose_pending_candidate(tmp_path, fake_key):
    info = setup(tmp_path)
    before = run(info)
    assert before["results"][0]["ai_status"] == "AI_DISABLED_BY_CONFIGURATION"
    assert not (info[-1] / "ai_costs.sqlite3").exists()
    opener = LocalOpener(packet())
    after = run(info, model=config(), allow_paid=True, opener=opener)
    assert after["new_ai_results"] == 1 and opener.calls == 1


def test_changed_contract_value_uses_new_version_and_previous_economic_state(tmp_path, fake_key):
    info = setup(tmp_path)
    opener = LocalOpener(packet())
    first = run(info, model=config(), allow_paid=True, opener=opener)
    collect(info[0], info[1], GOV, [("contract-1", TITLE.replace("1조원", "2조원"), URL)],
            at=NOW + timedelta(hours=1))
    second = run(info, model=config(), allow_paid=True, opener=opener)
    row = second["results"][0]
    assert row["novelty"] == "CHANGED_ECONOMIC_CLAIM_REVIEW"
    assert row["known_dimension_score_lower_bound"] == 8
    assert row["ai_status"] == "ANALYZED_UNVERIFIED"
    assert row["analysis_event_sha256"] != first["results"][0]["analysis_event_sha256"]
    assert opener.calls == 2
    assert second["source_versions_checked"] == 2 and len(second["results"]) == 1


@pytest.mark.parametrize("title", [
    "광고: " + TITLE, "루머: " + TITLE, TITLE + " 계약 취소", "HBM 반도체 행사 개최",
])
def test_rumor_ad_cancellation_or_keyword_alone_never_calls_ai(tmp_path, fake_key, title):
    info = setup(tmp_path, title)
    opener = LocalOpener(packet())
    report = run(info, model=config(), allow_paid=True, opener=opener)
    row = report["results"][0]
    assert not row["ai_eligible"] and row["ai_status"] == "NOT_ELIGIBLE"
    assert row["source_matched_fields"]
    assert not row["verified_economic_fact"] and opener.calls == 0


def test_partial_evidence_survives_missing_amount_and_unknown_dimensions(tmp_path):
    report = run(setup(tmp_path, "HBM 공급계약 체결"))
    row = report["results"][0]
    assert row["category_candidate"] == "NEW_CONTRACT"
    assert row["dimensions"]["novelty"] == "NEW_FACT_CANDIDATE"
    assert row["dimensions"]["scale"] == "UNKNOWN"
    assert row["source_matched_fields"][0]["value"] == "HBM"
    assert row["source_amount_mentions"] == [] and row["ai_analysis"] is None


@pytest.mark.parametrize("title,product", [
    ("가상회사, 배터리 성능 강화 GPS 시계 ‘Trail 4’ 출시", "Trail 4"),
    ("가상기업, 팀워크 돕는 ‘관계 번역기’ 정식 출시", "관계 번역기"),
    ('가상기업, "새로운 엔진"을 공식 출시했다', "새로운 엔진"),
    ("가상기업, 「신규 시스템」 국내 출시", "신규 시스템"),
])
def test_named_launch_without_known_sector_keyword_survives_to_dashboard(tmp_path, title, product):
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    from newscatalystos.research_dashboard import scan_saved_analysis
    info = setup(tmp_path, title)
    original = fingerprint(info[0].inbox_root.parent)
    opener = LocalOpener(packet())
    report = run(info, model=config(), allow_paid=True, opener=opener)
    row = report["results"][0]
    assert row["category_candidate"] == "PRODUCT_LAUNCH"
    assert row["novelty"] == "NEW_FACT_CANDIDATE_NEEDS_EVIDENCE"
    assert [x["value"] for x in row["source_matched_fields"]] == [product]
    assert not row["reported_plan_only"] and not row["verified_economic_fact"]
    assert row["dimensions"]["scale"] == "UNKNOWN"
    assert row["dimensions"]["affected_scope"] == "UNKNOWN"
    assert not row["ai_eligible"] and opener.calls == report["new_ai_results"] == 0
    root = tmp_path / "dashboard"
    path, digest = publish_feed_analysis(report, root / "core" / "reports")
    assert consume_feed_analysis(path, path.parent, digest)["results"] == report["results"]
    items, counts = scan_saved_analysis(root)
    assert counts["saved_reports_skipped"] == 0
    assert len(items) == 1 and items[0]["source_products"] == [product]
    assert items[0]["content_scope"] == "RSS_TITLE_METADATA"
    again = run(info)["results"][0]
    assert again["already_recorded_source_version"]
    assert again["analysis_event_sha256"] == row["analysis_event_sha256"]
    assert fingerprint(info[0].inbox_root.parent) == original


@pytest.mark.parametrize("suffix", ["출시 예정", "출시 계획 발표"])
def test_named_launch_plan_remains_a_plan(tmp_path, suffix):
    row = run(setup(tmp_path, "가상회사, ‘차세대 플랫폼’ " + suffix))["results"][0]
    assert row["category_candidate"] == "PRODUCT_LAUNCH"
    assert row["reported_plan_only"] and not row["ai_eligible"]
    assert not row["verified_economic_fact"]


@pytest.mark.parametrize("title", [
    "가상회사, ‘차세대 플랫폼’ 공개",
    "가상회사, ‘차세대 플랫폼’ 개발 중",
    "가상회사, ‘차세대 플랫폼’ 출시 기념 행사 개최",
    "가상회사, ‘차세대 플랫폼’ 출시를 앞두고 설명회 개최",
    "가상회사, ‘차세대 플랫폼’ 출시하지 않았다",
    "가상회사, ‘차세대 플랫폼’ 출시 사실무근",
    "가상회사, ‘차세대 플랫폼’ 출시 취소",
    "가상회사, 신제품 HBM 출시 기념 세미나 개최",
    "가상회사, ‘차세대 플랫폼’ 출시 이후 점유율 발표",
    "가상회사, ‘신제품 전략’ 발표…신기술 출시 경쟁",
])
def test_launch_context_or_denial_is_not_a_new_launch(tmp_path, title):
    row = run(setup(tmp_path, title))["results"][0]
    assert row["category_candidate"] is None
    assert row["novelty"] == "UNCLASSIFIED_SOURCE_CLAIM"
    assert not row["ai_eligible"]


def test_cumulative_order_results_are_not_a_new_contract(tmp_path):
    row = run(setup(tmp_path, "반도체 HBM 3분기 수주 및 매출 기록 달성"))["results"][0]
    assert row["category_candidate"] is None
    assert row["novelty"] == "UNCLASSIFIED_SOURCE_CLAIM"
    assert not row["ai_eligible"]


def test_explicit_order_contract_remains_reviewable(tmp_path):
    row = run(setup(tmp_path, "반도체 HBM 장비 수주 계약 확정"))["results"][0]
    assert row["category_candidate"] == "NEW_CONTRACT"
    assert row["novelty"] == "NEW_FACT_CANDIDATE_NEEDS_EVIDENCE"
    assert not row["verified_supply_transaction"]


def test_future_plan_preserved_even_after_successful_ai(tmp_path, fake_key):
    info = setup(tmp_path, TITLE.replace("체결", "계획"))
    report = run(info, model=config(), allow_paid=True, opener=LocalOpener(packet()))
    row = report["results"][0]
    assert row["reported_plan_only"] and row["ai_status"] == "ANALYZED_UNVERIFIED"
    assert not row["verified_supply_transaction"] and not row["verified_beneficiary"]


def test_provider_failure_keeps_partial_result_and_never_retries_billed_call(tmp_path, fake_key):
    info = setup(tmp_path)
    opener = LocalOpener(b'not JSON')
    first = run(info, model=config(), allow_paid=True, opener=opener)
    assert first["results"][0]["ai_status"] == "AI_PROVIDER_OR_CACHE_UNAVAILABLE"
    assert first["results"][0]["source_matched_fields"]
    second = run(info, model=config(), allow_paid=True, opener=opener)
    assert second["results"][0]["ai_status"] == "AI_ALREADY_RESERVED_OR_RESULT_UNAVAILABLE"
    assert opener.calls == 1 and second["new_ai_results"] == 0
    with sqlite3.connect(info[-1] / "ai_costs.sqlite3") as db:
        assert db.execute("SELECT settled_at FROM ai_invocations").fetchone()[0] is None


def test_missing_credential_does_not_create_billing_record(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    info = setup(tmp_path)
    opener = LocalOpener(packet())
    row = run(info, model=config(), allow_paid=True, opener=opener)["results"][0]
    assert row["ai_status"] == "AI_CREDENTIAL_UNAVAILABLE"
    assert opener.calls == 0 and not (info[-1] / "ai_costs.sqlite3").exists()


def test_tampered_source_fails_before_analysis_state_created(tmp_path):
    info = setup(tmp_path)
    payload = info[2] / "triage.json"
    payload.write_bytes(payload.read_bytes() + b" CORRUPTED")
    with pytest.raises(SourceShareError):
        run(info)
    assert not info[-1].exists()


def test_earlier_decision_cannot_use_completed_source_or_create_result(tmp_path):
    info = setup(tmp_path)
    with pytest.raises(SourceShareError):
        run(info, now=NOW + timedelta(seconds=1))
    assert not info[-1].exists()


def test_investment_amount_is_not_mislabeled_contract_amount(tmp_path):
    row = run(setup(tmp_path, "반도체 업계 HBM 설비 1조원 투자 결정"))["results"][0]
    assert row["category_candidate"] == "NEW_INVESTMENT"
    assert row["source_amount_mentions"] == ["1조원"]
    assert all(v["field"] != "CONTRACT_AMOUNT" for v in row["source_matched_fields"])


def test_private_report_and_cli_separate_process_work_without_ai(tmp_path):
    info = setup(tmp_path)
    project = Path(__file__).resolve().parent.parent
    args = [sys.executable, str(project / "scripts/run_feed_analysis.py"),
            "--registry", str(info[0].registry_path), "--inbox-root", str(info[0].inbox_root),
            "--state", str(info[0].poll_state), "--analysis-root", str(info[-1])]
    env = dict(os.environ, PYTHONPATH=str(project / "src"))
    child = subprocess.run(args, env=env, cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert child.returncode == 0, child.stderr
    data = json.loads(child.stdout)
    saved = Path(data["private_report_file"])
    assert sha256(saved.read_bytes()).hexdigest() == data["report_sha256"]
    assert saved.stat().st_mode & 0o077 == 0
    stored = json.loads(saved.read_bytes())
    assert stored["results"][0]["source_matched_fields"]
    assert data["requested_ai_complete"] is None
    assert data["new_ai_results"] == data["cache_hits"] == 0
    assert publish_feed_analysis(stored, saved.parent)[0] == saved
    assert not list(saved.parent.glob(".analysis_*"))


def test_cli_partial_ai_failure_returns_source_fields_and_exit_four(tmp_path, fake_key):
    info = setup(tmp_path)
    modelpath = info[-1].parent / "model" / "approved.json"
    modelpath.parent.mkdir(mode=0o700)
    modelpath.write_text(json.dumps(asdict(config())))
    modelpath.chmod(0o600)
    opts = run_feed_analysis.parser().parse_args([
        "--registry", str(info[0].registry_path), "--inbox-root", str(info[0].inbox_root),
        "--state", str(info[0].poll_state), "--analysis-root", str(info[-1]),
        "--model-config", str(modelpath), "--allow-paid"])
    code, data = run_feed_analysis.evaluate(opts, opener=LocalOpener(b'bad'))
    assert code == 4 and data["requested_ai_complete"] is False
    assert data["results"][0]["source_matched_fields"]
    assert Path(data["private_report_file"]).is_file()


def test_republished_same_claim_same_url_is_not_new_economic_event(tmp_path, fake_key):
    info = setup(tmp_path)
    opener = LocalOpener(packet())
    run(info, model=config(), allow_paid=True, opener=opener)
    collect(info[0], info[1], GOV, [("different-guid", TITLE, URL)],
            at=NOW + timedelta(hours=1))
    report = run(info, model=config(), allow_paid=True, opener=opener)
    repeated = next(r for r in report["results"] if r["document_id"] == "different-guid")
    assert repeated["novelty"] == "EXISTING_ECONOMIC_CLAIM"
    assert not repeated["ai_eligible"] and repeated["ai_analysis"] is None
    assert opener.calls == 1


def test_invalid_cache_keeps_source_result_without_rebilling(tmp_path, fake_key):
    info = setup(tmp_path)
    opener = LocalOpener(packet())
    run(info, model=config(), allow_paid=True, opener=opener)
    with sqlite3.connect(info[-1] / "ai_cache.sqlite3") as db:
        db.execute("UPDATE analysis_cache SET payload='modified'")
    report = run(info, model=config(), allow_paid=True, opener=opener)
    row = report["results"][0]
    assert row["ai_status"] == "AI_CACHE_UNAVAILABLE"
    assert row["source_matched_fields"] and row["ai_analysis"] is None
    assert opener.calls == 1


def test_currency_or_multiple_amounts_do_not_invent_krw_scale(tmp_path):
    for idx, value in enumerate(("100 million USD", "1조원, 2조원")):
        folder = tmp_path / str(idx); folder.mkdir(mode=0o700)
        report = run(setup(folder, TITLE.replace("1조원", value)))
        row = report["results"][0]
        assert row["dimensions"]["scale"] == "UNKNOWN"
        assert row["revenue_estimate_krw"] is None
        assert row["ai_status"] == "NOT_ELIGIBLE"


def test_publication_succeeds_on_filesystem_without_hard_links(tmp_path, monkeypatch):
    report = run(setup(tmp_path))
    def unsupported(*args, **kwargs):
        raise OSError(45, "Operation not supported")
    monkeypatch.setattr(os, "link", unsupported)
    dest, digest = publish_feed_analysis(report, tmp_path / "reports")
    original = dest.read_bytes()
    assert sha256(original).hexdigest() == digest
    assert publish_feed_analysis(report, dest.parent)[0] == dest
    assert dest.read_bytes() == original


def test_explicit_contract_termination_is_reviewed_not_a_new_contract(tmp_path):
    title = "글로벌 HBM 반도체 3년간 공급 계약 2000억원 해지"
    info = setup(tmp_path, title)
    report = run(info)  # no paid provider; original authorized metadata only
    row = report["results"][0]
    assert report["rule_version"] == "rss-title-economic-v8"
    assert row["category_candidate"] == "CONTRACT_TERMINATION"
    assert row["reported_termination_only"] and not row["reported_plan_only"]
    assert row["ai_eligible"] and row["ai_status"] == "AI_DISABLED_BY_CONFIGURATION"
    assert row["known_dimension_score_lower_bound"] >= 8
    assert "2000억원" in row["source_amount_mentions"]
    assert all(v["field"] != "CONTRACT_AMOUNT" for v in row["source_matched_fields"])
    assert not row["verified_economic_fact"] and not row["verified_supply_transaction"]
    assert not row["verified_beneficiary"] and row["revenue_estimate_krw"] is None
    assert any("independent official confirmation" in s for s in row["uncertainties"])
    assert report["source_fetch_calls"] == 0 and report["new_ai_results"] == 0


def test_revision_from_supply_contract_to_termination_preserves_pit_and_delivery(tmp_path):
    original = "글로벌 HBM 반도체 3년간 공급 계약 2000억원 체결"
    cancelled = original.replace("체결", "해지")
    info = setup(tmp_path, original)
    first = run(info)
    assert first["results"][0]["category_candidate"] == "NEW_CONTRACT"
    collect(info[0], info[1], GOV, [("contract-1", cancelled, URL)],
            at=NOW + timedelta(hours=1))
    second = run(info)
    row = second["results"][0]
    assert row["category_candidate"] == "CONTRACT_TERMINATION"
    assert row["novelty"] == "CHANGED_ECONOMIC_CLAIM_REVIEW"
    assert row["analysis_event_sha256"] != first["results"][0]["analysis_event_sha256"]
    assert row["source_available_at"] >= first["results"][0]["source_available_at"]
    assert row["ai_status"] == "AI_DISABLED_BY_CONFIGURATION"
    saved, digest = publish_feed_analysis(second, tmp_path / "reports")
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    output = consume_feed_analysis(saved, saved.parent, digest)
    assert output["results"][0] == row
    assert output["source_fetch_calls"] == output["ai_calls"] == 0
    assert not output["historical_decision_certified"]


@pytest.mark.parametrize("title", [
    "글로벌 HBM 반도체 3년간 공급 계약 2000억원 해지 부인",
    "글로벌 HBM 반도체 3년간 공급 계약 2000억원 해지 루머",
    "글로벌 HBM 반도체 3년간 공급 계약 2000억원 체결 후 취소",
])
def test_denied_rumored_or_contradictory_contract_termination_is_not_routed(tmp_path, title):
    row = run(setup(tmp_path, title))["results"][0]
    assert row["category_candidate"] is None
    assert not row["ai_eligible"] and row["ai_status"] == "NOT_ELIGIBLE"
    assert not row["reported_termination_only"] and not row["verified_economic_fact"]


def test_english_supply_contract_termination_does_not_become_a_new_deal(tmp_path):
    row = run(setup(tmp_path, "Global HBM semiconductor supply contract terminated"))["results"][0]
    assert row["category_candidate"] == "CONTRACT_TERMINATION"
    assert row["reported_termination_only"] and not row["verified_supply_transaction"]
    assert row["source_amount_mentions"] == []
    assert not row["ai_eligible"] and row["ai_status"] == "NOT_ELIGIBLE"


def test_contract_cancellation_followup_links_earlier_contract_only_as_candidate(tmp_path):
    original = "글로벌 HBM 반도체 3년간 공급 계약 2000억원 체결"
    info = setup(tmp_path, original)
    first = run(info)["results"][0]
    assert first["followup_change"] is None
    collect(info[0], info[1], GOV,
            [("contract-1", original.replace("체결", "해지"), URL)],
            at=NOW + timedelta(hours=1))
    second = run(info)["results"][0]
    followup = second["followup_change"]
    assert second["category_candidate"] == "CONTRACT_TERMINATION"
    assert followup["change_kind"] == "BUSINESS_CANCELLED"
    assert followup["status"] == "INVALIDATED_CANDIDATE"
    assert followup["prior_fact_sha256"] is not None
    assert followup["prior_title_sha256"] == first["source_title_sha256"]
    assert followup["prior_available_at"] == first["source_available_at"]
    assert followup["available_at"] >= second["source_available_at"]
    assert not followup["prior_claim_verified"] and not followup["realization_confirmed"]
    assert not second["verified_supply_transaction"] and not second["verified_economic_fact"]
    assert second["ai_status"] == "AI_DISABLED_BY_CONFIGURATION"
    report = run(info)
    saved, digest = publish_feed_analysis(report, tmp_path / "reports")
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    out = consume_feed_analysis(saved, saved.parent, digest)
    assert out["results"][0]["followup_change"]["status"] == "INVALIDATED_CANDIDATE"
    assert out["ai_calls"] == out["source_fetch_calls"] == out["database_writes"] == 0


def test_contract_cancellation_with_no_earlier_contract_is_held(tmp_path):
    info = setup(tmp_path, "글로벌 HBM 반도체 3년간 공급 계약 2000억원 해지")
    row = run(info)["results"][0]
    assert row["category_candidate"] == "CONTRACT_TERMINATION"
    assert row["followup_change"]["status"] == "NO_PRIOR_EVENT_HOLD"
    assert row["followup_change"]["prior_title_sha256"] is None
    assert row["followup_change"]["prior_fact_sha256"] is None
    assert not row["followup_change"]["realization_confirmed"]


def test_planned_or_unrelated_contract_does_not_establish_followup(tmp_path):
    for idx, original, next_id in (
        ("plan", "글로벌 HBM 반도체 공급 계약 2000억원 계획", "contract-1"),
        ("other", "글로벌 HBM 반도체 공급 계약 2000억원 체결", "another-document"),
    ):
        folder = tmp_path / idx
        folder.mkdir(mode=0o700)
        info = setup(folder, original)
        run(info)
        collect(info[0], info[1], GOV,
                [(next_id, "글로벌 HBM 반도체 공급 계약 2000억원 해지", URL)],
                at=NOW + timedelta(hours=1))
        second = run(info)
        cancelled = next(r for r in second["results"]
                         if r["headline"].endswith("해지"))
        assert cancelled["followup_change"]["status"] == "NO_PRIOR_EVENT_HOLD"
        assert cancelled["followup_change"]["prior_fact_sha256"] is None


def test_rumored_or_denied_cancellation_creates_no_followup(tmp_path):
    info = setup(tmp_path, "글로벌 HBM 반도체 공급 계약 2000억원 해지 루머")
    row = run(info)["results"][0]
    assert row["category_candidate"] is None
    assert row["followup_change"] is None
    assert row["ai_status"] == "NOT_ELIGIBLE"


def test_contract_reduction_links_prior_title_and_reaches_readonly_consumer(tmp_path):
    original = "글로벌 HBM 반도체 공급 계약 금액 3000억원 체결"
    reduced = "글로벌 HBM 반도체 공급 계약 금액 2000억원으로 감액"
    info = setup(tmp_path, original)
    first = run(info)["results"][0]
    collect(info[0], info[1], GOV, [("contract-1", reduced, URL)],
            at=NOW + timedelta(hours=1))
    report = run(info)
    row = report["results"][0]
    change = row["followup_change"]
    assert report["rule_version"] == "rss-title-economic-v8"
    assert row["category_candidate"] == "CONTRACT_REDUCTION"
    assert row["reported_reduction_only"] and not row["reported_termination_only"]
    assert row["dimensions"]["scale"] == "UNKNOWN"
    assert change["change_kind"] == "CONTRACT_REDUCED"
    assert change["status"] == "WEAKENED_CANDIDATE"
    assert change["prior_title_sha256"] == first["source_title_sha256"]
    assert change["prior_available_at"] == first["source_available_at"]
    assert change["available_at"] >= row["source_available_at"]
    assert not change["prior_claim_verified"] and not change["realization_confirmed"]
    assert not row["verified_economic_fact"] and not row["verified_supply_transaction"]
    assert row["revenue_estimate_krw"] is None
    saved, digest = publish_feed_analysis(report, tmp_path / "reports")
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    consumed = consume_feed_analysis(saved, saved.parent, digest)
    assert consumed["results"][0]["followup_change"] == change
    assert consumed["ai_calls"] == consumed["source_fetch_calls"] == 0


def test_contract_reduction_without_prior_or_with_other_document_is_held(tmp_path):
    reduced = "글로벌 HBM 반도체 3년간 공급 계약 금액 2000억원으로 감액"
    absent = run(setup(tmp_path / "absent", reduced))["results"][0]
    assert absent["followup_change"]["status"] == "NO_PRIOR_EVENT_HOLD"
    assert absent["followup_change"]["prior_fact_sha256"] is None
    assert not absent["ai_eligible"] and absent["ai_status"] == "NOT_ELIGIBLE"
    info = setup(tmp_path / "other", "HBM 반도체 공급 계약 금액 3000억원 체결")
    run(info)
    collect(info[0], info[1], GOV, [("other-document", reduced, URL)],
            at=NOW + timedelta(hours=1))
    changed = next(r for r in run(info)["results"] if r["headline"] == reduced)
    assert changed["followup_change"]["status"] == "NO_PRIOR_EVENT_HOLD"


@pytest.mark.parametrize("suffix", ["예정", "루머", "부인", "체결 후 감액", "해지"])
def test_ambiguous_contract_reduction_does_not_create_followup(tmp_path, suffix):
    title = "HBM 반도체 공급 계약 금액 2000억원 감액 " + suffix
    row = run(setup(tmp_path, title))["results"][0]
    assert row["category_candidate"] is None
    assert row["followup_change"] is None
    assert not row["verified_economic_fact"]


def test_contract_delivery_delay_links_prior_claim_and_reaches_consumer(tmp_path):
    original = "글로벌 HBM 반도체 3년간 공급 계약 2000억원 체결"
    delayed = "글로벌 HBM 반도체 3년간 공급 계약 납기 지연"
    info = setup(tmp_path, original)
    first = run(info)["results"][0]
    collect(info[0], info[1], GOV, [("contract-1", delayed, URL)],
            at=NOW + timedelta(hours=1))
    report = run(info)
    row = report["results"][0]
    change = row["followup_change"]
    assert report["rule_version"] == "rss-title-economic-v8"
    assert row["category_candidate"] == "CONTRACT_DELAY"
    assert row["reported_delay_only"] and not row["reported_termination_only"]
    assert row["dimensions"]["scale"] == "UNKNOWN"
    assert change["change_kind"] == "DATE_DELAYED"
    assert change["status"] == "WEAKENED_CANDIDATE"
    assert change["prior_title_sha256"] == first["source_title_sha256"]
    assert change["prior_available_at"] == first["source_available_at"]
    assert change["available_at"] >= row["source_available_at"]
    assert not change["prior_claim_verified"] and not change["realization_confirmed"]
    assert not row["verified_economic_fact"] and not row["verified_supply_transaction"]
    assert row["revenue_estimate_krw"] is None
    saved, digest = publish_feed_analysis(report, tmp_path / "reports")
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    consumed = consume_feed_analysis(saved, saved.parent, digest)
    assert consumed["results"][0]["followup_change"] == change
    assert consumed["ai_calls"] == consumed["source_fetch_calls"] == 0


def test_delivery_delay_without_prior_is_held_and_not_sent_to_ai(tmp_path):
    delayed = "글로벌 HBM 반도체 공급 계약 납기 지연"
    row = run(setup(tmp_path, delayed))["results"][0]
    assert row["category_candidate"] == "CONTRACT_DELAY"
    assert row["followup_change"]["status"] == "NO_PRIOR_EVENT_HOLD"
    assert row["followup_change"]["prior_fact_sha256"] is None
    assert not row["ai_eligible"] and row["ai_status"] == "NOT_ELIGIBLE"


@pytest.mark.parametrize("title", [
    "HBM 반도체 공급 계약 납기 지연 루머",
    "HBM 반도체 공급 계약 납기 지연 부인",
    "HBM 반도체 공급 계약 납기 지연 예정",
    "HBM 반도체 공급 계약 체결 후 납기 지연",
    "HBM 반도체 공급 계약 금액 감액 및 납기 지연",
])
def test_ambiguous_delivery_delay_is_not_routed(tmp_path, title):
    row = run(setup(tmp_path, title))["results"][0]
    assert row["category_candidate"] is None
    assert row["followup_change"] is None
    assert not row["ai_eligible"] and not row["verified_economic_fact"]


def test_english_delivery_delay_is_reported_without_confirming_delivery(tmp_path):
    row = run(setup(tmp_path, "HBM semiconductor supply contract delivery delayed"))["results"][0]
    assert row["category_candidate"] == "CONTRACT_DELAY"
    assert row["reported_delay_only"]
    assert row["followup_change"]["status"] == "NO_PRIOR_EVENT_HOLD"
    assert not row["verified_supply_transaction"]
