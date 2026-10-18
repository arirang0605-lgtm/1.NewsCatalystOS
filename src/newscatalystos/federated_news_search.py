"""Read-only search across independently approved RSS metadata workspaces.

Uses the same checkpoint/SHA/PIT checks as the existing title index, but does
not combine source databases, gold labels, rights registries, or caches.
Exact title/URL overlap is an automatic overlap signal, never evidence of an independent
news event, a verified economic fact, or a confirmed supply relationship.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable
import json
import re
import sqlite3

from .news_search import MAX_RESULTS, read_completed_title_snapshots
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _when

SCHEMA = "newscatalyst.federated_title_search.v1"
SCOPE_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class TitleSearchWorkspace:
    scope: str
    registry_path: Path
    poll_state: Path
    inbox_root: Path


def _identity(row: dict) -> tuple[str, str, str]:
    return row["provider_id"], row["event_id"], row["title_sha256"]


def _order(row: dict) -> tuple:
    return (-_when(row["source_available_at"], "source availability").timestamp(),
            *_identity(row))


def _overlap_hints(rows: list[dict]) -> list[dict]:
    """Preserve all versions. No fuzzy merger or transitive event inference."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[("EXACT_NORMALIZED_TITLE", row["headline"])].append(row)
        groups[("SHARED_CANONICAL_URL", row["source_url"])].append(row)
    hints = []
    for (reason, value), members in sorted(groups.items()):
        if len({row["provider_id"] for row in members}) < 2:
            continue
        keys = sorted(_identity(row) for row in members)
        digest = sha256(json.dumps([reason, value, keys], ensure_ascii=False,
                                   separators=(",", ":")).encode()).hexdigest()
        hints.append({
            "overlap_sha256": digest,
            "reason": reason,
            "member_versions": [dict(zip(
                ("provider_id", "event_id", "title_sha256"), key)) for key in keys],
            "different_title_versions": len({r["headline"] for r in members}) > 1,
            "automatic_action": "PRESERVE_SOURCE_VERSIONS",
            "same_economic_event_verified": False,
            "source_independence_verified": False,
        })
    return hints


