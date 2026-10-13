"""6_5 private consistent SQLite backups, verified cold restores and SHA pins.

Independent BACKUP DIRECTORY is separate from active source DB. The caller
supplies original SHA for restoration; integrity is a local comparison, not
an independent off-device disaster-recovery guarantee or 5-day operation.
No EraLeader paths/files, credentials, copyrighted articles or Git staging.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from uuid import uuid4

from .source_share import SourceShareError, _must_sha, _when

SCHEMA="newscatalyst.sqlite_backup.v1"
MAX_SOURCE_BYTES=50*1024*1024


@dataclass(frozen=True)
class BackupReceipt:
    backup_id: str
    source_name: str
    snapshot_sha256: str
    manifest_sha256: str
    created_at: datetime
    snapshot_bytes: int
    schema_version: str = SCHEMA


def _private_dir(path: Path, *, create: bool = False) -> Path:
    path=Path(path)
    if not path.is_absolute() or ".." in path.parts or path.is_symlink():
        raise SourceShareError("private absolute non-symlink folder required")
    if any(segment.lower()=="eraleader" for segment in path.parts):
        raise SourceShareError("EraLeader data cannot be backed up by NewsCatalystOS")
    if create:
        path.mkdir(mode=0o700,parents=True,exist_ok=True)
    try:
        info=path.lstat()
    except OSError as exc:
        raise SourceShareError("private directory unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or
            stat.S_IMODE(info.st_mode)&0o077):
        raise SourceShareError("private directory must be owner-only")
    return path


def _regular_owner(path: Path) -> None:
    try:
        info=path.lstat()
    except OSError as exc:
        raise SourceShareError("SQLite source unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or
            stat.S_IMODE(info.st_mode)&0o077 or
            not 0<info.st_size<=MAX_SOURCE_BYTES or path.is_symlink()):
        raise SourceShareError("source must be bounded owner-private SQLite file")


def _file_sha(path: Path) -> tuple[str,int]:
    flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or
                not 0<info.st_size<=MAX_SOURCE_BYTES or
                stat.S_IMODE(info.st_mode)&0o077):
            raise SourceShareError("untrusted backup file")
        digest=sha256()
        count=0
        while True:
            chunk=os.read(fd,65536)
            if not chunk:
                break
            digest.update(chunk)
            count+=len(chunk)
        if count!=info.st_size:
            raise SourceShareError("backup read length changed")
        return digest.hexdigest(),count
    finally:
        os.close(fd)


def _receipt_data(path: Path, manifest: dict) -> BackupReceipt:
    return BackupReceipt(
        manifest["backup_id"],manifest["source_name"],
        manifest["snapshot_sha256"],sha256(path.read_bytes()).hexdigest(),
        _when(manifest["created_at"],"backup created"),
        manifest["snapshot_bytes"],
    )


def backup_sqlite(
    source: Path, backup_root: Path, *,
    now: datetime | None = None,
) -> BackupReceipt:
    at=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    source=Path(source)
    if source.suffix!=".sqlite3" or source.name.startswith("."):
        raise SourceShareError("only NewsCatalystOS SQLite state supported")
    _private_dir(source.parent)
    _regular_owner(source)
    root=_private_dir(backup_root,create=True)
    if root.resolve()==source.parent.resolve() or root in source.parents:
        raise SourceShareError("backup must be separate from active state")
    backup_id="backup_"+uuid4().hex
    stage=Path(tempfile.mkdtemp(prefix=".backup_staging_",dir=root))
    stage.chmod(0o700)
    target=root/backup_id
    snapshot=stage/"state.sqlite3"
    manifest_file=stage/"manifest.json"
    try:
        with sqlite3.connect(f"file:{source}?mode=ro",uri=True) as active:
            with sqlite3.connect(snapshot) as backup:
                active.backup(backup)
                if backup.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                    raise SourceShareError("SQLite backup integrity failed")
        os.chmod(snapshot,0o600)
        signature,length=_file_sha(snapshot)
        if length>MAX_SOURCE_BYTES:
            raise SourceShareError("backup snapshot size limit")
        manifest={
            "schema":SCHEMA,"backup_id":backup_id,
            "source_name":source.name,
            "snapshot_sha256":signature,
            "snapshot_bytes":length,
            "created_at":at.isoformat(),
        }
        raw=(json.dumps(manifest,sort_keys=True,separators=(",",":"))+"\n").encode()
        fd=os.open(manifest_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        directory_fd=os.open(stage,os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        os.rename(stage,target)
        root_fd=os.open(root,os.O_RDONLY)
        try:
            os.fsync(root_fd)
        finally:
            os.close(root_fd)
        return BackupReceipt(
            backup_id,source.name,signature,sha256(raw).hexdigest(),at,length,
        )
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def restore_to_new_dir(
    backup_root: Path, receipt: BackupReceipt, restore_dir: Path,
    *,
    expected_manifest_sha256: str,
) -> Path:
    """Restore to a NEW directory; never overwrite an active SQLite DB."""
    if not isinstance(receipt,BackupReceipt):
        raise SourceShareError("verifiable original backup receipt required")
    pinned=_must_sha(expected_manifest_sha256,"independent expected manifest SHA")
    root=_private_dir(backup_root)
    if not receipt.backup_id.startswith("backup_") or not receipt.backup_id[7:].isalnum():
        raise SourceShareError("invalid backup ID")
    folder=_private_dir(root/receipt.backup_id)
    meta=folder/"manifest.json"
    _regular_owner(meta)
    if sha256(meta.read_bytes()).hexdigest()!=pinned or pinned!=receipt.manifest_sha256:
        raise SourceShareError("backup manifest SHA mismatch")
    try:
        document=json.loads(meta.read_text())
    except (OSError,ValueError) as exc:
        raise SourceShareError("invalid backup manifest") from exc
    if (set(document)!={"schema","backup_id","source_name","snapshot_sha256",
                        "snapshot_bytes","created_at"} or
            document["schema"]!=SCHEMA or document["backup_id"]!=receipt.backup_id or
            document["snapshot_sha256"]!=receipt.snapshot_sha256):
        raise SourceShareError("backup receipt/manifest mismatch")
    backup_file=folder/"state.sqlite3"
    _regular_owner(backup_file)
    signature,length=_file_sha(backup_file)
    if signature!=receipt.snapshot_sha256 or length!=receipt.snapshot_bytes:
        raise SourceShareError("backup snapshot SHA mismatch")
    output=Path(restore_dir)
    if (not output.is_absolute() or ".." in output.parts or output.is_symlink()
            or output.exists() or any(part.lower()=="eraleader" for part in output.parts)
            or root in output.parents):
        raise SourceShareError("restore requires a separate NEW private path")
    _private_dir(output.parent)
    output.mkdir(mode=0o700)
    try:
        dest=output/receipt.source_name
        if dest.suffix!=".sqlite3" or "/" in receipt.source_name or receipt.source_name.startswith("."):
            raise SourceShareError("invalid original DB filename")
        fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as target, open(backup_file,"rb") as original:
            shutil.copyfileobj(original,target,65536)
            target.flush();os.fsync(target.fileno())
        restored_hash,restored_length=_file_sha(dest)
        if restored_hash!=signature or restored_length!=length:
            raise SourceShareError("restored SHA mismatch")
        with sqlite3.connect(f"file:{dest}?mode=ro",uri=True) as checked:
            if checked.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise SourceShareError("restored SQLite integrity failed")
        return dest
    except Exception:
        shutil.rmtree(output)
        raise
