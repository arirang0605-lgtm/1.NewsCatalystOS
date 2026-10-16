"""Open the private daily/weekly/monthly research dashboard on this Mac only."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sqlite3
from hashlib import sha256
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit
import webbrowser

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT / "src"))
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.research_dashboard import KST, NoteStore, build_period, scan_saved_analysis, period_as_of
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore, period_activity, theme_presentation
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.article_company_identity import search_article_identities
from newscatalystos.era_company_assessment import enrich_candidates
from newscatalystos.theme_changes import compare_themes
from newscatalystos.theme_action_order import order_theme_actions
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.cross_product_period import period_cross_product
from newscatalystos.comparison_export import pack_comparison_export,query_comparison_export
from newscatalystos.theme_company_candidates import inclusion_presentations
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.federated_news_search import TitleSearchWorkspace,search_completed_workspaces
from scripts.run_feed_triage import _registry
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.company_timeline import company_timelines,select_timelines,timeline_evidence_view
from newscatalystos.timeline_counterevidence import targeted_counterevidence

ASSETS = Path(__file__).resolve().parent / "dashboard_assets"


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, port: int, reports: Path, notes: Path, documents: Path | None = None, *,
                 evidence_base: Path | None = None, news_search_workspaces=None):
        super().__init__(("127.0.0.1", port), Handler)
        self.reports = reports
        self.documents = documents
        self.evidence_base = evidence_base
        self.news_search_workspaces = news_search_workspaces
        self.notes = NoteStore(notes)


class Handler(BaseHTTPRequestHandler):
    def _origin_ok(self) -> bool:
        host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != host:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{host}"

    def _send(self, status: int, body: bytes, kind: str, headers=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; script-src 'self'; "
                         "connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'")
        for key,value in (headers or {}).items():self.send_header(key,value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if not self._origin_ok():
            self._json(403, {"error": "local browser origin required"})
            return
        url = urlsplit(self.path)
        if url.path == "/api/news-search":
            # Existing SHA-acknowledged source metadata only; no network, AI,
            # new search index, body storage, or unverified company promotion.
            if self.server.news_search_workspaces is None:
                self._json(503, {"error": "saved news search not configured"})
                return
            query = parse_qs(url.query)
            try:
                semiconductor_only = query.get("semiconductor_only", ["0"])[0]
                if semiconductor_only not in {"0", "1"}:
                    raise ValueError("invalid semiconductor option")
                result = search_completed_workspaces(
                    self.server.news_search_workspaces, query.get("q", [""])[0],
                    registry_reader=_registry,
                    source_id=query.get("source_id", [None])[0],
                    semiconductor_only=semiconductor_only == "1",
                    limit=int(query.get("limit", ["20"])[0]),
                )
                self._json(200, result)
            except (SourceShareError, OSError, ValueError, TypeError, sqlite3.Error):
                self._json(400, {"error": "invalid saved news search"})
            return
        if url.path=="/api/comparison-export":
            query=parse_qs(url.query)
            try:
                from newscatalystos.source_share import _when
                now=datetime.now(timezone.utc)
                at=_when(query['as_of'][0],'as of')
                root=(self.server.documents/'theme_history') if self.server.documents else Path('/nonexistent-nc-themes')
                payload=query_comparison_export(ThemeStore(root),as_of=at,
                    since=_when(query['since'][0],'since') if 'since' in query else None,
                    activity=query.get('activity',['all'])[0],query=query.get('q',[''])[0],now=now,
                    identity_root=self.server.documents/'theme_company_identity' if self.server.documents else None)
                digest=sha256(payload).hexdigest()
                self._send(200,payload,'application/json; charset=utf-8',{
                    'Content-Disposition':'attachment; filename="comparison_export_'+digest+'.json"','X-Content-SHA256':digest})
            except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                self._json(400,{'error':'invalid pinned comparison query'})
            return
        if url.path == "/api/period":
            query = parse_qs(url.query)
            view = query.get("view", ["day"])[0]
            selected = query.get("date", [datetime.now(KST).date().isoformat()])[0]
            try:
                now = datetime.now(timezone.utc)
                at = period_as_of(view, selected, now=now)
                records, source_info = scan_saved_analysis(self.server.reports, document_root=self.server.documents,
                                                            now=now, as_of=at)
                data = build_period(records, self.server.notes.read(), view, selected,
                                    source_info=source_info, now=now)
                theme_sort=query.get('theme_sort',['latest'])[0]
                if theme_sort not in {'latest','actions'}:raise ValueError('invalid theme sort')
                timeline_activity=query.get('timeline_activity',['all'])[0]
                if timeline_activity not in {'all','observed'}:raise ValueError('invalid timeline activity')
                activity=query.get('theme_activity',['all'])[0]
                if activity not in {'all','changed','new','updated'}:raise ValueError('invalid theme activity')
                start = datetime.fromisoformat(data['start']).replace(tzinfo=KST)
                end = datetime.fromisoformat(data["end"]).replace(tzinfo=KST) + timedelta(days=1) - timedelta(microseconds=1)
                try:
                    data['company_identities']=(search_article_identities(self.server.documents/'company_identity',
                        as_of=min(end,now)) if self.server.documents else [])
                    data['company_identity_status']='READY'
                except (SourceShareError,OSError,ValueError,TypeError,KeyError):
                    data['company_identities']=[]
                    data['company_identity_status']='UNAVAILABLE'
                try:
                    data["themes"] = (ThemeStore(self.server.documents / "theme_history").search(
                        as_of=min(end, now), now=now, since=min(start,now), activity=activity)
                        if self.server.documents and (activity=='all' or start<=now) else [])
                    bundle=json.loads(build_theme_bundle(data["themes"], decision_at=min(end, now), now=now,
                                                         include_company_candidates=True))
                    data['company_candidates']=bundle['CompanyCandidates']
                    data['common_cause_comparisons']=common_cause_comparisons(data['themes'],data['company_candidates'])
                    data['theme_presentations']={t['theme_id']:theme_presentation(t) for t in data['themes']}
                    try:
                        research=enrich_candidates(data['company_candidates'],self.server.documents/'era_assessments',
                                                   as_of=min(end,now),now=now,
                                                   identity_root=self.server.documents/'theme_company_identity') if self.server.documents else None
                        if research:
                            data['company_candidates']=research['CompanyCandidates']
                            data['assessment_source_status']=research['assessment_source_status']
                    except (SourceShareError,OSError,ValueError,TypeError,KeyError):
                        data['assessment_source_status']='UNAVAILABLE'
                    data['cross_product_demand']=cross_product_demand(data['themes'],data['company_candidates'],data['common_cause_comparisons'],as_of=min(end,now),since=start,query=query.get('q',[''])[0])
                    if self.server.documents:
                        data['cross_product_demand']=period_cross_product(ThemeStore(self.server.documents/'theme_history'),data['themes'],data['cross_product_demand'],since=start,as_of=min(end,now),now=now,query=query.get('q',[''])[0],identity_root=self.server.documents/'theme_company_identity')
                    if start<=now:
                        export=pack_comparison_export(data['themes'],data['cross_product_demand'],product_comparisons=data['common_cause_comparisons'],as_of=min(end,now),since=start,activity=activity,query=query.get('q',[''])[0],now=now)
                        data['comparison_export']={'query':json.loads(export)['query'],'sha256':sha256(export).hexdigest()}
                    context=company_search_context(data['themes'],data['company_candidates'])
                    data['company_search']={'query':query.get('q',[''])[0],'candidates':match_company_search(context,query.get('q',[''])[0])}
                    timeline=company_timelines(data['themes'],data['company_candidates'],context,data['common_cause_comparisons'],as_of=min(end,now),since=min(start,now))
                    timeline,timeline_context=targeted_counterevidence(ThemeStore(self.server.documents/'theme_history'),data['themes'],timeline,context,as_of=min(end,now),now=now,since=min(start,now),identity_root=self.server.documents/'theme_company_identity') if self.server.documents else (timeline,context)
                    data['timeline_search_context']=timeline_context
                    data['company_timelines']=timeline_evidence_view(select_timelines(timeline,match_company_search(timeline_context,query.get('q',[''])[0]),query.get('q',[''])[0]),timeline_activity)
                    data['company_inclusion_presentations']=inclusion_presentations(data['themes'],data['company_candidates'])
                    data['theme_activity']={row['theme_id']:period_activity(row,start) for row in data['themes']}
                    data['theme_activity_filter']=activity
                    comparison=None
                    data['theme_changes']={}
                    data['theme_changes_status']='NOT_STARTED' if start>now else 'READY'
                    if self.server.documents and start<=now:
                        try:
                            comparison=compare_themes(ThemeStore(self.server.documents/'theme_history'),
                                since=start,as_of=min(end,now),activity=activity,now=now)
                            data['theme_changes']={r['theme_id']:r for r in comparison['ThemeChanges']}
                        except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                            data['theme_changes_status']='UNAVAILABLE'
                    data['themes'],data['theme_order']=order_theme_actions(data['themes'],comparison,data['common_cause_comparisons'],
                        since=start,as_of=min(end,now),mode=theme_sort)
                    data["theme_status"] = "READY"
                except (SourceShareError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                    data["themes"], data["theme_status"] = [], "UNAVAILABLE"
                    data['company_candidates']=[]
                    data['timeline_search_context']={}
                    data['company_timelines']={'status':'UNAVAILABLE','companies':[]}
                    data['common_cause_comparisons']={}
                    data['cross_product_demand']={'status':'UNAVAILABLE','groups':[]}
                    data['company_inclusion_presentations']={}
                    data['company_search']={'query':'','candidates':{}}
                self._json(200, data)
            except (SourceShareError, OSError, ValueError, KeyError, TypeError) as exc:
                self._json(400, {"error": type(exc).__name__})
            return
        if url.path=='/api/company-evidence':
            query=parse_qs(url.query)
            try:
                from newscatalystos.source_share import _when, _must_sha
                from newscatalystos.company_evidence import company_evidence, installed_sources
                now=datetime.now(timezone.utc)
                at=_when(query['as_of'][0],'as of') if 'as_of' in query else now
                theme_id=_must_sha(query['theme_id'][0],'theme')
                entity=query['entity_id'][0]
                if not entity or len(entity)>120:raise ValueError('invalid company')
                themes=ThemeStore(self.server.documents/'theme_history').search(as_of=at,now=now) if self.server.documents else []
                theme=next((t for t in themes if t['theme_id']==theme_id
                            and any(c['entity_id']==entity for c in t['company_links'])),None)
                if theme is None:
                    self._json(404,{'error':'theme/company unavailable as of query'});return
                feeds,jobs=installed_sources(self.server.evidence_base)
                self._json(200,company_evidence(theme,entity,reports_root=self.server.reports,
                    document_root=self.server.documents,feeds=feeds,jobs=jobs,as_of=at,now=now))
            except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                self._json(400,{'error':'evidence unavailable for this query'})
            return
        if url.path=='/api/theme-changes':
            query=parse_qs(url.query)
            try:
                from newscatalystos.source_share import _when
                now=datetime.now(timezone.utc)
                root=self.server.documents/'theme_history' if self.server.documents else Path('/nonexistent-nc-themes')
                data=compare_themes(ThemeStore(root),since=_when(query['since'][0],'period start'),
                    as_of=_when(query['as_of'][0],'period end') if 'as_of' in query else now,
                    query=query.get('q',[''])[0],activity=query.get('activity',['all'])[0],now=now)
                self._json(200,data)
            except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                self._json(400,{'error':'invalid theme change query'})
            return
        if url.path in {"/api/themes", "/api/company-research"}:
            query = parse_qs(url.query)
            try:
                from newscatalystos.source_share import _when
                now = datetime.now(timezone.utc)
                at = _when(query["as_of"][0], "as of") if "as_of" in query else now
                themes = (ThemeStore(self.server.documents / "theme_history").search(
                    as_of=at, query='' if url.path=='/api/company-research' else query.get("q", [""])[0], now=now,
                    since=_when(query['since'][0],'period start') if 'since' in query else None,
                    activity=query.get('activity',['all'])[0]) if self.server.documents else [])
                companies=query.get('company_candidates',['0'])[0]
                if companies not in {'0','1'}:raise ValueError('invalid company candidate option')
                payload=build_theme_bundle(themes, decision_at=at, now=now,
                                           include_company_candidates=companies=='1' or url.path=='/api/company-research')
                if url.path=='/api/company-research':
                    timeline_activity=query.get('timeline_activity',['all'])[0]
                    if timeline_activity not in {'all','observed'}:raise ValueError('invalid timeline activity')
                    root=(self.server.documents/'era_assessments' if self.server.documents else Path('/nonexistent-nc-assessments'))
                    from newscatalystos.theme_company_identity import filter_research
                    research=enrich_candidates(json.loads(payload)['CompanyCandidates'],root,as_of=at,now=now,
                                               identity_root=root.parent/'theme_company_identity')
                    all_candidates=research['CompanyCandidates']
                    all_comparisons=common_cause_comparisons(themes,all_candidates)
                    research['cross_product_demand']=cross_product_demand(themes,all_candidates,all_comparisons,as_of=at,since=_when(query['since'][0],'period start') if 'since' in query else None,query=query.get('q',[''])[0])
                    if self.server.documents:
                        research['cross_product_demand']=period_cross_product(ThemeStore(self.server.documents/'theme_history'),themes,research['cross_product_demand'],since=_when(query['since'][0],'period start') if 'since' in query else None,as_of=at,now=now,query=query.get('q',[''])[0],identity_root=self.server.documents/'theme_company_identity')
                    export=pack_comparison_export(themes,research['cross_product_demand'],product_comparisons=all_comparisons,as_of=at,since=_when(query['since'][0],'since') if 'since' in query else None,activity=query.get('activity',['all'])[0],query=query.get('q',[''])[0],now=now)
                    research['comparison_export']={'query':json.loads(export)['query'],'sha256':sha256(export).hexdigest()}
                    filter_research(research,themes,query.get('q',[''])[0])
                    selected={c['theme_id'] for c in research['CompanyCandidates']}
                    research['common_cause_comparisons']=common_cause_comparisons([t for t in themes if t['theme_id'] in selected],research['CompanyCandidates'])
                    timeline=company_timelines(themes,research['CompanyCandidates'],research['company_search']['candidates'],research['common_cause_comparisons'],as_of=at,since=_when(query['since'][0],'period start') if 'since' in query else None)
                    timeline,timeline_context=targeted_counterevidence(ThemeStore(self.server.documents/'theme_history'),themes,timeline,research['company_search']['candidates'],as_of=at,now=now,since=_when(query['since'][0],'period start') if 'since' in query else None,identity_root=root.parent/'theme_company_identity') if self.server.documents else (timeline,research['company_search']['candidates'])
                    research['timeline_search_context']=timeline_context
                    research['company_timelines']=timeline_evidence_view(select_timelines(timeline,match_company_search(timeline_context,query.get('q',[''])[0]),query.get('q',[''])[0]),timeline_activity)
                    research['company_inclusion_presentations']=inclusion_presentations(themes,research['CompanyCandidates'])
                    payload=json.dumps(research,ensure_ascii=False,allow_nan=False).encode()
                self._send(200, payload,
                           "application/json; charset=utf-8")
            except (SourceShareError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                self._json(400, {"error": "invalid theme query"})
            return
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8")}
        if url.path not in files:
            self._json(404, {"error": "not found"})
            return
        name, kind = files[url.path]
        self._send(200, (ASSETS / name).read_bytes(), kind)

    def do_POST(self) -> None:
        if not self._origin_ok() or self.path != "/api/notes":
            self._json(403, {"error": "local browser origin required"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._json(415, {"error": "JSON required"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 8192:
                raise ValueError("invalid note request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("invalid note request")
            note = self.server.notes.add(data.get("view"), data.get("date"), data.get("text"))
            self._json(201, {"note": note})
        except (SourceShareError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": type(exc).__name__})

    def log_message(self, format: str, *args: object) -> None:
        # Paths and free-text notes must not enter persistent shell logs.
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--reports-root", type=Path,
                        default=PROJECT / "output" / "feed_analysis")
    parser.add_argument("--notes-root", type=Path,
                        default=Path.home() / "Library/Application Support/NewsCatalystOS/dashboard")
    parser.add_argument("--document-reports-root", type=Path,
                        default=Path.home() / "Library/Application Support/NewsCatalystOS/document_analysis")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--evidence-base",type=Path,
                        default=Path.home()/"Library/Application Support/NewsCatalystOS")
    options = parser.parse_args(argv)
    base = options.evidence_base
    workspaces = (
        TitleSearchWorkspace("core", base / "providers/authorized_sources.json",
                             base / "state/incremental_feeds.sqlite3", base / "inbox/feed_triage"),
        TitleSearchWorkspace("motir", base / "providers/motir_authorized_sources.json",
                             base / "state/motir_incremental_feeds.sqlite3", base / "inbox/motir_feed_triage"),
    )
    server = DashboardServer(options.port, options.reports_root, options.notes_root, options.document_reports_root,
                             evidence_base=base, news_search_workspaces=workspaces)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"NewsCatalystOS dashboard: {url}", flush=True)
    if not options.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
