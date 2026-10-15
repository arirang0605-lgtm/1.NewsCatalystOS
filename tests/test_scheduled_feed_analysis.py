"""Existing scheduler -> real checkpoint/ACK -> analysis/report, synthetic data only."""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.sax.saxutils import escape

import pytest

from newscatalystos import feed_analysis, incremental_ingest
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.source_share import SourceShareError
from scripts import run_feed_analysis, run_scheduled_triage as scheduled
from test_ai_openai_transport import LocalOpener, packet
from test_ai_provider import config
from test_feed_analysis import setup, TITLE, URL, fake_key
from test_federated_news_search import (
    setup_workspace, fingerprint, GOV, WIRE, sample,
)
from test_new_source_adapter import registry


def opts(source, work, *, operation="--once", names=None):
    args = ["--registry", str(source.registry_path), "--state", str(source.poll_state),
            "--dedup-state", str(source.poll_state.parent / "dedup.sqlite3"),
            "--inbox-root", str(source.inbox_root),
            "--output-root", str(source.inbox_root.parent / "results"),
            "--analysis-root", str(work), operation]
    for name in names or [GOV]:
        args.extend(["--provider-id", name])
    return scheduled.parser().parse_args(args)


def saved_report(summary, index=0):
    detail = summary["providers"][index]["analysis"]
    path = Path(detail["private_report_file"])
    raw = path.read_bytes()
    assert sha256(raw).hexdigest() == detail["report_sha256"]
    assert path.stat().st_mode & 0o077 == 0
    return json.loads(raw)


def no_call(*args, **kwargs):
    raise AssertionError("operation must not make this call")


def test_single_tick_collects_once_and_stores_analysis_after_committed_ack(tmp_path, monkeypatch):
    reg = registry()
    source = setup_workspace(tmp_path, "source", reg)
    work = tmp_path / "derived"
    calls = []
    rss = ('<rss><channel><item><guid>contract-1</guid><title>' + escape(TITLE)
           + '</title><link>' + URL + '</link></item></channel></rss>').encode()
    def fetch(approved, provider_id, *, at):
        calls.append(provider_id)
        return parse_authorized_feed(approved, provider_id, rss,
                                     observed_at=datetime.now(timezone.utc))
    monkeypatch.setattr(incremental_ingest, "fetch_authorized_once", fetch)
    monkeypatch.setattr(feed_analysis, "run_budgeted_openai_analysis", no_call)
    params = opts(source, work)
    code, first = scheduled.execute(params)
    assert code == 0 and calls == [GOV]
    assert first["providers"][0]["status"] == "FEED_METADATA_TRIAGE_READY"
    assert first["analysis_providers_completed"] == first["analyzed_rows"] == 1
    assert first["analysis_providers_failed"] == first["ai_call_count"] == 0
    stored = saved_report(first)
    row = stored["results"][0]
    assert row["ai_status"] == "AWAITING_EXPLICIT_AI_AUTHORIZATION"
    assert row["source_matched_fields"] and row["verified_economic_fact"] is False
    ack = json.loads(next((source.inbox_root / "acked").glob("*.json")).read_bytes())
    assert ack["confirmed_at"] <= row["analysis_available_at"]
    assert TITLE not in json.dumps(first, ensure_ascii=False)
    assert not (work / "ai_costs.sqlite3").exists()
    code, second = scheduled.execute(params)
    assert code == 0 and calls == [GOV]
    assert second["providers"][0]["status"] == "NOT_DUE"
    assert saved_report(second)["results"][0]["already_recorded_source_version"]


def test_dry_run_with_default_analysis_never_fetches_or_writes(tmp_path):
    reg = registry()
    source = setup_workspace(tmp_path, "source", reg)
    work = tmp_path / "derived"
    before = fingerprint(tmp_path)
    code, result = scheduled.execute(opts(source, work, operation="--dry-run"),
                                    feed_runner=no_call, analysis_runner=no_call)
    assert code == 0 and result["analysis_enabled"]
    assert result["analyzed_rows"] == 0 and not work.exists()
    assert fingerprint(tmp_path) == before


def test_analysis_write_failure_does_not_undo_ingest_and_replay_needs_no_fetch(tmp_path, monkeypatch):
    info = setup(tmp_path)
    source, _, _, _, work = info
    params = opts(source, work, operation="--replay-only")
    original = fingerprint(source.inbox_root.parent)
    writer = run_feed_analysis.publish_feed_analysis
    def disk_error(*args, **kwargs):
        raise OSError("synthetic failed report write")
    monkeypatch.setattr(run_feed_analysis, "publish_feed_analysis", disk_error)
    monkeypatch.setattr(incremental_ingest, "fetch_authorized_once", no_call)
    code, failed = scheduled.execute(params)
    assert code == 4 and failed["providers_failed"] == 0
    assert failed["analysis_providers_failed"] == 1
    assert fingerprint(source.inbox_root.parent) == original
    monkeypatch.setattr(run_feed_analysis, "publish_feed_analysis", writer)
    code, recovered = scheduled.execute(params)
    assert code == 0 and recovered["analysis_providers_completed"] == 1
    assert saved_report(recovered)["results"][0]["source_matched_fields"]
    assert fingerprint(source.inbox_root.parent) == original


