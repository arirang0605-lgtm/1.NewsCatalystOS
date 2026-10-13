"""Persistent Mac-side SHA pins for later T5DATA restore, without self-pin."""
from datetime import timedelta
import json
import sqlite3

import pytest

from newscatalystos import physical_recovery, physical_recovery_pin
from newscatalystos.source_share import SourceShareError
from test_physical_recovery import fixture


def pin_fixture(tmp_path, monkeypatch):
    source, state, backup, restore = fixture(tmp_path)
    # Only simulates two distinct OS devices in unit tests. Actual independent
    # Mac/T5DATA physical device identity is verified by a separate live run.
    monkeypatch.setattr(physical_recovery, "_different_disk", lambda *_: True)
    monkeypatch.setattr(physical_recovery_pin, "_different_disk", lambda *_: True)
    checked = physical_recovery.verify_physical_recovery(
        source, backup, restore, state_root=state,
    )
    pin_root = tmp_path / "independent-pins"
    record = physical_recovery_pin.record_recovery_pin(
        checked, backup, pin_root,
    )
    return source, backup, restore, checked, pin_root, record


def test_private_pin_reused_for_later_isolated_restoration(tmp_path, monkeypatch):
    source, backup, restore, checked, pin_root, saved = pin_fixture(tmp_path, monkeypatch)
    assert saved.pin_path.name.startswith("backup_")
    assert saved.pin_path.stat().st_mode & 0o077 == 0
    assert saved.receipt.snapshot_sha256 == checked.snapshot_sha256
    assert saved.receipt.manifest_sha256 == checked.backup_manifest_sha256
    original_bytes = source.read_bytes()
    reopened = physical_recovery_pin.read_recovery_pin(
        saved.pin_path, pin_root, backup,
    )
    assert reopened == saved
    later = physical_recovery_pin.verify_recovery_from_pin(
        saved.pin_path, pin_root, backup, restore,
    )
    assert source.read_bytes() == original_bytes
    assert later.parent.name.startswith("pin_verify_")
    assert later.exists()
    with sqlite3.connect(later) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT value FROM seen_events").fetchone()[0] == "test"


def test_corrupted_or_missing_pin_cannot_reapprove_backup(tmp_path, monkeypatch):
    _, backup, restore, _, pin_root, saved = pin_fixture(tmp_path, monkeypatch)
    saved.pin_path.write_bytes(saved.pin_path.read_bytes() + b"altered")
    with pytest.raises(SourceShareError, match="invalid JSON"):
        physical_recovery_pin.verify_recovery_from_pin(
            saved.pin_path, pin_root, backup, restore,
        )
    saved.pin_path.unlink()
    with pytest.raises(SourceShareError):
        physical_recovery_pin.read_recovery_pin(
            saved.pin_path, pin_root, backup,
        )


def test_tampered_independent_pin_fields_fail_closed(tmp_path, monkeypatch):
    _, backup, restore, _, pin_root, saved = pin_fixture(tmp_path, monkeypatch)
    body = json.loads(saved.pin_path.read_bytes())
    body["source_name"] = "eraleader.sqlite3"
    saved.pin_path.write_text(json.dumps(body))
    with pytest.raises(SourceShareError, match="invalid cross-device"):
        physical_recovery_pin.verify_recovery_from_pin(
            saved.pin_path, pin_root, backup, restore,
        )


def test_tampered_backup_snapshot_fails_against_saved_mac_pin(tmp_path, monkeypatch):
    _, backup, restore, checked, pin_root, saved = pin_fixture(tmp_path, monkeypatch)
    snapshot = backup / checked.backup_id / "state.sqlite3"
    with open(snapshot, "ab") as fh:
        fh.write(b"corrupted")
    with pytest.raises(SourceShareError, match="snapshot SHA"):
        physical_recovery_pin.verify_recovery_from_pin(
            saved.pin_path, pin_root, backup, restore,
        )


def test_pin_root_same_as_backup_device_is_rejected(tmp_path, monkeypatch):
    source, state, backup, restore = fixture(tmp_path)
    monkeypatch.setattr(physical_recovery, "_different_disk", lambda *_: True)
    checked = physical_recovery.verify_physical_recovery(
        source, backup, restore, state_root=state,
    )
    with pytest.raises(SourceShareError, match="other device"):
        physical_recovery_pin.record_recovery_pin(
            checked, backup, tmp_path / "same_disk_pin",
        )


def test_pin_time_cannot_predate_backup(tmp_path, monkeypatch):
    _, backup, _, checked, pin_root, _ = pin_fixture(tmp_path, monkeypatch)
    with pytest.raises(SourceShareError, match="predate"):
        physical_recovery_pin.record_recovery_pin(
            checked, backup, pin_root / "second_pin",
            now=checked.backup_created_at - timedelta(seconds=1),
        )


def test_wrong_backup_directory_does_not_match_trusted_pin(tmp_path, monkeypatch):
    _, backup, restore, _, pin_root, saved = pin_fixture(tmp_path, monkeypatch)
    other = tmp_path / "other-independent-device"
    other.mkdir(mode=0o700)
    with pytest.raises(SourceShareError, match="invalid cross-device"):
        physical_recovery_pin.read_recovery_pin(
            saved.pin_path, pin_root, other,
        )
