"""1_5 immutable private evidence receipts; no EraLeader writes or provider HTTP.

Stores small operator-authorized metadata or explicitly licensed source bytes
under a per-revision content digest, with SHA-bound receipts. Local SHA is
an integrity check, NOT independent publication-time notarization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile
import shutil

from .provider_registry import Provider, _safe_https_endpoint, permits_document_storage
from .source_share import SourceShareError, _json, _when, _must_sha, _must_id

SCHEMA = "newscatalyst.immutable_evidence.v1"
MAX_META = 16384
MAX_LICENSED_BYTES = 128 * 1024
READ_LIMIT = MAX_LICENSED_BYTES + 8192


@dataclass(frozen=True)
class ArchivedEvidence:
    version_id: str
    provider_id: str
    document_id: str
    payload_sha256: str
    receipt_sha256: str
    first_verified_at: datetime
    archived_at: datetime
    content_scope: str
    supersedes_version_id: str | None


def _private_root(root: Path) -> Path:
    root = Path(root)
    if (not root.is_absolute() or ".." in root.parts or root.is_symlink()
            or any(part.lower() == "eraleader" for part in root.parts)):
        raise SourceShareError("absolute non-symlink archive path required")
    try:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
    except OSError as exc:
        raise SourceShareError("private evidence directory unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or root.resolve(strict=True) != root):
        # A symlink in an ancestor can secretly redirect an archive root.
        raise SourceShareError("archive root must be owner-only")
    return root


def _read_once(path: Path, limit: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077
                    or not 0 < info.st_size <= limit):
                raise SourceShareError("unsafe or unbounded archive evidence")
            content = os.read(fd, limit + 1)
            if len(content) != info.st_size:
                raise SourceShareError("archive evidence changed during read")
            return content
        finally:
            os.close(fd)
    except OSError as exc:
        raise SourceShareError("archive evidence not available") from exc


def _write_new(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())


def _key(provider_id: str, document_id: str) -> str:
    return sha256((provider_id + "\0" + document_id).encode()).hexdigest()


def _read_version(root: Path, version: str) -> tuple[bytes, dict]:
    version = _must_sha(version, "version id")
    folder = root / version
    try:
        info = folder.lstat()
    except OSError as exc:
        raise SourceShareError("missing referenced archive version") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or folder.is_symlink()):
        raise SourceShareError("unsafe archived version")
    payload = _read_once(folder / "payload.bin", MAX_LICENSED_BYTES)
    manifest_raw = _read_once(folder / "receipt.json", 8192)
    manifest = _json(manifest_raw, "archived receipt")
    expected_fields = {
        "schema", "version_id", "document_key", "provider_id",
        "document_id", "payload_sha256", "receipt_sha256",
        "first_verified_at", "archived_at", "scope", "supersedes_version_id",
    }
    if set(manifest) != expected_fields or manifest["schema"] != SCHEMA:
        raise SourceShareError("invalid archived receipt")
    if manifest["version_id"] != version or (
        manifest["payload_sha256"] != sha256(payload).hexdigest()
    ):
        raise SourceShareError("archived payload SHA mismatch")
    receipt_sha = manifest["receipt_sha256"]
    unsealed = {k: v for k, v in manifest.items() if k != "receipt_sha256"}
    encoded = json.dumps(unsealed, sort_keys=True, separators=(",", ":")).encode()
    if sha256(encoded).hexdigest() != receipt_sha:
        raise SourceShareError("archived receipt SHA mismatch")
    return payload, manifest


def archive_evidence(
    root: Path, provider: Provider, document_id: str, payload: bytes,
    *, scope: str = "METADATA_ONLY",
    first_verified_at: datetime | None = None,
    supersedes_version_id: str | None = None,
    now: datetime | None = None,
) -> ArchivedEvidence:
    """Write once; correction links to a verified prior immutable version.

    Caller must supply a ProviderRegistry-approved provider. This function
    cannot independently authenticate whether the legal permission is genuine.
    """
    archived_at = _when((now or datetime.now(timezone.utc)).isoformat(), "archived_at")
    at = _when((first_verified_at or archived_at).isoformat(), "first_verified_at")
    if at > archived_at or archived_at > datetime.now(timezone.utc):
        raise SourceShareError("archive cannot claim a future receipt time")
    if not isinstance(provider, Provider) or not provider.enabled_at(at):
        raise SourceShareError("source storage permission missing or expired")
    _must_id(provider.provider_id, "provider id")
    _must_id(document_id, "document id")
    if scope not in ("METADATA_ONLY", "LICENSED_SOURCE_BYTES"):
        raise SourceShareError("unknown storage scope")
    if scope == "LICENSED_SOURCE_BYTES" and not permits_document_storage(provider):
        raise SourceShareError("licensed original storage not permitted")
    limit = MAX_META if scope == "METADATA_ONLY" else MAX_LICENSED_BYTES
    if not isinstance(payload, bytes) or not 0 < len(payload) <= limit:
        raise SourceShareError("bounded source payload required")
    if scope == "METADATA_ONLY":
        data = _json(payload, "metadata payload")
        if set(data) != {"event_id", "source_id", "source_url", "headline"}:
            raise SourceShareError("metadata fields must exclude raw article body")
        if (data["source_id"] != provider.provider_id
                or not isinstance(data["headline"], str)
                or not 0 < len(data["headline"]) <= 256):
            raise SourceShareError("metadata does not match approved provider")
        _must_sha(data["event_id"], "metadata event_id")
        _safe_https_endpoint(data["source_url"])
    root = _private_root(root)
    key = _key(provider.provider_id, document_id)
    digest = sha256(payload).hexdigest()
    version = sha256((key + "\0" + digest).encode()).hexdigest()
    if supersedes_version_id is not None:
        _, old = _read_version(root, supersedes_version_id)
        if old["document_key"] != key or old["version_id"] == version:
            raise SourceShareError("correction reference differs from document/version")
        if _when(old["first_verified_at"], "old verified_at") > at:
            raise SourceShareError("correction predates earlier version")
    final = root / version
    if final.exists() or final.is_symlink():
        old_payload, old = _read_version(root, version)
        if old_payload != payload or old["document_key"] != key or (
            old["supersedes_version_id"] != supersedes_version_id
        ):
            raise SourceShareError("immutable version collision or changed correction chain")
        return ArchivedEvidence(
            version, provider.provider_id, document_id, digest,
            old["receipt_sha256"], _when(old["first_verified_at"], "first verified"),
            _when(old["archived_at"], "archived at"),
            old["scope"], old["supersedes_version_id"],
        )
    base = {
        "schema": SCHEMA, "version_id": version, "document_key": key,
        "provider_id": provider.provider_id, "document_id": document_id,
        "payload_sha256": digest, "first_verified_at": at.isoformat(),
        "archived_at": archived_at.isoformat(),
        "scope": scope, "supersedes_version_id": supersedes_version_id,
    }
    body = json.dumps(base, sort_keys=True, separators=(",", ":")).encode()
    receipt_sha = sha256(body).hexdigest()
    receipt = json.dumps(
        {**base, "receipt_sha256": receipt_sha},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    staging = Path(tempfile.mkdtemp(prefix=".pending_", dir=root))
    try:
        staging.chmod(0o700)
        _write_new(staging / "payload.bin", payload)
        _write_new(staging / "receipt.json", receipt)
        fd = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        if final.exists():
            raise SourceShareError("concurrent version collision; retry after validation")
        os.rename(staging, final)
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise SourceShareError("archive commit failed") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return ArchivedEvidence(
        version, provider.provider_id, document_id, digest,
        receipt_sha, at, archived_at, scope, supersedes_version_id,
    )


def read_archived_evidence(
    root: Path, version_id: str, *, decision_at: datetime | None = None,
    now: datetime | None = None,
) -> tuple[bytes, ArchivedEvidence]:
    root = _private_root(root)
    payload, manifest = _read_version(root, version_id)
    first = _when(manifest["first_verified_at"], "first verified")
    archived = _when(manifest["archived_at"], "archived at")
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    decision = _when((decision_at or current).isoformat(), "decision_at")
    if archived < first or decision < archived or decision > current:
        raise SourceShareError("archive not available for historical decision")
    return payload, ArchivedEvidence(
        manifest["version_id"], manifest["provider_id"], manifest["document_id"],
        manifest["payload_sha256"], manifest["receipt_sha256"], first,
        archived, manifest["scope"], manifest["supersedes_version_id"],
    )
