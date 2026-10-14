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
    assert first["source_fetch_calls"] == first["human_labels_added"] == 0
    assert "FULL ARTICLE BODY" not in json.dumps(first)


def test_rules_only_then_authorized_run_does_not_lose_pending_candidate(tmp_path, fake_key):
    info = setup(tmp_path)
    before = run(info)
    assert before["results"][0]["ai_status"] == "AWAITING_EXPLICIT_AI_AUTHORIZATION"
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
    assert report["rule_version"] == "rss-title-economic-v2"
    assert row["category_candidate"] == "CONTRACT_TERMINATION"
    assert row["reported_termination_only"] and not row["reported_plan_only"]
    assert row["ai_eligible"] and row["ai_status"] == "AWAITING_EXPLICIT_AI_AUTHORIZATION"
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
    assert row["ai_status"] == "AWAITING_EXPLICIT_AI_AUTHORIZATION"
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
