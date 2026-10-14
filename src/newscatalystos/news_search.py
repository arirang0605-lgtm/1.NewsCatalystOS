"""Offline, owner-private title search over SHA-acknowledged RSS triage outputs.

Search ONLY already permitted 1_3/2_1/2_4/3_5 metadata; no source polling,
article fetch, AI call, issuer inference, DART/SEC/KRX collection, or Era writes.
The SQLite FTS5 cache is derived/rebuildable, not an independent PIT notary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import sqlite3

from .claim_filter import classify_claim
from .evidence_archive import _private_root
from .feed_recovery import (
    _ack_is_valid, check_committed_ingest, read_retry_checkpoint,
)
from .feed_triage import SCHEMA as TRIAGE_SCHEMA, _matched_terms, SOURCE_ROLES
from .incremental_ingest import _check_state_path
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _json, _read_regular, _must_sha, _when
from .text_normalization import normalize_feed_metadata

SCHEMA = "newscatalyst.news_title_search.v1"
MAX_RECEIPTS = 5000
MAX_RESULTS = 100
SHA_NAME = re.compile(r"^[0-9a-f]{64}\.json$")
ITEM_FIELDS = frozenset({
    "provider_id", "event_id", "document_id", "headline", "canonical_url",
    "title_sha256", "available_at", "source_kind", "claim_classification",
    "verified_fact", "reported_relevance_only", "matching_tokens",
    "source_new_identity", "exact_index_status", "needs_human_review",
    "importance_priority", "economic_fact_verified", "ai_called",
    "verified_real_benefit",
})


@dataclass(frozen=True)
class SearchSync:
    processed_receipts: int
    inserted_versions: int
    unique_documents: int
    confirmed_sources: int
    source_checked_at: datetime


def _connection(path: Path) -> sqlite3.Connection:
    if not Path(path).is_absolute():
        raise SourceShareError("absolute private search cache path required")
    safe = _check_state_path(path)
    db = sqlite3.connect(str(safe), timeout=5, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("""CREATE TABLE IF NOT EXISTS documents(
            rowid INTEGER PRIMARY KEY,
            provider_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            title_sha256 TEXT NOT NULL,
            source_document_id TEXT NOT NULL,
            headline TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            claim_classification TEXT NOT NULL,
            source_available_at TEXT NOT NULL,
            first_indexed_at TEXT NOT NULL,
            first_triage_sha256 TEXT NOT NULL,
            keyword_candidate INTEGER NOT NULL,
            needs_review INTEGER NOT NULL,
            UNIQUE(provider_id,event_id,title_sha256)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS consumed_receipts(
            checkpoint_sha256 TEXT PRIMARY KEY,
            triage_sha256 TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            acknowledged_at TEXT NOT NULL,
            indexed_at TEXT NOT NULL
        )""")
        db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS title_fts
                      USING fts5(headline,content='documents',
                                 content_rowid='rowid',tokenize='trigram')""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS doc_fts_insert
                     AFTER INSERT ON documents BEGIN
                     INSERT INTO title_fts(rowid,headline) VALUES(new.rowid,new.headline);
                     END""")
        return db
    except Exception:
        db.close()
        raise


