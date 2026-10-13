"""6_5 private SQLite WAL-safe snapshot SHA/restore, without EraLeader access."""
from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest

from newscatalystos.backup_recovery import backup_sqlite, restore_to_new_dir
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def fixture(tmp_path):
    state=tmp_path/"private_state"
    state.mkdir(mode=0o700)
    source=state/"incremental.sqlite3"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY, digest TEXT NOT NULL)")
        db.execute("INSERT INTO evidence VALUES(1,?)",("b"*64,))
        db.commit()
    source.chmod(0o600)
    backups=tmp_path/"private_backups"
    restored=tmp_path/"recovery"/"isolated-restore"
    restored.parent.mkdir(mode=0o700)
    return source,backups,restored


def test_atomic_snapshot_restore_sha_and_source_unmodified(tmp_path):
    source,backups,destination=fixture(tmp_path)
    before=source.read_bytes()
    receipt=backup_sqlite(source,backups,now=NOW)
    assert receipt.snapshot_bytes>0
    assert (backups/receipt.backup_id/"manifest.json").stat().st_mode&0o777==0o600
    recovered=restore_to_new_dir(
        backups,receipt,destination,
        expected_manifest_sha256=receipt.manifest_sha256,
    )
    assert source.read_bytes()==before
    with sqlite3.connect(recovered) as conn:
        assert conn.execute("SELECT digest FROM evidence").fetchone()[0]=="b"*64
    assert recovered.stat().st_mode&0o777==0o600
    with pytest.raises(SourceShareError,match="NEW"):
        restore_to_new_dir(backups,receipt,destination,
                           expected_manifest_sha256=receipt.manifest_sha256)


def test_backup_replays_consistent_wal_state(tmp_path):
    source,backups,destination=fixture(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("INSERT INTO evidence VALUES(2,?)",("c"*64,))
        db.commit()
        receipt=backup_sqlite(source,backups,now=NOW)
    recovered=restore_to_new_dir(
        backups,receipt,destination,
        expected_manifest_sha256=receipt.manifest_sha256,
    )
    with sqlite3.connect(recovered) as conn:
        assert conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]==2


def test_restore_requires_expected_manifest_pin(tmp_path):
    source,backups,destination=fixture(tmp_path)
    receipt=backup_sqlite(source,backups,now=NOW)
    with pytest.raises(SourceShareError,match="manifest SHA"):
        restore_to_new_dir(backups,receipt,destination,
                           expected_manifest_sha256="e"*64)
    assert not destination.exists()


def test_backup_corruption_causes_sha_failure_and_no_restore(tmp_path):
    source,backups,destination=fixture(tmp_path)
    receipt=backup_sqlite(source,backups,now=NOW)
    snap=backups/receipt.backup_id/"state.sqlite3"
    with open(snap,"ab") as fh:
        fh.write(b"CORRUPT")
    with pytest.raises(SourceShareError,match="snapshot SHA"):
        restore_to_new_dir(backups,receipt,destination,
                           expected_manifest_sha256=receipt.manifest_sha256)
    assert not destination.exists()


def test_unsafe_state_path_and_world_readable_database_denied(tmp_path):
    source,backups,destination=fixture(tmp_path)
    source.chmod(0o644)
    with pytest.raises(SourceShareError,match="owner-private"):
        backup_sqlite(source,backups,now=NOW)
    source.chmod(0o600)
    alias=tmp_path/"alias.sqlite3"
    alias.symlink_to(source)
    with pytest.raises(SourceShareError,match="owner-private"):
        backup_sqlite(alias,backups,now=NOW)


def test_backup_directory_cannot_equal_active_state(tmp_path):
    source,backups,destination=fixture(tmp_path)
    with pytest.raises(SourceShareError,match="separate"):
        backup_sqlite(source,source.parent,now=NOW)


def test_recovery_is_not_an_era_writing_interface(tmp_path):
    source,backups,destination=fixture(tmp_path)
    forbidden=tmp_path/"eraleader"/"private_backups"
    with pytest.raises(SourceShareError,match="EraLeader"):
        backup_sqlite(source,forbidden,now=NOW)
