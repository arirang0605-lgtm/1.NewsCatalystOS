"""6_2 private change-aware AI analysis cache.

A changed source revision SHA, prompt, model or metadata digest yields a new
cache key; no unmodified event may be re-analyzed simply due to feed polling.
The cache preserves only bounded normalized AI response (not article body).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

from .ai_provider import AIResult
from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.analysis_cache.v1"


@dataclass(frozen=True)
class CachedAnalysis:
    cache_key: str
    event_sha256: str
    source_version_sha256: str
    model_key_sha256: str
    result_sha256: str
    recorded_at: datetime
    available_at: datetime
    result: AIResult
    schema_version: str = SCHEMA


def _identity(event: str, source_version: str, model_identity: str,
              prompt: str, metadata_sha: str) -> str:
    return sha256("\0".join((event,source_version,model_identity,prompt,metadata_sha)).encode()).hexdigest()


def _connection(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(_check_state_path(db)),isolation_level=None,timeout=4)
    try:
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS analysis_cache(
            cache_sha TEXT PRIMARY KEY,
            event_sha TEXT NOT NULL,
            source_version_sha TEXT NOT NULL,
            model_sha TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            result_sha TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
        return conn
    except Exception:
        conn.close()
        raise


def _result_bytes(result: AIResult) -> bytes:
    if not isinstance(result,AIResult):
        raise SourceShareError("typed AI result required")
    if (len(result.summary)>1000 or len(result.claims)>12 or
            len(result.uncertainties)>12 or result.is_verified_market_fact):
        raise SourceShareError("unsafe unbounded or certified AI cache payload")
    payload = {
        "schema_version":result.schema_version,"event_sha256":result.event_sha256,
        "provider":result.provider,"model":result.model,
        "prompt_version":result.prompt_version,"content_sha256":result.content_sha256,
        "summary":result.summary,"claims":list(result.claims),
        "uncertainties":list(result.uncertainties),
        "input_tokens":result.input_tokens,"output_tokens":result.output_tokens,
        "estimated_cost_krw":result.estimated_cost_krw,
        "available_at":result.available_at.isoformat(),
        "classification":result.classification,
        "is_verified_market_fact":result.is_verified_market_fact,
    }
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    if len(raw)>16000:
        raise SourceShareError("oversized cached response")
    return raw


def _decode(blob: bytes) -> AIResult:
    from .ai_provider import AI_CLASS, SCHEMA as AI_SCHEMA
    if len(blob)>16000:
        raise SourceShareError("cache payload oversized")
    try:
        doc=json.loads(blob)
        if doc["schema_version"]!=AI_SCHEMA or doc["classification"]!=AI_CLASS:
            raise ValueError("nonstandard AI cache envelope")
        if doc["is_verified_market_fact"] is not False:
            raise ValueError("AI cannot self certify")
        obj=AIResult(
            doc["schema_version"],doc["event_sha256"],doc["provider"],
            doc["model"],doc["prompt_version"],doc["content_sha256"],
            doc["summary"],tuple(doc["claims"]),tuple(doc["uncertainties"]),
            doc["input_tokens"],doc["output_tokens"],doc["estimated_cost_krw"],
            _when(doc["available_at"],"AI result available"),
        )
        if _result_bytes(obj)!=blob:
            raise ValueError("noncanonical cached result")
        return obj
    except (ValueError,KeyError,TypeError,UnicodeDecodeError) as exc:
        raise SourceShareError("invalid cached analysis payload") from None


def cache_analysis_once(
    db: Path, result: AIResult, *,
    source_version_sha256: str,
    metadata_sha256: str,
    recorded_at: datetime | None = None,
) -> CachedAnalysis:
    at=_when((recorded_at or datetime.now(timezone.utc)).isoformat(),"recorded at")
    event=_must_sha(result.event_sha256,"event SHA")
    version=_must_sha(source_version_sha256,"source version")
    metadata=_must_sha(metadata_sha256,"metadata SHA")
    ready=_when(result.available_at.isoformat(),"AI result available")
    if ready>at:
        raise SourceShareError("cached AI result from future")
    model_key=sha256((result.provider+"\0"+result.model).encode()).hexdigest()
    key=_identity(event,version,model_key,result.prompt_version,metadata)
    serialized=_result_bytes(result)
    hash_value=sha256(serialized).hexdigest()
    con=_connection(db)
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            old=con.execute(
                "SELECT event_sha,source_version_sha,model_sha,recorded_at,"
                "result_sha,payload FROM analysis_cache WHERE cache_sha=?",(key,)
            ).fetchone()
            if old is None:
                con.execute(
                    "INSERT INTO analysis_cache VALUES(?,?,?,?,?,?,?)",
                    (key,event,version,model_key,at.isoformat(),hash_value,
                     serialized.decode("utf-8")),
                )
                saved_at=at
            else:
                if old[:3]!=(event,version,model_key) or old[4]!=hash_value or (
                    old[5].encode()!=serialized
                ):
                    raise SourceShareError("immutable AI cache conflict")
                saved_at=_when(old[3],"original AI cache time")
                if saved_at>at:
                    raise SourceShareError("future cached computation")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()
    return CachedAnalysis(key,event,version,model_key,hash_value,
                          saved_at,max(ready,saved_at),result)


def get_cached_analysis(
    db: Path, *,
    event_sha256: str, source_version_sha256: str,
    metadata_sha256: str, provider: str, model: str, prompt_version: str,
    decision_at: datetime, now: datetime | None = None,
) -> CachedAnalysis | None:
    at=_when(decision_at.isoformat(),"decision at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if at>current:
        raise SourceShareError("future cache decision")
    event=_must_sha(event_sha256,"event SHA")
    version=_must_sha(source_version_sha256,"source version")
    metadata=_must_sha(metadata_sha256,"metadata SHA")
    model_key=sha256((provider+"\0"+model).encode()).hexdigest()
    key=_identity(event,version,model_key,prompt_version,metadata)
    conn=_connection(db)
    try:
        row=conn.execute(
            "SELECT event_sha,source_version_sha,model_sha,recorded_at,"
            "result_sha,payload FROM analysis_cache WHERE cache_sha=?",(key,)
        ).fetchone()
        if row is None:
            return None
        raw=row[5].encode("utf-8")
        if sha256(raw).hexdigest()!=row[4] or row[:3]!=(event,version,model_key):
            raise SourceShareError("cached analysis SHA mismatch")
        result=_decode(raw)
        stored=_when(row[3],"recorded at")
        available=max(stored,result.available_at)
        if at<available:
            return None
        return CachedAnalysis(key,event,version,model_key,row[4],stored,
                              available,result)
    finally:
        conn.close()
