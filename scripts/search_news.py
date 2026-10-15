"""Local full-text title search of authorized, SHA-acknowledged RSS metadata.

Reads prior completed checkpoints/receipts only. No network requests,
official DART/SEC/KRX collectors, AI calls, trading actions, or news bodies.
This indexes all approved RSS titles as context; V1 beneficiary analysis stays
restricted to semiconductor keyword hypotheses.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry, default_state
from newscatalystos.news_search import search_titles, sync_completed_titles
from newscatalystos.feed_analysis_delivery import attach_saved_analysis_to_search
from newscatalystos.federated_news_search import (
    TitleSearchWorkspace, search_completed_workspaces,
)
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    p.add_argument("--query", required=True,
                   help="literal title substring in Korean or English")
    p.add_argument("--registry", type=Path,
                   default=base / "providers" / "authorized_sources.json")
    p.add_argument("--source-id", help="currently approved source only")
    p.add_argument("--semiconductor-only", action="store_true",
                   help="show only unverified semiconductor keyword candidates")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--state", type=Path, default=default_state())
    p.add_argument("--inbox-root", type=Path,
                   default=base / "inbox" / "feed_triage")
    p.add_argument("--index", type=Path,
                   default=PROJECT / "output" / "search_cache" / "news_search.sqlite3")
    p.add_argument("--scope", choices=("core", "motir", "all"), default="core",
                   help="core keeps the existing FTS cache; motir/all read isolated completed metadata")
    p.add_argument("--motir-registry", type=Path,
                   default=base / "providers" / "motir_authorized_sources.json")
    p.add_argument("--motir-state", type=Path,
                   default=base / "state" / "motir_incremental_feeds.sqlite3")
    p.add_argument("--motir-inbox-root", type=Path,
                   default=base / "inbox" / "motir_feed_triage")
    p.add_argument("--analysis-report-file", type=Path,
                   help="existing private feed analysis publication, optional")
    p.add_argument("--analysis-reports-root", type=Path,
                   help="private root containing that published report")
    p.add_argument("--analysis-expected-sha256",
                   help="producer's independently retained SHA, not calculated from input")
    p.add_argument("--theme-root", type=Path,
                   help="include matching stored theme candidates and their source event links")
    p.add_argument('--company-identity-root',type=Path,help='include saved article company identity matches')
    return p


def _with_saved_analysis(report: dict, opts: argparse.Namespace) -> dict:
    if getattr(opts,'company_identity_root',None) is not None:
        from newscatalystos.article_company_identity import search_article_identities
        report={**report,'article_company_identities':search_article_identities(opts.company_identity_root,query=opts.query)}
    if getattr(opts, "theme_root", None) is not None:
        report = {**report, "theme_candidates": ThemeStore(opts.theme_root).search(query=opts.query)}
    selected = (getattr(opts, "analysis_report_file", None),
                getattr(opts, "analysis_reports_root", None),
                getattr(opts, "analysis_expected_sha256", None))
    if not any(value is not None for value in selected):
        return report  # unchanged search when enrichment not requested
    if not all(selected):
        raise SourceShareError("complete saved analysis selection required")
    return attach_saved_analysis_to_search(report, *selected)


def evaluate(opts: argparse.Namespace) -> tuple[int, dict]:
    try:
        scope = getattr(opts, "scope", "core")
        if scope not in ("core", "motir", "all"):
            raise SourceShareError("unsupported search scope")
        if scope != "core":
            workspaces = []
            if scope in ("core", "all"):
                workspaces.append(TitleSearchWorkspace(
                    "core", opts.registry, opts.state, opts.inbox_root,
                ))
            if scope in ("motir", "all"):
                workspaces.append(TitleSearchWorkspace(
                    "motir", opts.motir_registry, opts.motir_state, opts.motir_inbox_root,
                ))
            report = search_completed_workspaces(
                tuple(workspaces), opts.query, registry_reader=_registry,
                source_id=opts.source_id, semiconductor_only=opts.semiconductor_only,
                limit=opts.limit,
            )
            return (0 if report["coverage_complete"] else 4), _with_saved_analysis(report, opts)
        registry = _registry(opts.registry)
        status = sync_completed_titles(
            opts.inbox_root, opts.state, opts.index, registry,
        )
        results = search_titles(
            opts.index, opts.query, registry=registry,
            source_id=opts.source_id,
            semiconductor_only=opts.semiconductor_only,
            limit=opts.limit,
        )
        return 0, _with_saved_analysis({
            "status": "LOCAL_APPROVED_METADATA_SEARCH",
            "indexed_document_versions": status.unique_documents,
            "acknowledged_triage_receipts_checked": status.processed_receipts,
            "keyword_hits": len(results),
            "results": list(results),
            "original_article_body_stored": False,
            "fact_verified_by_search": False,
            "verified_supply_relationships": 0,
            "market_action": None,
            "network_calls": 0,
            "ai_calls": 0,
        }, opts)
    except (SourceShareError, OSError, ValueError) as exc:
        return 4, {
            "status": "SEARCH_DATA_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "network_calls": 0,
            "ai_calls": 0,
            "fact_verified_by_search": False,
        }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
