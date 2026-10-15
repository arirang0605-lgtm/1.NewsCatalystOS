"""Archive one approved ministry press text from an already fetched HTML file.

This command never fetches the page or asserts a verified transaction. The
archived text is an attributed publisher claim available for source-backed
analysis without a separate news-article review.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.evidence_archive import archive_evidence
from newscatalystos.motir_press_document import MAX_HTML_BYTES, extract_motir_press_text
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_triage import _registry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--provider-id", required=True)
    p.add_argument("--html-file", required=True, type=Path)
    p.add_argument("--archive-root", required=True, type=Path)
    opts = p.parse_args(argv)
    try:
        provider = _registry(opts.registry).active(opts.provider_id)
        with opts.html_file.open("rb") as stream:
            html = stream.read(MAX_HTML_BYTES + 1)
        payload = extract_motir_press_text(provider, html)
        doc_id = provider.endpoint.split("/")[-2]
        archived = archive_evidence(
            opts.archive_root, provider, doc_id, payload,
            scope="LICENSED_SOURCE_BYTES",
        )
    except (SourceShareError, OSError, ValueError) as exc:
        print(json.dumps({"status": "MOTIR_PRESS_ARCHIVE_UNAVAILABLE",
                          "error_type": type(exc).__name__}, sort_keys=True))
        return 4
    print(json.dumps({
        "status": "MOTIR_PRESS_TEXT_ARCHIVED_SOURCE_CLAIM_ONLY",
        "source_url": provider.endpoint,
        "attribution": "산업통상부, 공공누리 제1유형, " + provider.endpoint,
        "source_html_sha256": sha256(html).hexdigest(),
        "document_sha256": archived.payload_sha256,
        "archive_version": archived.version_id,
        "archive_receipt_sha256": archived.receipt_sha256,
        "archived_at": archived.archived_at.isoformat(),
        "verified_transaction_count": 0,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
