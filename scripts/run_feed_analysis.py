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
from newscatalystos.economic_changes import normalized
from newscatalystos.theme_emergence import ThemeStore, economic_observation


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scope", choices=("core", "motir"), default="core")
    p.add_argument("--registry", type=Path)
    p.add_argument("--inbox-root", type=Path)
    p.add_argument("--state", type=Path, help="existing ingestion state, read-only")
    p.add_argument("--analysis-root", type=Path, help="separate derived state and private reports")
    p.add_argument("--theme-root", type=Path, help="existing private economic theme store")
    p.add_argument("--company-identity-config", type=Path, help="existing pinned filing directory configuration")
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


def read_model_config(path: Path | None) -> AIModel | None:
    if path is None:
        return None
    data = _json(_private_input(path, 8192), "private AI model configuration")
    if set(data) != {f.name for f in fields(AIModel)}:
        raise SourceShareError("AI model fields must exclude credentials")
    model = AIModel(**data)
    model.validate()
    return model


def evaluate(opts: argparse.Namespace, *, opener=None, now=None) -> tuple[int, dict]:
    try:
        base = Path.home() / "Library/Application Support/NewsCatalystOS"
        prefix = "motir_" if opts.scope == "motir" else ""
        registry_path = opts.registry or base / "providers" / (prefix + "authorized_sources.json")
        inbox = opts.inbox_root or base / "inbox" / (prefix + "feed_triage")
        state = opts.state or base / "state" / (prefix + "incremental_feeds.sqlite3")
        work = opts.analysis_root or PROJECT / "output" / "feed_analysis" / opts.scope
        standard_roots = {(PROJECT / "output/feed_analysis" / scope).resolve()
                          for scope in ("core", "motir")}
        identity_config = getattr(opts, "company_identity_config", None)
        if identity_config is None and work.resolve() in standard_roots:
            identity_config = base / "company_identity.json"
        model = read_model_config(opts.model_config)
        report = analyze_completed_feed(_registry(registry_path), inbox, state, work,
            provider_id=opts.provider_id, event_id=opts.event_id,
            title_sha256=opts.title_sha256, limit=opts.limit, model=model,
            allow_paid=opts.allow_paid, opener=opener, now=now,
            analyze_existing=getattr(opts, "analyze_existing", False),
            ai_ledger=getattr(opts, "ai_ledger", None), company_identity_config=identity_config)
        failures = sum((row["ai_eligible"] or row.get("analysis_purpose") == "EXISTING_ARTICLE") and row["ai_status"] not in
                       ("ANALYZED_UNVERIFIED", "CACHE_HIT") for row in report["results"])
        report["paid_execution_requested"] = opts.allow_paid
        report["requested_ai_complete"] = failures == 0 if opts.allow_paid else None
        path, digest = publish_feed_analysis(report, work / "reports")
        observations = [economic_observation(change,
            origin_reference=row["source_url"], source_url=row["source_url"],
            source_id=row["provider_id"], source_available_at=row["source_available_at"],
            content_scope="RSS_TITLE_METADATA", source_binding={
                "source_event_sha256":row["source_event_sha256"],
                "document_sha256":row["source_title_sha256"]},
            company_mappings=[{k: match[k] for k in ("source_name", "entity_id", "evidence_sha256")}
                for match in row.get("company_identity", {}).get("matches", [])
                if normalized(match["source_name"]) in {normalized(n) for n in change["entity_ids"]}] or None)
            for row in report["results"] for change in row.get("economic_changes", [])]
        # Standard installed scopes share the existing document theme store;
        # custom/test analysis roots remain isolated unless explicitly joined.
        theme_root = getattr(opts, "theme_root", None) or (
            base / "document_analysis/theme_history" if work.resolve() in standard_roots
            else work / "theme_history")
        themes = ThemeStore(theme_root).ingest(observations, now=now) if observations else []
        return (4 if opts.allow_paid and failures else 0), {
            **report, "private_report_file": str(path), "report_sha256": digest,
            "economic_changes_count":len(observations), "theme_versions_created":len(themes)}
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
