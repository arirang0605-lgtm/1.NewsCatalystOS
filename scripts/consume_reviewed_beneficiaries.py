"""Standalone read-only handoff consumer for an as-yet-unspecified project.

Requires an expected SHA stored independently by the consumer. Consuming is
local and does not import/edit EraLeader or create trade recommendations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from newscatalystos.reviewed_beneficiary_delivery import (
    consume_reviewed_beneficiary_graph,
)
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph-version", choices=("v1", "v2"), default="v1",
                   help="explicit v2 opt-in for publisher documents; default v1 is unchanged")
    p.add_argument("--folder", type=Path, required=True)
    p.add_argument("--out-root", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True,
                   help="out-of-band retained publisher payload SHA256")
    return p


def evaluate(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        version = getattr(args, "graph_version", "v1")
        if version not in ("v1", "v2"):
            raise SourceShareError("unsupported consumer graph version")
        options = {"graph_version": "v2"} if version == "v2" else {}
        report = consume_reviewed_beneficiary_graph(
            args.folder, args.out_root, args.expected_sha256, **options,
        )
        return 0, report
    except (SourceShareError, ValueError, OSError) as exc:
        return 4, {
            "status": "READONLY_CANDIDATE_DELIVERY_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "real_transaction_verified_count": 0,
            "verified_real_benefit_count": 0,
        }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
