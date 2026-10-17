"""An official RSS title's literal capex announcement is a plan, not spent cash."""
from datetime import datetime, timezone
from hashlib import sha256
import json

from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.feed_analysis import analyze_completed_feed, publish_feed_analysis
from newscatalystos.feed_triage import _matched_terms
from newscatalystos.news_search_evidence import saved_article_evidence
from newscatalystos.news_article_company_context import article_company_context, article_company_excerpt
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.federated_news_search import search_completed_workspaces
from scripts.run_feed_triage import _registry
from test_federated_news_search import collect, setup_workspace


TITLE = ("가상반도체, 용인 Y2 ∙ 청주 M17에 54조 원 투자… "
         "AI 시대 메모리 수요 대응 위한 중장기 생산 기반 확보")


def test_issuer_planned_facility_capex_has_literal_source_and_no_execution():
    changes=extract_economic_changes(TITLE)
    assert len(changes)==1
    event=changes[0]
    assert event["action"]=="INVESTMENT"
    assert event["phase"]=="PLANNED"
    assert event["industry_tags"]==["SEMICONDUCTOR"]
    assert event["entity_ids"]==["가상반도체"]
    assert event["verified_economic_effect"] is False
    assert event["source_paragraph_sha256"]==sha256(TITLE.encode()).hexdigest()
    assert len(_matched_terms(TITLE))>=1
    for bad in (
        "가상반도체, 자사주 54조 원 투자… AI 메모리 수요 대응 생산 기반",
        "가상반도체, 54조 원 투자 검토 중… AI 메모리 수요 대응 생산 기반",
        "가상반도체, 54조 원 투자 여부 미확정… AI 메모리 수요 대응 생산 기반",
        "가상반도체, 54조 원 투자 가능성… AI 메모리 수요 대응 생산 기반",
        "가상반도체, 54조 원 투자… AI 메모리 수요 대응",
        "기업들은 생산시설 AI 메모리 수요 대응 위해 54조 원 투자",
        "가상반도체, 54조 원 투자 집행… 메모리 수요 대응 생산 기반",
        "가상반도체, 생산시설 투자 설명회 개최… 메모리 수요 대응",
    ):
        other=extract_economic_changes(bad)
        assert not any(x["action"]=="INVESTMENT" and x["phase"]=="PLANNED" for x in other),bad


def test_approved_corporate_feed_title_reaches_saved_theme_and_company(tmp_path):
    from dataclasses import replace
    from newscatalystos.provider_registry import ProviderRegistry
    from test_new_source_adapter import registry
    original=registry().providers[0]
    provider="synthetic-corporate-press"
    approved=ProviderRegistry((replace(original,provider_id=provider,
        kind="COMPANY_IR",endpoint="https://company.example.org/rss/press"),))
    workspace=setup_workspace(tmp_path,"corporate",approved)
    from datetime import datetime as Clock
    observed=datetime.now(timezone.utc)
    collect(workspace,approved,provider,[("investment-one",TITLE,
        "https://company.example.org/news/investment")],at=observed)
    now=datetime.now(timezone.utc)
    analysis=analyze_completed_feed(_registry(workspace.registry_path),workspace.inbox_root,
       workspace.poll_state,tmp_path/"feed_analysis",provider_id=provider,
       now=now)
    assert len(analysis["results"])==1
    row=analysis["results"][0]
    assert len(row["economic_changes"])==1
    event=row["economic_changes"][0]
    assert event["action"]=="INVESTMENT" and event["phase"]=="PLANNED"
    assert not row["verified_beneficiary"]
    assert row.get("semantic_analysis", {}).get("status") in (None,"NOT_ANALYZED_NO_CALL")
    # Normalized RSS text preserves wording but normalizes ellipsis symbols.
    assert row["headline"]==TITLE.replace("…","...")
    assert event["source_paragraph_sha256"]==row["source_title_sha256"]
    source={"provider_id":provider,"event_id":row["source_event_sha256"],
        "title_sha256":row["source_title_sha256"],
        "source_url":row["source_url"],"source_available_at":row["source_available_at"],
        "headline":row["headline"]}
    observation=economic_observation(event,
        origin_reference=source["source_url"],source_url=source["source_url"],
        source_id=source["provider_id"],source_available_at=source["source_available_at"],
        source_binding={"source_event_sha256":source["event_id"],
                        "document_sha256":source["title_sha256"]},
        content_scope="RSS_TITLE_METADATA")
    corporate_root=workspace.registry_path.parent.parent
    history=ThemeStore(corporate_root/"document_analysis/theme_history")
    history.ingest([observation],now=datetime.now(timezone.utc))
    saved=history.search(now=datetime.now(timezone.utc))
    assert len(saved)==1
    assert saved[0]["status"] in {"CANDIDATE","EMERGING"}
    assert "가상반도체" in saved[0]["entity_ids"]
    doc=saved_article_evidence(source,history.root,now=datetime.now(timezone.utc))
    assert doc["status"]=="READY"
    ctx=article_company_context(doc,history.root,now=datetime.now(timezone.utc))
    assert ctx["status"]=="READY"
    companies=[p for t in ctx["themes"] for p in t["direct_parties"]]
    assert len(companies)==1
    assert companies[0]["source_name"]=="가상반도체"
    assert companies[0]["benefit_status"]=="UNVERIFIED"
    published, report_digest=publish_feed_analysis(analysis,corporate_root/"feed_analysis/core/reports")
    assert sha256(published.read_bytes()).hexdigest()==report_digest
    party=companies[0]
    kwargs=dict(
        theme_id=ctx["themes"][0]["theme_id"],
        entity_id=party["entity_id"],claim_event_id=party["event_id"],
        evidence_sha256=party["evidence_sha256"],
        theme_root=history.root, reports_root=corporate_root/"feed_analysis",
        feeds=[{"registry":workspace.registry_path,
                "inbox":workspace.inbox_root,"state":workspace.poll_state}],
        jobs=[], now=datetime.now(timezone.utc),
    )
    result=article_company_excerpt({"source":source,
        "article_company_context":ctx},**kwargs)
    assert result["status"]=="READY"
    assert "54조 원 투자" in result["excerpt"]
    assert result["content_scope"]=="RSS_TITLE_METADATA"
    assert result["verified_real_transaction"] is False
    assert result["verified_real_benefit"] is False



