"""Use existing accepted RSS snapshots in the local dashboard; never poll or invent facts."""
import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.open_research_dashboard import DashboardServer
from test_federated_news_search import sample, fingerprint


def _get(base, route, **params):
    with urlopen(base + route + '?' + urlencode(params), timeout=15) as reply:
        return reply.status, json.load(reply)


def test_dashboard_global_completed_news_search_is_read_only(sample, tmp_path, monkeypatch):
    import newscatalystos.feed_transport as transport
    monkeypatch.setattr(transport, 'fetch_authorized_once',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("external fetch")))
    workspaces = sample[0]
    old = fingerprint(tmp_path)
    server = DashboardServer(0, tmp_path / 'reports', tmp_path / 'notes',
                             news_search_workspaces=tuple(workspaces))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        code, result = _get(base, '/api/news-search', q='반도체', limit=2)
        assert code == 200
        assert result['coverage_complete']
        assert result['matched_document_versions'] == 5
        assert result['keyword_hits'] == 2 and result['has_more_matches']
        assert len(result['scopes']) == 2
        assert all(not r['verified_economic_fact']
                   and not r['confirmed_beneficiary']
                   and not r['article_body_included'] for r in result['results'])
        assert result['network_calls'] == result['ai_calls'] == 0
        assert not result['source_databases_modified']
        assert 'FULL ARTICLE BODY NOT FOR STORAGE' not in json.dumps(result)
        assert {r['search_scope'] for r in result['results']} <= {'core','motir'}

        code, only = _get(base, '/api/news-search', q='반도체',
                          semiconductor_only=1, limit=20)
        assert code == 200
        assert only['matched_document_versions'] <= result['matched_document_versions']
        assert all(r['semiconductor_keyword_candidate'] and r['analysis_candidate']
                   for r in only['results'])
        code, old_period = _get(base, '/api/period', view='day', date='2026-10-15')
        assert code == 200 and old_period['counts']['items'] == 0

        for params in ({'q':'a'}, {'q':'반도체', 'limit':0},
                       {'q':'반도체', 'semiconductor_only':'true'}):
            try:
                _get(base, '/api/news-search', **params)
                assert False, 'invalid request accepted'
            except HTTPError as error:
                assert error.code == 400
        req=Request(base+'/api/news-search?'+urlencode({'q':'반도체'}),headers={'Origin':'https://bad.invalid'})
        try:
            urlopen(req)
            assert False, 'foreign origin accepted'
        except HTTPError as error:
            assert error.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
    assert fingerprint(tmp_path) == old


