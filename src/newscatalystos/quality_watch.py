"""1_6 source freshness and failure gaps, with private pending queue.

Inspects only local NewsCatalystOS provider state. Missing, expired, blocked
or stale sources are NOT labeled complete. Recovery marks past alerts resolved.
No provider calls, EraLeader reads/writes, news bodies or secret logging.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from .incremental_ingest import _connect, state_snapshot
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _when


@dataclass(frozen=True)
class SourceQuality:
    provider_id: str
    status: str
    last_success_at: datetime | None
    gap_seconds: int | None
    queue_status: str
    incident_id: str | None


def _status(record: dict, at: datetime, *, freshness_seconds: int) -> tuple[str, datetime | None, int | None]:
    if record.get("status") == "UNSEEN":
        return "NOT_COLLECTED", None, None
    success = record.get("last_success_at")
    verified = _when(success, "last_success_at") if success is not None else None
    if verified is not None and verified > at:
        raise SourceShareError("source freshness timestamp is in future")
    if record.get("status") == "PERMISSION_BLOCKED":
        return "AUTH_BLOCKED", verified, (int((at - verified).total_seconds())
                                          if verified else None)
    if record.get("failure_count", 0) > 0:
        return "RETRY_PENDING", verified, (int((at - verified).total_seconds())
                                           if verified else None)
    if verified is None:
        return "NOT_COLLECTED", None, None
    gap = int((at - verified).total_seconds())
    return ("STALE" if gap > freshness_seconds else "HEALTHY"), verified, gap


def check_sources(
    registry: ProviderRegistry, database_path: Path,
    *, now: datetime | None = None, freshness_seconds: int = 14400,
) -> tuple[SourceQuality, ...]:
    """Atomically record unresolved provider gaps while leaving source rows intact."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if (not isinstance(registry, ProviderRegistry)
            or type(freshness_seconds) is not int
            or not 300 <= freshness_seconds <= 7 * 86400):
        raise SourceShareError("invalid source freshness policy")
    conn = _connect(database_path)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS quality_incidents(
            incident_id TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            problem TEXT NOT NULL,
            first_reported_at TEXT NOT NULL,
            resolved_at TEXT
        )""")
        results = []
        for provider in registry.providers:
            # No network can be initiated here. Keep discontinued sources out
            # of production readiness counts; their permission status is shown.
            record = state_snapshot(database_path, provider.provider_id)
            if not provider.enabled_at(at):
                status, verified, gap = "NOT_AUTHORIZED", None, None
            else:
                status, verified, gap = _status(record, at, freshness_seconds=freshness_seconds)
            conn.execute("BEGIN IMMEDIATE")
            try:
                open_cases = conn.execute(
                    "SELECT incident_id, problem, first_reported_at FROM quality_incidents "
                    "WHERE provider_id=? AND resolved_at IS NULL",
                    (provider.provider_id,),
                ).fetchall()
                unresolved = status not in ("HEALTHY", "NOT_AUTHORIZED")
                incident = None
                if not unresolved:
                    if open_cases:
                        conn.execute(
                            "UPDATE quality_incidents SET resolved_at=? "
                            "WHERE provider_id=? AND resolved_at IS NULL",
                            (at.isoformat(), provider.provider_id),
                        )
                else:
                    active = next((entry for entry in open_cases if entry[1] == status), None)
                    if active:
                        incident = active[0]
                    else:
                        # New problem supersedes the prior problem, but older
                        # incident rows survive for audit and future validation.
                        conn.execute(
                            "UPDATE quality_incidents SET resolved_at=? "
                            "WHERE provider_id=? AND resolved_at IS NULL",
                            (at.isoformat(), provider.provider_id),
                        )
                        incident = hashlib.sha256(
                            (provider.provider_id + "\0" + status + "\0" + at.isoformat()).encode()
                        ).hexdigest()
                        conn.execute(
                            "INSERT INTO quality_incidents VALUES(?,?,?,?,NULL)",
                            (incident, provider.provider_id, status, at.isoformat()),
                        )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            results.append(SourceQuality(
                provider_id=provider.provider_id,
                status=status,
                last_success_at=verified,
                gap_seconds=gap,
                queue_status="PENDING" if unresolved else ("NOT_APPLICABLE" if status == "NOT_AUTHORIZED" else "CLEAR"),
                incident_id=incident,
            ))
        return tuple(results)
    finally:
        conn.close()


def unresolved_count(database_path: Path) -> int:
    conn = _connect(database_path)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE name='quality_incidents'"
        ).fetchone()
        if exists is None:
            return 0
        return conn.execute(
            "SELECT COUNT(*) FROM quality_incidents WHERE resolved_at IS NULL"
        ).fetchone()[0]
    finally:
        conn.close()
