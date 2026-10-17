"""A separate approved RSS source is visible in existing dashboard/search.

Synthetic committed RSS input, immutable producer reports; no live collection,
cross-provider event merger, body storage, financial recommendation, or AI.
"""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

from newscatalystos.feed_analysis import analyze_completed_feed, publish_feed_analysis
from newscatalystos.federated_news_search import TitleSearchWorkspace
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.news_search import read_completed_title_snapshots
from newscatalystos.provider_registry import ProviderRegistry
from scripts.open_research_dashboard import DashboardServer
from scripts.run_feed_triage import _registry
from test_federated_news_search import GOV, collect, fingerprint, setup_workspace, write_registry
from test_new_source_adapter import registry


def test_core_and_new_msit_have_one_combined_saved_daily_view_and_exact_analysis(tmp_path):
    original=registry().providers[0]
    core_registry=ProviderRegistry((original,))
    msit_registry=ProviderRegistry((replace(
        original, provider_id="msit-official-press",
        endpoint="https://msit.example.org/official/rss"),))
    core=setup_workspace(tmp_path, "core", core_registry)
    msit_root=tmp_path/"msit"
    msit=TitleSearchWorkspace("msit",msit_root/"providers/authorized_sources.json",
                              msit_root/"state/incremental_feeds.sqlite3",
                              msit_root/"inbox/feed_triage")
    write_registry(msit.registry_path,msit_registry)
    collect(core, core_registry, GOV, [
        ("core-one", "반도체 산업 간담회 개최", "https://gov.example.org/meet/1")
    ])
    collect(msit, msit_registry, "msit-official-press", [
        ("msit-one", "가상반도체 HBM 1조원 공급계약 체결",
         "https://msit.example.org/article/1"),
    ])
    primary=tmp_path / "primary_reports"
    secondary=msit_root / "feed_analysis"
    for source, reg, root, provider in ((core, core_registry, primary, GOV),
                                       (msit, msit_registry, secondary, "msit-official-press")):
        completed=analyze_completed_feed(
            reg, source.inbox_root, source.poll_state, tmp_path / (source.scope+"_facts"),
            provider_id=provider, now=datetime.now(timezone.utc))
        assert len(completed["results"])==1
        published,_=publish_feed_analysis(completed, root/"core"/"reports")
        assert published.is_file()
    # An approved headline's preserved economic change already has an
    # ingestion path; the new source's derived theme DB stays separate.
    source_claim = next(x for x in read_completed_title_snapshots(
        msit.inbox_root,msit.poll_state,msit_registry,
        now=datetime.now(timezone.utc))[0][1]["items"]
        if x["headline"].startswith("가상반도체"))
    saved_changes=[row for row in completed["results"] if row["headline"]==source_claim["headline"]][0]["economic_changes"]
    assert saved_changes
    theme_store=ThemeStore(msit_root/"document_analysis/theme_history")
    now=datetime.now(timezone.utc)
    theme_store.ingest([economic_observation(
        change,
        origin_reference=source_claim["canonical_url"],
        source_url=source_claim["canonical_url"],
        source_id="msit-official-press",
        source_available_at=source_claim["available_at"],
        source_binding={"source_event_sha256":source_claim["event_id"],
                        "document_sha256":source_claim["title_sha256"]},
        content_scope="RSS_TITLE_METADATA") for change in saved_changes],now=now)
    assert len(theme_store.search(now=datetime.now(timezone.utc)))>=1
    documents=tmp_path / "documents"
    now=datetime.now(timezone.utc)
    day=now.astimezone(timezone(timedelta(hours=9))).date().isoformat()
    from newscatalystos.research_dashboard import scan_saved_analysis
    rows, info=scan_saved_analysis(primary, as_of=now, now=now,
        additional_roots=(("msit", secondary),))
    assert {r["scope"] for r in rows}=={"core","msit"}
    assert len(rows)==2 and info["saved_reports_skipped"]==0

    server=DashboardServer(0, primary, tmp_path/"notes", documents,
        news_search_workspaces=(core,msit),
        additional_reports=(("msit",secondary),),
        msit_source_root=msit_root)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    before=fingerprint(tmp_path)
    base=f"http://127.0.0.1:{server.server_port}"
    def get(route,params):
        with urlopen(base+route+"?"+urlencode(params),timeout=20) as response:
            assert response.status==200
            return json.load(response)
    try:
        period=get("/api/period",{"view":"day","date":day})
        assert period["counts"]["items"]==2
        assert {i["scope"] for i in period["items"]}=={"core","msit"}
        assert period["additional_source_theme_status"]=="READY"
        groups=period["additional_source_themes"]
        assert len(groups)==1 and groups[0]["scope"]=="msit"
        assert len(groups[0]["themes"])>=1
        assert any("SEMICONDUCTOR" in t["industry_tags"] for t in groups[0]["themes"])
        search=get("/api/news-search",{"q":"반도체","limit":"20"})
        assert search["coverage_complete"]
        assert len(search["results"])==2
        assert {r["search_scope"] for r in search["results"]}=={"core","msit"}
        msit_row=next(r for r in search["results"] if r["search_scope"]=="msit")
        exact=get("/api/news-evidence",{
            "q":"반도체",
            **{key:msit_row[key] for key in ("provider_id","event_id","title_sha256")},
        })
        report=exact["saved_title_analysis"]
        assert report["status"]=="READY"
        assert report["economic_change_status"]=="READY"
        assert any(x["action"]=="CONTRACT" for x in report["economic_changes"])
        assert not report["verified_economic_fact"] and not report["confirmed_beneficiary"]
        assert exact["source_coverage_complete"]
        # The core article shares the "반도체" search term but must never
        # inherit MSIT's separately stored contract/theme/company evidence.
        core_row=next(r for r in search["results"] if r["search_scope"]=="core")
        core_detail=get("/api/news-evidence", {
            "q":"반도체",
            **{key:core_row[key] for key in ("provider_id","event_id","title_sha256")}})
        assert core_detail["status"]=="N/A"
        assert core_detail["article_company_context"]["status"]=="N/A"
        # Source-specific theme and company must not inherit a core theme.
        assert exact["status"]=="READY" and exact["themes"]
        assert all(t["theme_id"] in {g["theme_id"] for g in groups[0]["themes"]}
                   for t in exact["themes"])
        assert exact["article_company_context"]["status"]=="READY"
        parties=[c for t in exact["article_company_context"]["themes"]
                 for c in t["direct_parties"]]
        assert all(p["benefit_status"]=="UNVERIFIED" for p in parties)
        assert not exact["article_company_context"]["verified_real_transaction"]
        assert not exact["article_company_context"]["verified_real_benefit"]
        if parties:
            party=parties[0]
            scoped=exact["article_company_context"]["themes"][0]
            proof=get("/api/news-evidence", {
                "q":"반도체",
                **{key:msit_row[key] for key in ("provider_id","event_id","title_sha256")},
                "excerpt_theme_id":scoped["theme_id"],
                "excerpt_entity_id":party["entity_id"],
                "excerpt_claim_event_id":party["event_id"],
                "excerpt_evidence_sha256":party["evidence_sha256"],
            })
            assert proof["article_company_excerpt"]["status"]=="READY"
            assert not proof["article_company_excerpt"]["verified_real_benefit"]
        early=datetime.fromisoformat(report["analysis_available_at"])-timedelta(microseconds=1)
        past=get("/api/news-evidence",{
            "q":"반도체","as_of":early.isoformat(),
            **{key:msit_row[key] for key in ("provider_id","event_id","title_sha256")},
        })
        assert past["saved_title_analysis"]["status"]=="N/A"
    finally:
        server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(tmp_path)==before


