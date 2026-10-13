"""6_5 launchd config only invokes approved NewsCatalystOS RSS, not Era APIs."""
from pathlib import Path
import plistlib
import sys

import pytest

from newscatalystos.source_share import SourceShareError
from scripts.create_triage_agent import (
    LABEL, V1_PROVIDERS, launchd_spec, write_launch_agent,
)


def setup_paths(tmp_path):
    project = tmp_path / "1.NewsCatalystOS"
    scripts = project / "scripts"
    scripts.mkdir(parents=True, mode=0o700)
    (scripts / "run_scheduled_triage.py").write_text("# fake existing runner\n")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    output = tmp_path / "private-logs"
    spec = launchd_spec(
        Path(sys.executable), project,
        private / "authorized_sources.json",
        private / "poll.sqlite3", private / "dedup.sqlite3",
        private / "inbox", output,
    )
    return spec, output


def test_launchd_runs_one_scheduler_only_on_explicit_two_approved_ids(tmp_path):
    spec, log_root = setup_paths(tmp_path)
    assert spec["Label"] == LABEL
    assert spec["StartInterval"] == 3600
    assert spec["RunAtLoad"] is False
    assert spec["KeepAlive"] is False
    assert spec["Umask"] == 0o077
    assert spec["ProgramArguments"].count("--provider-id") == len(V1_PROVIDERS)
    for provider in V1_PROVIDERS:
        assert provider in spec["ProgramArguments"]
    assert "run_incremental_feed.py" not in " ".join(spec["ProgramArguments"])
    assert spec["StandardErrorPath"] == str(log_root / "triage_stderr.log")
    assert spec["StandardOutPath"] == str(log_root / "triage_stdout.log")
    assert spec["EnvironmentVariables"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert not any("api_key" in v.lower() for v in spec.values() if isinstance(v,str))


def test_private_launchagent_writes_once_and_cannot_overwrite(tmp_path):
    spec, logs = setup_paths(tmp_path)
    dest = tmp_path / "LaunchAgents" / (LABEL + ".plist")
    result = write_launch_agent(spec, dest, logs)
    assert result == dest
    assert dest.stat().st_mode & 0o077 == 0
    saved = plistlib.loads(dest.read_bytes())
    assert saved["Label"] == LABEL
    assert saved["StartInterval"] == 3600
    assert saved["Umask"] == 0o077
    for name in ("triage_stdout.log", "triage_stderr.log"):
        f = logs / name
        assert f.exists() and f.stat().st_mode & 0o077 == 0
    with pytest.raises(SourceShareError, match="overwritten"):
        write_launch_agent(spec, dest, logs)


@pytest.mark.parametrize("interval", [0, 900, 3601, True, 1.5])
def test_invalid_interval_does_not_create_launchjob(tmp_path, interval):
    spec, log_root = setup_paths(tmp_path)
    base = Path(spec["WorkingDirectory"])
    args = spec["ProgramArguments"]
    with pytest.raises(SourceShareError, match="cadence"):
        launchd_spec(
            Path(args[0]), base,
            Path(args[args.index("--registry") + 1]),
            Path(args[args.index("--state") + 1]),
            Path(args[args.index("--dedup-state") + 1]),
            Path(args[args.index("--inbox-root") + 1]),
            log_root, interval=interval,
        )


def test_era_project_and_unexpected_output_root_rejected(tmp_path):
    spec, logs = setup_paths(tmp_path)
    args = spec["ProgramArguments"]
    era = tmp_path / "eraleader"
    era.mkdir(mode=0o700)
    with pytest.raises(SourceShareError, match="non-EraLeader"):
        launchd_spec(
            Path(args[0]), era,
            tmp_path / "sources", tmp_path / "state",
            tmp_path / "dedup", tmp_path / "inbox", logs,
        )
    with pytest.raises(SourceShareError, match="label"):
        write_launch_agent(spec, tmp_path / "LaunchAgents" / "incorrect.plist", logs)


def test_log_symlink_and_world_writable_directory_are_rejected(tmp_path):
    spec, logs = setup_paths(tmp_path)
    dest = tmp_path / "LaunchAgents" / (LABEL + ".plist")
    logs.mkdir(mode=0o700)
    outside = tmp_path / "other"
    outside.write_text("something")
    (logs / "triage_stdout.log").symlink_to(outside)
    with pytest.raises(SourceShareError, match="symlink"):
        write_launch_agent(spec, dest, logs)
    (logs / "triage_stdout.log").unlink()
    dest.parent.mkdir(mode=0o777, exist_ok=True)
    dest.parent.chmod(0o777)
    with pytest.raises(SourceShareError, match="owner-controlled"):
        write_launch_agent(spec, dest, logs)
