"""Read an independently pinned private MOTIR article/RSS binding."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.motir_article_binding import consume_motir_article_binding
from newscatalystos.source_share import SourceShareError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    opts = p.parse_args(argv)
    try:
        data = consume_motir_article_binding(opts.path, opts.expected_sha256)
    except (SourceShareError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "MOTIR_ARTICLE_RSS_BINDING_UNAVAILABLE",
                          "error_type": type(exc).__name__}, sort_keys=True))
        return 4
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
