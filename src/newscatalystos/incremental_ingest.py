"""1_3 incremental feed coordination; sqlite state is NewsCatalystOS-only.

Per-provider requests and seen event digests are committed atomically. Raw XML,
article text, URLs, titles and provider secrets NEVER enter this state DB.
Failed fetches preserve the last-success watermark and previously seen events.
An external scheduler may invoke this once; no background daemon is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3
import stat

from .feed_transport import FeedTransportError, fetch_authorized_once
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _must_sha, _when

BACKOFF_BASE_SECONDS = 60
MAX_BACKOFF_SECONDS = 3600
PERMANENT_BLOCK = "PERMISSION_BLOCKED"


@dataclass(frozen=True)
class IncrementalResult:
    provider_id: str
    status: str
    new_count: int
    duplicate_count: int
    watermark: datetime
    usable_from: datetime
    certified_raw_event_count: int = 0


def _check_state_path(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.suffix != ".sqlite3":
        raise SourceShareError("absolute private sqlite3 state path required")
    if any(part.lower() == "eraleader" for part in path.parts):
        raise SourceShareError("EraLeader database paths are read-only and forbidden")
    parent = path.parent
    try:
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = parent.lstat()
    except OSError as exc:
        raise SourceShareError("private state directory unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or parent.is_symlink()):
        raise SourceShareError("private state directory must be owner-only")
    if path.exists() or path.is_symlink():
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or stat.S_IMODE(st.st_mode) & 0o077):
            raise SourceShareError("unsafe state database file")
    else:
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
            os.close(fd)
        except FileExistsError:
            raise SourceShareError("concurrent private state initialization")
        except OSError as exc:
            raise SourceShareError("private state unavailable") from exc
    return path


def _connect(path: Path) -> sqlite3.Connection:
    safe = _check_state_path(path)
    conn = sqlite3.connect(str(safe), timeout=4, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout=4000")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS source_state(
            provider_id TEXT PRIMARY KEY,
            last_attempt_at TEXT,
            last_success_at TEXT,
            next_allowed_at TEXT,
            failure_count INTEGER NOT NULL DEFAULT 0,
            blocked INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS requests(
            provider_id TEXT NOT NULL, requested_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_request_window
                       ON requests(provider_id, requested_at)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS seen_events(
            provider_id TEXT NOT NULL, event_id TEXT NOT NULL,
            first_verified_at TEXT NOT NULL,
            PRIMARY KEY(provider_id,event_id)
        )""")
        return conn
    except Exception:
        conn.close()
        raise