def test_missing_search_config_fails_closed(tmp_path):
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes')
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/period?view=day&date=2026-10-15') as r:
            assert json.load(r)['counts']['items']==0
        try:
            urlopen(f'http://127.0.0.1:{server.server_port}/api/news-search?'+urlencode({'q':'반도체'}))
            assert False, 'missing search config accepted'
        except HTTPError as e:
            assert e.code==503
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_browser_search_renders_source_title_as_plain_text():
    import subprocess
    from pathlib import Path
    root=Path(__file__).resolve().parent.parent
    script=r'''
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert");
const all=fs.readFileSync("scripts/dashboard_assets/app.js","utf8");
const start="function renderSavedArticleThemeEvents(place,themes,caption,articleContext){";
assert(all.includes(start));
const code=all.slice(all.indexOf(start),all.indexOf('$("news-search-form").addEventListener'));
function el(){return {children:[],events:{},value:"",textContent:"",checked:false,
  replaceChildren(...x){this.children=[...x]},append(...x){this.children.push(...x)},
  addEventListener(name,fn){this.events[name]=fn}}}
const elements={"news-search-form":el(),"news-search-query":el(),"news-semiconductor-only":el(),
 "news-search-status":el(),"news-search-results":el()};
elements["news-search-query"].value="반도체";
const seen=[],payload={coverage_complete:true,matched_document_versions:1,keyword_hits:1,has_more_matches:false,results:[
{headline:"<b>반도체 & 테스트</b>",provider_id:"synthetic",event_id:"a".repeat(64),title_sha256:"b".repeat(64),
 source_url:"https://example.org/saved-title",source_available_at:"2026-10-17T00:00:00+00:00",semiconductor_keyword_candidate:true}
]};
const evidence={status:"READY",article_company_context:{
 status:"READY",themes:[{name:"합성 테마",theme_status:"CANDIDATE",industry_supported_in_v1:true,
 direct_parties:[{source_name:"가상전자<img src=x>",entity_id:"가상전자",action:"BUSINESS_START",
 phase:"SOURCE_REPORTED",identity_status:"SOURCE_NAME_ONLY",official_entity_id:null,
 active_in_theme:true,inclusion_status:"READY",inclusion_reasons:["기사와 일치한 사업 개시 근거"],
 source_url:"https://example.org/saved-title",source_available_at:"2026-10-17T00:00:00+00:00",
 recorded_at:"2026-10-17T00:01:00+00:00",benefit_status:"UNVERIFIED"}],
 related_supply_context:[{entity_id:"SEC_CIK:111111",role:"supplier",counterparty_id:"가상전자",
 product_stage:"ADVANCED_PACKAGING",relation_kind:"REPORTED_DIRECT_TRANSACTION",
 impact_category:"POTENTIAL_BENEFICIARY_UNVERIFIED",linked_at:"2026-10-17T00:01:00+00:00",
 source_urls:["https://example.org/separate-official-source"],reported_in_selected_article:false}]}]
 },saved_title_analysis:{
 status:"READY",analysis_available_at:"2026-10-17T00:01:00+00:00",
 report_sha256:"f".repeat(64),reported_plan_only:false,ai_status:"NOT_ELIGIBLE",
 economic_change_status:"READY",economic_changes:[{
 action:"BUSINESS_START",topic:"<img src=x>",phase:"SOURCE_REPORTED",
 economic_driver:"UNKNOWN",evidence_level:"REPORTED",entity_ids:["가상전자"],
 industry_tags:["SEMICONDUCTOR"],source_paragraph_sha256:"b".repeat(64)}]
 },themes:[{name:"합성 테마",status:"CANDIDATE",first_detected_at:"2026-10-17T00:00:00+00:00",decision_at:"2026-10-17T00:00:00+00:00",
 theme_id:"c".repeat(64),events:[{action:"BUSINESS_START",phase:"SOURCE_REPORTED",topic:"반도체",evidence_level:"REPORTED",
 polarity:"SUPPORT",active_in_theme:true,companies:[{entity_id:"가상전자"}],source_url:"https://example.org/saved-title",
 source_available_at:"2026-10-17T00:00:00+00:00",recorded_at:"2026-10-17T00:01:00+00:00"}]}]};
const change={activity:"updated",events:{independent_actions_added:0,independent_actions_removed:0},
 sources:{added:[{source_url:"https://example.org/more"}]},reasons:[{code:"ADDITIONAL_SOURCE",text:"후속 출처 추가"}]};
const ctx={
  $:id=>elements[id],URLSearchParams,
  economicActionLabels:{BUSINESS_START:"사업·서비스 개시"},economicPhaseLabels:{SOURCE_REPORTED:"출처 보도"},
  fetch:async url=>{seen.push(url);return {ok:true,json:async()=>url.includes("since=")?{
    theme_change:change,theme_change_status:"READY"}:url.startsWith("/api/news-evidence")?evidence:payload}},
  node:(tag,cls,value)=>{const e=el();e.tag=tag;e.className=cls;e.textContent=value||"";return e},
  renderThemeChanges:(place,c)=>{const e=el();e.textContent="기존 기간 렌더러 재사용";place.append(e)}
};
vm.runInNewContext(code,ctx);
(async()=>{
 await ctx.searchStoredNews({preventDefault(){}});
 const parent=elements["news-search-results"];assert.equal(parent.children.length,1);
 const article=parent.children[0];
 assert.equal(article.children[0].textContent,payload.results[0].headline);
 assert.equal(article.children[3].href,payload.results[0].source_url);
 assert(article.children[4].events.click);
 assert(seen[0].includes("q=%EB%B0%98%EB%8F%84%EC%B2%B4"));
 await article.children[4].events.click();
 assert(seen[1].startsWith("/api/news-evidence?")&&seen[1].includes("event_id="+"a".repeat(64)));
 const detail=article.children[5];
 const saved=detail.children.find(x=>x.className==="news-evidence-theme");
 assert(saved&&saved.children[0].textContent.includes("제목 경제 변화 분석"));
 assert(saved.children.some(x=>x.children?.some(y=>y.textContent.includes("<img src=x>"))));
 assert(detail.children.some(x=>x.textContent.includes("저장된 동일 기사 판본")));
 assert(detail.children.some(x=>x.children.some(y=>y.textContent.includes("가상전자"))));
 const companyBox=detail.children.find(x=>x.className==="news-evidence-company-context");
 assert(companyBox,"article company context must render");
 const companyCard=companyBox.children.find(x=>x.className==="news-evidence-theme");
 assert(companyCard);
 assert(companyCard.children.some(x=>x.children.some(y=>y.textContent.includes("가상전자<img src=x>"))));
 assert(companyCard.children.some(x=>x.children.some(y=>y.textContent.includes("기사와 일치한 사업 개시 근거"))));
 assert(companyCard.children.some(x=>x.children.some(y=>y.textContent.includes("SEC_CIK:111111"))));
 assert(companyCard.children.some(x=>x.children.some(y=>y.textContent.includes("별도 공급 관계 근거"))));
 const missingCompanies=el();ctx.renderSavedArticleCompanyContext(missingCompanies,{
   status:"N/A",reason_code:"NO_COMPANY_IN_EXACT_ARTICLE_EVENTS",themes:[]});
 assert(missingCompanies.children[0].children.some(x=>x.textContent.includes("기업 당사자")));
 const missing=el();ctx.showSavedNewsEvidence(missing,{status:"N/A",reason_code:"NO_SAVED_EXACT_THEME_EVIDENCE",
   saved_title_analysis:{...evidence.saved_title_analysis,economic_changes:[],economic_change_status:"NO_EXPLICIT_TITLE_CHANGE"}});
 assert(missing.children[0].children.some(x=>x.textContent.includes("명시된 경제 변화 없음")));
 assert(missing.children.some(x=>x.textContent.includes("N/A")));
 const bodyOnly=el();
 ctx.showSavedNewsEvidence(bodyOnly,{status:"N/A",reason_code:"NO_SAVED_EXACT_THEME_EVIDENCE",
   official_document_evidence:{status:"READY",document_sha256:"d".repeat(64),binding_sha256:"e".repeat(64),
     binding_available_at:"2026-10-17T00:00:00+00:00",themes:[{
       ...evidence.themes[0],events:[{...evidence.themes[0].events[0],
         action:"POLICY_CHANGE",topic:"반도체",companies:[]}]}]}});
 assert(bodyOnly.children.some(x=>x.textContent.includes("산업부 허용 공식 본문")));
 assert(bodyOnly.children.some(x=>x.textContent.includes("검증된 공식 본문")));
 assert(bodyOnly.children.some(x=>x.children.some(y=>y.textContent.includes("POLICY_CHANGE"))));
 const missingOfficial=el();ctx.showSavedNewsEvidence(missingOfficial,{
   status:"N/A",reason_code:"NO_SAVED_EXACT_THEME_EVIDENCE",
   official_document_evidence:{status:"N/A",reason_code:"NO_REPORTED_DOCUMENT_ECONOMIC_CHANGE"}});
 assert(missingOfficial.children.some(x=>x.textContent.includes("공식 본문 N/A")));
 const period=el();
 ctx.showSavedNewsEvidence(period,{status:"N/A",reason_code:"NO_SAVED_EXACT_THEME_EVIDENCE",
   official_document_evidence:{status:"READY",document_sha256:"d".repeat(64),binding_sha256:"e".repeat(64),
     binding_available_at:"2026-10-17T00:00:00+00:00",themes:[{...evidence.themes[0]}]}},
   payload.results[0],"반도체");
 const themeCard=period.children.find(x=>x.className==="news-evidence-theme");
 const toolbar=themeCard.children.find(x=>x.className==="news-change-toolbar");
 assert(toolbar&&toolbar.children.length===3);
 const dateInputs=toolbar.children.slice(0,2).map(x=>x.children[0]);
 assert(dateInputs[0].value&&dateInputs[1].value);
 await toolbar.children[2].events.click();
 assert(seen.at(-1).includes("theme_id="+"c".repeat(64)),JSON.stringify({last:seen.at(-1),from:dateInputs[0].value,to:dateInputs[1].value,msg:themeCard.children.at(-1).children.map(x=>x.textContent)}));
 assert(seen.at(-1).includes("since=")&&seen.at(-1).includes("as_of="));
 const rendered=themeCard.children.at(-1);
 assert(rendered.children.some(x=>x.textContent.includes("신규 독립 행동 0")));
 assert(rendered.children.some(x=>x.textContent.includes("기존 기간 렌더러 재사용")));
 dateInputs[0].value="2099-12-31";
 await toolbar.children[2].events.click();
 assert(rendered.children[0].textContent.includes("N/A"));
 process.stdout.write("BROWSER_DETAIL_OK");
})().catch(e=>{process.stderr.write(String(e.stack||e));process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script],cwd=root,text=True,
                          capture_output=True,timeout=15,check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'BROWSER_DETAIL_OK'
