"""3_6 immutable first detection and revision history with PIT checks.

No claim about exact web publication when unavailable, no backwards-cast of
current detection records. Historical detection recall on supplied labels is
a metric, not a certified score on an independently reviewed gold set.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3

from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _must_sha, _when

CATEGORIES=frozenset({
    "NEW_FACT_CANDIDATE","BARRIER_REMOVED_CANDIDATE",
    "STRENGTHENED_CANDIDATE","WEAKENED_CANDIDATE",
    "INVALIDATED_CANDIDATE","CORRECTION_PENDING_VERIFICATION",
})


@dataclass(frozen=True)
class DetectionInput:
    event_sha256: str
    source_sha256: str
    claim_value_sha256: str
    category: str
    first_source_seen_at: datetime
    supersedes_version_sha256: str | None = None


@dataclass(frozen=True)
class DetectionRecord:
    version_sha256: str
    event_sha256: str
    source_sha256: str
    claim_value_sha256: str
    category: str
    first_source_seen_at: datetime
    recorded_at: datetime
    available_at: datetime
    supersedes_version_sha256: str | None
    published_at: None = None


@dataclass(frozen=True)
class DetectionRecall:
    measured_recall: float | None
    missed_important_ids: tuple[str, ...]
    target_met_on_supplied_labels: bool
    release_gate_verified: bool = False


def _conn(db: Path) -> sqlite3.Connection:
    path=_check_state_path(db)
    con=sqlite3.connect(str(path),isolation_level=None,timeout=4)
    try:
        con.execute("PRAGMA synchronous=FULL")
        con.execute("""CREATE TABLE IF NOT EXISTS detection_versions(
           version_sha TEXT PRIMARY KEY,
           event_sha TEXT NOT NULL,
           source_sha TEXT NOT NULL,
           value_sha TEXT NOT NULL,
           category TEXT NOT NULL,
           first_seen_at TEXT NOT NULL,
           recorded_at TEXT NOT NULL,
           available_at TEXT NOT NULL,
           supersedes_sha TEXT
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS detection_asof ON detection_versions(recorded_at)")
        return con
    except Exception:
        con.close()
        raise


def record_detection(
    db: Path, observation: DetectionInput, *, now: datetime | None = None,
) -> DetectionRecord:
    at=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not isinstance(observation,DetectionInput) or observation.category not in CATEGORIES:
        raise SourceShareError("structured detection candidate required")
    eid=_must_sha(observation.event_sha256,"event SHA")
    source=_must_sha(observation.source_sha256,"source SHA")
    value=_must_sha(observation.claim_value_sha256,"value SHA")
    first=_when(observation.first_source_seen_at.isoformat(),"first source seen")
    if first>at:
        raise SourceShareError("future detection source")
    parent=observation.supersedes_version_sha256
    if parent is not None:
        _must_sha(parent,"previous detection version")
    version=sha256((eid+"\0"+source+"\0"+value+"\0"+observation.category).encode()).hexdigest()
    conn=_conn(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing=conn.execute(
                "SELECT version_sha,event_sha,source_sha,value_sha,category,"
                "first_seen_at,recorded_at,available_at,supersedes_sha "
                "FROM detection_versions WHERE version_sha=?",(version,)
            ).fetchone()
            if existing:
                if existing[-1]!=parent:
                    raise SourceShareError("immutable detection version collision")
                data=existing
            else:
                if parent is not None:
                    earlier=conn.execute(
                        "SELECT event_sha,recorded_at FROM detection_versions WHERE version_sha=?",
                        (parent,)
                    ).fetchone()
                    if (earlier is None or earlier[0]!=eid or
                            _when(earlier[1],"prior stored")>at or parent==version):
                        raise SourceShareError("invalid detection version lineage")
                data=(version,eid,source,value,observation.category,
                      first.isoformat(),at.isoformat(),at.isoformat(),parent)
                conn.execute(
                    "INSERT INTO detection_versions VALUES(?,?,?,?,?,?,?,?,?)",data
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return DetectionRecord(
            data[0],data[1],data[2],data[3],data[4],
            _when(data[5],"first seen"),_when(data[6],"recorded"),
            _when(data[7],"available"),data[8],
        )
    finally:
        conn.close()


def detection_history_as_of(
    db: Path, decision_at: datetime, *, now: datetime | None = None,
) -> tuple[DetectionRecord, ...]:
    decision=_when(decision_at.isoformat(),"decision_at")
    present=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if decision>present:
        raise SourceShareError("future detection query")
    conn=_conn(db)
    try:
        data=conn.execute(
            "SELECT version_sha,event_sha,source_sha,value_sha,category,"
            "first_seen_at,recorded_at,available_at,supersedes_sha "
            "FROM detection_versions WHERE recorded_at<=? AND available_at<=? "
            "ORDER BY recorded_at,version_sha",
            (decision.isoformat(),decision.isoformat())
        ).fetchall()
        return tuple(
            DetectionRecord(
                x[0],x[1],x[2],x[3],x[4],_when(x[5],"first seen"),
                _when(x[6],"recorded"),_when(x[7],"available"),x[8]
            )
            for x in data
        )
    finally:
        conn.close()


def evaluate_important_detection_recall(
    labeled_important_ids: tuple[str, ...] | list[str],
    detected_ids: tuple[str, ...] | list[str],
    *, target: float = 0.90,
) -> DetectionRecall:
    if not (0<target<=1.0):
        raise SourceShareError("invalid detection target")
    gold={_must_sha(x,"labeled important ID") for x in labeled_important_ids}
    found={_must_sha(x,"detected important ID") for x in detected_ids}
    if len(gold)!=len(labeled_important_ids):
        raise SourceShareError("duplicate labeled important IDs")
    if not gold:
        return DetectionRecall(None,(),False)
    misses=tuple(sorted(gold-found))
    recall=len(gold & found)/len(gold)
    return DetectionRecall(recall,misses,recall>=target,False)