def test_browser_displays_separate_msit_theme_and_source_backed_company():
    """The scoped candidate actually appears in the existing period UI."""
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    script = r'''
const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("scripts/dashboard_assets/app.js","utf8");
const start=src.indexOf("function renderThemes(term){");
const end=src.indexOf("function renderInvestmentStages(parent,links){",start);
assert(start>=0&&end>start);
function el(tag,cls,value){return {tag,className:cls||"",textContent:value||"",children:[],
  append(...xs){this.children.push(...xs)},replaceChildren(...xs){this.children=[...xs]}}}
const items={"themes":el(),"theme-total":el()};
const now="2026-10-17T01:00:00+00:00",link="https://msit.example.org/release/1";
const theme={theme_id:"a".repeat(64),provisional_name:"HBM 공급 계약",
  status:"CANDIDATE",economic_driver:"DEMAND_EXPANSION",first_detected_at:now,
  decision_at:now,scores:{distinct_economic_events:1,company_breadth:1},
  source_refs:[{entity_ids:["가상반도체"],topic:"HBM",action:"CONTRACT",phase:"SOURCE_REPORTED",
    evidence_level:"REPORTED",source_url:link,source_available_at:now,recorded_at:now}]};
const company={theme_id:theme.theme_id,display_name:"가상반도체",
  inclusion_basis:[{kind:"SOURCE_REPORTED_PARTICIPANT",reason:"HBM 계약 보도에 등장한 회사"}]};
const data={themes:[],company_candidates:[],company_search:{candidates:{}},
  additional_source_themes:[{scope:"msit",themes:[theme],company_candidates:[company]}]};
const context={
  currentData:data,$:id=>items[id],node:el,
  matchesTheme:(t,term)=>!term||t.provisional_name.includes(term),
  companySearchResults:()=>({}),
  renderCrossProductDemand:()=>{},renderCompanyTimelines:()=>{},
  economicActionLabels:{CONTRACT:"계약"},
  economicPhaseLabels:{SOURCE_REPORTED:"출처 보도"}
};
vm.runInNewContext(src.slice(start,end),context);
context.renderThemes("HBM");
assert.equal(items["theme-total"].textContent,"1개");
const card=items.themes.children.find(x=>x.tag==="article");
assert(card,"source-owned theme card missing");
function gather(node){return [node.textContent||"",...(node.children||[]).flatMap(gather)]}
const words=gather(card).join(" ");
assert(words.includes("과기정통부"));
assert(words.includes("HBM 공급 계약"));
assert(words.includes("가상반도체"));
assert(words.includes("HBM 계약 보도에 등장한 회사"));
const anchor=card.children.find(x=>x.tag==="details").children.find(x=>x.tag==="a");
assert.equal(anchor.href,link);
assert(words.includes("수혜 미확정"));
context.renderThemes("없는주제");
assert.equal(items["theme-total"].textContent,"0개");
console.log("MSIT source-owned theme and company UI rendered");
'''
    subprocess.run(["node","-e",script],cwd=root,check=True,capture_output=True,text=True)
