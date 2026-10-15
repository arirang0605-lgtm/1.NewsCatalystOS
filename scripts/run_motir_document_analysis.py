"""Analyze one licensed RSS-bound article; stdout contains status, never its text."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry
from scripts.run_feed_analysis import read_model_config
from newscatalystos.motir_document_analysis import analyze_motir_document, publish_motir_document_analysis
from newscatalystos.source_share import SourceShareError


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binding-path", type=Path, required=True)
    p.add_argument("--binding-sha256", required=True)
    p.add_argument("--archive-root", type=Path, required=True)
    p.add_argument("--article-registry", type=Path, required=True)
    p.add_argument("--analysis-root", type=Path, required=True)
    p.add_argument("--model-config", type=Path)
    p.add_argument("--ai-ledger", type=Path)
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--analyze-existing", action="store_true")
    return p


def evaluate(opts, *, opener=None, now=None):
    try:
        report = analyze_motir_document(opts.binding_path, opts.binding_sha256,
            opts.archive_root, _registry(opts.article_registry), opts.analysis_root,
            model=read_model_config(opts.model_config), ai_ledger=opts.ai_ledger,
            allow_paid=opts.allow_paid, analyze_existing=opts.analyze_existing,
            opener=opener, now=now)
        path, digest = publish_motir_document_analysis(report, opts.analysis_root / "reports")
        failed = opts.allow_paid and (report["ai_eligible"] or opts.analyze_existing) and report["ai_status"] not in ("CACHE_HIT", "ANALYZED_UNVERIFIED")
        return (4 if failed else 0), {k: report[k] for k in (
            "status", "content_scope", "ai_status", "ai_eligible", "new_ai_results",
            "cache_hits", "source_fetch_calls", "verified_new_economic_event"
        )} | {"private_report_file": str(path), "report_sha256": digest}
    except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
        return 4, {"status": "MOTIR_DOCUMENT_ANALYSIS_UNAVAILABLE",
                   "error_type": type(exc).__name__, "source_fetch_calls": 0}


def main(argv=None):
    code, status = evaluate(parser().parse_args(argv))
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
