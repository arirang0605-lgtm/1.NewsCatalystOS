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
from newscatalystos.source_share import SourceShareError


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
    return p


def evaluate(opts: argparse.Namespace) -> tuple[int, dict]:
    try:
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
        return 0, {
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
        }
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
