"""Recent metadata -> prior demand note -> directional comparison -> exact article."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.source_share import SourceShareError
from newscatalystos.public_demand_analysis import publish_notes,read_notes
from newscatalystos.recent_theme_followups import (
    SCHEMA,RECENT_FIELDS,publish_followups,read_followups,metadata_resolver,assess)
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.federated_news_search import TitleSearchWorkspace,search_completed_workspaces
from scripts.run_feed_triage import _registry
from scripts.run_manual_company_news_once import execute as import_titles,prepare
from scripts.run_recent_theme_followups_once import execute
from test_public_demand_analysis import setup
from test_manual_company_theme_path import private_json
from test_federated_news_search import fingerprint

def scenario(tmp_path,monkeypatch):
    root,w,registry,documents,sources,document,opener=setup(tmp_path,monkeypatch)
    publish_notes(root,document,sources)
    provider='latest-official-reviewed-titles';endpoint='https://latest.example.org/news'
    titles=['가상전기, 빅테크 전력인프라 공급계약 체결',
            '가상배전, 빅테크 데이터센터 배전솔루션 공급',
            '가상중공업, 수출 차단기 신공장 준공 … 후속 설명']
    payload={'items':[{'id':endpoint+'/'+str(i),'url':endpoint+'/'+str(i),'title':t} for i,t in enumerate(titles)]}
    metadata=private_json(tmp_path/'recent_metadata.json',payload)
    old=json.loads(registry.read_bytes())['providers']
    code,result=import_titles(w,root,provider_id=provider,official_list_url=endpoint,
                              metadata_file=metadata,scope='other')
    assert code==0 and not result['network_called']
    assert json.loads(registry.read_bytes())['providers'][:-1]==old
    workspace=TitleSearchWorkspace('other',registry,w/'state/incremental_feeds.sqlite3',w/'inbox/feed_triage')
    now=datetime.now(timezone.utc);base=read_notes(root,sources,as_of=now,now=now)
    baselines={r['note_id']:r for r in base}
    notes=[]
    kinds={'가상전기':'CONDITIONAL_FRAMEWORK','가상배전':'REPORTED_CONTRACT','가상중공업':'REPORTED_CAPACITY_OPERATION'}
    for b in base:
        company=b['note']['source_company']
        row,=search_completed_workspaces((workspace,),company,source_id=provider,
            registry_reader=_registry,now=now)['results']
        notes.append({'baseline_note_id':b['note_id'],'recent_source':{k:row[k] for k in RECENT_FIELDS},
            'reported_date':now.date().isoformat(),'evidence_kind':kinds[company],
            'factor_codes':['AI_LOAD'],'market_codes':['US'],'product_scope':'합성: 배전/변압기/차단기 범위 구분',
            'analysis_text':'합성 분석: 데이터센터 전력 수요와 계약 또는 가동을 연결한다.',
            'limitation':'합성: 후속 발주·향후 납품 및 기존 변압기 증설과의 차이를 확인한다.',
            'source_location':'합성 공식 발표의 계약·수요 설명'})
    return root,w,documents,workspace,baselines,{'schema':SCHEMA,'notes':notes},opener

def test_completed_recent_path_comparison_duplicate_pit_export_and_exact_http(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    root,w,documents,workspace,baselines,document,opener=scenario(tmp_path,monkeypatch)
    before=datetime.now(timezone.utc)
    fixed=export_discovery(root,as_of=before,now=before,include_common_causes=True,recent_workspaces=(workspace,))
    ordinary=export_discovery(root,as_of=before,now=before)
    p=private_json(tmp_path/'followups.json',document)
    assert execute(root,p,(workspace,))['created']==3
    assert execute(root,p,(workspace,))['created']==0
    pins=fingerprint(tmp_path);now=datetime.now(timezone.utc)
    view=read_discovery(root,as_of=now,now=now,include_common_causes=True,recent_workspaces=(workspace,))
    group,=[g for g in view['theme_outlook']['candidates'] if g.get('recent_news_comparison')]
    comparison=group['recent_news_comparison']
    assert comparison['status']=='SUPPORT_ADDED' and comparison['conditional_evidence_present']
    assert not comparison['article_count_used_as_strength'] and not comparison['common_market_shock_verified']
    assert comparison['shared_recent_factors'][0]['all_group_companies_covered']
    assert comparison['shared_recent_factors'][0]['code']=='AI_LOAD'
    assert group['public_page_demand_analysis']['shared_background_factors'][0]['code']=='RENEWABLE_INTEGRATION'
    assert export_discovery(root,as_of=before,now=now,include_common_causes=True,recent_workspaces=(workspace,))==fixed
    assert export_discovery(root,as_of=before,now=now)==ordinary
    assert not any('recent_news_comparison' in g for g in read_discovery(root)['theme_outlook']['candidates'])
    assert fingerprint(tmp_path)==pins and opener.calls==1
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,
        news_search_workspaces=(workspace,),additional_source_roots=(('other',w),))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def get(route,**args):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(args)) as r:return json.load(r)
    try:
        api=get('/api/economic-discovery',common_causes='1')
        assert any(g.get('recent_news_comparison') for g in api['theme_outlook']['candidates'])
        for n in document['notes']:
            r=n['recent_source'];query=dict(q=r['headline'],provider_id=r['provider_id'],event_id=r['event_id'],
                                            title_sha256=r['title_sha256'],discovery='1')
            detail=get('/api/news-evidence',**query)
            follow,=detail['recent_theme_followup_analysis']
            assert follow['note']['recent_source']==r
            assert follow['source_company'] in ['가상전기','가상배전','가상중공업']
            assert not follow['source_truth_verified'] and not follow['source_text_stored']
            assert 'recent_theme_followup_analysis' not in get('/api/news-evidence',**query,as_of=before.isoformat())
            assert 'recent_theme_followup_analysis' not in get('/api/news-evidence',**{**query,'discovery':'0'})
        bundle=get('/api/economic-discovery',common_causes='1',export='1')
        assert any(t.get('discovery_theme_outlook',{}).get('basis_available_at','')>=comparison['basis_available_at']
                   for t in bundle['ThemeCandidates'])
    finally:server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path)==pins

@pytest.mark.parametrize('kinds,status',[
    (['REPORTED_CONTRACT'],'SUPPORT_ADDED'),
    (['REPORTED_CAPACITY_OPERATION'],'SUPPORT_ADDED'),
    (['CONDITIONAL_FRAMEWORK'],'CONDITIONAL_SUPPORT_ONLY'),
    (['DEMAND_REDUCTION'],'WEAKENING_EVIDENCE'),
    (['CANCELLATION','REPORTED_CONTRACT'],'MIXED_EVIDENCE'),
    (['DEMAND_REDUCTION','CONDITIONAL_FRAMEWORK'],'MIXED_EVIDENCE'),
    (['PLAN_ONLY','CONTEXT_ONLY'],'NO_SUBSTANTIVE_CHANGE')])
def test_substantive_evidence_not_article_count_or_silence(kinds,status):
    rows=[{'source_company':'가상기업','available_at':'2026-10-18T00:00:00+00:00',
           'note':{'evidence_kind':k,'factor_codes':['AI_LOAD']}} for k in kinds]
    a=assess(rows,['가상기업','자료없는기업'])
    assert a['status']==status
    assert a['companies_without_followups']==['자료없는기업']
    assert assess(rows*7,['가상기업','자료없는기업'])['status']==status

@pytest.mark.parametrize('change',[
    {'body':'article body'},{'quote':'source words'},{'available_at':'1990-01-01'},
    {'baseline_note_id':'f'*64},{'reported_date':'2999-01-01'},
    {'evidence_kind':'FULL_VALUE_CONFIRMED_ORDER'},{'analysis_text':'x'*301}])
def test_no_body_backdate_wrong_baseline_or_unsupported_phase(tmp_path,monkeypatch,change):
    root,_,_,ws,base,doc,_=scenario(tmp_path,monkeypatch)
    data=deepcopy(doc);data['notes'][0].update(change)
    pins=fingerprint(tmp_path)
    with pytest.raises((SourceShareError,ValueError)):
        publish_followups(root,data,base,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    assert fingerprint(tmp_path)==pins

def test_rebound_source_inactive_baseline_revoked_provider_and_damage(tmp_path,monkeypatch):
    root,_,_,ws,base,doc,_=scenario(tmp_path,monkeypatch)
    bad=deepcopy(doc);bad['notes'][0]['recent_source']['triage_evidence_sha256']='f'*64
    with pytest.raises(SourceShareError):
        publish_followups(root,bad,base,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    publish_followups(root,doc,base,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    now=datetime.now(timezone.utc)
    assert read_followups(root,{},metadata_resolver((ws,),now=now),as_of=now,now=now)==[]
    config=json.loads(ws.registry_path.read_bytes());config['providers'][-1]['approved']=False
    private_json(ws.registry_path,config)
    assert read_followups(root,base,metadata_resolver((ws,),now=now),as_of=now,now=now)==[]
    f=next((root/'analysis_notes/recent_followups').glob('*.json'));f.write_bytes(f.read_bytes()+b' ')
    view=read_discovery(root,include_common_causes=True,recent_workspaces=(ws,))
    assert view['status']=='READY' and view['theme_outlook']['recent_news_comparison_status']=='UNAVAILABLE'

def test_UI_recent_comparison_escapes_text_and_passes_exact_source(tmp_path,monkeypatch):
    root,_,_,ws,base,doc,_=scenario(tmp_path,monkeypatch)
    doc['notes'][0]['analysis_text']='<img src=x> 합성 분석'
    publish_followups(root,doc,base,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    view=read_discovery(root,include_common_causes=True,recent_workspaces=(ws,))
    comparison=next(g['recent_news_comparison'] for g in view['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
    script=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8'),data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,text){return {textContent:text||'',children:[],listeners:{},append(...x){this.children.push(...x)},
replaceChildren(...x){this.children=x},addEventListener(k,f){this.listeners[k]=f}}}
let selected,request;const p=node('div'),ctx={node,URLSearchParams,
fetch:async u=>{request=u;return {ok:true,json:async()=>({})}},showSavedNewsEvidence:(p,d,item)=>{selected=item}};
for(const [a,b] of [['function renderRecentThemeComparison(','function renderPublicDemandNotes('],
['async function loadSavedNewsEvidence(','async function searchStoredNews(']])
vm.runInNewContext(src.slice(src.indexOf(a),src.indexOf(b)),ctx);
ctx.renderRecentThemeComparison(p,data,true);
function all(n){return [n,...n.children.flatMap(all)]}
const text=all(p).map(n=>n.textContent).join(' ');
for(const s of ['강화 근거 추가','후속 발주가 필요한 기본 공급계약','<img src=x> 합성 분석','원문 표시일','기존 근거:'])assert(text.includes(s),s);
(async()=>{await all(p).find(n=>n.textContent==='최근 뉴스의 기업·비교 근거 보기').listeners.click();
const q=new URLSearchParams(request.split('?')[1]);assert.equal(q.get('discovery'),'1');
assert.equal(q.get('event_id'),selected.event_id);assert.equal(q.get('title_sha256'),selected.title_sha256);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run(['node','-e',script],input=json.dumps(comparison),text=True,capture_output=True,check=True,
                   cwd=Path(__file__).resolve().parent.parent)