@pytest.mark.parametrize("raises", [False, True])
def test_failed_poll_keeps_failure_visible_but_analyzes_previous_completed_source(tmp_path, raises):
    source, _, _, _, work = setup(tmp_path)
    original = fingerprint(source.inbox_root.parent)
    def offline(_params):
        if raises:
            raise OSError("temporary source unavailable")
        return 4, {"status": "DATA_UNAVAILABLE"}
    code, result = scheduled.execute(opts(source, work), feed_runner=offline)
    assert code == 4 and result["providers_failed"] == 1
    assert result["providers"][0]["status"] == "DATA_UNAVAILABLE"
    assert result["analysis_providers_completed"] == 1
    assert saved_report(result)["results"][0]["source_available_at"]
    assert fingerprint(source.inbox_root.parent) == original


def test_one_corrupt_provider_does_not_block_other_provider_analysis(sample, tmp_path):
    sources, _, outputs, _ = sample
    source = sources[0]
    (outputs[0] / "triage.json").write_bytes(b"corrupt government result")
    params = opts(source, tmp_path / "analysis", names=[GOV, WIRE])
    code, result = scheduled.execute(params,
        feed_runner=lambda ns: (0, {"status": "NO_PENDING_REPLAY"}))
    assert code == 4 and result["providers_failed"] == 0
    assert result["analysis_providers_failed"] == result["analysis_providers_completed"] == 1
    assert result["providers"][0]["analysis"]["exit_code"] == 4
    assert {r["provider_id"] for r in saved_report(result, 1)["results"]} == {WIRE}


def test_existing_model_cache_reused_without_paid_permission_or_another_ai_call(tmp_path, fake_key, monkeypatch):
    source, _, _, _, work = setup(tmp_path)
    model_dir = tmp_path / "models"; model_dir.mkdir(mode=0o700)
    model_path = model_dir / "test-model.json"
    model_path.write_text(json.dumps(asdict(config()))); model_path.chmod(0o600)
    seed = run_feed_analysis.parser().parse_args([
        "--registry", str(source.registry_path), "--state", str(source.poll_state),
        "--inbox-root", str(source.inbox_root), "--analysis-root", str(work),
        "--model-config", str(model_path), "--allow-paid"])
    opener = LocalOpener(packet())
    code, first = run_feed_analysis.evaluate(seed, opener=opener)
    assert code == 0 and opener.calls == 1
    params = opts(source, work, operation="--replay-only")
    params.analysis_model_config = model_path
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(feed_analysis, "run_budgeted_openai_analysis", no_call)
    code, result = scheduled.execute(params)
    cached = saved_report(result)["results"][0]
    assert code == 0 and result["analysis_cache_hits"] == 1
    assert result["ai_call_count"] == 0 and opener.calls == 1
    assert cached["ai_status"] == "CACHE_HIT"
    assert cached["ai_analysis"] == first["results"][0]["ai_analysis"]
    assert result["providers"][0]["analysis"]["paid_execution_requested"] is False


def test_legacy_skip_analysis_keeps_only_collection(tmp_path):
    source, _, _, _, work = setup(tmp_path)
    params = opts(source, work, operation="--replay-only"); params.skip_analysis = True
    code, report = scheduled.execute(params, analysis_runner=no_call)
    assert code == 0 and not report["analysis_enabled"]
    assert "analysis" not in report["providers"][0] and not work.exists()


def test_latest_version_limit_is_explicit_not_claimed_as_full_history(sample, tmp_path):
    source = sample[0][0]
    params = opts(source, tmp_path / "analysis", operation="--replay-only")
    params.analysis_limit = 1
    code, result = scheduled.execute(params)
    assert code == 0
    assert result["analyzed_rows"] == 1
    assert result["providers"][0]["analysis"]["has_more_results"] is True


def test_standalone_replay_tick_saves_result_and_does_not_touch_source(tmp_path):
    source, _, _, _, work = setup(tmp_path)
    project = Path(__file__).resolve().parent.parent
    argv = [sys.executable, str(project / "scripts/run_scheduled_triage.py"),
        "--replay-only", "--registry", str(source.registry_path), "--provider-id", GOV,
        "--state", str(source.poll_state),
        "--dedup-state", str(source.poll_state.parent / "dedup.sqlite3"),
        "--inbox-root", str(source.inbox_root),
        "--output-root", str(source.inbox_root.parent / "results"),
        "--analysis-root", str(work)]
    before = fingerprint(source.inbox_root.parent)
    child = subprocess.run(argv, cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(project / "src")),
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == 0, child.stderr
    summary = json.loads(child.stdout)
    assert saved_report(summary)["results"][0]["source_matched_fields"]
    assert summary["ai_call_count"] == 0
    assert fingerprint(source.inbox_root.parent) == before


