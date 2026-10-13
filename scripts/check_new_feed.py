"""Check one operator-approved non-EraLeader RSS/JSON feed, metadata only.

Requires an existing owner-private registry file. No persistent jobs, source
secrets, article bodies, or provider auto-enrollment. Returns exit 4 on failure.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat

from newscatalystos.feed_transport import fetch_authorized_once
from newscatalystos.provider_registry import MAX_BYTES, parse_provider_registry
from newscatalystos.source_share import SourceShareError, _read_regular


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--provider-id", required=True)
    return p


def evaluate(args: argparse.Namespace) -> dict:
    path = Path(args.registry)
    try:
        info = path.lstat()
    except OSError as exc:
        raise SourceShareError("private provider registry unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("private provider registry must be owner-only")
    registry = parse_provider_registry(_read_regular(path, MAX_BYTES))
    rows = fetch_authorized_once(registry, args.provider_id)
    return {
        "status": "OBSERVED_METADATA_ONLY",
        "provider_id": args.provider_id,
        "metadata_count": len(rows),
        "verified_at": rows[0].first_seen_at.isoformat() if rows else None,
        "source_claims_unverified": True,
        "stored_article_body_count": 0,
        "certified_raw_event_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result, code = evaluate(args), 0
    except (SourceShareError, OSError, ValueError) as exc:
        result, code = {
            "status": "DATA_UNAVAILABLE",
            "reason": "PROVIDER_PERMISSION_OR_FEED_FAILED",
            "error_type": type(exc).__name__,
            "certified_raw_event_count": 0,
        }, 4
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