def _trusted_snapshot(ack: dict, root: Path, state: Path,
                      registry: ProviderRegistry, at: datetime) -> tuple[dict, str]:
    digest = _must_sha(ack.get("checkpoint_sha256"), "checkpoint digest")
    if not _ack_is_valid(root, digest, at):
        raise SourceShareError("missing or invalid acknowledgment")
    checkpoint = read_retry_checkpoint(root / ("pending_" + digest), root, digest)
    poll = checkpoint.poll
    if (ack.get("provider_id") != poll.provider_id
            or ack.get("record_count") != len(poll.observations)
            or ack.get("poll_verified_at") != poll.usable_from.isoformat()):
        raise SourceShareError("snapshot acknowledgment/poll mismatch")
    provider = registry.active(poll.provider_id, at=at)
    if provider.kind not in SOURCE_ROLES:
        raise SourceShareError("unsupported registry role for title search")
    check_committed_ingest(state, poll, now=at, read_only=True)
    folder = Path(ack["triage_folder"])
    raw = _read_regular(folder / "triage.json", 150_000)
    triage_sha = _must_sha(ack["triage_sha256"], "triage SHA")
    if sha256(raw).hexdigest() != triage_sha:
        raise SourceShareError("acknowledged search source SHA mismatch")
    doc = _json(raw, "acknowledged triage")
    reviewed = _when(doc.get("decision_at"), "triage decision")
    completed = _when(ack["confirmed_at"], "triage completion")
    if (doc.get("schema") != TRIAGE_SCHEMA
            or doc.get("status") != "FEED_METADATA_SCREENED_NOT_FACT_VERIFIED"
            or doc.get("provider_id") != poll.provider_id
            or doc.get("source_kind") != SOURCE_ROLES[provider.kind]
            or not poll.usable_from <= reviewed <= completed <= at
            or doc.get("source_body_count") != 0
            or doc.get("verified_new_economic_fact_count") != 0
            or doc.get("confirmed_supply_relationship_count") != 0
            or doc.get("ai_call_count") != 0
            or not isinstance(doc.get("items"), list)
            or len(doc["items"]) != len(poll.observations)):
        raise SourceShareError("untrusted search source status or time")
    from_source = {r.event_id: r for r in poll.observations}
    if len(from_source) != len(poll.observations):
        raise SourceShareError("duplicate checkpoint source records")
    seen = set()
    for item in doc["items"]:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            raise SourceShareError("search source fields unsupported")
        event = _must_sha(item["event_id"], "search event ID")
        if event in seen or event not in from_source:
            raise SourceShareError("search item not bound to original checkpoint")
        seen.add(event)
        source = from_source[event]
        normalized = normalize_feed_metadata(
            source, verified_at=poll.usable_from, now=at,
        )
        decision = classify_claim(
            normalized, SOURCE_ROLES[provider.kind], decision_at=reviewed,
            now=at,
        )
        tokens = list(_matched_terms(normalized.text))
        if (item["provider_id"] != poll.provider_id
                or item["document_id"] != source.document_id
                or item["headline"] != normalized.text
                or item["canonical_url"] != normalized.canonical_url
                or item["title_sha256"] != normalized.raw_title_sha256
                or item["available_at"] != poll.usable_from.isoformat()
                or item["source_kind"] != SOURCE_ROLES[provider.kind]
                or item["claim_classification"] != decision.classification
                or item["matching_tokens"] != tokens
                or item["reported_relevance_only"] != (
                    "KEYWORD_CANDIDATE" if tokens else "UNKNOWN")
                or item["needs_human_review"] is not bool(tokens and decision.eligible_for_review)
                or item["source_new_identity"] is not (
                    event in poll.newly_observed_event_ids)
                or item["verified_fact"] is not False
                or item["economic_fact_verified"] is not False
                or item["verified_real_benefit"] is not False
                or item["ai_called"] is not False):
            raise SourceShareError("search item contradicts original source observation")
    return doc, triage_sha


