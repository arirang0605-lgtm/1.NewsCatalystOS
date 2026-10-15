"""Read one private source-reported candidate with its separately retained SHA."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.source_article_claim import consume_source_article_claim
from newscatalystos.source_share import SourceShareError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", required=True, type=Path)
    p.add_argument("--expected-sha256", required=True)
    opts = p.parse_args(argv)
    try:
        claim = consume_source_article_claim(opts.path, opts.expected_sha256)
    except (SourceShareError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "SOURCE_ARTICLE_CLAIM_UNAVAILABLE",
                          "error_type": type(exc).__name__}, sort_keys=True))
        return 4
    print(json.dumps(claim, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
