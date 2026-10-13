"""4_6 per-event idempotency and conservative monthly AI cost reservations.

No provider network calls or credentials. The owner-private local SQLite ledger
prevents duplicate bills for unchanged event+model+prompt+metadata; failures
leave reservations charged until reviewed, never silently bypass the cap.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import math
import sqlite3

from .ai_provider import AIModel, AIRequest, AIResult, _check_request
from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _when

SOFT_BUDGET_KRW = 30000
HARD_BUDGET_KRW = 50000


@dataclass(frozen=True)
class AIReservation:
    invocation_sha256: str
    status: str
    reserved_cost_krw: float
    monthly_total_krw: float
    soft_limit_warning: bool
    month: str


def _conn(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(_check_state_path(path)), isolation_level=None, timeout=4)
    try:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("""CREATE TABLE IF NOT EXISTS ai_invocations(
            invocation_sha TEXT PRIMARY KEY,
            event_sha TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            month TEXT NOT NULL,
            reserved_krw REAL NOT NULL,
            settled_krw REAL,
            reserved_at TEXT NOT NULL,
            settled_at TEXT
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_ai_month ON ai_invocations(month)")
        return db
    except Exception:
        db.close()
        raise


def _identity(model: AIModel, request: AIRequest) -> str:
    return sha256(
        (request.event_sha256 + "\0" + model.provider + "\0" + model.model
         + "\0" + model.prompt_version + "\0"
         + sha256(request.metadata.encode()).hexdigest()).encode()
    ).hexdigest()


def reserve_ai_call(
    db: Path, model: AIModel, request: AIRequest,
    *, now: datetime | None = None,
    hard_budget_krw: int = HARD_BUDGET_KRW,
) -> AIReservation:
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    model.validate()
    _check_request(request, at)
    if type(hard_budget_krw) is not int or not 0 < hard_budget_krw <= HARD_BUDGET_KRW:
        raise SourceShareError("invalid monthly hard budget")
    month = at.strftime("%Y-%m")
    estimated = (
        model.max_input_tokens*model.input_krw_per_million +
        model.max_output_tokens*model.output_krw_per_million
    ) / 1_000_000
    key = _identity(model,request)
    conn = _conn(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                "SELECT reserved_at,settled_at,reserved_krw,settled_krw,month "
                "FROM ai_invocations WHERE invocation_sha=?", (key,)
            ).fetchone()
            total = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(settled_krw,reserved_krw)),0) "
                "FROM ai_invocations WHERE month=?", (month,)
            ).fetchone()[0]
            if existing:
                if _when(existing[0],"AI reserved at") > at:
                    raise SourceShareError("future cache record detected")
                status = "CACHED" if existing[1] else "IN_FLIGHT_OR_UNSETTLED"
                amount = existing[3] if existing[3] is not None else existing[2]
            else:
                if total+estimated > hard_budget_krw:
                    raise SourceShareError("AI monthly hard budget exhausted")
                conn.execute(
                    "INSERT INTO ai_invocations VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (key,request.event_sha256,model.provider,model.model,
                     model.prompt_version,month,estimated,None,at.isoformat(),None)
                )
                total += estimated
                amount = estimated
                status = "RESERVED"
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return AIReservation(
            key,status,amount,total,total>=SOFT_BUDGET_KRW,month
        )
    finally:
        conn.close()


def settle_ai_call(
    db: Path, reservation: AIReservation, result: AIResult,
    *, now: datetime | None = None,
) -> None:
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if (not isinstance(reservation,AIReservation)
            or reservation.status!="RESERVED"
            or not isinstance(result,AIResult)):
        raise SourceShareError("unsettled reservation/result required")
    if (type(result.estimated_cost_krw) not in (int,float)
            or not math.isfinite(result.estimated_cost_krw)
            or result.estimated_cost_krw < 0):
        raise SourceShareError("invalid settlement cost")
    conn = _conn(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT event_sha,provider,model,prompt_version,reserved_krw,"
                "reserved_at,settled_at FROM ai_invocations WHERE invocation_sha=?",
                (reservation.invocation_sha256,)
            ).fetchone()
            if row is None or row[6] is not None or (
                row[0]!=result.event_sha256 or row[1]!=result.provider or
                row[2]!=result.model or row[3]!=result.prompt_version or
                result.estimated_cost_krw>row[4] or
                _when(row[5],"reserved at")>at
            ):
                raise SourceShareError("AI result differs from reserved request/cost")
            conn.execute(
                "UPDATE ai_invocations SET settled_krw=?,settled_at=? "
                "WHERE invocation_sha=?",
                (result.estimated_cost_krw,at.isoformat(),reservation.invocation_sha256)
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
