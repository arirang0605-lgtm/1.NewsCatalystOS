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
from newscatalystos.official_filing_context import read_pinned_filing_context
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
    p.add_argument("--with-pinned-issuer-context", action="store_true",
                   help="read only previously anchored EraLeader DART/SEC raw metadata")
    p.add_argument("--era-root", type=Path)
    p.add_argument("--era-report", type=Path)
    p.add_argument("--independent-anchor", type=Path)
    p.add_argument("--issuer-contains", help="literal company-name filter; not issuer certification")
    p.add_argument("--title-contains", help="literal provider filing heading filter")
    p.add_argument("--filing-form", help="exact SEC form (e.g. 10-Q)")
    p.add_argument("--output-root", type=Path,
                   default=Path(__file__).resolve().parent.parent / "output")
    return p


def evaluate(args: argparse.Namespace, *,
             now: datetime | None = None) -> tuple[int, dict]:
    try:
        with_context = bool(getattr(args, "with_pinned_issuer_context", False))
        era_root, era_report, independent_anchor = (
            getattr(args, "era_root", None), getattr(args, "era_report", None),
            getattr(args, "independent_anchor", None),
        )
        issuer_contains, title_contains, filing_form = (
            getattr(args, "issuer_contains", None), getattr(args, "title_contains", None),
            getattr(args, "filing_form", None),
        )
        if with_context:
            if not all((era_root, era_report, independent_anchor)):
                raise SourceShareError("all independent Era first-capture paths required")
        elif (any((era_root, era_report, independent_anchor))
              or any(v is not None for v in (
                  issuer_contains, title_contains, filing_form))):
            raise SourceShareError("issuer metadata filters require pinned Era first captures")
        # Read first and stamp verification completion only after read finished.
        started = now or datetime.now(timezone.utc)
        published = read_published_observations(
            args.publication, args.publication_root, args.payload_sha256,
            started, now=started,
        )
        context = (read_pinned_filing_context(
            era_root, era_report, independent_anchor, now=now,
        ) if with_context else None)
        checked = now or datetime.now(timezone.utc)
        observations = project_operational_observations(
            published, checked, now=checked,
        )
        queue = build_official_review_queue(
            observations, decision_at=checked, source_id=args.source_id,
            offset=args.offset, limit=args.limit,
            document_id=args.document_id, now=checked,
            filing_context=context, issuer_contains=issuer_contains,
            title_contains=title_contains, filing_form=filing_form,
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
        "issuer_context_verified": bool(context is not None),
        "screening_mode": ("PINNED_CAPTURE_METADATA_ONLY" if context is not None
                           else "DOCUMENT_IDS_ONLY"),
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
