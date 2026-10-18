"""Bound reading analyses, distinct from title claims, with no source text stored."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.public_demand_analysis import (
    SCHEMA,BIND,publish_notes,read_notes,sources_from_outlook)
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.source_share import SourceShareError
from newscatalystos.federated_news_search import TitleSearchWorkspace
from test_official_power_news_path import collect
from test_manual_company_theme_path import manual,private_json,PAYLOAD,SOURCE,LIST
from test_business_demand_context import TITLE
from test_federated_news_search import fingerprint
from scripts.run_manual_company_news_once import execute as import_titles
from scripts.run_public_demand_analysis_once import execute


def setup(tmp_path,monkeypatch):
    hd,documents,opener=collect(tmp_path,monkeypatch)
    workspace,registry,metadata=manual(tmp_path,monkeypatch)
    data=deepcopy(PAYLOAD);url=LIST+'/8'
    data['items'].append({'id':url,'title':TITLE,'url':url});private_json(metadata,data)
    root=documents/'economic_discovery'
    code,_=import_titles(workspace,root,provider_id=SOURCE,official_list_url=LIST,metadata_file=metadata,scope='other')
    assert code==0
    now=datetime.now(timezone.utc);view=read_discovery(root,as_of=now,now=now,include_common_causes=True)
    sources=sources_from_outlook(view['theme_outlook'])
    group,=[g for g in view['theme_outlook']['candidates'] if g['source_company_name_count']==3]
    notes=[]
    markets={'가상전기':'US','가상배전':'KR','가상중공업':'GLOBAL'}
    for s in group['source_evidence']:
        name=s['source_companies'][0]
        notes.append({**{k:s[k] for k in BIND},'source_url':s['source_url'],'source_company':name,
            'market_codes':[markets[name]],'factors':[{'code':'RENEWABLE_INTEGRATION','relation':'MARKET_BACKGROUND'}],
            'analysis_text':'합성 분석: 재생 발전 전력을 보내기 위한 전력 설비 수요를 설명한다.',
            'source_location':'합성 보도자료의 수요 배경 설명'})
    document={'schema':SCHEMA,'notes':notes}
    return root,workspace,registry,documents,sources,document,opener


def test_real_path_notes_comparison_exact_article_http_repeated_input_and_past(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    root,w,registry,documents,sources,document,opener=setup(tmp_path,monkeypatch)
    before=datetime.now(timezone.utc)
    default=export_discovery(root,as_of=before,now=before)
    optional=export_discovery(root,as_of=before,now=before,include_common_causes=True)
    p=private_json(tmp_path/'reading_notes.json',document)
    result=execute(root,p);assert result['created']==3 and not result['source_text_stored']
    assert execute(root,p)['created']==0 and opener.calls==1
    now=datetime.now(timezone.utc);pins=fingerprint(tmp_path)
    view=read_discovery(root,as_of=now,now=now,include_common_causes=True)
    group,=[g for g in view['theme_outlook']['candidates'] if g['source_company_name_count']==3]
    analysis=group['public_page_demand_analysis']
    assert analysis['status']=='COMPANY_NOTES_AVAILABLE'
    assert analysis['market_scope_comparison']=='DIFFERENT_STATED_SCOPES'
    assert analysis['shared_background_factors'][0]['all_group_companies_covered']
    assert not analysis['common_market_shock_verified'] and not analysis['literal_common_cause_match_verified']
    assert group['source_demand_context']['companies_with_explicit_cause']==['가상중공업']
    assert all(r['available_at']>before.isoformat() and not r['source_text_stored'] for r in analysis['notes'])
    assert export_discovery(root,as_of=before,now=now)==default
    assert export_discovery(root,as_of=before,now=now,include_common_causes=True)==optional
    assert not any('public_page_demand_analysis' in g for g in read_discovery(root)['theme_outlook']['candidates'])
    assert fingerprint(tmp_path)==pins
    workspace=TitleSearchWorkspace('other',registry,w/'state/incremental_feeds.sqlite3',w/'inbox/feed_triage')
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,
        news_search_workspaces=(workspace,),additional_source_roots=(('other',w),))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    source=next(s for s in group['source_evidence'] if s['provider_id']==SOURCE)
    query=dict(q=source['headline'],provider_id=SOURCE,event_id=source['source_event_sha256'],
               title_sha256=source['source_title_sha256'],discovery='1')
    def get(route,**args):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(args)) as r:return json.load(r)
    try:
        detail=get('/api/news-evidence',**query)
        n,=detail['public_page_demand_analysis']
        assert n['note']['source_company'] in ['가상배전','가상중공업']
        assert n['note']['source_event_sha256']==query['event_id']
        past=get('/api/news-evidence',**query,as_of=before.isoformat())
        assert 'public_page_demand_analysis' not in past
        ordinary=get('/api/news-evidence',**{**query,'discovery':'0'})
        assert 'public_page_demand_analysis' not in ordinary
        exported=get('/api/economic-discovery',common_causes='1',export='1')
        extensions=[t['discovery_theme_outlook'] for t in exported['ThemeCandidates']]
        assert any(e['basis_available_at']>=analysis['basis_available_at'] for e in extensions)
    finally:server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path)==pins


@pytest.mark.parametrize('change',[
    {'body':'source body'}, {'quote':'source quote'}, {'available_at':'2000-01-01T00:00:00+00:00'},
    {'source_truth_verified':True},{'source_company':'다른회사'},
    {'event_id':'f'*64},{'report_sha256':'f'*64},{'source_title_sha256':'f'*64},
    {'source_url':'https://foreign.example.org/article'},
    {'market_codes':['MARS']},{'analysis_text':'x'*241},
    {'factors':[{'code':'RENEWABLE_INTEGRATION','relation':'VERIFIED_TRANSACTION'}]},
])
def test_no_text_rights_expansion_rebinding_or_backdated_input(tmp_path,monkeypatch,change):
    root,*_,sources,document,opener=setup(tmp_path,monkeypatch)
    data=deepcopy(document);data['notes'][0].update(change)
    pins=fingerprint(tmp_path)
    with pytest.raises(SourceShareError):publish_notes(root,data,sources)
    assert fingerprint(tmp_path)==pins


def test_revised_or_inactive_event_cannot_borrow_note_and_corruption_isolated(tmp_path,monkeypatch):
    root,*_,sources,document,opener=setup(tmp_path,monkeypatch)
    publish_notes(root,document,sources)
    now=datetime.now(timezone.utc)
    assert len(read_notes(root,{},as_of=now,now=now))==0
    changed=deepcopy(sources)
    for s in changed.values():s['source_url']='https://foreign.example.org/article'
    assert read_notes(root,changed,as_of=now,now=now)==[]
    files=sorted((root/'analysis_notes/public_demand').glob('*.json'))
    files[0].write_bytes(files[0].read_bytes()+b' ')
    plain=export_discovery(root,as_of=now,now=now)
    view=read_discovery(root,as_of=now,now=now,include_common_causes=True)
    assert view['status']=='READY' and view['theme_outlook']['public_page_demand_analysis_status']=='UNAVAILABLE'
    assert view['counts']['events']==3 and export_discovery(root,as_of=now,now=now)==plain


def test_comparison_UI_safe_analysis_labels_and_exact_source_click(tmp_path,monkeypatch):
    root,*_,sources,document,opener=setup(tmp_path,monkeypatch)
    document['notes'][0]['analysis_text']='<img src=x> 합성 분석'
    publish_notes(root,document,sources)
    data=read_discovery(root,include_common_causes=True)['theme_outlook']
    script=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8'),data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,txt){return {textContent:txt||'',children:[],listeners:{},append(...x){this.children.push(...x)},
replaceChildren(...x){this.children=x},addEventListener(k,f){this.listeners[k]=f}}}
let request,selection;const p=node('div'),ctx={node,URLSearchParams,economicActionLabels:{CONTRACT:'계약',CAPACITY_ADDITION:'증설'},
fetch:async u=>{request=u;return {ok:true,json:async()=>({})}},showSavedNewsEvidence:(box,data,item)=>{selection=item}};
for(const [a,b] of [['function renderPublicDemandNotes(','function showSavedNewsEvidence('],
['async function loadSavedNewsEvidence(','async function searchStoredNews('],
['function renderThemeOutlook(','function renderLaunchComparisons(']])
vm.runInNewContext(s.slice(s.indexOf(a),s.indexOf(b)),ctx);
ctx.renderThemeOutlook(p,data);
function all(n){return [n,...n.children.flatMap(all)]}
const text=all(p).map(n=>n.textContent).join(' ');
for(const x of ['공통 배경(분석 분류)','신재생 발전의 전력망 연계','지역 범위는 서로 다릅니다','<img src=x> 합성 분석','원문 문장 인용·본문 보관·독립 사실 인증이 아닙니다'])assert(text.includes(x),x);
(async()=>{await all(p).find(n=>n.textContent==='이 수요 분석의 기업·기사 근거 보기').listeners.click();
const q=new URLSearchParams(request.split('?')[1]);assert.equal(q.get('discovery'),'1');
assert.equal(q.get('event_id'),selection.event_id);assert.equal(q.get('title_sha256'),selection.title_sha256);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run(['node','-e',script],input=json.dumps(data),text=True,capture_output=True,check=True,
                   cwd=Path(__file__).resolve().parent.parent)
