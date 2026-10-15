"""1_3 scheduler-friendly ONCE invocation; no background process installed.

A launchd/cron timer may call this at a reasonable interval. The private
sqlite request ledger enforces limits across invocations and restarts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

from newscatalystos.incremental_ingest import (
    incremental_poll,
)
from newscatalystos.provider_registry import MAX_BYTES, parse_provider_registry
from newscatalystos.source_share import SourceShareError, _read_regular


def default_state() -> Path:
    return (Path.home() / "Library" / "Application Support" /
            "NewsCatalystOS" / "state" / "incremental_feeds.sqlite3")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--provider-id", help="One approved provider")
    p.add_argument("--all-approved", action="store_true",
                   help="One attempt for each due approved provider")
    p.add_argument("--state", type=Path, default=default_state())
    return p


def _registry(path: Path):
    path = Path(path)
    try:
        info = path.lstat()
        parent = path.parent.lstat()
    except OSError as exc:
        raise SourceShareError("private provider registry missing") from exc
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
            or not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise SourceShareError("owner-private provider registry required")
    return parse_provider_registry(_read_regular(path, MAX_BYTES))


def run(args: argparse.Namespace) -> tuple[int, dict]:
    if (args.provider_id is None) == (not args.all_approved):
        raise SourceShareError("select exactly one provider or --all-approved")
    registered = _registry(args.registry)
    now = datetime.now(timezone.utc)
    names = (registered.approved_ids(at=now) if args.all_approved
             else (args.provider_id,))
    results = []
    failed = 0
    for provider in names:
        try:
            result = incremental_poll(registered, provider, args.state)
            results.append({
                "provider_id": provider, "status": result.status,
                "new_count": result.new_count,
                "duplicate_count": result.duplicate_count,
                "certified_raw_event_count": 0,
                "first_usable_at": result.usable_from.isoformat(),
            })
        except SourceShareError as exc:
            # Expected cooldown/limit is normal for a frequent OS scheduler.
            msg = str(exc)
            delayed = ("backoff" in msg or "hourly request budget" in msg)
            if not delayed:
                failed += 1
            results.append({
                "provider_id": provider,
                "status": "NOT_DUE" if delayed else "DATA_UNAVAILABLE",
                "certified_raw_event_count": 0,
            })
    return (4 if failed else 0), {
        "status": "FAILED" if failed else "COMPLETE_OR_NOT_DUE",
        "providers": results, "stored_article_body_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        code, report = run(parser().parse_args(argv))
    except (SourceShareError, OSError, ValueError) as exc:
        code = 4
        report = {"status": "DATA_UNAVAILABLE", "error_type": type(exc).__name__,
                  "certified_raw_event_count": 0, "stored_article_body_count": 0}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
