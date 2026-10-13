"""6_5 isolated SQLite restore workflow and independent-device guard.

Unit tests simulate a distinct device only to verify the function's success
path. Real Mac external-SSD restore is separately validated by the CLI.
"""
from pathlib import Path
import sqlite3

import pytest

from newscatalystos import physical_recovery
from newscatalystos.source_share import SourceShareError


def fixture(tmp_path: Path, source_name: str = "incremental_feeds.sqlite3"):
    state = tmp_path / "live-state"
    state.mkdir(mode=0o700, parents=True)
    source = state / source_name
    tables = physical_recovery.ALLOWED.get(source_name, {"unrecognized"})
    with sqlite3.connect(source) as conn:
        for table in sorted(tables):
            conn.execute(f"CREATE TABLE {table}(id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute(f"INSERT INTO {table} VALUES(1,'test')")
        conn.commit()
    source.chmod(0o600)
    external_parent = tmp_path / "external-simulation"
    external_parent.mkdir(mode=0o700)
    backup_root = external_parent / "snapshots"
    restore_parent = tmp_path / "restore-checks"
    return source, state, backup_root, restore_parent


@pytest.mark.parametrize("name", sorted(physical_recovery.ALLOWED))
def test_safe_isolated_restore_after_device_boundary_verified(
    tmp_path, monkeypatch, name,
):
    source, state, backup, restore = fixture(tmp_path, name)
    original = source.read_bytes()
    # Simulated device difference here; a separate real SSD is checked by CLI.
    monkeypatch.setattr(physical_recovery, "_different_disk",
                        lambda active, backup_parent: True)
    result = physical_recovery.verify_physical_recovery(
        source, backup, restore, state_root=state,
    )
    assert result.source_and_backup_on_different_devices
    assert result.restored_to_separate_directory
    assert result.restored_sqlite_integrity
    assert result.snapshot_bytes > 0
    assert len(result.snapshot_sha256) == len(result.backup_manifest_sha256) == 64
    restored_files = list(restore.glob("backup_*/*.sqlite3"))
    assert len(restored_files) == 1
    assert restored_files[0].parent != source.parent
    assert source.read_bytes() == original
    with sqlite3.connect(restored_files[0]) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        for table in physical_recovery.ALLOWED[name]:
            assert conn.execute(f"SELECT value FROM {table}").fetchone()[0] == "test"


def test_same_device_is_rejected_before_any_snapshot(tmp_path):
    source, state, backup, restore = fixture(tmp_path)
    assert not physical_recovery._different_disk(source, backup.parent)
    with pytest.raises(SourceShareError, match="physically separate"):
        physical_recovery.verify_physical_recovery(
            source, backup, restore, state_root=state,
        )
    assert not backup.exists()


def test_arbitrary_source_name_and_cross_project_paths_rejected(tmp_path):
    source, state, backup, restore = fixture(tmp_path, "personal.sqlite3")
    with pytest.raises(SourceShareError, match="only isolated"):
        physical_recovery.verify_physical_recovery(
            source, backup, restore, state_root=state,
        )
    assert not backup.exists()
    valid, state, backup, restore = fixture(tmp_path / "valid")
    with pytest.raises(SourceShareError, match="only isolated"):
        physical_recovery.verify_physical_recovery(
            valid, tmp_path / "eraleader" / "copy",
            restore, state_root=state,
        )


def test_corrupt_restored_schema_is_not_verified(tmp_path, monkeypatch):
    source, state, backup, restore = fixture(tmp_path)
    with sqlite3.connect(source) as conn:
        conn.execute("DROP TABLE requests")
        conn.commit()
    monkeypatch.setattr(physical_recovery, "_different_disk",
                        lambda *_: True)
    with pytest.raises(SourceShareError, match="schema incomplete"):
        physical_recovery.verify_physical_recovery(
            source, backup, restore, state_root=state,
        )


def test_symlink_and_world_readable_backup_parent_rejected(tmp_path, monkeypatch):
    source, state, backup, restore = fixture(tmp_path)
    monkeypatch.setattr(physical_recovery, "_different_disk",
                        lambda *_: True)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    backup.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SourceShareError, match="non-symlink"):
        physical_recovery.verify_physical_recovery(
            source, backup, restore, state_root=state,
        )
    backup.unlink()
    backup.parent.chmod(0o755)
    with pytest.raises(SourceShareError, match="owner-only"):
        physical_recovery.verify_physical_recovery(
            source, backup, restore, state_root=state,
        )


def test_restore_wont_overwrite_existing_source_or_destination(tmp_path, monkeypatch):
    source, state, backup, restore = fixture(tmp_path)
    monkeypatch.setattr(physical_recovery, "_different_disk",
                        lambda *_: True)
    initial = physical_recovery.verify_physical_recovery(
        source, backup, restore, state_root=state,
    )
    assert initial.snapshot_bytes == len(source.read_bytes())
    assert source.exists()
    assert len(list(backup.glob("backup_*/state.sqlite3"))) == 1
    assert len(list(restore.glob("backup_*/*.sqlite3"))) == 1
