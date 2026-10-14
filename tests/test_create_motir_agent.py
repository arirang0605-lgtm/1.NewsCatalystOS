"""Dedicated official ministry RSS agent never edits the prior user jobs."""
import plistlib
import stat
from pathlib import Path

import pytest
from scripts.create_motir_agent import (
    LABEL, INTERVAL, motir_launchd_spec, install_new_motir_launchd,
)
from newscatalystos.source_share import SourceShareError


def assets(tmp_path):
    project=tmp_path/"1.NewsCatalystOS"
    target=project/"scripts"/"run_motir_policy_once.py"
    target.parent.mkdir(parents=True)
    target.write_text("noop")
    base=tmp_path/"private"
    spec=motir_launchd_spec(Path("/usr/local/bin/python3"),project,base)
    return spec,base


def test_motir_agent_dedicated_to_exact_runner_and_source_not_trading(tmp_path):
    spec,base=assets(tmp_path)
    assert spec["Label"]==LABEL
    assert spec["StartInterval"]==3600
    assert spec["RunAtLoad"] is False
    assert spec["ProgramArguments"][1].endswith("/scripts/run_motir_policy_once.py")
    assert "run_scheduled_triage" not in str(spec)
    assert "OPENAI_API_KEY" not in str(spec)
    assert spec["EnvironmentVariables"]["PYTHONDONTWRITEBYTECODE"]=="1"


def test_new_plist_keeps_existing_rss_service_in_place(tmp_path):
    spec,base=assets(tmp_path)
    target=tmp_path/"LaunchAgents"/(LABEL+".plist")
    assert install_new_motir_launchd(spec,target,base/"logs")==target
    assert stat.S_IMODE(target.stat().st_mode)==0o600
    assert plistlib.loads(target.read_bytes())["StartInterval"]==INTERVAL
    with pytest.raises(FileExistsError):
        install_new_motir_launchd(spec,target,base/"logs")
    assert not (target.parent/"com.newscatalystos.triage.plist").exists()


def test_wrong_label_or_world_readable_log_not_installed(tmp_path):
    spec,base=assets(tmp_path)
    target=tmp_path/"LaunchAgents"/(LABEL+".plist")
    invalid=dict(spec,Label="com.newscatalystos.triage")
    with pytest.raises(SourceShareError):
        install_new_motir_launchd(invalid,target,base/"logs")
    logs=base/"logs"
    logs.mkdir(parents=True)
    logs.chmod(0o700)
    log=logs/"motir_stdout.log"
    log.write_text("not-private")
    log.chmod(0o644)
    with pytest.raises(SourceShareError):
        install_new_motir_launchd(spec,target,logs)
    assert not target.exists()
