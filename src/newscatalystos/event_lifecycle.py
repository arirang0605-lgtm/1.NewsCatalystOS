"""6_1 append-only economic catalyst lifecycle, with explicit proof boundaries.

No automatic expiry. CONFIRMED requires an already authenticated anchored
publication, never a boolean from a model, news headline, or synthetic JSON.
Reactivation preserves INVALIDATED history and begins as DETECTED again.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3

from .incremental_ingest import _check_state_path
from .official_promotion import AnchoredOfficialPublication
from .source_share import SourceShareError, _must_sha, _when

STATES = frozenset({"DETECTED", "CONFIRMED", "STRENGTHENED", "WEAKENED", "INVALIDATED"})
TRANSITIONS = {
    None: frozenset({"DETECTED"}),
    "DETECTED": frozenset({"CONFIRMED", "INVALIDATED"}),
    "CONFIRMED": frozenset({"STRENGTHENED", "WEAKENED", "INVALIDATED"}),
    "STRENGTHENED": frozenset({"STRENGTHENED", "WEAKENED", "INVALIDATED"}),
    "WEAKENED": frozenset({"STRENGTHENED", "WEAKENED", "INVALIDATED"}),
    "INVALIDATED": frozenset({"DETECTED"}),
}
SCHEMA = "newscatalyst.lifecycle.v1"


@dataclass(frozen=True)
class LifecycleVersion:
    version_sha256: str
    event_sha256: str
    previous_version_sha256: str | None
    evidence_sha256: str
    previous_state: str | None
    state: str
    source_available_at: datetime
    recorded_at: datetime
    available_at: datetime
    evidence_status: str
    revision_number: int
    schema_version: str = SCHEMA


@dataclass(frozen=True)
class LifecycleState:
    event_sha256: str
    decision_at: datetime
    versions: tuple[LifecycleVersion, ...]
    current_state: str | None
    independently_certified_release: bool = False


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(_check_state_path(path)), isolation_level=None, timeout=4)
    try:
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS lifecycle_versions(
            version_sha TEXT PRIMARY KEY,
            event_sha TEXT NOT NULL,
            parent_sha TEXT,
            evidence_sha TEXT NOT NULL,
            previous_state TEXT,
            state TEXT NOT NULL,
            source_available TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            evidence_status TEXT NOT NULL,
            revision_number INTEGER NOT NULL,
            UNIQUE(event_sha, revision_number)
        )""")
        conn.execute("""CREATE INDEX IF NOT EXISTS ix_lifecycle_event
                        ON lifecycle_versions(event_sha,revision_number)""")
        return conn
    except Exception:
        conn.close()
        raise


def _decode(row: tuple) -> LifecycleVersion:
    return LifecycleVersion(
        row[0], row[1], row[2], row[3], row[4], row[5],
        _when(row[6], "source available"),
        _when(row[7], "stored at"), _when(row[7], "available at"),
        row[8], row[9],
    )


def append_lifecycle(
    db: Path, event_sha256: str, state: str,
    evidence_sha256: str, source_available_at: datetime, *,
    at: datetime | None = None,
    anchored_publication: AnchoredOfficialPublication | None = None,
) -> LifecycleVersion:
    """Transition an event once, atomically, preserving all old states.

    Event SHA can be a normalized event or grouped digest. A genuine signed
    proof can only confirm an IDENTICAL underlying event SHA (no loose ID).
    """
    current = _when((at or datetime.now(timezone.utc)).isoformat(), "at")
    event = _must_sha(event_sha256, "event id")
    evidence = _must_sha(evidence_sha256, "lifecycle evidence")
    observed = _when(source_available_at.isoformat(), "source available")
    if observed > current:
        raise SourceShareError("future lifecycle evidence cannot be used")
    if state not in STATES:
        raise SourceShareError("invalid lifecycle status")
    certification = "UNVERIFIED_SOURCE_CLAIM"
    if state == "CONFIRMED":
        if not isinstance(anchored_publication, AnchoredOfficialPublication):
            raise SourceShareError("CONFIRMED requires anchored official publication")
        source = anchored_publication.as_of(current, now=current)
        if source.event_id != event:
            raise SourceShareError("signed event ID does not match lifecycle ID")
        if anchored_publication.usable_from > observed:
            raise SourceShareError("signed proof became usable after claimed source time")
        certification = "ANCHORED_WITNESS_RELEASE_CLAIM"
    elif anchored_publication is not None:
        raise SourceShareError("signed release proof permitted only for CONFIRMED")
    conn = _connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            last = conn.execute(
                "SELECT version_sha,event_sha,parent_sha,evidence_sha,previous_state,"
                "state,source_available,recorded_at,evidence_status,revision_number "
                "FROM lifecycle_versions WHERE event_sha=? "
                "ORDER BY revision_number DESC LIMIT 1",
                (event,),
            ).fetchone()
            previous = last[5] if last else None
            if state not in TRANSITIONS[previous]:
                raise SourceShareError("illegal lifecycle transition")
            parent = last[0] if last else None
            revision = (last[9]+1) if last else 1
            version = sha256(
                (event+"\0"+(parent or "")+"\0"+evidence+"\0"+state).encode()
            ).hexdigest()
            conn.execute(
                "INSERT INTO lifecycle_versions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (version,event,parent,evidence,previous,state,observed.isoformat(),
                 current.isoformat(),certification,revision),
            )
            conn.execute("COMMIT")
            return LifecycleVersion(version,event,parent,evidence,previous,state,
                                    observed,current,current,certification,revision)
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def lifecycle_as_of(
    db: Path, event_sha256: str, decision_at: datetime,
    *, now: datetime | None = None,
) -> LifecycleState:
    event = _must_sha(event_sha256, "event SHA")
    decision = _when(decision_at.isoformat(), "decision at")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if decision > present:
        raise SourceShareError("future lifecycle history query")
    conn = _connect(db)
    try:
        data = conn.execute(
            "SELECT version_sha,event_sha,parent_sha,evidence_sha,previous_state,"
            "state,source_available,recorded_at,evidence_status,revision_number "
            "FROM lifecycle_versions WHERE event_sha=? AND recorded_at<=? "
            "ORDER BY revision_number",
            (event,decision.isoformat()),
        ).fetchall()
        versions = tuple(_decode(x) for x in data)
        return LifecycleState(event,decision,versions,
                              versions[-1].state if versions else None,
                              # A synthetic test proof's signature does not
                              # independently certify issuer authority in real life.
                              False)
    finally:
        conn.close()
