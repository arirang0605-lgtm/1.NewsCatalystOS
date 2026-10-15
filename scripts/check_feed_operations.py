"""6_5 one-shot read-only check of recorded private source triage sessions.

Does not start a scheduler, fetch a URL, alter EraLeader, or certify five
actual exchange trading days. Reports only SHA/PIT-checked local receipts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

from newscatalystos.feed_operations import operation_status
from newscatalystos.provider_registry import MAX_BYTES, parse_provider_registry
from newscatalystos.source_share import SourceShareError, _read_regular


def parser() -> argparse.ArgumentParser:
    base = Path.home() / "Library" / "Application Support" / "NewsCatalystOS"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", type=Path, default=base / "providers" / "authorized_sources.json")
    p.add_argument("--inbox-root", type=Path, default=base / "inbox" / "feed_triage")
    p.add_argument("--state", type=Path, default=base / "state" / "incremental_feeds.sqlite3")
    p.add_argument("--physical-pin-root", type=Path,
                   default=None)
    p.add_argument("--backup-root", type=Path,
                   default=None)
    return p


def _registry(path: Path):
    try:
        info, parent = path.lstat(), path.parent.lstat()
    except OSError as exc:
        raise SourceShareError("private provider configuration unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or path.is_symlink()
            or not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise SourceShareError("private provider configuration only")
    return parse_provider_registry(_read_regular(path, MAX_BYTES))


def main(argv: list[str] | None = None) -> int:
    opts = parser().parse_args(argv)
    try:
        report = operation_status(_registry(opts.registry),
                                  opts.inbox_root, opts.state,
                                  physical_pin_root=opts.physical_pin_root,
                                  backup_root=opts.backup_root)
        code = 0
    except (SourceShareError, OSError, ValueError) as exc:
        code, report = 4, {"status": "OPERATIONS_EVIDENCE_UNAVAILABLE",
                           "error_type": type(exc).__name__,
                           "five_trading_day_operation_certified": False,
                           "v1_release_ready": False}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
