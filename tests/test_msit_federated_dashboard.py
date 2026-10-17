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
from newscatalystos.provider_registry import ProviderRegistry
from scripts.open_research_dashboard import DashboardServer
from scripts.run_feed_triage import _registry
from test_federated_news_search import GOV, collect, fingerprint, setup_workspace
from test_new_source_adapter import registry


def test_core_and_new_msit_have_one_combined_saved_daily_view_and_exact_analysis(tmp_path):
    original=registry().providers[0]
    core_registry=ProviderRegistry((original,))
    msit_registry=ProviderRegistry((replace(
        original, provider_id="msit-official-press",
        endpoint="https://msit.example.org/official/rss"),))
    core=setup_workspace(tmp_path, "core", core_registry)
    msit=setup_workspace(tmp_path, "msit", msit_registry)
    collect(core, core_registry, GOV, [
        ("core-one", "반도체 산업 간담회 개최", "https://gov.example.org/meet/1")
    ])
    collect(msit, msit_registry, "msit-official-press", [
        ("msit-one", "가상반도체 HBM 1조원 공급계약 체결",
         "https://msit.example.org/article/1"),
    ])
    primary=tmp_path / "primary_reports"
    secondary=tmp_path / "msit_reports"
    for source, reg, root, provider in ((core, core_registry, primary, GOV),
                                       (msit, msit_registry, secondary, "msit-official-press")):
        completed=analyze_completed_feed(
            reg, source.inbox_root, source.poll_state, tmp_path / (source.scope+"_facts"),
            provider_id=provider, now=datetime.now(timezone.utc))
        assert len(completed["results"])==1
        published,_=publish_feed_analysis(completed, root/"core"/"reports")
        assert published.is_file()
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
        additional_reports=(("msit",secondary),))
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
        early=datetime.fromisoformat(report["analysis_available_at"])-timedelta(microseconds=1)
        past=get("/api/news-evidence",{
            "q":"반도체","as_of":early.isoformat(),
            **{key:msit_row[key] for key in ("provider_id","event_id","title_sha256")},
        })
        assert past["saved_title_analysis"]["status"]=="N/A"
    finally:
        server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(tmp_path)==before
