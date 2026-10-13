"""6_5 bounded once-per-invocation scheduling of two explicitly approved feeds.

Each invocation delegates to the existing rate-limited, PIT-safe 1_3->3_5
triage. A macOS launchd agent may run this script repeatedly. No EraLeader
API calls, trading, AI model calls, paid text, or new collector is implemented.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

# Work both when called as "python scripts/..." and imported in pytest.
PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry, evaluate as evaluate_feed, default_state
from newscatalystos.provider_registry import RESERVED
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--provider-id", action="append", required=True)
    p.add_argument("--state", type=Path, default=default_state())
    p.add_argument("--dedup-state", type=Path,
                   default=base / "state" / "triage_exact_index.sqlite3")
    p.add_argument("--inbox-root", type=Path,
                   default=base / "inbox" / "feed_triage")
    p.add_argument("--output-root", type=Path,
                   default=PROJECT / "output")
    operation = p.add_mutually_exclusive_group(required=True)
    operation.add_argument("--once", action="store_true",
                           help="do one scheduled tick; existing 1_3 budget applies")
    operation.add_argument("--dry-run", action="store_true",
                           help="only check authorization, without any feed HTTP/state writes")
    return p


def execute(opts: argparse.Namespace, *, registry_reader=_registry,
            feed_runner=evaluate_feed) -> tuple[int, dict]:
    """Keep an individual provider failure from blocking other approved feeds."""
    selected = tuple(opts.provider_id)
    if (not 1 <= len(selected) <= 10 or len(set(selected)) != len(selected)
            or any(not isinstance(n, str) or n.casefold() in RESERVED
                   or n.casefold().startswith(("krx-", "dart-", "sec-"))
                   for n in selected)):
        return 4, {"status": "INVALID_EXPLICIT_PROVIDER_SELECTION",
                   "providers_checked": 0, "ai_call_count": 0}
    try:
        registered = registry_reader(opts.registry)
        at = datetime.now(timezone.utc)
    except (SourceShareError, OSError, ValueError) as exc:
        return 4, {"status": "PRIVATE_REGISTRY_UNAVAILABLE",
                   "error_type": type(exc).__name__, "providers_checked": 0}
    outcomes = []
    failures = 0
    for name in selected:
        try:
            registered.active(name, at=at)
            if opts.dry_run:
                outcomes.append({"provider_id": name, "status": "AUTHORIZED_NO_REQUEST"})
                continue
            tick_opts = argparse.Namespace(
                registry=opts.registry, provider_id=name, state=opts.state,
                dedup_state=opts.dedup_state, output_root=opts.output_root,
                inbox_root=opts.inbox_root, replay_only=False,
            )
            code, detail = feed_runner(tick_opts)
            status = detail.get("status", "DATA_UNAVAILABLE")
            failures += int(code != 0 or status == "DATA_UNAVAILABLE")
            outcomes.append({
                "provider_id": name, "status": status,
                "new_provider_ids": detail.get("new_provider_ids", 0),
                "semiconductor_keyword_review": detail.get("semiconductor_keyword_review", 0),
            })
        except (SourceShareError, OSError, ValueError):
            failures += 1
            outcomes.append({"provider_id": name, "status": "DATA_UNAVAILABLE"})
    return (4 if failures else 0), {
        "status": ("SCHEDULED_TICK_FAILED" if failures else
                   "DRY_RUN_APPROVED_NO_REQUEST" if opts.dry_run else
                   "SCHEDULED_TICK_COMPLETE_OR_NOT_DUE"),
        "providers_checked": len(selected),
        "providers_failed": failures,
        "providers": outcomes,
        "ai_call_count": 0,
        "stored_article_body_count": 0,
        "official_era_api_request_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    code, summary = execute(parser().parse_args(argv))
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
