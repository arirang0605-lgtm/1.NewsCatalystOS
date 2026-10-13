"""6_3 append-only causal audit of evidence, states and analysis model hashes.

Stores no raw news text, credentials or secret prompts. Unverified publication
timestamps stay UNKNOWN; historical as-of views cannot include later audits.
Each new record references an earlier record for the same event.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3

from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _must_sha, _when

SCHEMA="newscatalyst.catalyst_audit.v1"
KINDS=frozenset({"SOURCE_OBSERVED","LIFECYCLE_CHANGED","AI_ANALYZED","EVIDENCE_CORRECTED"})


@dataclass(frozen=True)
class AuditInput:
    event_sha256: str
    source_evidence_sha256: str
    transition_sha256: str | None
    analysis_sha256: str | None
    model_sha256: str | None
    prompt_sha256: str | None
    kind: str
    first_seen_at: datetime
    source_available_at: datetime
    supersedes_audit_sha256: str | None = None


@dataclass(frozen=True)
class AuditVersion:
    audit_sha256: str
    event_sha256: str
    source_evidence_sha256: str
    transition_sha256: str | None
    analysis_sha256: str | None
    model_sha256: str | None
    prompt_sha256: str | None
    kind: str
    first_seen_at: datetime
    source_available_at: datetime
    recorded_at: datetime
    supersedes_audit_sha256: str | None
    externally_certified_release_at: None = None
    schema_version: str = SCHEMA


def _conn(path: Path) -> sqlite3.Connection:
    con=sqlite3.connect(str(_check_state_path(path)),timeout=4,isolation_level=None)
    try:
        con.execute("PRAGMA synchronous=FULL")
        con.execute("""CREATE TABLE IF NOT EXISTS catalyst_audit(
            audit_sha TEXT PRIMARY KEY,
            event_sha TEXT NOT NULL,
            source_sha TEXT NOT NULL,
            transition_sha TEXT,
            analysis_sha TEXT,
            model_sha TEXT,
            prompt_sha TEXT,
            kind TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            source_available_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            supersedes_sha TEXT
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS ix_catalyst_audit ON catalyst_audit(event_sha,recorded_at)")
        return con
    except Exception:
        con.close()
        raise


def _from_row(row: tuple) -> AuditVersion:
    return AuditVersion(
        row[0],row[1],row[2],row[3],row[4],row[5],row[6],row[7],
        _when(row[8],"first seen"),_when(row[9],"source available"),
        _when(row[10],"recorded at"),row[11],
    )


def append_catalyst_audit(
    db: Path, audit: AuditInput, *, now: datetime | None = None,
) -> AuditVersion:
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not isinstance(audit,AuditInput) or audit.kind not in KINDS:
        raise SourceShareError("structured catalyst audit event required")
    event=_must_sha(audit.event_sha256,"event")
    source=_must_sha(audit.source_evidence_sha256,"source evidence")
    for label,sha in (
        ("transition",audit.transition_sha256),("analysis",audit.analysis_sha256),
        ("model",audit.model_sha256),("prompt",audit.prompt_sha256),
        ("supersedes",audit.supersedes_audit_sha256),
    ):
        if sha is not None:
            _must_sha(sha,label)
    first=_when(audit.first_seen_at.isoformat(),"first seen")
    available=_when(audit.source_available_at.isoformat(),"source available")
    if not first<=available<=current:
        raise SourceShareError("future or impossible source availability")
    if audit.kind=="LIFECYCLE_CHANGED" and audit.transition_sha256 is None:
        raise SourceShareError("missing lifecycle transition SHA")
    if audit.kind=="AI_ANALYZED" and (
        audit.analysis_sha256 is None or audit.model_sha256 is None
        or audit.prompt_sha256 is None
    ):
        raise SourceShareError("missing model/prompt/analysis lineage")
    identity=sha256(("\0".join((
        event,source,audit.kind,audit.transition_sha256 or "",
        audit.analysis_sha256 or "",audit.model_sha256 or "",
        audit.prompt_sha256 or "",audit.supersedes_audit_sha256 or "",
    ))).encode()).hexdigest()
    con=_conn(db)
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            old=con.execute(
                "SELECT * FROM catalyst_audit WHERE audit_sha=?",(identity,)
            ).fetchone()
            if old is None:
                if audit.supersedes_audit_sha256 is not None:
                    parent=con.execute(
                        "SELECT event_sha,recorded_at FROM catalyst_audit WHERE audit_sha=?",
                        (audit.supersedes_audit_sha256,)
                    ).fetchone()
                    if (parent is None or parent[0]!=event or
                            _when(parent[1],"prior audit")>current or
                            audit.supersedes_audit_sha256==identity):
                        raise SourceShareError("invalid prior audit chain")
                entry=(identity,event,source,audit.transition_sha256,
                       audit.analysis_sha256,audit.model_sha256,audit.prompt_sha256,
                       audit.kind,first.isoformat(),available.isoformat(),
                       current.isoformat(),audit.supersedes_audit_sha256)
                con.execute(
                    "INSERT INTO catalyst_audit VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",entry
                )
            else:
                if old[8]!=first.isoformat() or old[9]!=available.isoformat():
                    raise SourceShareError("immutable audit evidence timestamps differ")
                if _when(old[10],"recorded at")>current:
                    raise SourceShareError("future recorded audit")
                entry=old
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return _from_row(entry)
    finally:
        con.close()


def audit_as_of(db: Path, event_sha256: str, decision_at: datetime,
                *, now: datetime | None = None) -> tuple[AuditVersion, ...]:
    event=_must_sha(event_sha256,"event SHA")
    at=_when(decision_at.isoformat(),"decision at")
    present=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if at>present:
        raise SourceShareError("future audit query")
    con=_conn(db)
    try:
        rows=con.execute(
            "SELECT * FROM catalyst_audit WHERE event_sha=? AND recorded_at<=? "
            "AND source_available_at<=? ORDER BY recorded_at,rowid",
            (event,at.isoformat(),at.isoformat())
        ).fetchall()
        return tuple(_from_row(row) for row in rows)
    finally:
        con.close()
