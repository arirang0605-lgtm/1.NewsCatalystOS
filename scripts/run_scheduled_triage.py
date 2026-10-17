"""6_5 bounded once-per-invocation scheduling of two explicitly approved feeds.

Each invocation delegates to the existing rate-limited, PIT-safe 1_3->3_5
triage and then the existing metadata analysis/report writer. The installed
launchd command gains rules-only analysis without another collector or agent.
Paid AI can be enabled once in the scheduler configuration with --allow-paid-ai;
the existing eligibility, cache, credentials and cost ledger govern each call.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
import sys

# Work both when called as "python scripts/..." and imported in pytest.
PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry, evaluate as evaluate_feed, default_state
from scripts.run_feed_analysis import evaluate as evaluate_analysis
from newscatalystos.provider_registry import RESERVED
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--provider-id", action="append", required=True)
    p.add_argument("--alternate-registry", type=Path,
                   help="alternate approved RSS category of the SAME publisher; one provider ID only")
    p.add_argument("--state", type=Path, default=default_state())
    p.add_argument("--dedup-state", type=Path,
                   default=base / "state" / "triage_exact_index.sqlite3")
    p.add_argument("--inbox-root", type=Path,
                   default=base / "inbox" / "feed_triage")
    p.add_argument("--output-root", type=Path,
                   default=PROJECT / "output")
    p.add_argument("--analysis-root", type=Path,
                   help="derived state/reports; defaults to output-root/feed_analysis/core")
    p.add_argument("--analysis-limit", type=int, default=100,
                   help="latest bounded versions per selected source; reports show truncation")
    p.add_argument("--analysis-model-config", type=Path,
                   help="model and accounting configuration for cache or authorized AI")
    p.add_argument("--allow-paid-ai", action="store_true",
                   help="enable budgeted AI for eligible events on scheduled ticks")
    p.add_argument("--analysis-ai-ledger", type=Path, help="shared monthly AI cost ledger")
    p.add_argument("--semantic-ai", action="store_true")
    p.add_argument("--semantic-call-limit", type=int, default=3)
    p.add_argument("--analysis-theme-root", type=Path, help="existing private economic theme store")
    p.add_argument("--skip-analysis", action="store_true",
                   help="explicit legacy collection-only tick")
    operation = p.add_mutually_exclusive_group(required=True)
    operation.add_argument("--once", action="store_true",
                           help="do one scheduled tick; existing 1_3 budget applies")
    operation.add_argument("--dry-run", action="store_true",
                           help="only check authorization, without any feed HTTP/state writes")
    operation.add_argument("--replay-only", action="store_true",
                           help="recover prior checkpoints and analyze completed input; no source HTTP")
    return p


def _approved_feed_variant(opts, selected, registered, at, registry_reader):
    """One publisher's two verified RSS endpoints, alternating by saved ACK.

    An ACK means one durable completed source poll, not a new independent
    publisher. Reuse the SAME provider request/seen-ID state and never count
    unacknowledged or failed polls as successful rotation steps.
    """
    other_path = getattr(opts, "alternate_registry", None)
    if other_path is None:
        return opts.registry, "primary"
    if len(selected) != 1:
        raise SourceShareError("alternate RSS requires one publisher ID")
    other = registry_reader(other_path)
    name = selected[0]
    primary = registered.active(name, at=at)
    alternate = other.active(name, at=at)
    fields = ("provider_id", "kind", "method", "grant", "rights_reference",
              "expires_at", "approved", "allow_full_text_storage", "hourly_limit")
    if (len(other.providers) != 1
            or any(getattr(primary, key) != getattr(alternate, key) for key in fields)
            or primary.method != "RSS" or primary.allow_full_text_storage
            or primary.endpoint == alternate.endpoint
            or urlsplit(primary.endpoint).hostname != urlsplit(alternate.endpoint).hostname):
        raise SourceShareError("alternate RSS must be same approved publisher and rights")
    # A dry-run/replay never consumes another RSS slot. A replay continues
    # committed metadata regardless of which category produced the receipt.
    if opts.dry_run or getattr(opts, "replay_only", False):
        return opts.registry, "primary"
    from newscatalystos.news_search import read_completed_title_snapshots
    completed = read_completed_title_snapshots(
        opts.inbox_root, opts.state, registered, now=at)
    count = sum(ack["provider_id"] == name for ack, _, _ in completed)
    return (other_path, "alternate") if count % 2 else (opts.registry, "primary")


FEED_SUCCESS = frozenset({
    "FEED_METADATA_TRIAGE_READY", "RECOVERED_FROM_DURABLE_CHECKPOINT",
    "NOT_DUE", "NO_PENDING_REPLAY",
})


def _analyze_provider(opts: argparse.Namespace, name: str, runner) -> tuple[int, dict]:
    """Downstream errors never roll back a committed source or hide its status."""
    root = getattr(opts, "analysis_root", None) or (
        Path(opts.output_root) / "feed_analysis" / "core")
    params = argparse.Namespace(
        scope=getattr(opts, "analysis_scope", "core"),
        registry=opts.registry, inbox_root=opts.inbox_root,
        state=opts.state, analysis_root=root, provider_id=name,
        event_id=None, title_sha256=None,
        limit=getattr(opts, "analysis_limit", 100),
        model_config=getattr(opts, "analysis_model_config", None),
        ai_ledger=getattr(opts, "analysis_ai_ledger", None),
        theme_root=getattr(opts, "analysis_theme_root", None),
        semantic_ai=getattr(opts,"semantic_ai",False),
        semantic_call_limit=getattr(opts,"semantic_call_limit",3),
        semantic_scheduled_only=True,
        company_identity_config=getattr(opts, "company_identity_config", None),
        allow_paid=(getattr(opts, "allow_paid_ai", False)
                    and not getattr(opts, "replay_only", False)
                    and not getattr(opts, "dry_run", False)),
    )
    try:
        code, detail = runner(params)
        state = detail.get("status", "FEED_ANALYSIS_INPUT_UNAVAILABLE")
        incomplete_states = {"UNAVAILABLE", "MODEL_UNAVAILABLE", "UNSUPPORTED_PROPOSAL",
                             "AI_PREVIOUS_CALL_UNSETTLED", "AI_PREVIOUS_RESULT_MISSING"}
        incomplete_rows = [row for row in detail.get("results", [])
                           if row.get("semantic_analysis", {}).get("status") in incomplete_states]
        # One optional, historical semantic AI reservation must not mark a
        # successfully stored source analysis as failed. Keep the incomplete
        # count and producer request verdict visible; important eligible
        # failures and source/DB failures still return exit 4.
        optional_only = (code == 4 and state == "FEED_ECONOMIC_ANALYSIS_READY"
                         and params.semantic_ai and bool(incomplete_rows)
                         and detail.get("requested_ai_complete") is False
                         and all(not row.get("ai_eligible") for row in incomplete_rows))
        good = (code == 0 or optional_only) and state in {
            "FEED_ECONOMIC_ANALYSIS_READY", "NO_COMPLETED_FEED_INPUT"}
        # Metadata/AI content stays in the private report, never launchd stdout.
        summary = {"semantic_ai_attempts":detail.get("semantic_ai_attempts",0),
            "semantic_ai_incomplete":len(incomplete_rows),
            "semantic_ai_deferred":sum(r.get("semantic_analysis",{}).get("status") in
                {"AI_PREVIOUS_CALL_UNSETTLED","AI_PREVIOUS_RESULT_MISSING"}
                for r in incomplete_rows),
            "requested_ai_complete":detail.get("requested_ai_complete"),
            "optional_semantic_incomplete":optional_only,
            "status": state, "exit_code": 0 if good else 4,
            "analyzed_rows": len(detail.get("results", [])),
            "source_versions_checked": detail.get("source_versions_checked", 0),
            "has_more_results": detail.get("has_more_results", False),
            "ai_eligible_candidates": detail.get("ai_eligible_candidates", 0),
            "cache_hits": detail.get("cache_hits", 0),
            "new_ai_results": detail.get("new_ai_results", 0),
            "economic_changes_count": detail.get("economic_changes_count", 0),
            "theme_versions_created": detail.get("theme_versions_created", 0),
            "theme_identity_resolution": detail.get("theme_identity_resolution", {"status":"NOT_CONFIGURED"}),
            "private_report_file": detail.get("private_report_file"),
            "report_sha256": detail.get("report_sha256"),
            "paid_execution_requested": params.allow_paid,
            "ai_adapter_attempts": sum(bool(row.get("ai_adapter_attempted"))
                                       for row in detail.get("results", [])),
            "source_fetch_calls": 0}
        if "error_type" in detail:
            summary["error_type"] = detail["error_type"]
        return summary["exit_code"], summary
    except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
        return 4, {"status": "FEED_ANALYSIS_INPUT_UNAVAILABLE",
                   "exit_code": 4, "error_type": type(exc).__name__,
                   "analyzed_rows": 0, "cache_hits": 0,
                   "paid_execution_requested": params.allow_paid,
                   "ai_adapter_attempts": None, "source_fetch_calls": 0}


def execute(opts: argparse.Namespace, *, registry_reader=_registry,
            feed_runner=evaluate_feed, analysis_runner=evaluate_analysis) -> tuple[int, dict]:
    """One tick: collect/recover -> committed ACK -> isolated analysis -> report.

    NOT_DUE or a failed fetch still permits analysis of earlier completed data.
    The feed status remains explicit, so older data never masks a failed poll.
    """
    selected = tuple(opts.provider_id)
    if (not 1 <= len(selected) <= 10 or len(set(selected)) != len(selected)
            or any(not isinstance(n, str) or n.casefold() in RESERVED
                   or n.casefold().startswith(("krx-", "dart-", "sec-"))
                   for n in selected)):
        return 4, {"status": "INVALID_EXPLICIT_PROVIDER_SELECTION",
                   "providers_checked": 0, "ai_call_count": 0}
    enabled = not getattr(opts, "skip_analysis", False)
    paid = (enabled and getattr(opts, "allow_paid_ai", False)
            and not opts.dry_run and not getattr(opts, "replay_only", False))
    if paid and getattr(opts, "analysis_model_config", None) is None:
        return 4, {"status": "AI_MODEL_CONFIGURATION_REQUIRED",
                   "providers_checked": 0, "ai_call_count": 0}
    limit = getattr(opts, "analysis_limit", 100)
    if enabled and (type(limit) is not int or not 1 <= limit <= 100):
        return 4, {"status": "INVALID_ANALYSIS_LIMIT", "providers_checked": 0,
                   "ai_call_count": 0}
    try:
        registered = registry_reader(opts.registry)
        at = datetime.now(timezone.utc)
        feed_registry, chosen_variant = _approved_feed_variant(
            opts, selected, registered, at, registry_reader)
    except (SourceShareError, OSError, ValueError, sqlite3.Error) as exc:
        return 4, {"status": "PRIVATE_REGISTRY_UNAVAILABLE",
                   "error_type": type(exc).__name__, "providers_checked": 0}
    outcomes = []
    failures = analysis_failures = analysis_completed = analysis_rows = cache_hits = 0
    for name in selected:
        try:
            registered.active(name, at=at)
        except (SourceShareError, OSError, ValueError):
            failures += 1
            outcomes.append({"provider_id": name, "status": "DATA_UNAVAILABLE"})
            continue  # no analysis of a revoked source
        if opts.dry_run:
            outcomes.append({"provider_id": name, "status": "AUTHORIZED_NO_REQUEST"})
            continue
        tick_opts = argparse.Namespace(
            registry=feed_registry, provider_id=name, state=opts.state,
            dedup_state=opts.dedup_state, output_root=opts.output_root,
            inbox_root=opts.inbox_root, replay_only=getattr(opts, "replay_only", False),
        )
        try:
            code, detail = feed_runner(tick_opts)
            status = detail.get("status", "DATA_UNAVAILABLE")
        except (SourceShareError, OSError, ValueError, sqlite3.Error):
            code, status, detail = 4, "DATA_UNAVAILABLE", {}
        failures += int(code != 0 or status not in FEED_SUCCESS)
        outcome = {"provider_id": name, "status": status,
            **({"feed_variant": chosen_variant} if getattr(opts, "alternate_registry", None) else {}),
            "new_provider_ids": detail.get("new_provider_ids", 0),
            "semiconductor_keyword_candidates": detail.get("semiconductor_keyword_candidates", 0)}
        if enabled:
            analysis_code, analysis = _analyze_provider(opts, name, analysis_runner)
            outcome["analysis"] = analysis
            analysis_failures += int(analysis_code != 0)
            analysis_completed += int(analysis_code == 0 and
                analysis["status"] == "FEED_ECONOMIC_ANALYSIS_READY")
            analysis_rows += analysis["analyzed_rows"]
            cache_hits += analysis["cache_hits"]
        outcomes.append(outcome)
    bad = failures or analysis_failures
    return (4 if bad else 0), {
        "status": ("SCHEDULED_TICK_FAILED" if bad else
                   "DRY_RUN_APPROVED_NO_REQUEST" if opts.dry_run else
                   "SCHEDULED_TICK_COMPLETE_OR_NOT_DUE"),
        "providers_checked": len(selected), "providers_failed": failures,
        "providers": outcomes,
        "analysis_enabled": enabled,
        "analysis_mode": ("BUDGETED_AI_AND_CACHE" if paid else
                          "RULES_AND_EXISTING_CACHE_ONLY" if enabled else "DISABLED"),
        "analysis_providers_completed": analysis_completed,
        "analysis_providers_failed": analysis_failures,
        "analyzed_rows": analysis_rows, "analysis_cache_hits": cache_hits,
        # Adapter attempts include budget/cache failures before HTTP. The cost
        # ledger is the source for actual dispatch counts, not this summary.
        "ai_call_count": None if paid else 0,
        "new_ai_results": sum(x.get("analysis", {}).get("new_ai_results", 0)
                              for x in outcomes),
        "stored_article_body_count": 0,
        "official_era_api_request_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    code, summary = execute(parser().parse_args(argv))
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
