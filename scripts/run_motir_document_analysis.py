"""Analyze one licensed RSS-bound article; stdout contains status, never its text."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
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
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.motir_article_binding import consume_motir_article_binding
from newscatalystos.article_company_identity import search_article_identities, ensure_article_identity
from newscatalystos.evidence_archive import _read_once
from newscatalystos.source_share import _json
from newscatalystos.economic_changes import normalized


DEFAULT_IDENTITY_CONFIG = Path.home() / 'Library/Application Support/NewsCatalystOS/company_identity.json'


def generate_identity(opts, binding, registry, *, now=None):
    config=getattr(opts,'company_identity_config',None)
    if config is None or not Path(config).exists():return None,'NOT_CONFIGURED'
    settings=_json(_read_once(Path(config),8192),'company identity configuration')
    if not isinstance(settings,dict) or set(settings)!={'era_root','era_report','independent_anchor'}:
        raise SourceShareError('invalid company identity configuration')
    paths={k:Path(v) for k,v in settings.items()}
    if any(not p.is_absolute() or '..' in p.parts for p in paths.values()):
        raise SourceShareError('absolute filing snapshot paths required')
    return ensure_article_identity(opts.archive_root,binding,registry,
        opts.analysis_root.parent/'company_identity',**paths,now=now)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binding-path", type=Path, required=True)
    p.add_argument("--binding-sha256", required=True)
    p.add_argument("--archive-root", type=Path, required=True)
    p.add_argument("--article-registry", type=Path, required=True)
    p.add_argument("--analysis-root", type=Path, required=True)
    p.add_argument("--company-identity-config", type=Path, default=DEFAULT_IDENTITY_CONFIG)
    p.add_argument("--model-config", type=Path)
    p.add_argument("--ai-ledger", type=Path)
    p.add_argument("--allow-paid", action="store_true")
    p.add_argument("--analyze-existing", action="store_true")
    p.add_argument("--semantic-ai", action="store_true")
    return p


def evaluate(opts, *, opener=None, now=None):
    try:
        registry=_registry(opts.article_registry)
        binding=consume_motir_article_binding(opts.binding_path,opts.binding_sha256,now=now)
        identity=None
        try:
            identity,generation_status=generate_identity(opts,binding,registry,now=now)
        except (SourceShareError,OSError,ValueError,TypeError,KeyError):
            generation_status='UNAVAILABLE'
        identity_status='NOT_AVAILABLE'
        try:
            if generation_status=='NOT_CONFIGURED':
                identities=search_article_identities(opts.analysis_root.parent/'company_identity',
                    as_of=now or datetime.now(timezone.utc))
                identity=next((r for r in identities if r['archive_version']==binding['archive_version']
                    and r['document_sha256']==binding['document_sha256'] and r['source_url']==binding['source_url']),None)
            if identity:
                identity_status='READY'
            elif generation_status=='UNAVAILABLE':identity_status='UNAVAILABLE'
        except (SourceShareError,OSError,ValueError,TypeError,KeyError):
            identity=None
            identity_status='UNAVAILABLE'
        report = analyze_motir_document(opts.binding_path, opts.binding_sha256,
            opts.archive_root, registry, opts.analysis_root,
            model=read_model_config(opts.model_config), ai_ledger=opts.ai_ledger,
            allow_paid=opts.allow_paid, analyze_existing=opts.analyze_existing,
            semantic_ai=getattr(opts, 'semantic_ai', False),
            opener=opener, now=now, company_names=[r['source_name'] for r in (identity or {}).get('matches',[]) if len(r['source_name'])<=120])
        if identity:report['company_identity']=identity
        path, digest = publish_motir_document_analysis(report, opts.analysis_root / "reports")
        mapped={normalized(r['source_name']):r for r in (identity or {}).get('matches',[])}
        observations = [economic_observation(change,
            origin_reference=report["source_url"], source_url=report["source_url"],
            source_id="motir-official-press", source_available_at=report["source_available_at"],
            source_binding={"source_event_sha256":binding["archive_version"],
                            "document_sha256":report["document_sha256"]},
            **({'company_mappings':[{'source_name':n,'entity_id':mapped[normalized(n)]['entity_id'],
                    'evidence_sha256':mapped[normalized(n)]['evidence_sha256']}
                   for n in change['entity_ids'] if normalized(n) in mapped]} if identity else {}))
            for change in report.get("economic_changes", [])]
        themes = ThemeStore(opts.analysis_root.parent / "theme_history").ingest(observations, now=now) if observations else []
        failed = opts.allow_paid and (report["ai_eligible"] or opts.analyze_existing) and report["ai_status"] not in ("CACHE_HIT", "ANALYZED_UNVERIFIED")
        return (4 if failed else 0), {k: report[k] for k in (
            "status", "content_scope", "ai_status", "ai_eligible", "new_ai_results",
            "cache_hits", "source_fetch_calls", "verified_new_economic_event", "ai_adapter_attempted"
        )} | {"private_report_file": str(path), "report_sha256": digest,
              "economic_changes": len(observations), "theme_versions_created": len(themes),
              "company_identity_status":identity_status,
              "company_identity_generation":generation_status}
    except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
        return 4, {"status": "MOTIR_DOCUMENT_ANALYSIS_UNAVAILABLE",
                   "error_type": type(exc).__name__, "source_fetch_calls": 0}


def main(argv=None):
    code, status = evaluate(parser().parse_args(argv))
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
