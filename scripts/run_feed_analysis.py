"""Analyze already committed RSS metadata; no source polling or automatic paid AI.

A model configuration and --allow-paid are both required for OpenAI or
Gemini. API credentials remain in the private process environment.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import sqlite3
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry
from newscatalystos.ai_provider import AIModel
from newscatalystos.feed_analysis import analyze_completed_feed, publish_feed_analysis
from newscatalystos.official_relation_intake import _private_input
from newscatalystos.source_share import SourceShareError, _json


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scope", choices=("core", "motir"), default="core")
    p.add_argument("--registry", type=Path)
    p.add_argument("--inbox-root", type=Path)
    p.add_argument("--state", type=Path, help="existing ingestion state, read-only")
    p.add_argument("--analysis-root", type=Path, help="separate derived state and private reports")
    p.add_argument("--provider-id")
    p.add_argument("--event-id")
    p.add_argument("--title-sha256")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--model-config", type=Path,
                   help="owner-private AIModel JSON; no key or unverified default live prices")
    p.add_argument("--allow-paid", action="store_true",
                   help="explicitly authorize bounded live AI; ignored for noneligible/duplicate inputs")
    p.add_argument("--analyze-existing", action="store_true",
                   help="analyze one selected article without changing its new-event eligibility")
    p.add_argument("--ai-ledger", type=Path, help="shared monthly cost ledger for all scopes")
    return p


def evaluate(opts: argparse.Namespace, *, opener=None, now=None) -> tuple[int, dict]:
    try:
        base = Path.home() / "Library/Application Support/NewsCatalystOS"
        prefix = "motir_" if opts.scope == "motir" else ""
        registry_path = opts.registry or base / "providers" / (prefix + "authorized_sources.json")
        inbox = opts.inbox_root or base / "inbox" / (prefix + "feed_triage")
        state = opts.state or base / "state" / (prefix + "incremental_feeds.sqlite3")
        work = opts.analysis_root or PROJECT / "output" / "feed_analysis" / opts.scope
        model = None
        if opts.model_config:
            data = _json(_private_input(opts.model_config, 8192), "private AI model configuration")
            if set(data) != {f.name for f in fields(AIModel)}:
                raise SourceShareError("AI model fields must exclude credentials")
            model = AIModel(**data)
            model.validate()
        report = analyze_completed_feed(_registry(registry_path), inbox, state, work,
            provider_id=opts.provider_id, event_id=opts.event_id,
            title_sha256=opts.title_sha256, limit=opts.limit, model=model,
            allow_paid=opts.allow_paid, opener=opener, now=now,
            analyze_existing=getattr(opts, "analyze_existing", False),
            ai_ledger=getattr(opts, "ai_ledger", None))
        failures = sum((row["ai_eligible"] or row.get("analysis_purpose") == "EXISTING_ARTICLE") and row["ai_status"] not in
                       ("ANALYZED_UNVERIFIED", "CACHE_HIT") for row in report["results"])
        report["paid_execution_requested"] = opts.allow_paid
        report["requested_ai_complete"] = failures == 0 if opts.allow_paid else None
        path, digest = publish_feed_analysis(report, work / "reports")
        return (4 if opts.allow_paid and failures else 0), {
            **report, "private_report_file": str(path), "report_sha256": digest}
    except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
        return 4, {"status": "FEED_ANALYSIS_INPUT_UNAVAILABLE", "error_type": type(exc).__name__,
                   "source_fetch_calls": 0,
                   "verified_economic_facts": 0}


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
