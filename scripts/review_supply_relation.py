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
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.official_relation_intake import (
    read_official_relation_intake, read_publisher_relation_intake,
)
from newscatalystos.official_relation_review import PUBLISHER_RELATION_STATUS
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-kind", choices=("official", "publisher"), default="official")
    p.add_argument("--publication", type=Path)
    p.add_argument("--publication-root", type=Path)
    p.add_argument("--payload-sha256",
                   help="independent private SHA pin for completed observation payload")
    p.add_argument("--review-json", type=Path, required=True)
    p.add_argument("--document-text", type=Path)
    p.add_argument("--document-sha256", required=True,
                   help="independently retained SHA pin, not taken from document")
    p.add_argument("--archive-root", type=Path)
    p.add_argument("--archive-version")
    p.add_argument("--archive-receipt-sha256")
    p.add_argument("--registry", type=Path,
                   help="existing owner-private provider registry with document storage permission")
    return p


def evaluate(args: argparse.Namespace, *, now: datetime | None = None) -> tuple[int, dict]:
    # Production passes now=None so intake stamps the time AFTER reading files.
    # Injected 'now' is reserved for deterministic offline tests.
    try:
        kind = getattr(args, "input_kind", "official")
        if kind == "publisher":
            from scripts.run_feed_triage import _registry
            if (not all(getattr(args, name, None) for name in (
                    "archive_root", "archive_version", "archive_receipt_sha256", "registry"))
                    or any(getattr(args, name, None) is not None for name in (
                        "publication", "publication_root", "payload_sha256", "document_text"))):
                raise SourceShareError("publisher archive inputs required; no filing substitution")
            edge = read_publisher_relation_intake(
                args.archive_root, args.archive_version, args.archive_receipt_sha256,
                args.review_json, args.document_sha256, _registry(args.registry), now=now,
            )
        elif kind == "official":
            if (not all(getattr(args, name, None) for name in (
                    "publication", "publication_root", "payload_sha256", "document_text"))
                    or any(getattr(args, name, None) is not None for name in (
                        "archive_root", "archive_version", "archive_receipt_sha256", "registry"))):
                raise SourceShareError("official filing inputs required")
            edge = read_official_relation_intake(
                args.publication, args.publication_root, args.payload_sha256,
                args.review_json, args.document_text, args.document_sha256, now=now,
            )
        else:
            raise SourceShareError("unknown relation input kind")
    except (SourceShareError, ValueError, TypeError, OSError) as exc:
        return 4, {
            "status": "DATA_UNAVAILABLE",
            "reason": "PRIVATE_DOCUMENT_REVIEW_OR_PIN_VERIFICATION_FAILED",
            "error_type": type(exc).__name__,
            "verified_real_transaction_count": 0,
        }
    return 0, {
        "status": ("PUBLISHER_DOCUMENT_REVIEW_CANDIDATE_ONLY"
                   if edge.evidence_status == PUBLISHER_RELATION_STATUS
                   else "OFFICIAL_DOCUMENT_REVIEW_CANDIDATE_ONLY"),
        "relation_evidence_status": edge.evidence_status,
        "relation_kind": edge.relation_kind,
        "relation_sha256": edge.edge_sha256,
        "review_proof_sha256": edge.review_proof_sha256,
        "usable_from": edge.available_at.isoformat(),
        "verified_real_transaction_count": 0,
        "verified_real_benefit_count": 0,
        "note": "source-backed relation is not evidence of contract performance",
    }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
