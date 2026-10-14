"""Read one saved RSS analysis using its previously retained producer SHA.

Reads only the selected report: no source collection, AI calls, database writes,
external project edits or orders. Run with PYTHONPATH=src from the project root.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report-file", type=Path, required=True)
    p.add_argument("--reports-root", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True,
                   help="SHA retained from producer output, not derived from the input file")
    p.add_argument("--provider-id")
    p.add_argument("--event-id", help="source event ID, not the derived analysis ID")
    p.add_argument("--title-sha256", help="exact title version; requires --event-id")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--limit", type=int, default=20)
    return p


def evaluate(opts: argparse.Namespace, *, now: datetime | None = None) -> tuple[int, dict]:
    try:
        return 0, consume_feed_analysis(
            opts.report_file, opts.reports_root, opts.expected_sha256,
            provider_id=opts.provider_id, event_id=opts.event_id,
            title_sha256=opts.title_sha256, offset=opts.offset, limit=opts.limit, now=now)
    except (SourceShareError, OSError, ValueError, TypeError, KeyError) as exc:
        return 4, {"status": "SAVED_FEED_ANALYSIS_UNAVAILABLE",
                   "error_type": type(exc).__name__, "source_fetch_calls": 0,
                   "ai_calls": 0, "database_writes": 0,
                   "verified_economic_facts": 0, "market_action": None}


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
