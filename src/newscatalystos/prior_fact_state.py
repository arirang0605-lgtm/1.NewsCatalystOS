"""3_1 PIT-safe lookup of previously recorded economic claim state.

Only source/event/claim digests and explicit reviewed subject keys are stored;
unverified claims remain unverified, and current ingestion never backfills
an earlier decision. No EraLeader DB/API access or news full-text storage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import sqlite3

from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _when, _must_sha

STATUS_VALUES = frozenset({"UNVERIFIED_CLAIM", "OFFICIAL_CHANNEL_OBSERVED",
                           "FACT_REFUTED", "CORRECTION_UNVERIFIED"})
ID = re.compile(r"[A-Za-z0-9_.:-]{2,100}\Z")


@dataclass(frozen=True)
class FactInput:
    reviewed_subject_id: str
    fact_key: str
    source_event_sha256: str
    value_sha256: str
    available_at: datetime
    evidence_status: str = "UNVERIFIED_CLAIM"
    supersedes_fact_sha256: str | None = None


@dataclass(frozen=True)
class FactVersion:
    fact_sha256: str
    reviewed_subject_id: str
    fact_key: str
    source_event_sha256: str
    value_sha256: str
    available_at: datetime
    recorded_at: datetime
    evidence_status: str
    supersedes_fact_sha256: str | None


@dataclass(frozen=True)
class PriorState:
    reviewed_subject_id: str
    decision_at: datetime
    facts: tuple[FactVersion, ...]
    status: str = "PRIOR_OBSERVED_CLAIMS_NOT_CERTIFIED_FACTS"

    def latest_by_key(self) -> tuple[FactVersion, ...]:
        latest: dict[str, FactVersion] = {}
        for item in self.facts:
            latest[item.fact_key] = item
        return tuple(latest[key] for key in sorted(latest))


def _connect(db: Path) -> sqlite3.Connection:
    path = _check_state_path(db)
    conn=sqlite3.connect(str(path),timeout=4,isolation_level=None)
    try:
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS fact_versions(
            fact_sha TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL, fact_key TEXT NOT NULL,
            source_sha TEXT NOT NULL, value_sha TEXT NOT NULL,
            available_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
            evidence_status TEXT NOT NULL, supersedes_fact_sha TEXT
        )""")
        conn.execute("""CREATE INDEX IF NOT EXISTS ix_fact_history
                       ON fact_versions(subject_id,fact_key,recorded_at)""")
        return conn
    except Exception:
        conn.close()
        raise


def record_prior_fact(
    db: Path, item: FactInput, *, now: datetime | None = None,
) -> FactVersion:
    moment=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not isinstance(item,FactInput):
        raise SourceShareError("typed fact input required")
    if not isinstance(item.reviewed_subject_id,str) or not ID.fullmatch(item.reviewed_subject_id):
        raise SourceShareError("explicit reviewed subject required")
    if not isinstance(item.fact_key,str) or not ID.fullmatch(item.fact_key):
        raise SourceShareError("invalid fact key")
    if item.evidence_status not in STATUS_VALUES:
        raise SourceShareError("invalid observed claim status")
    event_id=_must_sha(item.source_event_sha256,"source event SHA")
    value_id=_must_sha(item.value_sha256,"fact value SHA")
    source_at=_when(item.available_at.isoformat(),"source available_at")
    if source_at>moment:
        raise SourceShareError("future fact before arrival")
    if item.supersedes_fact_sha256 is not None:
        _must_sha(item.supersedes_fact_sha256,"supersedes fact SHA")
    digest=sha256((item.reviewed_subject_id+"\0"+item.fact_key+"\0"
                   +event_id+"\0"+value_id).encode()).hexdigest()
    conn=_connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            known=conn.execute(
                "SELECT subject_id,fact_key,available_at,recorded_at,evidence_status,"
                "supersedes_fact_sha FROM fact_versions WHERE fact_sha=?",(digest,)
            ).fetchone()
            if known is not None:
                if known[4]!=item.evidence_status or known[5]!=item.supersedes_fact_sha256:
                    raise SourceShareError("immutable fact identity collision")
                available=_when(known[2],"stored availability")
                recorded=_when(known[3],"stored recorded_at")
                if recorded>moment:
                    raise SourceShareError("historical fact recorded after decision")
            else:
                if item.supersedes_fact_sha256:
                    earlier=conn.execute(
                        "SELECT subject_id,fact_key,recorded_at FROM fact_versions "
                        "WHERE fact_sha=?",(item.supersedes_fact_sha256,)
                    ).fetchone()
                    if (earlier is None or earlier[0]!=item.reviewed_subject_id or
                            earlier[1]!=item.fact_key or
                            _when(earlier[2],"prior recorded_at")>moment or
                            item.supersedes_fact_sha256==digest):
                        raise SourceShareError("invalid prior fact correction chain")
                available=max(source_at,moment)
                recorded=moment
                conn.execute(
                    "INSERT INTO fact_versions VALUES(?,?,?,?,?,?,?,?,?)",
                    (digest,item.reviewed_subject_id,item.fact_key,event_id,value_id,
                     available.isoformat(),recorded.isoformat(),item.evidence_status,
                     item.supersedes_fact_sha256)
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return FactVersion(
            digest,item.reviewed_subject_id,item.fact_key,event_id,value_id,
            available,recorded,item.evidence_status,item.supersedes_fact_sha256,
        )
    finally:
        conn.close()


def prior_state_as_of(
    db: Path, subject_id: str, decision_at: datetime,
    *, now: datetime | None = None,
) -> PriorState:
    if not isinstance(subject_id,str) or not ID.fullmatch(subject_id):
        raise SourceShareError("reviewed subject required")
    decision=_when(decision_at.isoformat(),"decision_at")
    present=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if decision>present:
        raise SourceShareError("future historical decision")
    conn=_connect(db)
    try:
        rows=conn.execute(
            "SELECT fact_sha,subject_id,fact_key,source_sha,value_sha,"
            "available_at,recorded_at,evidence_status,supersedes_fact_sha "
            "FROM fact_versions WHERE subject_id=? AND available_at<=? "
            "AND recorded_at<=? ORDER BY recorded_at,fact_sha",
            (subject_id,decision.isoformat(),decision.isoformat())
        ).fetchall()
        return PriorState(subject_id,decision,tuple(
            FactVersion(row[0],row[1],row[2],row[3],row[4],
                        _when(row[5],"available_at"),_when(row[6],"recorded_at"),
                        row[7],row[8])
            for row in rows
        ))
    finally:
        conn.close()
