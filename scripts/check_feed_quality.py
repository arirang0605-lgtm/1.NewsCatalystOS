"""Private NewsCatalystOS collection freshness + pending incident report.

No network calls. Only aggregate source states are printed, no headlines,
personal data, auth tokens or third-party article bodies.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import stat

from newscatalystos.quality_watch import check_sources, unresolved_count
from newscatalystos.source_share import SourceShareError, _read_regular
from newscatalystos.provider_registry import MAX_BYTES, parse_provider_registry


def default_state() -> Path:
    return Path.home() / "Library" / "Application Support" / "NewsCatalystOS" / "state" / "incremental_feeds.sqlite3"


def _registry(path: Path):
    try:
        info, parent = path.lstat(), path.parent.lstat()
    except OSError as exc:
        raise SourceShareError("private provider registry missing") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077 or path.is_symlink()
            or not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise SourceShareError("private provider registry unsafe")
    return parse_provider_registry(_read_regular(path, MAX_BYTES))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=default_state())
    parser.add_argument("--freshness-seconds", type=int, default=14400)
    args = parser.parse_args(argv)
    try:
        providers = _registry(args.registry)
        findings = check_sources(
            providers, args.state, freshness_seconds=args.freshness_seconds
        )
        pending = unresolved_count(args.state)
        report = {
            "status": "QUALITY_DEGRADED" if pending else "QUALITY_OK",
            "pending_count": pending,
            "sources": [
                {"provider_id": x.provider_id, "status": x.status,
                 "gap_seconds": x.gap_seconds, "queue": x.queue_status}
                for x in findings
            ],
            "certified_raw_event_count": 0,
        }
        code = 4 if pending else 0
    except (SourceShareError, OSError, ValueError) as exc:
        report = {"status": "DATA_UNAVAILABLE",
                  "error_type": type(exc).__name__, "pending_count": None}
        code = 4
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