def test_real_grammar_synthetic_corporate_news_through_http(tmp_path):
    """Original title SHA -> saved rules -> planned capex -> theme/firm on UI API."""
    import threading
    from urllib.parse import urlencode
    from urllib.request import urlopen
    from scripts.open_research_dashboard import DashboardServer
    from newscatalystos.provider_registry import ProviderRegistry
    from dataclasses import replace
    from test_new_source_adapter import registry
    from newscatalystos.feed_analysis import publish_feed_analysis
    from test_federated_news_search import collect, write_registry
    from newscatalystos.federated_news_search import TitleSearchWorkspace

    approved=ProviderRegistry((replace(registry().providers[0],kind="COMPANY_IR",
        provider_id="synthetic-issuer",endpoint="https://issuer.example.org/rss"),))
    root=tmp_path/"corp"
    w=TitleSearchWorkspace("corp",root/"providers/authorized_sources.json",
                           root/"state/incremental_feeds.sqlite3",
                           root/"inbox/feed_triage")
    write_registry(w.registry_path,approved)
    collect(w,approved,"synthetic-issuer",[
        ("one",TITLE,"https://issuer.example.org/news/capex")
    ],at=datetime.now(timezone.utc))
    now=datetime.now(timezone.utc)
    report=analyze_completed_feed(_registry(w.registry_path),w.inbox_root,w.poll_state,
        tmp_path/"facts",provider_id="synthetic-issuer",now=now)
    path,_=publish_feed_analysis(report,root/"feed_analysis/core/reports")
    row,=report["results"]
    event,=row["economic_changes"]
    observation=economic_observation(event,origin_reference=row["source_url"],
        source_url=row["source_url"],source_id="synthetic-issuer",
        source_available_at=row["source_available_at"],
        source_binding={"source_event_sha256":row["source_event_sha256"],
                        "document_sha256":row["source_title_sha256"]},
        content_scope="RSS_TITLE_METADATA")
    ThemeStore(root/"document_analysis/theme_history").ingest(
        [observation],now=datetime.now(timezone.utc))
    server=DashboardServer(0,tmp_path/"empty_reports",tmp_path/"notes",tmp_path/"docs",
        news_search_workspaces=(w,),
        additional_reports=(("corp",root/"feed_analysis"),),
        additional_source_roots=(("corp",root),))
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    base=f"http://127.0.0.1:{server.server_port}"
    def get(route,**params):
        from urllib.request import urlopen
        with urlopen(base+route+"?"+urlencode(params),timeout=15) as response:
            assert response.status==200
            return json.load(response)
    try:
        search=get("/api/news-search",q="메모리")
        assert search["coverage_complete"] and len(search["results"])==1
        item=search["results"][0]
        params={k:item[k] for k in ("provider_id","event_id","title_sha256")}
        detail=get("/api/news-evidence",q="메모리",**params)
        economic=detail["saved_title_analysis"]
        assert economic["status"]=="READY"
        assert len(economic["economic_changes"])==1
        assert economic["economic_changes"][0]["action"]=="INVESTMENT"
        assert economic["economic_changes"][0]["phase"]=="PLANNED"
        assert not economic["verified_real_transaction"]
        assert detail["article_company_context"]["status"]=="READY"
        firms=[p for t in detail["article_company_context"]["themes"]
               for p in t["direct_parties"]]
        assert len(firms)==1 and firms[0]["entity_id"]=="가상반도체"
        assert firms[0]["benefit_status"]=="UNVERIFIED"
        day=datetime.now(timezone.utc).astimezone(
            __import__("datetime").timezone(__import__("datetime").timedelta(hours=9))
        ).date().isoformat()
        period=get("/api/period",view="day",date=day)
        assert period["counts"]["items"]==1
        assert period["additional_source_themes"]
        proof=get("/api/news-evidence",q="메모리",**params,
            excerpt_theme_id=detail["article_company_context"]["themes"][0]["theme_id"],
            excerpt_entity_id=firms[0]["entity_id"],
            excerpt_claim_event_id=firms[0]["event_id"],
            excerpt_evidence_sha256=firms[0]["evidence_sha256"])
        assert proof["article_company_excerpt"]["status"]=="READY"
        assert "54조 원 투자" in proof["article_company_excerpt"]["excerpt"]
    finally:
        server.shutdown();server.server_close();worker.join(2)
