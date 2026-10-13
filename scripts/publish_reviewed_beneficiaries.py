"""Publish 5_2 official human review to 5_3-5_5 candidate-only outbox.

Never fetch a DART/SEC filing, write to EraLeader or certify sales. Requires
a previously SHA-pinned completed observation publication and official text
review supplied privately by the authorized operator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from newscatalystos.reviewed_beneficiary_delivery import (
    prepare_reviewed_beneficiary_graph, publish_reviewed_beneficiary_graph,
)
from newscatalystos.semiconductor_profile import CAUSES
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publication", type=Path, required=True)
    p.add_argument("--publication-root", type=Path, required=True)
    p.add_argument("--payload-sha256", required=True)
    p.add_argument("--review-json", type=Path, required=True)
    p.add_argument("--document-text", type=Path, required=True)
    p.add_argument("--document-sha256", required=True)
    p.add_argument("--trigger", required=True, choices=CAUSES)
    p.add_argument("--direction", default="UNKNOWN",
                   choices=("UNKNOWN", "POSITIVE", "NEGATIVE", "MIXED"))
    p.add_argument("--evidence-note",
                   default="Impact direction unverified; independent sales proof missing")
    p.add_argument("--out-root", type=Path,
                   default=Path(__file__).resolve().parent.parent /
                   "output" / "consumer_outbox")
    return p


def evaluate(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        delivery = prepare_reviewed_beneficiary_graph(
            args.publication, args.publication_root, args.payload_sha256,
            args.review_json, args.document_text, args.document_sha256,
            trigger=args.trigger, direction=args.direction,
            evidence_note=args.evidence_note,
        )
        published = publish_reviewed_beneficiary_graph(delivery, args.out_root)
        return 0, {
            "status": "PRIVATE_REVIEWED_CANDIDATE_DELIVERY_READY",
            "outbox_folder": str(published.folder),
            "payload_sha256": published.payload_sha256,
            "reviewed_relation_candidate_count": published.candidate_count,
            "real_transaction_verified_count": 0,
            "real_beneficiary_verified_count": 0,
            "revenue_estimated": False,
            "automatic_external_project_write": False,
            "network_calls": 0,
        }
    except (SourceShareError, ValueError, TypeError, OSError) as exc:
        return 4, {
            "status": "REVIEWED_CANDIDATE_DATA_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "real_transaction_verified_count": 0,
            "real_beneficiary_verified_count": 0,
            "network_calls": 0,
        }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
