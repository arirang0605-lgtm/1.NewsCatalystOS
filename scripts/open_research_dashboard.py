"""Open the private daily/weekly/monthly research dashboard on this Mac only."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
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

from newscatalystos.research_dashboard import KST, NoteStore, build_period, scan_saved_analysis, saved_title_analysis, period_as_of
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore, period_activity, theme_presentation
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.article_company_identity import search_article_identities
from newscatalystos.era_company_assessment import enrich_candidates
from newscatalystos.catalyst_material import materials_for_store, attach_material, default_since
from newscatalystos.era_daily_assessment import enrich_daily, read_latest as read_daily, assessment_for, project_themes
from newscatalystos.theme_changes import compare_themes
from newscatalystos.theme_action_order import order_theme_actions
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.cross_product_period import period_cross_product
from newscatalystos.comparison_export import pack_comparison_export,query_comparison_export
from newscatalystos.theme_company_candidates import inclusion_presentations
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.federated_news_search import TitleSearchWorkspace,search_completed_workspaces
from newscatalystos.news_search_evidence import saved_article_evidence
from newscatalystos.motir_saved_document_evidence import bound_motir_document_evidence
from newscatalystos.news_article_company_context import article_company_context, article_company_excerpt
from scripts.run_feed_triage import _registry
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.company_timeline import company_timelines,select_timelines,timeline_evidence_view
from newscatalystos.timeline_counterevidence import targeted_counterevidence

ASSETS = Path(__file__).resolve().parent / "dashboard_assets"


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, port: int, reports: Path, notes: Path, documents: Path | None = None, *,
                 evidence_base: Path | None = None, news_search_workspaces=None,
                 additional_reports: tuple[tuple[str, Path], ...] = (),
                 msit_source_root: Path | None = None,
                 additional_source_roots: tuple[tuple[str, Path], ...] = ()):
        super().__init__(("127.0.0.1", port), Handler)
        self.reports = reports
        self.documents = documents
        self.evidence_base = evidence_base
        self.news_search_workspaces = news_search_workspaces
        self.additional_reports = additional_reports
        roots = ((("msit", msit_source_root),) if msit_source_root is not None else ())
        roots += additional_source_roots
        if len({scope for scope, _ in roots}) != len(roots):
            raise SourceShareError("duplicate independent source scope")
        self.source_roots = dict(roots)
        self.era_daily_root = (Path(documents)/"era_daily_assessments" if documents else None)
        self.msit_source_root = msit_source_root  # earlier caller compatibility
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
        if url.path=="/api/economic-discovery":
            query=parse_qs(url.query)
            try:
                from newscatalystos.discovery_watch import read_discovery,export_discovery
                from newscatalystos.source_share import _when
                if set(query)-{'as_of','since','export','common_causes'} or any(len(v)!=1 for v in query.values()):
                    raise ValueError('invalid discovery query')
                if query.get('common_causes',['0']) not in (['0'],['1']):
                    raise ValueError('invalid common causes option')
                causes=query.get('common_causes',['0'])==['1']
                now=datetime.now(timezone.utc)
                at=_when(query['as_of'][0],'as of') if 'as_of' in query else now
                since=_when(query['since'][0],'since') if 'since' in query else None
                if not self.server.documents:
                    self._json(503,{'status':'DISCOVERY_NOT_CONFIGURED'});return
                root=self.server.documents/'economic_discovery'
                if query.get('export',['0'])==['1']:
                    self._send(200,export_discovery(root,as_of=at,since=since,now=now,include_common_causes=causes,recent_workspaces=self.server.news_search_workspaces),'application/json; charset=utf-8')
                else:self._json(200,read_discovery(root,as_of=at,since=since,now=now,include_common_causes=causes,recent_workspaces=self.server.news_search_workspaces))
            except (SourceShareError,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
                self._json(400,{'status':'DISCOVERY_INPUT_UNAVAILABLE'})
            return
        if url.path == "/api/news-evidence":
            if self.server.news_search_workspaces is None or self.server.documents is None:
                self._json(503, {"error": "saved article evidence not configured"})
                return
            query = parse_qs(url.query)
            try:
                required = ("q", "provider_id", "event_id", "title_sha256")
                excerpt_keys = ("excerpt_theme_id", "excerpt_entity_id",
                                "excerpt_claim_event_id", "excerpt_evidence_sha256")
                discovery = query.get("discovery", ["0"]) == ["1"]
                history = "since" in query or "theme_id" in query
                excerpt = any(k in query for k in excerpt_keys)
                if (set(query) - set(required) - {"as_of", "since", "theme_id", "discovery", *excerpt_keys}
                        or any(len(query.get(k, [])) != 1 for k in required)
                        or ("as_of" in query and len(query["as_of"]) != 1)
                        or (history and (any(len(query.get(k, [])) != 1
                                                for k in ("as_of", "since", "theme_id"))))
                        or (excerpt and (history or any(
                            len(query.get(k, [])) != 1 for k in excerpt_keys)))):
                    raise ValueError("complete exact article selection required")
                if query.get("discovery", ["0"]) not in (["0"], ["1"]):
                    raise ValueError("invalid discovery evidence option")
                from newscatalystos.source_share import _when
                now = datetime.now(timezone.utc)
                at = (_when(query["as_of"][0], "evidence as of")
                      if "as_of" in query else now)
                exact = tuple(query[k][0] for k in required[1:])
                found = search_completed_workspaces(
                    self.server.news_search_workspaces, query["q"][0],
                    registry_reader=_registry, exact_identity=exact, limit=1, now=now,
                )
                if not found["results"]:
                    self._json(404, {"error": "exact completed source version unavailable"})
                    return
                # The new approved feed has an independent saved ThemeStore.
                # Keep the original theme database immutable; no cross-source
                # merge or promotion based on a similar company/topic name.
                source_scope = found["results"][0]["search_scope"]
                external_root = self.server.source_roots.get(source_scope)
                article_root = (external_root / "document_analysis" if external_root
                                else self.server.documents)
                discovery_reports = None
                if discovery:
                    article_root = self.server.documents / "economic_discovery"
                    folder = "d_" + sha256((source_scope+":"+exact[0]).encode()).hexdigest()[:16]
                    discovery_reports = article_root / "feed_analysis" / folder
                detail = saved_article_evidence(
                    found["results"][0], article_root / "theme_history",
                    as_of=at, now=now,
                )
                detail["source_coverage_complete"] = found["coverage_complete"]
                if found["results"][0].get("acquisition_method") == "MANUAL_METADATA":
                    detail["acquisition_method"] = "MANUAL_METADATA"
                # The saved rule analysis is distinct from a ThemeStore event.
                # One missing or unreadable derived report does not prevent
                # viewing the independent theme or licensed ministry evidence.
                try:
                    if discovery:
                        selected = dict(found["results"][0], search_scope="discovery")
                        detail["saved_title_analysis"] = saved_title_analysis(
                            selected, article_root / "none", as_of=at, now=now,
                            additional_roots=(("discovery", discovery_reports),))
                        detail["analysis_scope"] = "ECONOMIC_DISCOVERY"
                    else:
                        detail["saved_title_analysis"] = saved_title_analysis(
                            found["results"][0], self.server.reports, as_of=at, now=now,
                            additional_roots=self.server.additional_reports)
                except (SourceShareError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                    detail["saved_title_analysis"] = {
                        "status": "N/A", "reason_code": "SAVED_TITLE_ANALYSIS_UNAVAILABLE",
                        "content_scope": "RSS_TITLE_METADATA",
                        "economic_changes": [], "economic_change_status": "N/A",
                        "verified_economic_fact": False, "verified_real_transaction": False,
                        "confirmed_beneficiary": False}
                # Official licensed-body evidence is a separate, later-available
                # source scope, never substituted for RSS title metadata.
                if (self.server.evidence_base is not None
                        and not discovery and found["results"][0]["provider_id"] == "motir-official-press"):
                    try:
                        detail["official_document_evidence"] = bound_motir_document_evidence(
                            found["results"][0],
                            self.server.evidence_base / "document_collection",
                            self.server.documents, self.server.documents / "theme_history",
                            registry_reader=_registry, as_of=at, now=now)
                    except (SourceShareError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                        detail["official_document_evidence"] = {
                            "status": "N/A", "reason_code": "DOCUMENT_EVIDENCE_UNAVAILABLE",
                            "content_scope": "LICENSED_ARTICLE_TEXT",
                            "themes": [], "verified_real_transaction": False,
                            "verified_real_benefit": False, "independent_fact_verified": False}
                # Exact article/theme refs determine membership, never a
                # broad company-name/topic search. Failure remains local.
                try:
                    detail["article_company_context"] = article_company_context(
                        detail, article_root / "theme_history",
                        as_of=at, now=now)
                except (SourceShareError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                    detail["article_company_context"] = {
                        "status": "N/A", "reason_code": "ARTICLE_COMPANY_CONTEXT_UNAVAILABLE",
                        "themes": [], "verified_real_transaction": False,
                        "verified_real_benefit": False, "investment_merit": "NOT_ASSESSED"}
                # News owns material novelty and conditional economic effects.
                # The existing Era financial display is supplemental, not the
                # main direction of the selection pipeline.
                try:
                    material=materials_for_store(ThemeStore(article_root/"theme_history"),
                        since=_when(query['since'][0],'material since') if 'since' in query else default_since(at),
                        as_of=at,scope=source_scope,now=now)
                    for group in detail["article_company_context"].get("themes",[]):
                        value=material.get(group["theme_id"])
                        if not value:continue
                        group["catalyst_material"]=value
                        for party in group["direct_parties"]:
                            party["catalyst_materials"]=[m for m in value["materials"]
                                if party["event_id"] in m["event_ids"]]
                except (SourceShareError,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
                    detail["catalyst_material_status"]="UNAVAILABLE"
                # Optional completed producer evidence enriches the exact
                # article party, never rewrites source identity or the theme.
                if self.server.era_daily_root is not None:
                    try:
                        snap,_=read_daily(self.server.era_daily_root,as_of=at,now=now)
                    except (SourceShareError,OSError,ValueError,TypeError,KeyError):
                        snap=None
                    for group in detail["article_company_context"].get("themes",[]):
                        for party in group["direct_parties"]:
                            party["era_daily_assessment"]=assessment_for(party["entity_id"],snap)
                if discovery:
                    from newscatalystos.discovery_watch import read_discovery
                    from newscatalystos.public_demand_analysis import article_notes
                    if (article_root / "analysis_notes" / "public_demand").exists():
                        view=read_discovery(article_root,as_of=at,now=now,include_common_causes=True,
                            recent_workspaces=self.server.news_search_workspaces)
                        notes=article_notes(view["theme_outlook"],*exact)
                        if notes:detail["public_page_demand_analysis"]=notes
                        from newscatalystos.recent_theme_followups import article_followups
                        recent=article_followups(view["theme_outlook"],*exact)
                        if recent:detail["recent_theme_followup_analysis"]=recent
                if excerpt:
                    from newscatalystos.source_share import _must_sha
                    for key in ("excerpt_theme_id", "excerpt_claim_event_id",
                                "excerpt_evidence_sha256"):
                        _must_sha(query[key][0], key)
                    entity_id = query["excerpt_entity_id"][0]
                    if (not 1 <= len(entity_id) <= 120
                            or any(ord(c) < 32 for c in entity_id)):
                        raise ValueError("invalid exact company selection")
                    try:
                        if external_root is not None:
                            # Extra company/government RSS scopes use metadata
                            # only, never another source's licensed article job.
                            jobs = []
                            extra = external_root
                            feed_sources = [{
                                "registry": extra / "providers/authorized_sources.json",
                                "inbox": extra / "inbox/feed_triage",
                                "state": extra / "state/incremental_feeds.sqlite3"}]
                            reports_root = extra / "feed_analysis"
                        else:
                            feed_sources = jobs = None
                            reports_root = self.server.reports
                        if discovery:
                            reports_root = discovery_reports
                            if feed_sources is None:
                                selected_workspace = next(w for w in self.server.news_search_workspaces if w.scope == source_scope)
                                feed_sources = [{"registry": selected_workspace.registry_path,
                                                 "inbox": selected_workspace.inbox_root,
                                                 "state": selected_workspace.poll_state}]
                                jobs = []
                        detail["article_company_excerpt"] = article_company_excerpt(
                            detail, theme_id=query["excerpt_theme_id"][0],
                            entity_id=entity_id,
                            claim_event_id=query["excerpt_claim_event_id"][0],
                            evidence_sha256=query["excerpt_evidence_sha256"][0],
                            theme_root=article_root / "theme_history",
                            reports_root=reports_root,
                            document_root=article_root,
                            evidence_base=self.server.evidence_base,
                            feeds=feed_sources, jobs=jobs,
                            as_of=at, now=now)
                    except (SourceShareError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                        detail["article_company_excerpt"] = {
                            "status": "N/A",
                            "reason_code": "EXACT_ARTICLE_CLAUSE_UNAVAILABLE",
                            "excerpt": None, "verified_real_transaction": False,
                            "verified_real_benefit": False}
                if history:
                    from newscatalystos.source_share import _must_sha
                    theme_id = _must_sha(query["theme_id"][0], "selected article theme")
                    linked = {x["theme_id"] for x in detail["themes"]}
                    official = detail.get("official_document_evidence", {})
                    if official.get("status") == "READY":
                        linked.update(x["theme_id"] for x in official["themes"])
                    if theme_id not in linked:
                        # Do not use a later-linked article to expose a theme
                        # at an earlier as-of, or enumerate unrelated themes.
                        self._json(404, {"error": "theme not linked to this article as of query"})
                        return
                    start = _when(query["since"][0], "theme period start")
                    timeline = compare_themes(
                        ThemeStore(article_root / "theme_history"),
                        since=start, as_of=at, now=now)
                    change = next((x for x in timeline["ThemeChanges"]
                                   if x["theme_id"] == theme_id), None)
                    detail["theme_change"] = change
                    detail["theme_change_status"] = (
                        "N/A" if change is None
                        else "NO_CHANGE" if (change["activity"] == "unchanged"
                                           and change["reasons"][0]["code"] == "NO_CHANGE")
                        else "READY")
                    detail["theme_change_since"] = start.isoformat()
                self._json(200, detail)
            except (SourceShareError, OSError, ValueError, TypeError, KeyError, sqlite3.Error):
                self._json(400, {"error": "invalid exact saved article evidence query"})
            return
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
                records, source_info = scan_saved_analysis(
                    self.server.reports, document_root=self.server.documents,
                    now=now, as_of=at, additional_roots=self.server.additional_reports)
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
                    data['catalyst_material']={}
                    data['catalyst_material_status']='READY'
                    try:
                        if self.server.documents:
                            data['catalyst_material']=materials_for_store(
                                ThemeStore(self.server.documents/'theme_history'),
                                since=min(start,now),as_of=min(end,now),scope='base',now=now)
                    except (SourceShareError,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
                        data['catalyst_material_status']='UNAVAILABLE'
                    data['common_cause_comparisons']=common_cause_comparisons(data['themes'],data['company_candidates'])
                    data['theme_presentations']={t['theme_id']:theme_presentation(t) for t in data['themes']}
                    try:
                        research=enrich_candidates(data['company_candidates'],self.server.documents/'era_assessments',
                                                   as_of=min(end,now),now=now,
                                                   identity_root=self.server.documents/'theme_company_identity') if self.server.documents else None
                        if research:
                            data['company_candidates']=research['CompanyCandidates']
                            data['assessment_source_status']=research['assessment_source_status']
                        if self.server.era_daily_root is not None:
                            data['company_candidates']=enrich_daily(data['company_candidates'],
                                self.server.era_daily_root,as_of=min(end,now),now=now)
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
                if self.server.documents and (self.server.documents/'economic_discovery').is_dir():
                    try:
                        from newscatalystos.discovery_watch import read_discovery
                        data['economic_discovery']=read_discovery(self.server.documents/'economic_discovery',
                            as_of=min(end,now),since=min(start,now),now=now,include_common_causes=True)
                    except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                        data['economic_discovery']={'status':'UNAVAILABLE','candidates':[]}
                if self.server.source_roots:
                    # Every approved RSS source keeps its own immutable theme
                    # history. Never merge identity merely by matching topic.
                    data["additional_source_themes"] = []
                    data["additional_source_theme_status"] = "READY"
                    for scope, root in self.server.source_roots.items():
                        try:
                            own = ThemeStore(root / "document_analysis/theme_history")
                            selected = (own.search(as_of=min(end,now), now=now,
                                        since=min(start,now), activity=activity)
                                        if activity == "all" or start <= now else [])
                            if selected:
                                payload = json.loads(build_theme_bundle(
                                    selected, decision_at=min(end,now), now=now,
                                    include_company_candidates=True))
                                candidates=payload["CompanyCandidates"]
                                if self.server.era_daily_root is not None:
                                    candidates=enrich_daily(candidates,self.server.era_daily_root,
                                        as_of=min(end,now),now=now)
                                material={};material_status='READY'
                                try:
                                    material=materials_for_store(own,since=min(start,now),
                                        as_of=min(end,now),scope=scope,now=now)
                                except (SourceShareError,OSError,ValueError,TypeError,KeyError,sqlite3.Error):
                                    material_status='UNAVAILABLE'
                                data["additional_source_themes"].append({
                                    "scope": scope, "themes": selected,
                                    "catalyst_material":material,"catalyst_material_status":material_status,
                                    "company_candidates": candidates})
                        except (SourceShareError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                            data["additional_source_theme_status"] = "UNAVAILABLE"
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
        if url.path=="/api/era-assessment":
            query=parse_qs(url.query)
            try:
                from newscatalystos.source_share import _when
                if set(query)-{'entity_id','as_of'} or len(query.get('entity_id',[]))!=1:
                    raise ValueError('one company identity required')
                now=datetime.now(timezone.utc)
                at=_when(query['as_of'][0],'assessment as of') if 'as_of' in query else now
                snap,skipped=(read_daily(self.server.era_daily_root,as_of=at,now=now)
                              if self.server.era_daily_root else (None,0))
                result=assessment_for(query['entity_id'][0],snap)
                result['skipped_invalid_snapshots']=skipped
                self._json(200,result)
            except (SourceShareError,OSError,ValueError,KeyError,TypeError):
                self._json(400,{'error':'invalid assessment query'})
            return
        if url.path in {"/api/themes", "/api/company-research"}:
            query = parse_qs(url.query)
            try:
                from newscatalystos.source_share import _when
                now = datetime.now(timezone.utc)
                at = _when(query["as_of"][0], "as of") if "as_of" in query else now
                # Unfiltered existing receiver URL uses the completed edition
                # once the hourly producer is connected. Explicit analytical
                # filters retain the original live comparison behavior.
                if url.path=='/api/themes' and not query and self.server.documents:
                    from newscatalystos.material_publication import read_published
                    saved=read_published(self.server.documents/'material_outbox',now=now)
                    if saved is not None:
                        self._send(200,saved[1],'application/json; charset=utf-8')
                        return
                if 'publication' in query:
                    if (url.path!='/api/themes' or query['publication']!=['latest']
                            or set(query)-{'publication','as_of'} or len(query.get('as_of',['']))!=1):
                        raise ValueError('published material is an exact immutable edition')
                    from newscatalystos.material_publication import read_published
                    root=(self.server.documents/'material_outbox' if self.server.documents
                          else Path('/nonexistent-ncos-material-outbox'))
                    saved=read_published(root,as_of=at,now=now)
                    if saved is None:
                        self._json(404,{'status':'NO_PUBLISHED_MATERIAL_AS_OF'});return
                    self._send(200,saved[1],'application/json; charset=utf-8')
                    return
                default_scope=("all" if url.path=="/api/themes" and self.server.source_roots
                               and query.get('company_candidates',['0'])==['0'] else "base")
                scope=query.get("scope",[default_scope])[0]
                if (len(query.get("scope",["base"]))!=1 or scope not in {"base","all",*self.server.source_roots}
                        or (url.path=="/api/company-research" and scope!="base")):
                    raise ValueError("invalid export scope")
                if url.path=="/api/themes" and scope!="base":
                    if query.get('company_candidates',['0'])!=['0']:
                        raise ValueError('scoped receiver export uses theme delivery v1/v2')
                    roots={"base":self.server.documents / "theme_history"} if self.server.documents else {}
                    roots.update({key:root/"document_analysis/theme_history" for key,root in self.server.source_roots.items()})
                    snap=(read_daily(self.server.era_daily_root,as_of=at,now=now)[0]
                          if self.server.era_daily_root is not None else None)
                    exported=[]
                    for key,root in roots.items():
                        if scope!="all" and key!=scope:continue
                        selected=ThemeStore(root).search(as_of=at,now=now,query=query.get('q',[''])[0],
                            since=_when(query['since'][0],'period start') if 'since' in query else None,
                            activity=query.get('activity',['all'])[0])
                        # Existing base IDs/payloads remain unchanged for
                        # long-lived receiver histories; appended independent
                        # stores have stable source-qualified IDs.
                        material=materials_for_store(ThemeStore(root),
                            since=_when(query['since'][0],'material since') if 'since' in query else default_since(at),
                            as_of=at,scope=key,now=now)
                        projected=selected if key=="base" else project_themes(selected,key,snap)
                        exported.extend(attach_material(projected,material))
                    payload=build_theme_bundle(exported,decision_at=at,now=now)
                    self._send(200,payload,"application/json; charset=utf-8")
                    return
                themes = (ThemeStore(self.server.documents / "theme_history").search(
                    as_of=at, query='' if url.path=='/api/company-research' else query.get("q", [""])[0], now=now,
                    since=_when(query['since'][0],'period start') if 'since' in query else None,
                    activity=query.get('activity',['all'])[0]) if self.server.documents else [])
                if url.path=="/api/themes" and self.server.documents:
                    material=materials_for_store(ThemeStore(self.server.documents/'theme_history'),
                        since=_when(query['since'][0],'material since') if 'since' in query else default_since(at),
                        as_of=at,scope='base',now=now)
                    themes=attach_material(themes,material)
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
    parser.add_argument("--msit-source-root", type=Path,
                        help="separate, read-only approved MSIT developer RSS reports and receipts")
    parser.add_argument("--additional-source-root", action="append", default=[],
                        metavar="SCOPE=ABSOLUTE_PATH",
                        help="read-only additional approved RSS workspace; repeatable")
    options = parser.parse_args(argv)
    base = options.evidence_base
    workspaces = (
        TitleSearchWorkspace("core", base / "providers/authorized_sources.json",
                             base / "state/incremental_feeds.sqlite3", base / "inbox/feed_triage"),
        TitleSearchWorkspace("motir", base / "providers/motir_authorized_sources.json",
                             base / "state/motir_incremental_feeds.sqlite3", base / "inbox/motir_feed_triage"),
    )
    extras = [("msit", options.msit_source_root)] if options.msit_source_root else []
    for option in options.additional_source_root:
        if option.count("=") != 1:
            parser.error("expected SCOPE=ABSOLUTE_PATH for additional RSS root")
        name, location = option.split("=", 1)
        extras.append((name, Path(location)))
    existing_scopes = {"core", "motir"}
    seen_roots = {base, options.reports_root, options.document_reports_root}
    for scope, root in extras:
        if (not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", scope)
                or scope in existing_scopes or not root.is_absolute()
                or ".." in root.parts or root.resolve() != root or root.is_symlink()
                or any(part.casefold() == "eraleader" for part in root.parts)
                or root in seen_roots):
            parser.error("distinct, absolute, isolated RSS scope root required")
        existing_scopes.add(scope)
        seen_roots.add(root)
        workspaces += (TitleSearchWorkspace(
            scope, root / "providers/authorized_sources.json",
            root / "state/incremental_feeds.sqlite3", root / "inbox/feed_triage"),)
    extra_reports = tuple((scope, root / "feed_analysis") for scope, root in extras)
    server = DashboardServer(options.port, options.reports_root, options.notes_root, options.document_reports_root,
                             evidence_base=base, news_search_workspaces=workspaces,
                             additional_reports=extra_reports,
                             additional_source_roots=tuple(extras))
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