def test_invalid_limit_rejected_before_source_poll(tmp_path):
    source = setup_workspace(tmp_path, "source", registry())
    params = opts(source, tmp_path / "analysis"); params.analysis_limit = 0
    code, report = scheduled.execute(params, feed_runner=no_call, analysis_runner=no_call)
    assert code == 4 and report["status"] == "INVALID_ANALYSIS_LIMIT"


@pytest.mark.parametrize("gold_fails", [False, True])
def test_motir_completed_input_reaches_separate_analysis_even_if_gold_fails(tmp_path, gold_fails):
    from scripts import run_motir_policy_once as sector
    from test_motir_sector_pipeline import config as sector_options
    from test_motir_rss_post import registry as official
    from test_federated_news_search import collect, write_registry
    from newscatalystos.federated_news_search import TitleSearchWorkspace
    params = sector_options(tmp_path)
    params.capture_gold = True
    params.skip_analysis = False
    params.replay_only = True
    params.analysis_root = tmp_path / "sector_analysis"
    reg = official()
    write_registry(params.registry, reg)
    source = TitleSearchWorkspace("motir", params.registry, params.state, params.inbox_root)
    collect(source, reg, "motir-official-press",
            [("policy-1", "반도체 HBM 설비 투자 발표", "https://www.motir.go.kr/policy/1")],
            at=datetime.now(timezone.utc))
    original = fingerprint(params.inbox_root)
    def gold_step(_params):
        if gold_fails:
            raise OSError("synthetic unavailable Gold workspace")
        return 0, {"status": "NO_NEW_VERIFIED_RSS_CANDIDATES"}
    code, result = sector.run_once(params, gold_runner=gold_step)
    assert code == 0
    assert bool(result["research_warning"]) is gold_fails
    assert result["analysis"]["exit_code"] == 0
    path = Path(result["analysis"]["private_report_file"])
    report = json.loads(path.read_bytes())
    assert path.parent == params.analysis_root / "reports"
    assert {r["provider_id"] for r in report["results"]} == {"motir-official-press"}
    assert report["source_fetch_calls"] == result["ai_calls"] == 0
    assert fingerprint(params.inbox_root) == original


def test_installed_entrypoints_default_to_separate_rules_only_analysis(tmp_path):
    from scripts.run_motir_policy_once import parser as motir_parser
    core = scheduled.parser().parse_args([
        "--once", "--registry", str(tmp_path / "reg.json"), "--provider-id", GOV])
    motir = motir_parser().parse_args([])
    assert not core.skip_analysis and not motir.skip_analysis
    assert motir.capture_gold is False
    assert core.analysis_model_config is motir.analysis_model_config is None
    assert motir.analysis_root.name == "motir"
    assert core.output_root / "feed_analysis" / "core" != motir.analysis_root


def test_scheduled_ai_permission_persists_and_cache_avoids_repeat_call(tmp_path, fake_key):
    source, _, _, _, work = setup(tmp_path)
    model_dir = tmp_path / "models"
    model_dir.mkdir(mode=0o700)
    model_path = model_dir / "model.json"
    model_path.write_text(json.dumps(asdict(config())))
    model_path.chmod(0o600)
    params = opts(source, work)
    params.analysis_model_config = model_path
    params.allow_paid_ai = True
    opener = LocalOpener(packet())
    def analyze(args):
        return run_feed_analysis.evaluate(args, opener=opener)
    for expected_calls in (1, 1):
        code, result = scheduled.execute(params,
            feed_runner=lambda _: (0, {"status": "NOT_DUE"}), analysis_runner=analyze)
        assert code == 0 and opener.calls == expected_calls
        assert result["analysis_mode"] == "BUDGETED_AI_AND_CACHE"
        assert result["providers"][0]["analysis"]["paid_execution_requested"]
    assert result["analysis_cache_hits"] == 1


@pytest.mark.parametrize("operation", ["--dry-run", "--replay-only"])
def test_paid_setting_never_charges_dry_run_or_recovery(tmp_path, operation, monkeypatch):
    source, _, _, _, work = setup(tmp_path)
    params = opts(source, work, operation=operation)
    params.allow_paid_ai = True
    monkeypatch.setattr(feed_analysis, "run_budgeted_openai_analysis", no_call)
    code, result = scheduled.execute(params)
    assert code == 0 and result["ai_call_count"] == 0


def test_paid_schedule_requires_model_configuration_before_poll(tmp_path):
    source, _, _, _, work = setup(tmp_path)
    params = opts(source, work)
    params.allow_paid_ai = True
    code, result = scheduled.execute(params, feed_runner=no_call, analysis_runner=no_call)
    assert code == 4 and result["status"] == "AI_MODEL_CONFIGURATION_REQUIRED"
