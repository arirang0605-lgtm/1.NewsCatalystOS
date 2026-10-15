"""6_5 operator health diagnoses the actual scheduled pipeline; no HTTP."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import plistlib
import subprocess

import pytest

from scripts.check_triage_agent_health import check, evaluate_health
from scripts.create_triage_agent import LABEL, V1_PROVIDERS, launchd_spec

NOW = datetime(2026, 10, 14, 10, 50, tzinfo=timezone.utc)
PRINT = "gui/501/com.newscatalystos.triage = {\n\truns = 3\n\tlast exit code = 0\n\trun interval = 3600 seconds\n}"
PASS_LOG = {
    "status": "SCHEDULED_TICK_COMPLETE_OR_NOT_DUE",
    "providers_failed": 0,
    "providers": [
        {"provider_id": name, "status": "FEED_METADATA_TRIAGE_READY"}
        for name in V1_PROVIDERS
    ],
    "ai_call_count": 0, "official_era_api_request_count": 0,
    "stored_article_body_count": 0,
}


def fixture(tmp_path):
    project = tmp_path / "NewsCatalystOS"
    script = project / "scripts" / "run_scheduled_triage.py"
    script.parent.mkdir(parents=True)
    script.write_text("# local stub for spec generation\n")
    base = tmp_path / "private"
    spec = launchd_spec(
        Path("/usr/local/bin/python3"), project,
        base / "providers" / "authorized_sources.json",
        base / "state" / "incremental_feeds.sqlite3",
        base / "state" / "triage_exact_index.sqlite3",
        base / "inbox" / "feed_triage", base / "logs",
    )
    return project, base, plistlib.dumps(spec)


def inspect(tmp_path, **changes):
    project, base, data = fixture(tmp_path)
    opts = {
        "plist_data": data, "project": project, "base": base,
        "launch_text": PRINT, "duplicate_active": False,
        "last_log": PASS_LOG, "log_mtime": NOW.timestamp() - 3200,
        "now": NOW,
    }
    opts.update(changes)
    return evaluate_health(**opts)


def test_recent_valid_agent_observed_without_exchange_certification(tmp_path):
    r = inspect(tmp_path)
    assert r["status"] == "AGENT_HEALTHY_OBSERVED"
    assert r["reasons"] == [] and r["runs"] == 3
    assert r["last_exit_code"] == 0
    assert r["log_age_seconds"] == 3200
    assert "five_trading_day_operation_certified" not in r


@pytest.mark.parametrize("variant,reason", [
    ("stale", "NO_RECENT_TICK"),
    ("clock_future", "LOG_MTIME_IN_FUTURE"),
    ("duplicate", "DUPLICATE_SCHEDULER_ACTIVE"),
    ("failed", "LAST_RUN_FAILED"),
    ("wrong_period", "AGENT_NOT_RUNNING_AS_EXPECTED"),
    ("not_run", "AGENT_NOT_RUNNING_AS_EXPECTED"),
])
def test_operational_faults_fail_closed(tmp_path, variant, reason):
    project, base, data = fixture(tmp_path)
    opts = {
        "plist_data": data, "project": project, "base": base,
        "launch_text": PRINT, "duplicate_active": False,
        "last_log": PASS_LOG, "log_mtime": NOW.timestamp() - 3600,
        "now": NOW,
    }
    if variant == "stale":
        opts["log_mtime"] = NOW.timestamp() - 8101
    elif variant == "clock_future":
        opts["log_mtime"] = NOW.timestamp() + 901
    elif variant == "duplicate":
        opts["duplicate_active"] = True
    elif variant == "failed":
        opts["launch_text"] = PRINT.replace("last exit code = 0", "last exit code = 4")
    elif variant == "wrong_period":
        opts["launch_text"] = PRINT.replace("3600 seconds", "7200 seconds")
    else:
        opts["launch_text"] = PRINT.replace("runs = 3", "runs = 0")
    output = evaluate_health(**opts)
    assert output["status"] == "AGENT_UNHEALTHY"
    assert reason in output["reasons"]


@pytest.mark.parametrize("change", [
    {"providers_failed": 1},
    {"status": "SCHEDULED_TICK_FAILED"},
    {"official_era_api_request_count": 1},
    {"ai_call_count": 1},
    {"providers": []},
    {"providers": [dict(PASS_LOG["providers"][0]), {"provider_id": "sec-submissions", "status": "NOT_DUE"}]},
    {"providers": "invalid"},
])
def test_unverified_tick_never_passes(tmp_path, change):
    broken = {**PASS_LOG, **change}
    report = inspect(tmp_path, last_log=broken)
    assert "LAST_TICK_UNVERIFIED" in report["reasons"]


def test_changed_or_malformed_plist_is_rejected(tmp_path):
    project, base, data = fixture(tmp_path)
    spec = plistlib.loads(data)
    spec["RunAtLoad"] = True
    report = evaluate_health(
        plist_data=plistlib.dumps(spec), project=project, base=base,
        launch_text=PRINT, duplicate_active=False, last_log=PASS_LOG,
        log_mtime=NOW.timestamp(), now=NOW,
    )
    assert "AGENT_CONFIG_MISMATCH" in report["reasons"]
    other = inspect(tmp_path / "separate", plist_data=b"not a plist")
    assert "AGENT_CONFIG_INVALID" in other["reasons"]


def test_readonly_cli_check_follows_private_installed_agent_and_log(tmp_path):
    project, base, data = fixture(tmp_path)
    home = tmp_path / "home"
    launch_dir = home / "Library" / "LaunchAgents"
    launch_dir.mkdir(parents=True)
    plist = launch_dir / (LABEL + ".plist")
    plist.write_bytes(data)
    plist.chmod(0o600)
    logs = base / "logs"
    logs.mkdir(parents=True)
    stdout = logs / "triage_stdout.log"
    stdout.write_text(json.dumps(PASS_LOG) + "\n")
    stdout.chmod(0o600)
    stderr = logs / "triage_stderr.log"
    stderr.write_text("")
    stderr.chmod(0o600)
    seen = []
    def runner(args, **_kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(
            args, 1 if "incremental" in args[-1] else 0,
            stdout=PRINT if LABEL in args[-1] else "",
        )
    at = datetime.now(timezone.utc)
    code, result = check(
        project=project, base=base, home=home, now=at, runner=runner,
    )
    assert code == 0 and result["status"] == "AGENT_HEALTHY_OBSERVED"
    assert len(seen) == 2
    assert all(command[0] == "launchctl" and command[1] == "print"
               for command in seen)
    assert not (base / "state").exists()
    assert stdout.read_text() == json.dumps(PASS_LOG) + "\n"

    stderr.unlink()
    stderr.symlink_to(stdout)
    code, result = check(
        project=project, base=base, home=home, now=at, runner=runner,
    )
    assert code == 4 and result["status"] == "AGENT_EVIDENCE_UNAVAILABLE"


def test_cli_missing_service_is_unhealthy_not_healthy(tmp_path):
    project, base, data = fixture(tmp_path)
    home = tmp_path / "home"
    launch_dir = home / "Library" / "LaunchAgents"
    launch_dir.mkdir(parents=True)
    (launch_dir / (LABEL + ".plist")).write_bytes(data)
    (launch_dir / (LABEL + ".plist")).chmod(0o600)
    logs = base / "logs"
    logs.mkdir(parents=True)
    for name in ("triage_stdout.log", "triage_stderr.log"):
        path = logs / name
        path.write_text(json.dumps(PASS_LOG) + "\n" if name.startswith("triage_stdout") else "")
        path.chmod(0o600)
    def missing(args, **_):
        return subprocess.CompletedProcess(args, 4, stdout="")
    code, result = check(
        project=project, base=base, home=home,
        now=datetime.now(timezone.utc), runner=missing,
    )
    assert code == 4 and result["reasons"] == ["AGENT_NOT_LOADED"]


def test_recovered_checkpoint_and_completed_analysis_is_a_healthy_tick(tmp_path):
    recovered = {**PASS_LOG, "analysis_providers_completed": 2,
                 "analysis_providers_failed": 0,
                 "providers": [{"provider_id": name,
                     "status": "RECOVERED_FROM_DURABLE_CHECKPOINT"}
                     for name in V1_PROVIDERS]}
    assert inspect(tmp_path, last_log=recovered)["status"] == "AGENT_HEALTHY_OBSERVED"


def test_configured_paid_scheduler_is_not_reported_as_health_failure(tmp_path):
    project, base, data = fixture(tmp_path)
    spec = plistlib.loads(data)
    spec['ProgramArguments'].extend([
        '--analysis-model-config', str(base / 'models/gemini.json'), '--allow-paid-ai'])
    log = dict(PASS_LOG, ai_call_count=None, analysis_mode='BUDGETED_AI_AND_CACHE',
               analysis_providers_failed=0)
    result = evaluate_health(plist_data=plistlib.dumps(spec), project=project, base=base,
        launch_text=PRINT, duplicate_active=False, last_log=log,
        log_mtime=NOW.timestamp(), now=NOW)
    assert result['status'] == 'AGENT_HEALTHY_OBSERVED'
    log['analysis_providers_failed'] = 1
    result = evaluate_health(plist_data=plistlib.dumps(spec), project=project, base=base,
        launch_text=PRINT, duplicate_active=False, last_log=log,
        log_mtime=NOW.timestamp(), now=NOW)
    assert 'LAST_TICK_UNVERIFIED' in result['reasons']
