"""Separate non-polling gold user LaunchAgent; existing triage job untouched."""
from pathlib import Path
import os
import plistlib
import stat
import pytest

from newscatalystos.source_share import SourceShareError
from scripts.create_gold_agent import (
    LABEL, INTERVAL, gold_agent_spec, write_gold_agent,
)


def fixture(tmp_path):
    project = tmp_path / "project"
    runner = project / "scripts" / "run_gold_capture_once.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("# harmless gold runner fixture")
    base = tmp_path / "mac_private"
    logs = base / "logs"
    spec = gold_agent_spec(Path("/usr/local/bin/python3"), project, base, logs)
    return spec, base, logs


def test_agent_launches_only_existing_rss_gold_snapshot_no_scrapers(tmp_path):
    spec, base, logs = fixture(tmp_path)
    args = spec["ProgramArguments"]
    assert spec["Label"] == LABEL
    assert spec["StartInterval"] == 3600
    assert spec["RunAtLoad"] is False
    assert "run_gold_capture_once.py" in args[1]
    assert "--inbox-root" in args and "--state" in args
    assert "eraleader" not in " ".join(args).lower()
    assert "run_scheduled_triage.py" not in " ".join(args)
    assert "--provider-id" not in args
    assert "OPENAI_API_KEY" not in spec["EnvironmentVariables"]
    assert spec["Umask"] == 0o077


def test_only_private_new_agent_is_written_without_overwrite(tmp_path):
    spec, base, logs = fixture(tmp_path)
    dest = tmp_path / "LaunchAgents" / (LABEL + ".plist")
    assert write_gold_agent(spec, dest, logs) == dest
    assert plistlib.loads(dest.read_bytes())["Label"] == LABEL
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    for log in ("gold_stdout.log", "gold_stderr.log"):
        assert stat.S_IMODE((logs / log).stat().st_mode) == 0o600
    assert (tmp_path / "LaunchAgents" / "com.newscatalystos.triage.plist").exists() is False
    with pytest.raises(FileExistsError):
        write_gold_agent(spec, dest, logs)
    assert plistlib.loads(dest.read_bytes())["StartInterval"] == 3600


def test_paths_and_wrong_log_configuration_rejected(tmp_path):
    spec, base, logs = fixture(tmp_path)
    with pytest.raises(SourceShareError, match="interval"):
        gold_agent_spec(Path("/usr/bin/python3"), tmp_path/"project", base, logs, interval=30)
    with pytest.raises(SourceShareError, match="absolute"):
        gold_agent_spec(Path("python3"), tmp_path/"project", base, logs)
    spec["StandardErrorPath"] = str(tmp_path / "not-private.log")
    dest = tmp_path / "LaunchAgents" / (LABEL + ".plist")
    with pytest.raises(SourceShareError):
        write_gold_agent(spec, dest, logs)
    assert not dest.exists()


def test_log_symlink_and_world_readable_file_rejected(tmp_path):
    spec, base, logs = fixture(tmp_path)
    logs.mkdir(parents=True, mode=0o700)
    logs.chmod(0o700)
    dest = tmp_path / "LaunchAgents" / (LABEL + ".plist")
    log = logs / "gold_stdout.log"
    log.symlink_to(tmp_path / "unsafe")
    with pytest.raises(SourceShareError):
        write_gold_agent(spec, dest, logs)
    log.unlink()
    log.write_text("not a secret")
    log.chmod(0o644)
    with pytest.raises(SourceShareError):
        write_gold_agent(spec, dest, logs)
    assert not dest.exists()
