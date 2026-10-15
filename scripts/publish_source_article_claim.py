"""Publish a source-reported supply candidate from a licensed private article."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.source_article_claim import (
    prepare_source_article_claim, publish_source_article_claim,
)
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_triage import _registry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--archive-root", required=True, type=Path)
    p.add_argument("--archive-version", required=True)
    p.add_argument("--archive-receipt-sha256", required=True)
    p.add_argument("--document-sha256", required=True)
    p.add_argument("--supplier-name", required=True)
    p.add_argument("--customer-name", required=True)
    p.add_argument("--product-stage", required=True)
    p.add_argument("--out-root", required=True, type=Path)
    opts = p.parse_args(argv)
    try:
        payload = prepare_source_article_claim(
            opts.archive_root, opts.archive_version, opts.archive_receipt_sha256,
            opts.document_sha256, _registry(opts.registry),
            supplier_name=opts.supplier_name, customer_name=opts.customer_name,
            product_stage=opts.product_stage,
        )
        path, digest = publish_source_article_claim(payload, opts.out_root)
    except (SourceShareError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "SOURCE_ARTICLE_CLAIM_UNAVAILABLE",
                          "error_type": type(exc).__name__}, sort_keys=True))
        return 4
    print(json.dumps({"status": "SOURCE_REPORTED_CANDIDATE_PUBLISHED",
                      "path": str(path), "payload_sha256": digest,
                      "verified_real_transaction": False,
                      "verified_real_benefit": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
