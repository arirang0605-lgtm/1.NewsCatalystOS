"""Evaluate 5_6 semiconductor candidate cases from private pinned deliveries and labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from newscatalystos.beneficiary_case_evaluation import evaluate_semiconductor_cases
from newscatalystos.evidence_archive import _read_once
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True, type=Path,
                   help="owner-private JSON with schema and pinned outbox list")
    p.add_argument("--labels", required=True, type=Path,
                   help="owner-private independent case labels JSON")
    return p


def evaluate(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        manifest = json.loads(_read_once(args.manifest, 1_000_000))
        labels = json.loads(_read_once(args.labels, 1_000_000))
        if (not isinstance(manifest, dict)
                or set(manifest) != {"schema", "pins"}
                or manifest["schema"] != "newscatalyst.semiconductor_evaluation_pins.v1"
                or not isinstance(labels, dict)
                or set(labels) != {"schema", "cases"}
                or labels["schema"] != "newscatalyst.semiconductor_case_labels.v1"):
            raise SourceShareError("typed 5_6 input files required")
        return 0, evaluate_semiconductor_cases(manifest["pins"], labels["cases"])
    except (SourceShareError, ValueError, TypeError, OSError) as exc:
        return 4, {"status": "SEMICONDUCTOR_CASE_EVALUATION_UNAVAILABLE",
                   "error_type": type(exc).__name__, "real_case_gate_verified": False}


def main(argv: list[str] | None = None) -> int:
    code, result = evaluate(parser().parse_args(argv))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
