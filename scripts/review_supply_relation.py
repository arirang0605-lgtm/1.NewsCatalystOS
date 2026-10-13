"""Offline official semiconductor supplier/customer review from private evidence.

This tool never downloads disclosures, writes to EraLeader, or stores document
text. Output contains only SHA and status; verified transactions always 0.
Both SHA pins must come from previously secured records independent of inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from newscatalystos.official_relation_intake import read_official_relation_intake
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publication", type=Path, required=True)
    p.add_argument("--publication-root", type=Path, required=True)
    p.add_argument("--payload-sha256", required=True,
                   help="independent private SHA pin for completed observation payload")
    p.add_argument("--review-json", type=Path, required=True)
    p.add_argument("--document-text", type=Path, required=True)
    p.add_argument("--document-sha256", required=True,
                   help="independently retained SHA pin, not taken from document")
    return p


def evaluate(args: argparse.Namespace, *, now: datetime | None = None) -> tuple[int, dict]:
    # Production passes now=None so intake stamps the time AFTER reading files.
    # Injected 'now' is reserved for deterministic offline tests.
    try:
        edge = read_official_relation_intake(
            args.publication, args.publication_root, args.payload_sha256,
            args.review_json, args.document_text, args.document_sha256,
            now=now,
        )
    except (SourceShareError, ValueError, TypeError, OSError) as exc:
        return 4, {
            "status": "DATA_UNAVAILABLE",
            "reason": "PRIVATE_DOCUMENT_REVIEW_OR_PIN_VERIFICATION_FAILED",
            "error_type": type(exc).__name__,
            "verified_real_transaction_count": 0,
        }
    return 0, {
        "status": "OFFICIAL_DOCUMENT_REVIEW_CANDIDATE_ONLY",
        "relation_sha256": edge.edge_sha256,
        "review_proof_sha256": edge.review_proof_sha256,
        "usable_from": edge.available_at.isoformat(),
        "verified_real_transaction_count": 0,
        "verified_real_benefit_count": 0,
        "note": "human-reviewed relation is not evidence of contract performance",
    }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
