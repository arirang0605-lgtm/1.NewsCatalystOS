"""Screen one RSS-bound licensed article for new versus prior investment claims."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.motir_document_screen import (
    prepare_motir_document_screen, publish_motir_document_screen,
)
from newscatalystos.source_share import SourceShareError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binding-path", type=Path, required=True)
    p.add_argument("--binding-sha256", required=True)
    p.add_argument("--archive-root", type=Path, required=True)
    p.add_argument("--out-root", type=Path, required=True)
    opts = p.parse_args(argv)
    try:
        payload = prepare_motir_document_screen(
            opts.binding_path, opts.binding_sha256, opts.archive_root,
        )
        path, digest = publish_motir_document_screen(payload, opts.out_root)
        data = json.loads(payload)
    except (SourceShareError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "MOTIR_DOCUMENT_SCREEN_UNAVAILABLE",
                          "error_type": type(exc).__name__}, sort_keys=True))
        return 4
    print(json.dumps({"status": "MOTIR_DOCUMENT_SCREENED",
                      "path": str(path), "payload_sha256": digest,
                      "findings": data["findings"],
                      "ai_routing_candidate": data["ai_routing_candidate"],
                      "ai_provider_calls": 0,
                      "verified_new_economic_event": False}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
