"""Create an offline owner-private 5_2 disclosure screening worklist.

Previously completed, SHA-checked DART/SEC metadata only. This does NOT
identify semiconductor filings or confirm suppliers. No API calls, no Era writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from newscatalystos.official_review_queue import (
    build_official_review_queue, publish_official_review_queue,
)
from newscatalystos.operational_observations import project_operational_observations
from newscatalystos.published_observations import read_published_observations
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publication", type=Path, required=True)
    p.add_argument("--publication-root", type=Path, required=True)
    p.add_argument("--payload-sha256", required=True,
                   help="independently retained official metadata payload SHA")
    p.add_argument("--source-id", default="ALL",
                   choices=("ALL", "dart-disclosures", "sec-submissions"))
    p.add_argument("--document-id", help="select an already observed official filing ID")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--output-root", type=Path,
                   default=Path(__file__).resolve().parent.parent / "output")
    return p


def evaluate(args: argparse.Namespace, *,
             now: datetime | None = None) -> tuple[int, dict]:
    try:
        # Read first and stamp verification completion only after read finished.
        started = now or datetime.now(timezone.utc)
        published = read_published_observations(
            args.publication, args.publication_root, args.payload_sha256,
            started, now=started,
        )
        checked = now or datetime.now(timezone.utc)
        observations = project_operational_observations(
            published, checked, now=checked,
        )
        queue = build_official_review_queue(
            observations, decision_at=checked, source_id=args.source_id,
            offset=args.offset, limit=args.limit,
            document_id=args.document_id, now=checked,
        )
        result = publish_official_review_queue(queue, args.output_root, now=now)
    except (SourceShareError, ValueError, OSError, TypeError) as exc:
        return 4, {"status": "DATA_UNAVAILABLE",
                   "reason": "VERIFIED_PRIVATE_REVIEW_QUEUE_FAILED",
                   "error_type": type(exc).__name__,
                   "verified_relation_count": 0}
    return 0, {
        "status": "RESEARCH_METADATA_REVIEW_QUEUE_READY",
        "queue_path": str(result.location),
        "payload_sha256": result.payload_sha256,
        "item_count": queue.selected_count,
        "total_eligible": queue.total_eligible,
        "source_filter": args.source_id,
        "requested_document_id": args.document_id,
        "industry_relevance_verified_count": 0,
        "verified_relation_count": 0,
        "first_published_at": result.published_at.isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
