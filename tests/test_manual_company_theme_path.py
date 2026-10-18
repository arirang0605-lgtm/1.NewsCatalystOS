"""Public-title handoff -> common theme -> exact companies; synthetic fixtures."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess
import threading
from urllib.request import urlopen
from urllib.parse import urlencode

import pytest
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.feed_transport import fetch_authorized_once
from newscatalystos.source_share import SourceShareError
from newscatalystos.discovery_watch import read_discovery, export_discovery
from newscatalystos.federated_news_search import TitleSearchWorkspace
from scripts.run_manual_company_news_once import execute, prepare
from test_official_power_news_path import collect, registry
from test_federated_news_search import fingerprint

SOURCE='other-company-reviewed-titles'
LIST='https://news.example.org/news'
URL=LIST+'/7'
TITLE='가상배전, HVDC 변환용 변압기 사업 수주'
PAYLOAD={'items':[{'id':URL,'title':TITLE,'url':URL}]}


def private_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False));path.chmod(0o600)
    return path


def manual(tmp_path,monkeypatch):
    workspace=tmp_path/'other'
    _,path=prepare(workspace,SOURCE,LIST,datetime.now(timezone.utc))
    return workspace,path,private_json(tmp_path/'metadata.json',PAYLOAD)


def test_manual_source_never_opens_http_and_keeps_pit(tmp_path,monkeypatch):
    _,path,_=manual(tmp_path,monkeypatch)
    from scripts.run_feed_triage import _registry
    registered=_registry(path);at=datetime.now(timezone.utc)
    row,=parse_authorized_feed(registered,SOURCE,json.dumps(PAYLOAD).encode(),observed_at=at)
    assert row.document_id==row.source_url==URL and row.first_seen_at==at
    assert row.reported_published_at is None
    class NoHTTP:
        def open(self,*a,**kw):raise AssertionError('manual metadata must not request HTTP')
    with pytest.raises(SourceShareError):fetch_authorized_once(registered,SOURCE,opener=NoHTTP())


@pytest.mark.parametrize('change',[
    {'body':'PRIVATE BODY'}, {'summary':'PRIVATE SUMMARY'}, {'published_at':'1999-01-01'},
    {'url':'https://foreign.example.org/news/7'}, {'id':'alternate-id'},
    {'url':'http://news.example.org/news/7'},
])
def test_body_fields_foreign_origin_alias_ids_and_unsafe_urls_rejected(tmp_path,monkeypatch,change):
    _,path,_=manual(tmp_path,monkeypatch)
    from scripts.run_feed_triage import _registry
    data={'items':[{**PAYLOAD['items'][0],**change}]}
    with pytest.raises(SourceShareError):parse_authorized_feed(_registry(path),SOURCE,json.dumps(data).encode())


@pytest.mark.parametrize('change',[
    {'kind':'GOVERNMENT_POLICY'}, {'allow_full_text_storage':True},
    {'grant':'WRITTEN_LICENSE'},
])
def test_manual_rights_remain_company_title_only(change):
    with pytest.raises(SourceShareError):registry(datetime.now(timezone.utc),method='MANUAL_METADATA',**change)


def test_two_company_theme_exact_http_evidence_repeat_and_historical_snapshot(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    hd,documents,opener=collect(tmp_path,monkeypatch)
    workspace,path,metadata=manual(tmp_path,monkeypatch)
    root=documents/'economic_discovery'
    before=datetime.now(timezone.utc)
    old=export_discovery(root,as_of=before,now=before)
    args=dict(provider_id=SOURCE,official_list_url=LIST,metadata_file=metadata,scope='other')
    code,result=execute(workspace,root,**args)
    assert code==0 and not result['network_called'] and not result['ingest']['network_called']
    assert result['ingest']['acquisition_method']=='MANUAL_METADATA'
    assert opener.calls==1
    assert result['stored_article_bodies']==result['paid_ai_calls']==0
    current=read_discovery(root)
    group,=[r for r in current['theme_outlook']['candidates'] if r['subject']=='변압기']
    assert group['source_company_names']==['가상배전','가상전기']
    assert group['economic_actions']==['CONTRACT']
    assert group['attention_tier']=='MULTI_COMPANY'
    assert not group['common_demand_cause_verified'] and group['market_newness']=='UNKNOWN'
    assert all(s['shared_object_evidence']['text']=='변압기' for s in group['source_evidence'])
    code,repeat=execute(workspace,root,**args)
    assert code==0 and repeat['discovery']['sources'][0]['theme_versions_created']==0
    assert export_discovery(root,as_of=before,now=datetime.now(timezone.utc))==old
    w=TitleSearchWorkspace('other',path,workspace/'state/incremental_feeds.sqlite3',
                          workspace/'inbox/feed_triage')
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,
        news_search_workspaces=(w,),additional_source_roots=(('other',workspace),))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    pins=fingerprint(tmp_path)
    def get(args):
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/news-evidence?'+urlencode(args)) as r:return json.load(r)
    try:
        source,=[s for s in group['source_evidence'] if s['provider_id']==SOURCE]
        query={'q':TITLE,'discovery':'1','provider_id':SOURCE,
               'event_id':source['source_event_sha256'],'title_sha256':source['source_title_sha256']}
        detail=get(query)
        assert detail['acquisition_method']=='MANUAL_METADATA'
        theme,=detail['article_company_context']['themes']
        party,=theme['direct_parties']
        assert party['source_name']=='가상배전'
        excerpt=get({**query,'excerpt_theme_id':theme['theme_id'],'excerpt_entity_id':party['entity_id'],
            'excerpt_claim_event_id':party['event_id'],'excerpt_evidence_sha256':party['evidence_sha256']})
        assert excerpt['article_company_excerpt']['excerpt']==TITLE
        assert get({**query,'as_of':before.isoformat()})['article_company_context']['themes']==[]
    finally:server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path)==pins


def test_theme_source_button_passes_exact_identity_and_common_analysis(tmp_path):
    code=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(tag,cls,text){return {textContent:text||'',children:[],listeners:{},append(...v){this.children.push(...v)},
replaceChildren(...v){this.children=v},addEventListener(k,f){this.listeners[k]=f}}}
let selected,request,place=node('div');
const ctx={node,URLSearchParams,economicActionLabels:{CONTRACT:'수주'},
fetch:async u=>{request=u;return {ok:true,json:async()=>({})}},
showSavedNewsEvidence:(box,data,item)=>{selected=item}};
vm.runInNewContext(src.slice(src.indexOf('async function loadSavedNewsEvidence('),src.indexOf('async function searchStoredNews(')),ctx);
vm.runInNewContext(src.slice(src.indexOf('function renderThemeOutlook('),src.indexOf('function renderLaunchComparisons(')),ctx);
ctx.renderThemeOutlook(place,{candidates:[{title:'변압기',attention_tier:'MULTI_COMPANY',attention_label:'복수 기업',
source_company_names:['가상전기','가상배전'],attention_reasons:[],related_business_areas:[],conditional_paths:[],
source_evidence:[{provider_id:'provider',source_event_sha256:'e'.repeat(64),source_title_sha256:'a'.repeat(64),
headline:'literal title',shared_object_evidence:{text:'변압기'},source_url:'https://example.org/7',action:'CONTRACT'}]}]});
function all(n){return [n,...n.children.flatMap(all)]}
(async()=>{await all(place).find(n=>n.textContent==='이 테마의 기업·분석 근거 보기').listeners.click();
assert.equal(selected.event_id,'e'.repeat(64));assert.equal(selected.title_sha256,'a'.repeat(64));
assert.equal(selected.analysis_scope,'ECONOMIC_DISCOVERY');
const q=new URLSearchParams(request.split('?')[1]);assert.equal(q.get('q'),'literal title');
assert.equal(q.get('discovery'),'1');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run(['node','-e',code],cwd=Path(__file__).resolve().parent.parent,check=True,capture_output=True)