def _reserve(conn: sqlite3.Connection, name: str, at: datetime, hourly_limit: int) -> None:
    """Atomic lock/reserve BEFORE opening network; no simultaneous double fetch."""
    timestamp = at.isoformat()
    cutoff = (at - timedelta(hours=1)).isoformat()
    interval = max(1, 3600 // hourly_limit)
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT OR IGNORE INTO source_state(provider_id) VALUES(?)", (name,)
        )
        record = conn.execute(
            "SELECT last_attempt_at,next_allowed_at,blocked FROM source_state "
            "WHERE provider_id=?", (name,)
        ).fetchone()
        last, next_allowed, blocked = record
        if blocked:
            raise SourceShareError("provider blocked until operator reviews permission")
        if last is not None and _when(last, "last attempt") > at:
            raise SourceShareError("system clock moved before last request")
        count = conn.execute(
            "SELECT COUNT(*) FROM requests WHERE provider_id=? AND requested_at>=?",
            (name, cutoff),
        ).fetchone()[0]
        if count >= hourly_limit:
            raise SourceShareError("provider hourly request budget exhausted")
        if next_allowed is not None and _when(next_allowed, "next allowed") > at:
            raise SourceShareError("provider rate or backoff window not elapsed")
        conn.execute("DELETE FROM requests WHERE requested_at<?", (cutoff,))
        conn.execute("INSERT INTO requests VALUES(?,?)", (name, timestamp))
        conn.execute(
            "UPDATE source_state SET last_attempt_at=?,next_allowed_at=? "
            "WHERE provider_id=?",
            (timestamp, (at + timedelta(seconds=interval)).isoformat(), name),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _failure(conn: sqlite3.Connection, name: str, at: datetime,
             exc: SourceShareError) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT failure_count, next_allowed_at FROM source_state WHERE provider_id=?",
            (name,),
        ).fetchone()
        count, existing_next = row
        count += 1
        code = exc.http_code if isinstance(exc, FeedTransportError) else None
        blocked = bool(code in (401, 403))
        delay = min(MAX_BACKOFF_SECONDS, BACKOFF_BASE_SECONDS * (2 ** min(count-1, 6)))
        if not isinstance(exc, FeedTransportError) or not exc.retryable:
            delay = MAX_BACKOFF_SECONDS
        requested_next = at + timedelta(seconds=delay)
        if existing_next is not None:
            requested_next = max(requested_next, _when(existing_next, "next allowed"))
        conn.execute(
            "UPDATE source_state SET failure_count=?, blocked=?, next_allowed_at=? "
            "WHERE provider_id=?",
            (count, int(blocked), requested_next.isoformat(), name),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def incremental_poll(
    registry: ProviderRegistry, provider_id: str, database_path: Path,
    *, now: datetime | None = None, fetcher=None,
) -> IncrementalResult:
    """One safe attempt: reserve -> one bounded feed read -> atomic watermark.

    Each successful event is deduplicated by stable provider_id/event_id;
    timestamp values from RSS titles or reported publication are never used as
    the collection watermark. A disabled/expired source is rejected first.
    """
    observed = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved provider registry required")
    provider = registry.active(provider_id, at=observed)
    conn = _connect(database_path)
    try:
        _reserve(conn, provider_id, observed, provider.hourly_limit)
        reader = fetch_authorized_once if fetcher is None else fetcher
        try:
            rows = reader(registry, provider_id, at=now)
            if not rows:
                raise SourceShareError("empty feed: no new success watermark")
        except SourceShareError as exc:
            _failure(conn, provider_id, observed, exc)
            raise
        verified = _when((now or datetime.now(timezone.utc)).isoformat(), "verified_at")
        if verified < observed:
            raise SourceShareError("system clock moved during feed collection")
        conn.execute("BEGIN IMMEDIATE")
        try:
            fresh, duplicates = 0, 0
            for row in rows:
                if (row.provider_id != provider_id or row.reported_published_at is not None
                        or row.first_seen_at > verified):
                    raise SourceShareError("feed metadata violates first-observation PIT")
                changed = conn.execute(
                    "INSERT OR IGNORE INTO seen_events VALUES(?,?,?)",
                    (provider_id, _must_sha(row.event_id, "event digest"), verified.isoformat()),
                ).rowcount
                fresh += changed
                duplicates += 1 - changed
            conn.execute(
                "UPDATE source_state SET last_success_at=?,failure_count=0 "
                "WHERE provider_id=?",
                (verified.isoformat(), provider_id),
            )
            conn.execute("COMMIT")
        except SourceShareError as exc:
            conn.execute("ROLLBACK")
            _failure(conn, provider_id, observed, exc)
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return IncrementalResult(
            provider_id=provider_id,
            status="SUCCESS_NEW" if fresh else "SUCCESS_UNCHANGED",
            new_count=fresh, duplicate_count=duplicates,
            watermark=verified, usable_from=verified,
        )
    finally:
        conn.close()


def state_snapshot(database_path: Path, provider_id: str) -> dict:
    """Diagnostics: aggregate counts, never article metadata or secrets."""
    conn = _connect(database_path)
    try:
        row = conn.execute(
            "SELECT last_attempt_at,last_success_at,next_allowed_at,"
            "failure_count,blocked FROM source_state WHERE provider_id=?",
            (provider_id,),
        ).fetchone()
        if row is None:
            return {"status": "UNSEEN", "seen_count": 0}
        count = conn.execute(
            "SELECT COUNT(*) FROM seen_events WHERE provider_id=?", (provider_id,)
        ).fetchone()[0]
        return {"status": PERMANENT_BLOCK if row[4] else "ACTIVE",
                "last_attempt_at": row[0], "last_success_at": row[1],
                "next_allowed_at": row[2], "failure_count": row[3],
                "seen_count": count}
    finally:
        conn.close()


def resume_after_rights_review(
    registry: ProviderRegistry, provider_id: str, database_path: Path, *,
    now: datetime | None = None,
) -> bool:
    """Explicitly unblock a 401/403 source only after a NEW rights review.

    Not automatic: simply waiting or restarting never erases a permission
    block. The operator must have renewed approved source metadata AFTER the
    last blocked network attempt.
    """
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    provider = registry.active(provider_id, at=instant)
    conn = _connect(database_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            state = conn.execute(
                "SELECT last_attempt_at,blocked FROM source_state WHERE provider_id=?",
                (provider_id,),
            ).fetchone()
            if state is None or not state[1]:
                conn.execute("COMMIT")
                return False
            if provider.reviewed_at is None or (
                state[0] is not None and provider.reviewed_at <= _when(state[0], "last attempt")
            ):
                raise SourceShareError("fresh operator rights review required to unblock")
            conn.execute(
                "UPDATE source_state SET blocked=0,failure_count=0,next_allowed_at=? "
                "WHERE provider_id=?",
                (instant.isoformat(), provider_id),
            )
            conn.execute("COMMIT")
            return True
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
