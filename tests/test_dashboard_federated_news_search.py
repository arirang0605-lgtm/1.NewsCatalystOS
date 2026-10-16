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
const start="async function searchStoredNews(event){";
assert(all.includes(start));
const code=start+all.split(start)[1].split('$("news-search-form").addEventListener')[0];
function el(){return {children:[],value:"",textContent:"",checked:false,replaceChildren(...x){this.children=[...x]},append(...x){this.children.push(...x)}}}
const elements={"news-search-form":el(),"news-search-query":el(),"news-semiconductor-only":el(),"news-search-status":el(),"news-search-results":el()};
elements["news-search-query"].value="반도체";
const seen=[];
const payload={coverage_complete:true,matched_document_versions:1,keyword_hits:1,has_more_matches:false,results:[
{headline:"<b>반도체 & 테스트</b>",provider_id:"synthetic",source_url:"https://example.org/saved-title",source_available_at:"2026-10-17T00:00:00+00:00",semiconductor_keyword_candidate:true}
]};
const ctx={
  $:id=>elements[id],URLSearchParams,
  fetch:async url=>{seen.push(url);return {ok:true,json:async()=>payload}},
  node:(tag,cls,value)=>{const e=el();e.tag=tag;e.className=cls;e.textContent=value||"";return e},
};
vm.runInNewContext(code,ctx);
ctx.searchStoredNews({preventDefault(){}}).then(()=>{
 const parent=elements["news-search-results"];
 assert.equal(parent.children.length,1);
 const article=parent.children[0];
 assert.equal(article.children[0].textContent,payload.results[0].headline);
 assert.equal(article.children[3].href,payload.results[0].source_url);
 assert(seen[0].includes("q=%EB%B0%98%EB%8F%84%EC%B2%B4"));
 assert(elements["news-search-status"].textContent.includes("1개"));
 process.stdout.write("BROWSER_RENDER_OK");
}).catch(e=>{process.stderr.write(String(e));process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script],cwd=root,text=True,
                          capture_output=True,timeout=15,check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'BROWSER_RENDER_OK'
