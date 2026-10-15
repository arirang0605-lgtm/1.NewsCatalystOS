"""One scheduled sector-policy tick: authorized MOTIR POST -> RSS triage -> analysis.

Optional private Gold candidate capture is a separate research workflow.
Separate private source registry, SQLite, inbox, gold workspace and PIN.
Existing two-source launchd, EraLeader and project V1.0 tasks are unchanged.
AI uses the existing budgeted adapter when enabled; content is RSS title metadata.
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

from scripts.run_feed_triage import _registry, evaluate as triage_once
from scripts.run_gold_capture_once import capture as gold_once
from scripts.run_scheduled_triage import _analyze_provider, evaluate_analysis
from scripts.prepare_motir_source import ENDPOINT, SOURCE
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    home = Path.home() / "Library/Application Support/NewsCatalystOS"
    p.add_argument("--registry", type=Path,
                   default=home / "providers" / "motir_authorized_sources.json")
    p.add_argument("--state", type=Path,
                   default=home / "state" / "motir_incremental_feeds.sqlite3")
    p.add_argument("--dedup-state", type=Path,
                   default=home / "state" / "motir_triage_exact_index.sqlite3")
    p.add_argument("--inbox-root", type=Path,
                   default=home / "inbox" / "motir_feed_triage")
    p.add_argument("--output-root", type=Path,
                   default=PROJECT / "output" / "motir_policy")
    p.add_argument("--gold-root", type=Path,
                   default=PROJECT / "output" / "motir_gold_review")
    p.add_argument("--pin-root", type=Path,
                   default=home / "pins" / "motir_gold")
    p.add_argument("--workspace-root", type=Path,
                   default=home / "motir_gold_review_workspace")
    p.add_argument("--lock-root", type=Path,
                   default=home / "state" / "motir_gold_lock")
    p.add_argument("--analysis-root", type=Path,
                   default=PROJECT / "output" / "feed_analysis" / "motir")
    p.add_argument("--analysis-limit", type=int, default=100)
    p.add_argument("--analysis-model-config", type=Path,
                   help="model and accounting configuration for cache or authorized AI")
    p.add_argument("--allow-paid-ai", action="store_true",
                   help="enable budgeted AI for eligible events on scheduled ticks")
    p.add_argument("--skip-analysis", action="store_true")
    p.add_argument("--capture-gold", action="store_true",
                   help="optional research candidate capture; no news review or release gate")
    p.add_argument("--replay-only", action="store_true",
                   help="use completed input and recovery checkpoints without source HTTP")
    p.set_defaults(analysis_scope="motir")
    return p


def run_once(opts: argparse.Namespace, *,
             registry_reader=_registry,
             feed_runner=triage_once,
             gold_runner=gold_once,
             analysis_runner=evaluate_analysis) -> tuple[int, dict]:
    """Treat source analysis and optional Gold research as separate outcomes."""
    try:
        enabled = not getattr(opts, "skip_analysis", False)
        paid = (enabled and getattr(opts, "allow_paid_ai", False)
                and not getattr(opts, "replay_only", False))
        if paid and getattr(opts, "analysis_model_config", None) is None:
            raise SourceShareError("AI model configuration required")
        limit = getattr(opts, "analysis_limit", 100)
        if enabled and (type(limit) is not int or not 1 <= limit <= 100):
            raise SourceShareError("invalid bounded analysis limit")
        source = registry_reader(opts.registry)
        approved = tuple(source.approved_ids(at=datetime.now(timezone.utc)))
        if approved != (SOURCE,):
            raise SourceShareError("only reviewed MOTIR sector feed permitted")
        provider = source.active(SOURCE)
        if (provider.kind != "GOVERNMENT_POLICY"
                or provider.method != "RSS_POST"
                or provider.endpoint != ENDPOINT
                or provider.allow_full_text_storage):
            raise SourceShareError("sector source rights or exact endpoint unsupported")
        capture_gold = getattr(opts, "capture_gold", False)
        paths = (opts.registry, opts.state, opts.dedup_state, opts.inbox_root,
                 opts.output_root)
        if capture_gold:
            paths += (opts.gold_root, opts.pin_root, opts.workspace_root,
                      opts.lock_root)
        if (not all(Path(p).is_absolute() and ".." not in Path(p).parts
                    and all(part.casefold() != "eraleader" for part in Path(p).parts)
                    for p in paths)
                or (capture_gold and (opts.gold_root == opts.output_root
                                      or opts.gold_root == opts.inbox_root))
                or opts.state == opts.dedup_state):
            raise SourceShareError("isolated private sector paths required")
        tick = argparse.Namespace(
            registry=opts.registry, provider_id=SOURCE, state=opts.state,
            dedup_state=opts.dedup_state,
            inbox_root=opts.inbox_root, output_root=opts.output_root,
            replay_only=getattr(opts, "replay_only", False),
        )
        try:
            feed_code, feed_status = feed_runner(tick)
        except (SourceShareError, OSError, ValueError) as exc:
            feed_code, feed_status = 4, {"status": "DATA_UNAVAILABLE",
                                        "error_type": type(exc).__name__}
        gold_code, gold_status = 0, {"status": "DISABLED_BY_V1_POLICY"}
        if capture_gold:
            # Research may replay an earlier completed ACK even when polling is
            # NOT_DUE. It never controls the article-analysis result.
            gold_opts = argparse.Namespace(
                registry=opts.registry, inbox_root=opts.inbox_root,
                state=opts.state, out_root=opts.gold_root,
                pin_root=opts.pin_root, workspace_root=opts.workspace_root,
                lock_root=opts.lock_root, motir_policy_only=True,
            )
            try:
                gold_code, gold_status = gold_runner(gold_opts)
            except (SourceShareError, OSError, ValueError) as exc:
                gold_code, gold_status = 4, {"status": "GOLD_CAPTURE_UNAVAILABLE",
                                            "error_type": type(exc).__name__}
        analysis_code, analysis = (0, {"status": "DISABLED"})
        if enabled:
            analysis_opts = argparse.Namespace(**vars(opts))
            analysis_opts.analysis_scope = "motir"
            if getattr(analysis_opts, "analysis_root", None) is None:
                analysis_opts.analysis_root = Path(opts.output_root).parent / "feed_analysis" / "motir"
            analysis_code, analysis = _analyze_provider(analysis_opts, SOURCE, analysis_runner)
        good_feed = (feed_code == 0 and feed_status.get("status") in {
            "FEED_METADATA_TRIAGE_READY", "RECOVERED_FROM_DURABLE_CHECKPOINT",
            "NOT_DUE", "NO_PENDING_REPLAY",
        })
        good_gold = gold_code == 0 and gold_status.get("status") in {
            "DISABLED_BY_V1_POLICY",
            "NEW_VERIFIED_RSS_CANDIDATES_FROZEN",
            "NO_NEW_VERIFIED_RSS_CANDIDATES",
        }
        good_source_analysis = good_feed and analysis_code == 0
        good_tick = good_source_analysis
        return (0 if good_tick else 4), {
            "status": ("MOTIR_SECTOR_SOURCE_ANALYSIS_READY" if good_tick
                       else "MOTIR_SECTOR_SOURCE_OR_ANALYSIS_UNAVAILABLE"),
            "provider_id": SOURCE,
            "feed_status": feed_status.get("status", "DATA_UNAVAILABLE"),
            "feed_new_identities": feed_status.get("new_provider_ids", 0),
            "semiconductor_keyword_review_hints": feed_status.get(
                "semiconductor_keyword_review", 0),
            "gold_status": gold_status.get("status", "DATA_UNAVAILABLE"),
            "gold_capture_requested": capture_gold,
            "research_warning": None if good_gold else "OPTIONAL_GOLD_CAPTURE_FAILED",
            "newly_frozen_gold_candidates": gold_status.get("newly_frozen_cases", 0),
            "total_sector_gold_candidates": gold_status.get("total_pinned_unique_cases"),
            "analysis_enabled": enabled, "analysis": analysis,
            "human_gold_labeled_cases": 0,
            "ai_calls": None if paid else 0,
            "new_ai_results": analysis.get("new_ai_results", 0),
            "era_api_calls": 0,
            "release_gate_verified": False,
        }
    except (OSError, SourceShareError, ValueError, TypeError) as exc:
        return 4, {
            "status": "MOTIR_SECTOR_INPUT_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "human_gold_labeled_cases": 0, "era_api_calls": 0,
            "ai_calls": 0, "release_gate_verified": False,
        }


def main(argv: list[str] | None = None) -> int:
    code, status = run_once(parser().parse_args(argv))
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
