"""Analyze already committed RSS metadata; no source polling or automatic paid AI.

A model configuration and --allow-paid are both required for OpenAI or
Gemini. API credentials remain in the private process environment.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry
from newscatalystos.ai_provider import AIModel
from newscatalystos.feed_analysis import analyze_completed_feed, publish_feed_analysis
from newscatalystos.official_relation_intake import _private_input
from newscatalystos.evidence_archive import _private_root
from newscatalystos.source_share import SourceShareError, _json
from newscatalystos.economic_changes import normalized
from newscatalystos.theme_emergence import ThemeStore, economic_observation


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--semantic-ai", action="store_true", help="extract source-bounded events with existing Gemini; cache works without --allow-paid")
    p.add_argument("--semantic-call-limit", type=int, default=3)
    p.add_argument("--scope", choices=("core", "motir"), default="core")
    p.add_argument("--industry",choices=("SEMICONDUCTOR","POWER_EQUIPMENT"),default="SEMICONDUCTOR",
                   help="V1 default unchanged; optional power profile requires separate explicit derived roots")
    p.add_argument("--discover-economy",action="store_true",
                   help="find source-stated economic actions first; unknown industry/company stays observable")
    p.add_argument("--new-discovery-only",action="store_true",
                   help="reuse valid prior event-first reports; process only unprocessed title versions")
    p.add_argument("--discovery-offset",type=int,default=0,
                   help="event-first pagination of already stored source titles; never fetches more news")
    p.add_argument("--registry", type=Path)
    p.add_argument("--inbox-root", type=Path)
    p.add_argument("--state", type=Path, help="existing ingestion state, read-only")
    p.add_argument("--analysis-root", type=Path, help="separate derived state and private reports")
    p.add_argument("--theme-root", type=Path, help="existing private economic theme store")
    p.add_argument("--company-identity-config", type=Path, help="existing pinned filing directory configuration")
    p.add_argument("--provider-id")
    p.add_argument("--event-id")
    p.add_argument("--title-sha256")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--model-config", type=Path,
                   help="owner-private AIModel JSON; no key or unverified default live prices")
    p.add_argument("--allow-paid", action="store_true",
                   help="explicitly authorize bounded live AI; ignored for noneligible/duplicate inputs")
    p.add_argument("--analyze-existing", action="store_true",
                   help="analyze one selected article without changing its new-event eligibility")
    p.add_argument("--ai-ledger", type=Path, help="shared monthly cost ledger for all scopes")
    return p


def read_model_config(path: Path | None) -> AIModel | None:
    if path is None:
        return None
    data = _json(_private_input(path, 8192), "private AI model configuration")
    if set(data) != {f.name for f in fields(AIModel)}:
        raise SourceShareError("AI model fields must exclude credentials")
    model = AIModel(**data)
    model.validate()
    return model



def report_observations(report):
    return [economic_observation(change,
                origin_reference=row["source_url"], source_url=row["source_url"],
                source_id=row["provider_id"], source_available_at=row["source_available_at"],
                content_scope="RSS_TITLE_METADATA", source_binding={
                    "source_event_sha256":row["source_event_sha256"],
                    "document_sha256":row["source_title_sha256"]},
                company_mappings=[{k: match[k] for k in ("source_name", "entity_id", "evidence_sha256")}
                    for match in row.get("company_identity", {}).get("matches", [])
                    if normalized(match["source_name"]) in {normalized(n) for n in change["entity_ids"]}] or None)
                for row in report["results"] for change in row.get("economic_changes", [])]


def known_discovery_versions(work,theme_root,at):
    """Reuse the existing SHA/schema/PIT report reader, including empty-event titles."""
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    import re
    root=Path(work)/'reports';known=set()
    stored=ThemeStore(theme_root).search(as_of=at,now=at)
    refs={(r['event_id'],r['source_id'],r['evidence_sha256'],
           r.get('source_binding',{}).get('source_event_sha256'),r['action'],r['phase'])
          for t in stored for r in t['source_refs']}
    if not root.exists():return known
    for path in sorted(root.glob('feed_analysis_*.json')):
        match=re.fullmatch(r'feed_analysis_([0-9a-f]{64})\.json',path.name)
        if not match:continue
        try:
            data=consume_feed_analysis(path,root,match[1],limit=100,now=at)
        except (SourceShareError,OSError,ValueError,TypeError,KeyError):continue
        for row in data['results']:
            if row.get('analysis_industry')=='ECONOMIC_DISCOVERY':
                observations=report_observations({'results':[row]})
                if any((o['event_id'],o['source_id'],o['change']['source_paragraph_sha256'],
                        o.get('source_binding',{}).get('source_event_sha256'),
                        o['change']['action'],o['change']['phase']) not in refs for o in observations):
                    continue  # report may precede an interrupted ThemeStore commit
                known.add((row['provider_id'],row['source_event_sha256'],row['source_title_sha256']))
    return known


def evaluate(opts: argparse.Namespace, *, opener=None, now=None) -> tuple[int, dict]:
    try:
        base = Path.home() / "Library/Application Support/NewsCatalystOS"
        prefix = "motir_" if opts.scope == "motir" else ""
        registry_path = opts.registry or base / "providers" / (prefix + "authorized_sources.json")
        inbox = opts.inbox_root or base / "inbox" / (prefix + "feed_triage")
        state = opts.state or base / "state" / (prefix + "incremental_feeds.sqlite3")
        work = opts.analysis_root or PROJECT / "output" / "feed_analysis" / opts.scope
        standard_roots = {(PROJECT / "output/feed_analysis" / scope).resolve()
                          for scope in ("core", "motir")}
        identity_config = getattr(opts, "company_identity_config", None)
        if identity_config is None and work.resolve() in standard_roots:
            identity_config = base / "company_identity.json"
        industry=getattr(opts,"industry","SEMICONDUCTOR")
        if getattr(opts,"discover_economy",False):
            if industry!="SEMICONDUCTOR":raise SourceShareError("event-first discovery does not select an industry")
            industry="ECONOMIC_DISCOVERY"
        theme_path=getattr(opts,"theme_root",None)
        if industry!="SEMICONDUCTOR":
            if (opts.analysis_root is None or theme_path is None or work.resolve() in standard_roots
                    or Path(theme_path).resolve()==(base/'document_analysis/theme_history').resolve()):
                raise SourceShareError("power analysis requires explicit isolated derived roots")
            theme_path=Path(theme_path)
            marker=theme_path/'industry_profile.json'
            from newscatalystos.feed_analysis import _encoded
            from newscatalystos.evidence_archive import _read_once
            if marker.exists():
                if _read_once(marker,4096)!=_encoded({'industry':industry}):raise SourceShareError('theme industry differs')
            elif theme_path.exists() and any(theme_path.iterdir()):raise SourceShareError('separate empty power theme root required')
        elif theme_path and (Path(theme_path)/'industry_profile.json').exists():
            raise SourceShareError('default analysis cannot use another industry store')
        new_only=getattr(opts,'new_discovery_only',False)
        if new_only and (industry!='ECONOMIC_DISCOVERY' or opts.event_id is not None
                         or opts.title_sha256 is not None or getattr(opts,'discovery_offset',0)):
            raise SourceShareError('new discovery mode requires unpaged event-first selection')
        excluded=known_discovery_versions(work,theme_path,now or datetime.now(timezone.utc)) if new_only else ()
        model = read_model_config(opts.model_config)
        report = analyze_completed_feed(_registry(registry_path), inbox, state, work,
            provider_id=opts.provider_id, event_id=opts.event_id,
            title_sha256=opts.title_sha256, limit=opts.limit, model=model,
            allow_paid=opts.allow_paid, opener=opener, now=now,
            analyze_existing=getattr(opts, "analyze_existing", False),
            ai_ledger=getattr(opts, "ai_ledger", None), company_identity_config=identity_config, semantic_ai=getattr(opts,"semantic_ai",False),
            semantic_call_limit=getattr(opts,"semantic_call_limit",3),
            semantic_scheduled_only=getattr(opts,"semantic_scheduled_only",False),industry=industry,
            discovery_offset=getattr(opts,"discovery_offset",0),
            **({"excluded_versions":excluded} if new_only else {}))
        if new_only:
            report['discovery_selection_scope']='UNPROCESSED_SOURCE_VERSIONS'
            if not report['results']:
                return 0,{**report,'status':'NO_NEW_DISCOVERY_TITLES' if excluded else report['status'],'matched_versions':0,
                    'has_more_results':False,'economic_changes_count':0,'theme_versions_created':0,
                    'reports_published':0}
        failures = sum((row["ai_eligible"] or row.get("analysis_purpose") == "EXISTING_ARTICLE") and row["ai_status"] not in
                       ("ANALYZED_UNVERIFIED", "CACHE_HIT") for row in report["results"])
        if getattr(opts,"semantic_ai",False):
            incomplete = {"UNAVAILABLE","MODEL_UNAVAILABLE","UNSUPPORTED_PROPOSAL",
                          "AI_PREVIOUS_CALL_UNSETTLED","AI_PREVIOUS_RESULT_MISSING"}
            failures=sum(r.get("semantic_analysis",{}).get("status") in incomplete
                         for r in report["results"])
        report["paid_execution_requested"] = opts.allow_paid
        report["requested_ai_complete"] = failures == 0 if opts.allow_paid else None
        # A failed/empty first source has no rows, so analyze_completed_feed
        # returns BEFORE creating its private analysis root. Create that root
        # with 0700 first; otherwise mkdir(parents=True) for the empty report
        # creates an unsafe 0755 ancestor and blocks the next healthy source.
        # This happens after original source/rights/PIT validation above.
        _private_root(work)
        path, digest = publish_feed_analysis(report, work / "reports")
        observations = report_observations(report)
        # Standard installed scopes share the existing document theme store;
        # custom/test analysis roots remain isolated unless explicitly joined.
        theme_root = getattr(opts, "theme_root", None) or (
            base / "document_analysis/theme_history" if work.resolve() in standard_roots
            else work / "theme_history")
        if industry!="SEMICONDUCTOR":
            from newscatalystos.evidence_archive import _write_new
            _private_root(Path(theme_root));marker=Path(theme_root)/'industry_profile.json'
            if not marker.exists():_write_new(marker,_encoded({'industry':industry}))
        themes = ThemeStore(theme_root).ingest(observations, now=now) if observations else []
        identity_resolution={'status':'NOT_CONFIGURED'}
        if identity_config is not None:
            try:
                from newscatalystos.theme_company_identity import resolve_stored_candidates
                identity_resolution={'status':'READY',**resolve_stored_candidates(
                    theme_root,identity_config,Path(theme_root).parent/'theme_company_identity',now=now)}
            except (SourceShareError,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
                identity_resolution={'status':'UNAVAILABLE'}
        return (4 if opts.allow_paid and failures else 0), {
            **report, "private_report_file": str(path), "report_sha256": digest,
            "economic_changes_count":len(observations), "theme_versions_created":len(themes),
            "theme_identity_resolution":identity_resolution}
    except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
        return 4, {"status": "FEED_ANALYSIS_INPUT_UNAVAILABLE", "error_type": type(exc).__name__,
                   "source_fetch_calls": 0,
                   "verified_economic_facts": 0}


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
