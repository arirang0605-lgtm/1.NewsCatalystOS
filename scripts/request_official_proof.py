"""Prepare a research-only request for independent SEC/DART release witnesses.

This does not collect data, trust a signer, register a key, or certify release
time. Output contains metadata hashes/identifiers, not raw filings or secrets.
Treat the JSON as a private request until its sharing scope is independently
approved. Incomplete evidence remains DATA_UNAVAILABLE.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from newscatalystos.proof_request import request_from_era_readonly
from newscatalystos.source_share import SourceShareError, _when


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--era-root", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--anchor", type=Path, required=True)
    p.add_argument("--source-id", choices=["sec-submissions", "dart-disclosures"], required=True)
    p.add_argument("--document-id", required=True)
    p.add_argument("--decision-at", help="ISO timestamp with timezone (default now)")
    return p


def evaluate(args: argparse.Namespace, *, now: datetime | None = None) -> dict:
    instant = now or datetime.now(timezone.utc)
    decision = _when(args.decision_at or instant.isoformat(), "decision_at")
    return request_from_era_readonly(
        args.era_root, args.reference, args.anchor, args.source_id,
        args.document_id, decision, now=instant,
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = evaluate(args)
        code = 0
    except (SourceShareError, OSError, ValueError) as exc:
        code = 4
        result = {
            "status": "DATA_UNAVAILABLE",
            "certified_raw_event_count": 0,
            "reason": "PINNED_CAPTURE_OR_DOCUMENT_NOT_AVAILABLE",
            "error_type": type(exc).__name__,
        }
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
