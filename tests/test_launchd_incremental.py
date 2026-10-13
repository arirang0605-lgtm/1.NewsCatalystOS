"""Launchd schedule generation never starts an unauthorized background process."""
from pathlib import Path
import plistlib

import pytest

from scripts.launchd_incremental import (
    LABEL, launchd_spec, save_private_template,
)
from newscatalystos.source_share import SourceShareError


def sample(tmp_path, interval=900):
    return launchd_spec(
        Path("/usr/bin/python3"),
        Path("/opt/newscatalyst/scripts/run_incremental_feed.py"),
        tmp_path / "authorized_sources.json",
        tmp_path / "incremental.sqlite3",
        Path("/opt/newscatalyst/src"),
        interval=interval,
    )


def test_launchd_interval_is_bounded_and_not_autorun(tmp_path):
    data = sample(tmp_path)
    assert data["StartInterval"] == 900
    assert data["RunAtLoad"] is False
    assert data["KeepAlive"] is False
    assert data["Label"] == LABEL
    assert "--all-approved" in data["ProgramArguments"]
    assert "authorized_sources.json" in " ".join(data["ProgramArguments"])
    assert "PASSWORD" not in str(data)


@pytest.mark.parametrize("interval", [0, 60, 299, 3601, "900", True])
def test_invalid_schedule_refused(tmp_path, interval):
    with pytest.raises(SourceShareError, match="interval"):
        sample(tmp_path, interval=interval)


def test_private_plist_written_once_and_parsed(tmp_path):
    path = tmp_path / "launchd" / "feed.plist"
    saved = sample(tmp_path)
    save_private_template(saved, path)
    assert plistlib.loads(path.read_bytes()) == saved
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(SourceShareError, match="exists"):
        save_private_template(saved, path)


def test_world_readable_parent_is_rejected(tmp_path):
    path = tmp_path / "shared" / "feed.plist"
    path.parent.mkdir()
    path.parent.chmod(0o755)
    with pytest.raises(SourceShareError, match="owner-only"):
        save_private_template(sample(tmp_path), path)
