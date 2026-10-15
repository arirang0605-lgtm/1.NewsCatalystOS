"""Join one archived public-license article to an existing MOTIR RSS receipt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.motir_article_binding import (
    prepare_motir_article_binding, publish_motir_article_binding,
)
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_triage import _registry


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("feed-registry", "inbox-root", "state", "article-registry",
                 "archive-root", "out-root"):
        p.add_argument("--" + name, type=Path, required=True)
    for name in ("article-provider-id", "archive-version", "archive-receipt-sha256",
                 "document-sha256", "source-event-sha256", "title-sha256"):
        p.add_argument("--" + name, required=True)
    opts = p.parse_args(argv)
    try:
        payload = prepare_motir_article_binding(
            _registry(opts.feed_registry), opts.inbox_root, opts.state,
            _registry(opts.article_registry), opts.article_provider_id,
            opts.archive_root, opts.archive_version, opts.archive_receipt_sha256,
            opts.document_sha256, opts.source_event_sha256, opts.title_sha256,
        )
        path, digest = publish_motir_article_binding(payload, opts.out_root)
    except (SourceShareError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "MOTIR_ARTICLE_RSS_BINDING_UNAVAILABLE",
                          "error_type": type(exc).__name__}, sort_keys=True))
        return 4
    print(json.dumps({"status": "MOTIR_ARTICLE_RSS_BOUND",
                      "path": str(path), "payload_sha256": digest,
                      "new_economic_event_verified": False,
                      "verified_real_transaction": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
