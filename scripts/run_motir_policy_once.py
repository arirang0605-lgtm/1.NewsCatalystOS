"""One scheduled sector-policy tick: authorized MOTIR POST -> RSS triage -> analysis.

Separate private source registry, SQLite and inbox.
Existing two-source launchd, EraLeader and project V1.0 tasks are unchanged.
AI uses the existing budgeted adapter; registered licensed bodies run separately.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry, evaluate as triage_once
from scripts.run_scheduled_triage import _analyze_provider, evaluate_analysis
from scripts.prepare_motir_source import ENDPOINT, SOURCE
from newscatalystos.source_share import SourceShareError, _json, _must_sha
from newscatalystos.official_relation_intake import _private_input
from scripts.run_motir_document_analysis import evaluate as evaluate_document
from newscatalystos.motir_document_collection import collect_motir_documents


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    home = Path.home() / "Library/Application Support/NewsCatalystOS"
    p.add_argument("--registry", type=Path,
                   default=home / "providers" / "motir_authorized_sources.json")
    p.add_argument("--state", type=Path,
                   default=home / "state" / "motir_incremental_feeds.sqlite3")
    p.add_argument("--dedup-state", type=Path,
                   default=home / "state" / "motir_triage_exact_index.sqlite3")
    p.add_argument("--inbox-root", type=Path,
                   default=home / "inbox" / "motir_feed_triage")
    p.add_argument("--output-root", type=Path,
                   default=PROJECT / "output" / "motir_policy")
    p.add_argument("--analysis-root", type=Path,
                   default=PROJECT / "output" / "feed_analysis" / "motir")
    p.add_argument("--analysis-limit", type=int, default=100)
    p.add_argument("--analysis-model-config", type=Path,
                   help="model and accounting configuration for cache or authorized AI")
    p.add_argument("--allow-paid-ai", action="store_true",
                   help="enable budgeted AI for eligible events on scheduled ticks")
    p.add_argument("--analysis-ai-ledger", type=Path, help="shared monthly AI cost ledger")
    p.add_argument("--document-collection-root", type=Path,
                   help="enable bounded automatic collection of licensed ministry press text")
    p.add_argument("--document-jobs", type=Path,
                   help="private registered binding/archive jobs; never collects article bodies")
    p.add_argument("--document-analysis-root", type=Path,
                   help="separate private document result/cache root")
    p.add_argument("--document-model-config", type=Path,
                   help="licensed document model/token limits; defaults to the analysis model")
    p.add_argument("--skip-analysis", action="store_true")
    p.add_argument("--replay-only", action="store_true",
                   help="use completed input and recovery checkpoints without source HTTP")
    p.set_defaults(analysis_scope="motir")
    return p


def _analyze_documents(opts, runner, extra_jobs=()):
    jobs_path = getattr(opts, "document_jobs", None)
    jobs = {"schema": "newscatalyst.motir_document_jobs.v1", "jobs": []}
    manifest_error = None
    if jobs_path is not None:
        try:
            jobs = _json(_private_input(jobs_path, 65536), "document jobs")
            if (set(jobs) != {"schema", "jobs"} or jobs["schema"] != "newscatalyst.motir_document_jobs.v1"
                    or type(jobs["jobs"]) is not list or len(jobs["jobs"]) > 20):
                raise SourceShareError("bounded document jobs required")
        except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
            jobs = {"jobs": []}
            manifest_error = {"status": "DOCUMENT_JOBS_UNAVAILABLE", "error_type": type(exc).__name__, "exit_code": 4}
    # Each source is independently bounded at 20; one broken manifest cannot
    # stop automatically collected articles from reaching analysis.
    jobs["jobs"].extend(extra_jobs)
    if not jobs["jobs"] and manifest_error is None:
        return 0, {"status": "NO_REGISTERED_DOCUMENTS", "results": []}
    results = [manifest_error] if manifest_error else []
    seen = set()
    for job in jobs["jobs"]:
        try:
            if not isinstance(job, dict) or set(job) != {"binding_path", "binding_sha256", "archive_root", "article_registry"}:
                raise SourceShareError("invalid document job")
            pin = _must_sha(job["binding_sha256"], "document binding")
            if pin in seen:
                continue
            seen.add(pin)
            paths = {k: Path(job[k]) for k in ("binding_path", "archive_root", "article_registry")}
            if any(not p.is_absolute() or ".." in p.parts for p in paths.values()):
                raise SourceShareError("absolute document input paths required")
            root = getattr(opts, "analysis_root", None) or Path(opts.output_root).parent / "feed_analysis/motir"
            document_root = getattr(opts, "document_analysis_root", None) or Path(root) / "documents"
            args = argparse.Namespace(**paths, binding_sha256=pin,
                analysis_root=Path(document_root) / pin,
                model_config=(getattr(opts, "document_model_config", None)
                              or getattr(opts, "analysis_model_config", None)),
                ai_ledger=getattr(opts, "analysis_ai_ledger", None),
                allow_paid=(getattr(opts, "allow_paid_ai", False)
                            and not getattr(opts, "replay_only", False)),
                analyze_existing=False)
            code, result = runner(args)
            results.append({**result, "exit_code": code})
        except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
            results.append({"status": "MOTIR_DOCUMENT_ANALYSIS_UNAVAILABLE",
                            "exit_code": 4, "error_type": type(exc).__name__})
    failures = sum(row["exit_code"] != 0 for row in results)
    return (4 if failures else 0), {"status": "DOCUMENT_ANALYSIS_PARTIAL" if failures else "DOCUMENT_ANALYSIS_READY",
        "results": results, "new_ai_results": sum(row.get("new_ai_results", 0) for row in results),
        "cache_hits": sum(row.get("cache_hits", 0) for row in results)}


def run_once(opts: argparse.Namespace, *,
             registry_reader=_registry,
             feed_runner=triage_once,
             analysis_runner=evaluate_analysis,
             document_runner=evaluate_document,
             document_collector=collect_motir_documents) -> tuple[int, dict]:
    """Run source collection and automatic analysis."""
    try:
        enabled = not getattr(opts, "skip_analysis", False)
        paid = (enabled and getattr(opts, "allow_paid_ai", False)
                and not getattr(opts, "replay_only", False))
        if paid and getattr(opts, "analysis_model_config", None) is None:
            raise SourceShareError("AI model configuration required")
        limit = getattr(opts, "analysis_limit", 100)
        if enabled and (type(limit) is not int or not 1 <= limit <= 100):
            raise SourceShareError("invalid bounded analysis limit")
        source = registry_reader(opts.registry)
        approved = tuple(source.approved_ids(at=datetime.now(timezone.utc)))
        if approved != (SOURCE,):
            raise SourceShareError("only reviewed MOTIR sector feed permitted")
        provider = source.active(SOURCE)
        if (provider.kind != "GOVERNMENT_POLICY"
                or provider.method != "RSS_POST"
                or provider.endpoint != ENDPOINT
                or provider.allow_full_text_storage):
            raise SourceShareError("sector source rights or exact endpoint unsupported")
        paths = (opts.registry, opts.state, opts.dedup_state, opts.inbox_root,
                 opts.output_root)
        if (not all(Path(p).is_absolute() and ".." not in Path(p).parts
                    and all(part.casefold() != "eraleader" for part in Path(p).parts)
                    for p in paths)
                or opts.state == opts.dedup_state):
            raise SourceShareError("isolated private sector paths required")
        tick = argparse.Namespace(
            registry=opts.registry, provider_id=SOURCE, state=opts.state,
            dedup_state=opts.dedup_state,
            inbox_root=opts.inbox_root, output_root=opts.output_root,
            replay_only=getattr(opts, "replay_only", False),
        )
        try:
            feed_code, feed_status = feed_runner(tick)
        except (SourceShareError, OSError, ValueError) as exc:
            feed_code, feed_status = 4, {"status": "DATA_UNAVAILABLE",
                                        "error_type": type(exc).__name__}
        analysis_code, analysis = (0, {"status": "DISABLED"})
        if enabled:
            analysis_opts = argparse.Namespace(**vars(opts))
            analysis_opts.analysis_scope = "motir"
            if getattr(analysis_opts, "analysis_root", None) is None:
                analysis_opts.analysis_root = Path(opts.output_root).parent / "feed_analysis" / "motir"
            analysis_code, analysis = _analyze_provider(analysis_opts, SOURCE, analysis_runner)
        good_feed = (feed_code == 0 and feed_status.get("status") in {
            "FEED_METADATA_TRIAGE_READY", "RECOVERED_FROM_DURABLE_CHECKPOINT",
            "NOT_DUE", "NO_PENDING_REPLAY",
        })
        document_code, documents = (0, {"status": "DISABLED", "results": []})
        collection = {"status": "DISABLED", "source_fetch_calls": 0, "jobs": []}
        if enabled:
            collection_root = getattr(opts, "document_collection_root", None)
            if collection_root is not None:
                try:
                    collection = document_collector(source, opts.inbox_root, opts.state,
                        collection_root, replay_only=getattr(opts, "replay_only", False))
                except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
                    collection = {"status": "DOCUMENT_COLLECTION_UNAVAILABLE", "jobs": [],
                                  "error_type": type(exc).__name__}
            document_code, documents = _analyze_documents(opts, document_runner, collection.get("jobs", []))
        good_source_analysis = good_feed and analysis_code == 0 and document_code == 0
        good_collection = collection["status"] in {"DISABLED", "DOCUMENT_COLLECTION_READY"}
        good_tick = good_source_analysis and good_collection
        return (0 if good_tick else 4), {
            "status": ("MOTIR_SECTOR_SOURCE_ANALYSIS_READY" if good_tick
                       else "MOTIR_SECTOR_SOURCE_OR_ANALYSIS_UNAVAILABLE"),
            "provider_id": SOURCE,
            "feed_status": feed_status.get("status", "DATA_UNAVAILABLE"),
            "feed_new_identities": feed_status.get("new_provider_ids", 0),
            "semiconductor_keyword_candidates_hints": feed_status.get(
                "semiconductor_keyword_candidates", 0),
            "analysis_enabled": enabled, "analysis": analysis, "documents": documents,
            "document_collection": {k:v for k,v in collection.items() if k != "jobs"},
            "ai_calls": None if paid else 0,
            "new_ai_results": analysis.get("new_ai_results", 0) + documents.get("new_ai_results", 0),
            "era_api_calls": 0,
            "release_gate_verified": False,
        }
    except (OSError, SourceShareError, ValueError, TypeError) as exc:
        return 4, {
            "status": "MOTIR_SECTOR_INPUT_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "era_api_calls": 0,
            "ai_calls": 0, "release_gate_verified": False,
        }


def main(argv: list[str] | None = None) -> int:
    code, status = run_once(parser().parse_args(argv))
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
