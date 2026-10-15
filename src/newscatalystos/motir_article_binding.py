"""Bind a licensed MOTIR press text to an already committed RSS observation.

This is an offline provenance join. It never fetches a page, backdates body
availability to the RSS timestamp, or treats a current article as a new deal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .evidence_archive import _private_root, _read_once, _write_new, read_archived_evidence
from .news_search import read_completed_title_snapshots
from .provider_registry import (
    MOTIR_PRESS_DOCUMENT, ProviderRegistry, permits_document_storage,
)
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA = "newscatalyst.motir_article_rss_binding.v1"
STATUS = "ATTRIBUTED_ARTICLE_BOUND_NOT_NEW_EVENT_VERIFIED"
FEED_ID = "motir-official-press"
FEED_URL = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/rss"


def prepare_motir_article_binding(
    feed_registry: ProviderRegistry, inbox_root: Path, poll_state: Path,
    article_registry: ProviderRegistry, article_provider_id: str,
    archive_root: Path, archive_version: str, archive_receipt_sha256: str,
    document_sha256: str, source_event_sha256: str, title_sha256: str,
    *, now: datetime | None = None,
) -> bytes:
    """Return a SHA-pinnable receipt after validating both independent paths."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "binding time")
    if not isinstance(feed_registry, ProviderRegistry) or not isinstance(
        article_registry, ProviderRegistry
    ):
        raise SourceShareError("two approved registries required")
    feed = feed_registry.active(FEED_ID, at=at)
    article = article_registry.active(article_provider_id, at=at)
    if (feed.kind != "GOVERNMENT_POLICY" or feed.method != "RSS_POST"
            or feed.endpoint != FEED_URL or article.kind != "GOVERNMENT_POLICY"
            or article.method != "DOCUMENT" or not permits_document_storage(article)
            or MOTIR_PRESS_DOCUMENT.fullmatch(article.endpoint) is None):
        raise SourceShareError("exact authorized MOTIR feed and press article required")
    expected_event = _must_sha(source_event_sha256, "RSS event")
    expected_title = _must_sha(title_sha256, "RSS title")
    expected_receipt = _must_sha(archive_receipt_sha256, "archive receipt")
    expected_document = _must_sha(document_sha256, "article document")
    _, archived = read_archived_evidence(archive_root, archive_version, now=at)
    article_id = article.endpoint.split("/")[-2]
    if (archived.provider_id != article.provider_id
            or archived.document_id != article_id
            or archived.content_scope != "LICENSED_SOURCE_BYTES"
            or archived.receipt_sha256 != expected_receipt
            or archived.payload_sha256 != expected_document
            or not article.enabled_at(archived.first_verified_at)):
        raise SourceShareError("article archive identity, rights or SHA mismatch")
    matches = []
    for ack, snapshot, triage_sha in read_completed_title_snapshots(
        inbox_root, poll_state, feed_registry, now=at
    ):
        if ack["provider_id"] != FEED_ID:
            continue
        for item in snapshot["items"]:
            if (item["provider_id"] == FEED_ID
                    and item["event_id"] == expected_event
                    and item["title_sha256"] == expected_title
                    and item["canonical_url"] == article.endpoint
                    and item["document_id"] == article.endpoint):
                seen = _when(item["available_at"], "RSS available")
                confirmed = _when(ack["confirmed_at"], "RSS acknowledged")
                if not seen <= confirmed <= at:
                    raise SourceShareError("RSS observation not available for binding")
                matches.append((seen, confirmed, ack["checkpoint_sha256"], triage_sha))
    if not matches:
        raise SourceShareError("article has no exact committed RSS identity")
    seen, confirmed, checkpoint, triage = min(matches)
    result = {
        "schema": SCHEMA, "status": STATUS,
        "source_url": article.endpoint,
        "rss_provider_id": FEED_ID, "article_provider_id": article.provider_id,
        "source_event_sha256": expected_event, "title_sha256": expected_title,
        "rss_checkpoint_sha256": _must_sha(checkpoint, "RSS checkpoint"),
        "rss_triage_sha256": _must_sha(triage, "RSS triage"),
        "rss_first_seen_at": seen.isoformat(),
        "rss_acknowledged_at": confirmed.isoformat(),
        "archive_version": archived.version_id,
        "archive_receipt_sha256": expected_receipt,
        "document_sha256": expected_document,
        "article_archived_at": archived.archived_at.isoformat(),
        "binding_at": at.isoformat(),
        "new_economic_event_verified": False,
        "verified_real_transaction": False,
        "verified_real_benefit": False,
    }
    return (json.dumps(result, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def publish_motir_article_binding(payload: bytes, out_root: Path) -> tuple[Path, str]:
    data = _json(payload, "article RSS binding")
    if data.get("schema") != SCHEMA or data.get("status") != STATUS:
        raise SourceShareError("article binding schema mismatch")
    digest = sha256(payload).hexdigest()
    root = _private_root(out_root)
    path = root / ("motir_article_binding_" + digest + ".json")
    if path.exists():
        if _read_once(path, 8192) != payload:
            raise SourceShareError("article binding hash collision")
    else:
        _write_new(path, payload)
    return path, digest


def consume_motir_article_binding(path: Path, expected_sha256: str, *,
                                  now: datetime | None = None) -> dict:
    expected = _must_sha(expected_sha256, "article binding pin")
    payload = _read_once(path, 8192)
    if sha256(payload).hexdigest() != expected:
        raise SourceShareError("article binding SHA mismatch")
    data = _json(payload, "article RSS binding")
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "consumer time")
    required = {
        "schema", "status", "source_url", "rss_provider_id", "article_provider_id",
        "source_event_sha256", "title_sha256", "rss_checkpoint_sha256",
        "rss_triage_sha256", "rss_first_seen_at", "rss_acknowledged_at",
        "archive_version", "archive_receipt_sha256", "document_sha256",
        "article_archived_at", "binding_at", "new_economic_event_verified",
        "verified_real_transaction", "verified_real_benefit",
    }
    if (set(data) != required or data["schema"] != SCHEMA or data["status"] != STATUS
            or data["rss_provider_id"] != FEED_ID
            or not isinstance(data["source_url"], str)
            or MOTIR_PRESS_DOCUMENT.fullmatch(data["source_url"]) is None
            or any(data[key] is not False for key in (
                "new_economic_event_verified", "verified_real_transaction",
                "verified_real_benefit"))
            or not _when(data["rss_first_seen_at"], "RSS available")
                <= _when(data["rss_acknowledged_at"], "RSS acknowledged") <= at
            or not _when(data["article_archived_at"], "article archived")
                <= _when(data["binding_at"], "binding time") <= at):
        raise SourceShareError("unavailable or overstated article binding")
    for key in ("source_event_sha256", "title_sha256", "rss_checkpoint_sha256",
                "rss_triage_sha256", "archive_version", "archive_receipt_sha256",
                "document_sha256"):
        _must_sha(data[key], key)
    return data
