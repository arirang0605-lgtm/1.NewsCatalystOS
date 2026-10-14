"""Offline preview of a short public relation reference, never official approval."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from newscatalystos.public_relation_reference import inspect_public_relation_reference
from newscatalystos.source_share import SourceShareError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-file', type=Path, required=True)
    p.add_argument('--pin-file', type=Path, required=True)
    opts = p.parse_args(argv)
    try:
        report = inspect_public_relation_reference(opts.reference_file, opts.pin_file)
    except (SourceShareError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status': 'PUBLIC_REFERENCE_UNAVAILABLE',
                          'error_type': type(exc).__name__, 'eligible_for_delivery': False,
                          'human_labels_added': 0, 'network_calls': 0, 'ai_calls': 0}))
        return 4
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
