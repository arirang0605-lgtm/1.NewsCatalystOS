"""2_2 exact novelty index with immutable per-version SHA and no article text.

Scope source/provider identity: do not collapse apparently independent reports
into one official fact. A changed text digest for the same source document is
a NEW VERSION, never silently discarded. Only NEW/REVISED items may consume AI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import sqlite3
from pathlib import Path

from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _must_sha, _when
from .text_normalization import NormalizedText

SCHEMA = "newscatalyst.exact_dedup.v1"


@dataclass(frozen=True)
class DedupDecision:
    status: str
    document_key_sha256: str
    raw_title_sha256: str
    first_processed_at: datetime
    ai_eligible: bool
    canonical_record_sha256: str


def register_exact(
    db: Path, item: NormalizedText, source_document_id: str,
    *, now: datetime | None = None,
) -> DedupDecision:
    """Idempotent across restarts. A reissued headline is a new version.

    Similar but NOT exact cross-source stories remain separate for the
    provenance-aware 2_3/2_5 event grouping stage.
    """
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not isinstance(item, NormalizedText):
        raise SourceShareError("normalized metadata required")
    if item.available_at > at or item.observed_at > at:
        raise SourceShareError("dedup decision precedes metadata arrival")
    _must_sha(item.event_id, "event ID")
    _must_sha(item.raw_title_sha256, "title SHA")
    if not isinstance(source_document_id, str) or not 0 < len(source_document_id) <= 512:
        raise SourceShareError("invalid source document ID")
    provider = item.source_id
    key = sha256((provider + "\0" + source_document_id).encode()).hexdigest()
    url_key = sha256((provider + "\0" + item.canonical_url).encode()).hexdigest()
    version = sha256((key + "\0" + item.raw_title_sha256).encode()).hexdigest()
    safe = _check_state_path(db)
    connection = sqlite3.connect(str(safe), timeout=4, isolation_level=None)
    try:
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("""CREATE TABLE IF NOT EXISTS document_versions(
            record_digest TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            document_key TEXT NOT NULL,
            url_key TEXT NOT NULL,
            title_digest TEXT NOT NULL,
            first_processed_at TEXT NOT NULL
        )""")
        connection.execute("""CREATE INDEX IF NOT EXISTS doc_versions
                           ON document_versions(provider_id, document_key)""")
        connection.execute("""CREATE INDEX IF NOT EXISTS url_versions
                           ON document_versions(provider_id, url_key, title_digest)""")
        connection.execute("BEGIN IMMEDIATE")
        try:
            exact = connection.execute(
                "SELECT record_digest, first_processed_at FROM document_versions "
                "WHERE record_digest=?", (version,)
            ).fetchone()
            alias = connection.execute(
                "SELECT record_digest, first_processed_at FROM document_versions "
                "WHERE provider_id=? AND url_key=? AND title_digest=? "
                "ORDER BY first_processed_at LIMIT 1",
                (provider, url_key, item.raw_title_sha256),
            ).fetchone()
            previous = connection.execute(
                "SELECT COUNT(*) FROM document_versions "
                "WHERE provider_id=? AND document_key=?", (provider, key),
            ).fetchone()[0]
            if exact is not None:
                outcome, match = "DUPLICATE", exact
            elif alias is not None:
                outcome, match = "DUPLICATE", alias
            else:
                outcome = "REVISED" if previous else "NEW"
                connection.execute(
                    "INSERT INTO document_versions VALUES(?,?,?,?,?,?)",
                    (version, provider, key, url_key,
                     item.raw_title_sha256, at.isoformat()),
                )
                match = (version, at.isoformat())
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        observed_at = _when(match[1], "first processed")
        if observed_at > at:
            raise SourceShareError("stored novelty decision is in future")
        return DedupDecision(
            status=outcome, document_key_sha256=key,
            raw_title_sha256=item.raw_title_sha256,
            first_processed_at=observed_at,
            ai_eligible=outcome in ("NEW", "REVISED"),
            canonical_record_sha256=match[0],
        )
    finally:
        connection.close()