def read_completed_title_snapshots(
    inbox_root: Path, poll_state: Path, registry: ProviderRegistry, *,
    now: datetime | None = None,
) -> tuple[tuple[dict, dict, str], ...]:
    """Read verified metadata without creating a cache or polling a source."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved provider registry required")
    if not Path(inbox_root).exists() and not Path(inbox_root).is_symlink():
        return ()
    root = _private_root(inbox_root)
    ack_root = root / "acked"
    if not ack_root.exists() and not ack_root.is_symlink():
        return ()
    ack_root = _private_root(ack_root)
    receipts = sorted(ack_root.iterdir())
    if len(receipts) > MAX_RECEIPTS:
        raise SourceShareError("search requires bounded approved receipt batch")
    trusted = []
    approved = set(registry.approved_ids(at=at))
    for path in receipts:
        if not path.is_file() or path.is_symlink() or not SHA_NAME.fullmatch(path.name):
            raise SourceShareError("unexpected search index acknowledgment")
        ack = _json(_read_regular(path, 4096), "search receipt")
        if ack.get("checkpoint_sha256") != path.name[:-5]:
            raise SourceShareError("search receipt digest mismatch")
        if ack.get("provider_id") not in approved:
            # Revoked rights: do not expose old headlines as current search.
            continue
        document, triage_sha = _trusted_snapshot(ack, root, poll_state, registry, at)
        trusted.append((ack, document, triage_sha))
    return tuple(trusted)


def sync_completed_titles(inbox_root: Path, poll_state: Path, index_path: Path,
                          registry: ProviderRegistry, *,
                          now: datetime | None = None) -> SearchSync:
    """Transactional private FTS index of all SHA-verified, committed RSS ACKs."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    trusted = read_completed_title_snapshots(inbox_root, poll_state, registry, now=at)
    if not trusted:
        return SearchSync(0, 0, 0, 0, at)
    db = _connection(index_path)
    added = 0
    try:
        db.execute("BEGIN IMMEDIATE")
        for ack, snapshot, triage_sha in trusted:
            checkpoint = ack["checkpoint_sha256"]
            previous = db.execute(
                "SELECT triage_sha256 FROM consumed_receipts WHERE checkpoint_sha256=?",
                (checkpoint,),
            ).fetchone()
            if previous is not None:
                if previous[0] != triage_sha:
                    raise SourceShareError("already indexed receipt was modified")
                continue
            for item in snapshot["items"]:
                if item["verified_fact"] is not False:
                    raise SourceShareError("search cannot certify headline as fact")
                inserted = db.execute("""INSERT OR IGNORE INTO documents(
                    provider_id,event_id,title_sha256,source_document_id,headline,
                    canonical_url,source_kind,claim_classification,
                    source_available_at,first_indexed_at,first_triage_sha256,
                    keyword_candidate,needs_review
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    item["provider_id"],item["event_id"],item["title_sha256"],
                    item["document_id"],item["headline"],item["canonical_url"],
                    item["source_kind"],item["claim_classification"],
                    item["available_at"],at.isoformat(),triage_sha,
                    int(bool(item["matching_tokens"])),
                    int(item["needs_human_review"]),
                )).rowcount
                added += inserted
            db.execute("""INSERT INTO consumed_receipts VALUES(?,?,?,?,?)""", (
                checkpoint,triage_sha,ack["provider_id"],
                ack["confirmed_at"],at.isoformat(),
            ))
        total = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    finally:
        db.close()
    return SearchSync(len(trusted), added, total,
                      len({r[0]["provider_id"] for r in trusted}), at)


def search_titles(index_path: Path, phrase: str, *,
                  registry: ProviderRegistry,
                  source_id: str | None = None, semiconductor_only: bool = False,
                  limit: int = 20,
                  now: datetime | None = None) -> tuple[dict, ...]:
    """Literal title substring search. All results are explicitly UNVERIFIED."""
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if (not isinstance(phrase, str) or not 2 <= len(phrase.strip()) <= 80
            or any(ord(ch) < 32 for ch in phrase)
            or type(limit) is not int or not 1 <= limit <= MAX_RESULTS
            or type(semiconductor_only) is not bool
            or (source_id is not None and
                (not isinstance(source_id,str) or len(source_id)>128))):
        raise SourceShareError("invalid title search/filter")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("search requires approved provider registry")
    approved = tuple(sorted(registry.approved_ids(at=current)))
    if source_id is not None and source_id not in approved:
        raise SourceShareError("search source currently unapproved")
    if not approved:
        return ()
    key = phrase.strip()
    db = _connection(index_path)
    try:
        conditions = ["d.first_indexed_at<=?",
                      "d.provider_id IN ("+",".join("?" for _ in approved)+")"]
        args: list[object] = [current.isoformat(), *approved]
        if len(key) >= 3:
            conditions.append("d.rowid IN (SELECT rowid FROM title_fts WHERE title_fts MATCH ?)")
            args.append('"' + key.replace('"', '""') + '"')
        else:
            safe = key.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            conditions.append("d.headline LIKE ? ESCAPE '!'")
            args.append("%" + safe + "%")
        if source_id is not None:
            conditions.append("d.provider_id=?")
            args.append(source_id)
        if semiconductor_only:
            conditions.append("d.keyword_candidate=1 AND d.needs_review=1")
        statement = ("""SELECT d.provider_id,d.event_id,d.title_sha256,d.headline,
                        d.canonical_url,d.source_kind,d.claim_classification,
                        d.source_available_at,d.first_indexed_at,
                        d.first_triage_sha256,d.keyword_candidate,d.needs_review
                        FROM documents d WHERE """
                     + " AND ".join(conditions)
                     + " ORDER BY d.first_indexed_at DESC,d.rowid DESC LIMIT ?")
        rows = db.execute(statement, (*args, limit)).fetchall()
        return tuple({
            "provider_id":row[0], "event_id":row[1], "title_sha256":row[2],
            "headline":row[3], "source_url":row[4],
            "source_kind":row[5], "source_claim_classification":row[6],
            "source_available_at":row[7], "first_searchable_at":row[8],
            "triage_evidence_sha256":row[9],
            "semiconductor_keyword_candidate": bool(row[10]),
            "needs_human_review": bool(row[11]),
            "verified_economic_fact":False,
            "verified_supply_transaction":False,
            "confirmed_beneficiary":False,
            "article_body_included":False,
        } for row in rows)
    except sqlite3.OperationalError as exc:
        raise SourceShareError("local FTS search unavailable") from exc
    finally:
        db.close()
