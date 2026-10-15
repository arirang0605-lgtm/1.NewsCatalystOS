"""Read a pinned private article analysis without network or cache writes."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from newscatalystos.motir_document_analysis import consume_motir_document_analysis
from newscatalystos.source_share import SourceShareError


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    opts = p.parse_args(argv)
    try:
        result = consume_motir_document_analysis(opts.path, opts.expected_sha256)
    except (SourceShareError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "MOTIR_DOCUMENT_ANALYSIS_UNAVAILABLE", "error_type": type(exc).__name__}))
        return 4
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