def search_completed_workspaces(
    workspaces: tuple[TitleSearchWorkspace, ...], phrase: str, *,
    registry_reader: Callable[[Path], ProviderRegistry],
    source_id: str | None = None, semiconductor_only: bool = False,
    limit: int = 20, now: datetime | None = None,
    exact_identity: tuple[str, str, str] | None = None,
    exact_source_only: bool = False,
) -> dict:
    """Search bounded completed snapshots; damaged scopes are explicit partials.

    Results never come from a stale cache. A scope with missing/corrupt receipts
    contributes no rows; healthy scopes remain available with coverage=false.
    A query's global limit is applied AFTER sorting all verified matches.
    """
    if (not isinstance(phrase, str) or not 2 <= len(phrase.strip()) <= 80
            or any(ord(ch) < 32 for ch in phrase)
            or type(limit) is not int or not 1 <= limit <= MAX_RESULTS
            or type(semiconductor_only) is not bool
            or type(exact_source_only) is not bool
            or (exact_source_only and exact_identity is None)
            or (source_id is not None and (not isinstance(source_id, str)
                or not source_id or len(source_id) > 128))
            or not isinstance(workspaces, tuple) or not 1 <= len(workspaces) <= 8):
        raise SourceShareError("invalid federated title search options")
    if exact_identity is not None:
        if (not isinstance(exact_identity, tuple) or len(exact_identity) != 3
                or not isinstance(exact_identity[0], str)
                or not 1 <= len(exact_identity[0]) <= 128
                or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in exact_identity[1:])
                or (source_id is not None and source_id != exact_identity[0])):
            raise SourceShareError("invalid exact saved source version")
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    names, paths = set(), set()
    for workspace in workspaces:
        if (not isinstance(workspace, TitleSearchWorkspace)
                or not isinstance(workspace.scope, str)
                or not SCOPE_NAME.fullmatch(workspace.scope)
                or workspace.scope in names):
            raise SourceShareError("distinct search workspace names required")
        names.add(workspace.scope)
        for value in (workspace.registry_path, workspace.poll_state, workspace.inbox_root):
            path = Path(value)
            if (not path.is_absolute() or ".." in path.parts
                    or any(part.casefold() == "eraleader" for part in path.parts)
                    or path.resolve(strict=False) != path or path in paths):
                raise SourceShareError("isolated non-symlink search inputs required")
            paths.add(path)
    # Read registries before any data, to detect ambiguous provider ownership.
    registries, failures, owners = {}, {}, {}
    for workspace in workspaces:
        try:
            registry = registry_reader(workspace.registry_path)
            if not isinstance(registry, ProviderRegistry):
                raise SourceShareError("approved provider registry required")
            approved = registry.approved_ids(at=at)
        except (SourceShareError, OSError, ValueError) as exc:
            failures[workspace.scope] = type(exc).__name__
            continue
        for provider_id in approved:
            if provider_id in owners:
                raise SourceShareError("provider is assigned to multiple search scopes")
            owners[provider_id] = workspace.scope
        registries[workspace.scope] = registry
    if source_id is not None and source_id not in owners:
        raise SourceShareError("search source currently unapproved or unavailable")
    selected_scope=None
    if exact_source_only:
        selected_scope=owners.get(exact_identity[0])
        if selected_scope is None:
            raise SourceShareError("exact search source currently unapproved or unavailable")
    versions, summaries = {}, []
    for workspace in workspaces:
        # All registry/path/ambiguous ownership checks above still run. An
        # exact article only needs completed receipts from its owning scope.
        if selected_scope is not None and workspace.scope!=selected_scope:
            continue
        summary = {
            "scope": workspace.scope, "status": "SEARCH_DATA_UNAVAILABLE",
            "approved_provider_ids": [], "verified_provider_ids": [],
            "missing_approved_provider_ids": [],
            "acknowledged_triage_receipts_checked": 0,
            "searched_document_versions": 0, "coverage_complete": False,
        }
        summaries.append(summary)
        if workspace.scope in failures:
            summary["error_type"] = failures[workspace.scope]
            continue
        registry = registries[workspace.scope]
        approved = set(registry.approved_ids(at=at))
        summary["approved_provider_ids"] = sorted(approved)
        summary["missing_approved_provider_ids"] = sorted(approved)
        if not approved:
            summary["status"] = "NO_APPROVED_SOURCES"
            continue
        try:
            if not workspace.inbox_root.is_dir() or not workspace.poll_state.is_file():
                raise SourceShareError("completed source workspace missing")
            snapshots = read_completed_title_snapshots(
                workspace.inbox_root, workspace.poll_state, registry, now=at,
            )
            scoped = {}
            verified_providers = set()
            for ack, document, digest in snapshots:
                verified_providers.add(ack["provider_id"])
                for item in document["items"]:
                    row = {
                        "search_scope": workspace.scope,
                        "provider_id": item["provider_id"],
                        "event_id": item["event_id"],
                        "title_sha256": item["title_sha256"],
                        "headline": item["headline"],
                        "source_url": item["canonical_url"],
                        "source_kind": item["source_kind"],
                        "source_claim_classification": item["claim_classification"],
                        "source_available_at": item["available_at"],
                        "triage_evidence_sha256": digest,
                        "semiconductor_keyword_candidate": bool(item["matching_tokens"]),
                        "analysis_candidate": item["analysis_candidate"],
                        "verified_economic_fact": False,
                        "verified_supply_transaction": False,
                        "confirmed_beneficiary": False,
                        "article_body_included": False,
                    }
                    if registry.active(item["provider_id"], at=at).method == "MANUAL_METADATA":
                        row["acquisition_method"] = "MANUAL_METADATA"
                    key = _identity(row)
                    previous = scoped.get(key)
                    if previous is None or _order(row) > _order(previous):
                        # Repeated polls retain the earliest verified version,
                        # not the most recent re-observation as a new event.
                        scoped[key] = row
            versions.update(scoped)
            missing = approved - verified_providers
            summary.update({
                "status": "VERIFIED_METADATA_READY" if not missing
                          else "INCOMPLETE_SOURCE_COVERAGE",
                "verified_provider_ids": sorted(verified_providers),
                "missing_approved_provider_ids": sorted(missing),
                "acknowledged_triage_receipts_checked": len(snapshots),
                "searched_document_versions": len(scoped),
                "coverage_complete": not missing,
            })
        except (SourceShareError, OSError, ValueError, sqlite3.Error) as exc:
            # No rows from this scope have been exposed before full validation.
            summary["error_type"] = type(exc).__name__
    checked = _when((now or datetime.now(timezone.utc)).isoformat(), "search checked")
    if checked < at:
        raise SourceShareError("search clock moved backwards")
    matches = sorted((row for row in versions.values()
                      if phrase.strip().casefold() in row["headline"].casefold()
                      and (exact_identity is None or _identity(row) == exact_identity)
                      and (source_id is None or row["provider_id"] == source_id)
                      and (not semiconductor_only or (
                          row["semiconductor_keyword_candidate"] and row["analysis_candidate"]))),
                     key=_order)
    results = [dict(row, search_verified_at=checked.isoformat()) for row in matches[:limit]]
    coverage = all(scope["coverage_complete"] for scope in summaries)
    return {
        **({"coverage_scope":"EXACT_PROVIDER_WORKSPACE"} if exact_source_only else {}),
        "schema": SCHEMA,
        "status": "FEDERATED_APPROVED_METADATA_SEARCH" if coverage
                  else "FEDERATED_SEARCH_PARTIAL_DATA_UNAVAILABLE",
        "coverage_complete": coverage,
        "search_verified_at": checked.isoformat(),
        "scopes": summaries,
        "searched_document_versions": len(versions),
        "verified_provider_count": len({row["provider_id"] for row in versions.values()}),
        "matched_document_versions": len(matches),
        "keyword_hits": len(results),
        "has_more_matches": len(matches) > len(results),
        "results": results,
        "metadata_overlap_scope": "RETURNED_RESULTS_ONLY",
        "metadata_overlap_hints": _overlap_hints(results),
        "independent_economic_event_count": None,
        "original_article_body_stored": False,
        "fact_verified_by_search": False,
        "verified_supply_relationships": 0,
        "market_action": None,
        "source_databases_modified": False,
        "network_calls": 0,
        "ai_calls": 0,
    }
