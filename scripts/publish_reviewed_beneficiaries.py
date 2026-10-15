"""Publish 5_2 official source evidence to 5_3-5_5 candidate-only outbox.

Never fetch a DART/SEC filing, write to EraLeader or certify sales. Requires
a previously SHA-pinned completed observation publication and official text
review supplied privately by the authorized operator.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.reviewed_beneficiary_delivery import (
    prepare_reviewed_beneficiary_graph, publish_reviewed_beneficiary_graph,
    prepare_publisher_beneficiary_graph,
)
from newscatalystos.semiconductor_profile import CAUSES
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-kind", choices=("official", "publisher"), default="official")
    p.add_argument("--publication", type=Path)
    p.add_argument("--publication-root", type=Path)
    p.add_argument("--payload-sha256")
    p.add_argument("--archive-root", type=Path)
    p.add_argument("--archive-version")
    p.add_argument("--archive-receipt-sha256")
    p.add_argument("--registry", type=Path)
    p.add_argument("--review-json", type=Path, required=True)
    p.add_argument("--document-text", type=Path)
    p.add_argument("--document-sha256", required=True)
    p.add_argument("--trigger", required=True, choices=CAUSES)
    p.add_argument("--direction", default="UNKNOWN",
                   choices=("UNKNOWN", "POSITIVE", "NEGATIVE", "MIXED"))
    p.add_argument("--evidence-note",
                   default="Impact direction unverified; independent sales proof missing")
    p.add_argument("--out-root", type=Path,
                   default=Path(__file__).resolve().parent.parent /
                   "output" / "consumer_outbox")
    p.add_argument("--theme-root", type=Path,
                   help="Automatically connect the completed graph to this theme store")
    return p


def evaluate(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        kind = getattr(args, "input_kind", "official")
        official_fields = ("publication", "publication_root", "payload_sha256", "document_text")
        publisher_fields = ("archive_root", "archive_version", "archive_receipt_sha256", "registry")
        options = dict(trigger=args.trigger, direction=args.direction, evidence_note=args.evidence_note)
        if kind == "publisher":
            from scripts.run_feed_triage import _registry
            if (not all(getattr(args, key, None) for key in publisher_fields)
                    or any(getattr(args, key, None) is not None for key in official_fields)):
                raise SourceShareError("publisher archive inputs required; no filing substitution")
            delivery = prepare_publisher_beneficiary_graph(
                args.archive_root, args.archive_version, args.archive_receipt_sha256,
                args.review_json, args.document_sha256, _registry(args.registry), **options,
            )
        elif kind == "official":
            if (not all(getattr(args, key, None) for key in official_fields)
                    or any(getattr(args, key, None) is not None for key in publisher_fields)):
                raise SourceShareError("official filing inputs required")
            delivery = prepare_reviewed_beneficiary_graph(
                args.publication, args.publication_root, args.payload_sha256,
                args.review_json, args.document_text, args.document_sha256, **options,
            )
        else:
            raise SourceShareError("unknown relation input kind")
        published = publish_reviewed_beneficiary_graph(delivery, args.out_root)
        result = {
            "status": "PRIVATE_REVIEWED_CANDIDATE_DELIVERY_READY",
            "outbox_folder": str(published.folder),
            "payload_sha256": published.payload_sha256,
            "graph_schema": delivery.graph.schema_version,
            "reviewed_relation_candidate_count": published.candidate_count,
            "real_transaction_verified_count": 0,
            "real_beneficiary_verified_count": 0,
            "revenue_estimated": False,
            "automatic_external_project_write": False,
            "network_calls": 0,
        }
        if getattr(args,"theme_root",None) is not None:
            from newscatalystos.theme_emergence import ThemeStore
            try:
                rows=ThemeStore(args.theme_root).ingest_supply_graph(
                    published.folder,args.out_root,published.payload_sha256,
                    graph_version="v2" if kind=="publisher" else "v1")
                result.update(theme_link_status="REGISTERED",theme_versions_created=len(rows))
            except (SourceShareError,ValueError,TypeError,OSError,sqlite3.Error):
                # A separate destination failure cannot undo a completed publication.
                # connect_theme_supply_chain retries this same pinned publication.
                result.update(theme_link_status="UNAVAILABLE",theme_versions_created=0)
        return 0,result
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
