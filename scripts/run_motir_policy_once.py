"""One scheduled sector-policy tick: authorized MOTIR POST -> existing RSS triage -> private gold.

Separate private source registry, SQLite, inbox, gold workspace and PIN.
Existing two-source launchd, EraLeader and project V1.0 tasks are unchanged.
No AI calls or human labels; content remains official RSS title metadata.
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
    return p


def run_once(opts: argparse.Namespace, *,
             registry_reader=_registry,
             feed_runner=triage_once,
             gold_runner=gold_once) -> tuple[int, dict]:
    """Do not conflate successful feed work and human gold verification."""
    try:
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
        paths = (opts.registry, opts.state, opts.dedup_state, opts.inbox_root,
                 opts.output_root, opts.gold_root, opts.pin_root,
                 opts.workspace_root, opts.lock_root)
        if (not all(Path(p).is_absolute() and ".." not in Path(p).parts
                    and all(part.casefold() != "eraleader" for part in Path(p).parts)
                    for p in paths)
                or opts.gold_root == opts.output_root
                or opts.gold_root == opts.inbox_root
                or opts.state == opts.dedup_state):
            raise SourceShareError("isolated private sector paths required")
        tick = argparse.Namespace(
            registry=opts.registry, provider_id=SOURCE, state=opts.state,
            dedup_state=opts.dedup_state,
            inbox_root=opts.inbox_root, output_root=opts.output_root,
            replay_only=False,
        )
        feed_code, feed_status = feed_runner(tick)
        # A previously successful observation must still reach its blind
        # private gold queue, even if an hourly poll is NOT_DUE or fails.
        gold_opts = argparse.Namespace(
            registry=opts.registry, inbox_root=opts.inbox_root,
            state=opts.state, out_root=opts.gold_root,
            pin_root=opts.pin_root, workspace_root=opts.workspace_root,
            lock_root=opts.lock_root, motir_policy_only=True,
        )
        gold_code, gold_status = gold_runner(gold_opts)
        good_feed = (feed_code == 0 and feed_status.get("status") in {
            "FEED_METADATA_TRIAGE_READY", "RECOVERED_FROM_DURABLE_CHECKPOINT",
            "NOT_DUE", "NO_PENDING_REPLAY",
        })
        good_gold = gold_code == 0 and gold_status.get("status") in {
            "NEW_VERIFIED_RSS_CANDIDATES_FROZEN",
            "NO_NEW_VERIFIED_RSS_CANDIDATES",
        }
        return (0 if good_feed and good_gold else 4), {
            "status": ("MOTIR_SECTOR_SOURCE_AND_GOLD_READY"
                       if good_feed and good_gold else "MOTIR_SECTOR_REQUIRES_REVIEW"),
            "provider_id": SOURCE,
            "feed_status": feed_status.get("status", "DATA_UNAVAILABLE"),
            "feed_new_identities": feed_status.get("new_provider_ids", 0),
            "semiconductor_keyword_review_hints": feed_status.get(
                "semiconductor_keyword_review", 0),
            "gold_status": gold_status.get("status", "DATA_UNAVAILABLE"),
            "newly_frozen_gold_candidates": gold_status.get("newly_frozen_cases", 0),
            "total_sector_gold_candidates": gold_status.get("total_pinned_unique_cases"),
            "human_gold_labeled_cases": 0,
            "ai_calls": 0,
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
