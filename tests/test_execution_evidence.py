"""Actual receipt path for execution, earlier periods, risk references and PIT."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,sqlite3,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.recent_theme_followups import (
    SCHEMA_V2,RECENT_FIELDS,publish_followups,read_followups,metadata_resolver)
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.source_share import SourceShareError
from newscatalystos.federated_news_search import search_completed_workspaces
from newscatalystos.incremental_ingest import incremental_poll
from scripts.run_feed_triage import _registry
from scripts.run_manual_company_news_once import execute as import_titles
from scripts.run_recent_theme_followups_once import execute
from test_recent_theme_followups import scenario
from test_manual_company_theme_path import private_json
from test_federated_news_search import fingerprint

def fixture(tmp_path,monkeypatch):
    root,w,documents,ws,baselines,old,opener=scenario(tmp_path,monkeypatch)
    now=datetime.now(timezone.utc);anchor_date=(now.date()-timedelta(days=30)).isoformat()
    for n in old['notes']:n['reported_date']=anchor_date
    publish_followups(root,old,baselines,metadata_resolver((ws,),now=now),now=now)
    anchors=read_followups(root,baselines,metadata_resolver((ws,),now=now),as_of=now,now=now)
    names=['가상전기','가상배전','가상중공업'];endpoint='https://latest.example.org/news'
    data={'items':[{'id':endpoint+'/results/'+str(i),'url':endpoint+'/results/'+str(i),
                    'title':name+', 분기 수주·매출 실적 발표'} for i,name in enumerate(names)]}
    p=private_json(tmp_path/'results_metadata.json',data)
    pins={k:v for k,v in fingerprint(root/'feed_analysis').items() if '/reports/' in k}
    code,result=import_titles(w,root,provider_id='latest-official-reviewed-titles',official_list_url=endpoint,
                              metadata_file=p,scope='other')
    assert code==0 and result['status']=='READY' and not result['network_called']
    # Three prior articles are not reanalyzed when new articles are submitted.
    assert result['discovery']['analyzed_titles']==3
    current=fingerprint(root/'feed_analysis');assert all(current[k]==v for k,v in pins.items())
    now=datetime.now(timezone.utc);notes=[]
    for anchor in anchors:
        company=anchor['source_company']
        row,=search_completed_workspaces((ws,),company+', 분기',registry_reader=_registry,now=now)['results']
        oldnote=anchor['note'];note={**oldnote,
            'recent_source':{k:row[k] for k in RECENT_FIELDS},
            'reported_date':now.date().isoformat(),'evidence_kind':'REPORTED_ORDER_PERFORMANCE',
            'analysis_text':'합성: 해당 사업의 분기 수주·매출 증가를 보도했다.',
            'execution':{'anchor_note_id':anchor['note_id'],'project_relation':'RELATED_BUSINESS_ONLY',
             'matching_basis':'합성: 관련 제품이지만 같은 고객·계약의 이행인지는 확인되지 않았다.',
             'evidence_stage':'ORDER_RESULTS','period_end':(now.date()-timedelta(days=40)).isoformat(),
             'counter_reference':None}}
        if company=='가상배전':
            note['reported_date']=(now.date()-timedelta(days=35)).isoformat()
            note['execution']['counter_reference']={'title':'합성: 잔고의 매출 전환과 고객 집중 위험',
                'source_url':'https://press.example.org/story/1','reported_date':note['reported_date'],
                'analysis_text':'합성 반론 분석: 잔고 소화와 고객 투자 지속성이 변수라는 우려다. 취소·수요 감소 발생 보도는 아니다.',
                'access_basis':'PUBLIC_SEARCH_RESULT_READING'}
        notes.append(note)
    return root,w,documents,ws,baselines,anchors,{'schema':SCHEMA_V2,'notes':notes},opener

def test_results_risk_reference_and_exact_article_main_screen_past_export(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    root,w,documents,ws,bases,anchors,doc,opener=fixture(tmp_path,monkeypatch)
    before=datetime.now(timezone.utc)
    original=export_discovery(root,as_of=before,now=before,include_common_causes=True,recent_workspaces=(ws,))
    p=private_json(tmp_path/'execution_notes.json',doc)
    assert execute(root,p,(ws,))['created']==3
    assert execute(root,p,(ws,))['created']==0
    now=datetime.now(timezone.utc);pins=fingerprint(tmp_path)
    view=read_discovery(root,as_of=now,now=now,include_common_causes=True,recent_workspaces=(ws,))
    g,=[g for g in view['theme_outlook']['candidates'] if g.get('recent_news_comparison')]
    comparison=g['recent_news_comparison'];e=comparison['execution_comparison']
    assert comparison['status']=='SUPPORT_ADDED' and e['status']=='NO_NEW_EXECUTION_PROOF'
    assert len(e['company_results'])==3 and not e['risk_commentary_is_actual_reversal']
    rows=[r for r in comparison['notes'] if 'execution_context' in r]
    assert {r['execution_context']['chronology'] for r in rows}=={'LATER_PUBLICATION_PRIOR_PERIOD','EARLIER_PUBLICATION'}
    assert all(not r['execution_context']['reported_execution_progress'] for r in rows)
    assert export_discovery(root,as_of=before,now=now,include_common_causes=True,recent_workspaces=(ws,))==original
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,news_search_workspaces=(ws,),
                           additional_source_roots=(('other',w),))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def get(route,**args):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(args)) as response:return json.load(response)
    try:
        period=get('/api/period',view='day')['economic_discovery']
        assert any(g.get('recent_news_comparison',{}).get('execution_comparison') for g in period['theme_outlook']['candidates'])
        for row in rows:
            r=row['note']['recent_source'];query=dict(q=r['headline'],provider_id=r['provider_id'],
                event_id=r['event_id'],title_sha256=r['title_sha256'],discovery='1')
            detail=get('/api/news-evidence',**query)
            note,=detail['recent_theme_followup_analysis']
            assert note['execution_context']==row['execution_context']
            assert 'recent_theme_followup_analysis' not in get('/api/news-evidence',**query,as_of=before.isoformat())
    finally:server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path)==pins and opener.calls==1

@pytest.mark.parametrize('stage,kind,status',[
 ('INDIVIDUAL_ORDER','REPORTED_CONTRACT','SOURCE_REPORTED_PROGRESS'),
 ('DELIVERY_COMPLETED','REPORTED_DELIVERY','SOURCE_REPORTED_PROGRESS'),
 ('DELIVERY_DELAY','REPORTED_DELAY','SOURCE_REPORTED_SETBACK'),
 ('CANCELLATION','CANCELLATION','SOURCE_REPORTED_SETBACK'),
 ('DEMAND_REDUCTION','DEMAND_REDUCTION','SOURCE_REPORTED_SETBACK'),
 ('RISK_COMMENTARY','RISK_ONLY','NO_NEW_EXECUTION_PROOF'),
 ('DELIVERY_PLANNED','PLAN_ONLY','NO_NEW_EXECUTION_PROOF'),
 ('ORDER_RESULTS','REPORTED_ORDER_PERFORMANCE','NO_NEW_EXECUTION_PROOF')])
def test_normal_bound_progress_and_setback_paths(tmp_path,monkeypatch,stage,kind,status):
    root,_,_,ws,bases,anchors,doc,_=fixture(tmp_path,monkeypatch)
    n=doc['notes'][0];n['reported_date']=datetime.now(timezone.utc).date().isoformat();n['evidence_kind']=kind
    n['execution'].update(project_relation='SAME_PROJECT_EXPLICIT',matching_basis='합성: 동일 고객·설비·계약 식별자를 원문이 명시한다.',
                          evidence_stage=stage,period_end=None)
    publish_followups(root,doc,bases,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    g=next(g for g in read_discovery(root,include_common_causes=True,recent_workspaces=(ws,))['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
    assert g['recent_news_comparison']['execution_comparison']['status']==status

@pytest.mark.parametrize('change',[
 {'anchor_note_id':'f'*64},{'evidence_stage':'DELIVERY_COMPLETED'},
 {'project_relation':'SAME_COMPANY_IS_SAME_PROJECT'},{'period_end':'2999-01-01'},
 {'fact_verified':True},{'matching_basis':'x'*201},
 {'counter_reference':{'body':'article body'}},
 {'counter_reference':{'title':'위험','source_url':'https://localhost/private','reported_date':'2026-01-01',
                       'analysis_text':'외부 링크','access_basis':'PUBLIC_SEARCH_RESULT_READING'}}])
def test_invalid_execution_and_external_reference_does_not_publish(tmp_path,monkeypatch,change):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch)
    data=deepcopy(doc);data['notes'][0]['execution'].update(change);pins=fingerprint(tmp_path)
    with pytest.raises((SourceShareError,ValueError)):
        publish_followups(root,data,bases,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    assert fingerprint(tmp_path)==pins

def test_mixed_evidence_and_same_company_not_same_project(tmp_path,monkeypatch):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch)
    for n,stage,kind in zip(doc['notes'],['INDIVIDUAL_ORDER','CANCELLATION','DELIVERY_COMPLETED'],
                            ['REPORTED_CONTRACT','CANCELLATION','REPORTED_DELIVERY']):
        n['reported_date']=datetime.now(timezone.utc).date().isoformat();n['evidence_kind']=kind
        n['execution'].update(project_relation='SAME_PROJECT_EXPLICIT',evidence_stage=stage,period_end=None)
    publish_followups(root,doc,bases,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    g=next(g for g in read_discovery(root,include_common_causes=True,recent_workspaces=(ws,))['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
    assert g['recent_news_comparison']['execution_comparison']['status']=='MIXED_EXECUTION_EVIDENCE'
    assert not g['recent_news_comparison']['execution_comparison']['source_truth_independently_verified']

def test_manual_local_inputs_do_not_use_network_budget_and_bad_body_keeps_state(tmp_path,monkeypatch):
    root,w,_,ws,_,_,_,_=fixture(tmp_path,monkeypatch)
    connection=sqlite3.connect(ws.poll_state)
    assert connection.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==0
    connection.close()
    provider='latest-official-reviewed-titles';endpoint='https://latest.example.org/news'
    p=private_json(tmp_path/'local_again.json',{'items':[{'id':endpoint+'/extra','url':endpoint+'/extra','title':'가상배전, 추가 수주 실적 발표'}]})
    code,result=import_titles(w,root,provider_id=provider,official_list_url=endpoint,metadata_file=p,scope='other')
    assert code==0 and result['status']=='READY' and not result['network_called']
    pins=fingerprint(w/'state');p.write_text(p.read_text().replace('"title":','"body":"forbidden","title":'))
    code,result=import_titles(w,root,provider_id=provider,official_list_url=endpoint,metadata_file=p,scope='other')
    assert code==4 and result['status']=='INPUT_UNAVAILABLE'
    assert fingerprint(w/'state')==pins
    from test_official_power_news_path import registry
    approved=registry(datetime.now(timezone.utc))
    with pytest.raises(SourceShareError,match='explicit manual'):
        incremental_poll(approved,approved.providers[0].provider_id,tmp_path/'bad.sqlite3',manual_payload=b'{}')

def test_execution_UI_risk_labels_chronology_and_source_links(tmp_path,monkeypatch):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch)
    publish_followups(root,doc,bases,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    data=next(g['recent_news_comparison'] for g in read_discovery(root,include_common_causes=True,recent_workspaces=(ws,))['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
    script=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8'),data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,text){return {textContent:text||'',children:[],append(...x){this.children.push(...x)},addEventListener(){}}}
const p=node('div'),ctx={node};vm.runInNewContext(s.slice(s.indexOf('function renderRecentThemeComparison('),s.indexOf('function renderPublicDemandNotes(')),ctx);
ctx.renderRecentThemeComparison(p,data);function all(n){return [n,...n.children.flatMap(all)]}
const text=all(p).map(n=>n.textContent).join(' ');
for(const x of ['개별 발주·납품·수주 실적의 실행 비교','실적 대상 기간은 앞섬','수집 원장 미등록 외부 참고 링크','반증 후보·위험 참고 기사','실제 취소·수요 감소를 확인한 자료 아님'])assert(text.includes(x),x);
assert(all(p).some(n=>n.href==='https://press.example.org/story/1'));
"""
    subprocess.run(['node','-e',script],input=json.dumps(data),text=True,capture_output=True,check=True,
                   cwd=Path(__file__).resolve().parent.parent)

@pytest.mark.parametrize('stage,kind',[('DELIVERY_COMPLETED','REPORTED_DELIVERY'),('CANCELLATION','CANCELLATION')])
def test_undated_reference_keeps_pit_and_never_becomes_followup_execution(tmp_path,monkeypatch,stage,kind):
    from newscatalystos.recent_theme_followups import SCHEMA_V3
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch)
    before=datetime.now(timezone.utc)
    original=export_discovery(root,as_of=before,now=before,include_common_causes=True,recent_workspaces=(ws,))
    doc['schema']=SCHEMA_V3;doc['notes']=doc['notes'][:1];n=doc['notes'][0]
    n.update(reported_date=None,evidence_kind=kind)
    n['execution'].update(project_relation='SAME_PROJECT_EXPLICIT',evidence_stage=stage,period_end=None,
        counter_reference={'title':'합성: 납기와 환율 위험 전망','source_url':'https://press.example.org/full',
            'reported_date':before.date().isoformat(),'analysis_text':'공개 본문에 실린 전망이며 실제 취소 확인은 아니다.',
            'access_basis':'PUBLIC_PAGE_READING'})
    p=private_json(tmp_path/'undated.json',doc)
    assert execute(root,p,(ws,))['created']==1
    assert execute(root,p,(ws,))['created']==0
    now=datetime.now(timezone.utc)
    rows=read_followups(root,bases,metadata_resolver((ws,),now=now),as_of=now,now=now)
    selected=[r for r in rows if r['note']['reported_date'] is None];row,=selected
    assert row['schema']==SCHEMA_V3 and row['recent_available_at']<=row['available_at']
    context=row['execution_context']
    assert context['chronology']=='PUBLICATION_DATE_UNAVAILABLE'
    assert not context['reported_execution_progress'] and not context['reported_execution_setback']
    assert export_discovery(root,as_of=before,now=now,include_common_causes=True,recent_workspaces=(ws,))==original
    script=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8'),data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,text){return {textContent:text||'',children:[],append(...x){this.children.push(...x)},addEventListener(){}}}
const p=node('div'),ctx={node};vm.runInNewContext(s.slice(s.indexOf('function renderRecentThemeComparison('),s.indexOf('function renderPublicDemandNotes(')),ctx);
ctx.renderRecentThemeComparison(p,data);function all(n){return [n,...n.children.flatMap(all)]}
const text=all(p).map(n=>n.textContent).join(' ');
for(const x of ['원문 표시일 미확인','후속 이행 시점 판단 제외','공개 기사 본문을 읽은 별도 분석'])assert(text.includes(x),x);
assert(!text.includes('null')&&!text.includes('undefined'));
"""
    from newscatalystos.recent_theme_followups import assess
    subprocess.run(['node','-e',script],input=json.dumps(assess(selected,[row['source_company']])),
                   text=True,capture_output=True,check=True,cwd=Path(__file__).resolve().parent.parent)

@pytest.mark.parametrize('version,period',[
    ('newscatalyst.recent_theme_followup.v2',None),
    ('newscatalyst.recent_theme_followup.v3','2026-01-01')])
def test_undated_reference_requires_new_version_and_no_invented_period(tmp_path,monkeypatch,version,period):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch)
    doc['schema']=version;doc['notes']=doc['notes'][:1];doc['notes'][0]['reported_date']=None
    doc['notes'][0]['execution']['period_end']=period;pins=fingerprint(tmp_path)
    with pytest.raises(SourceShareError):
        publish_followups(root,doc,bases,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    assert fingerprint(tmp_path)==pins


def test_reference_only_notes_stay_queryable_without_entering_legacy_evaluation_contract(tmp_path,monkeypatch):
    from newscatalystos.recent_theme_followups import SCHEMA_V3
    from newscatalystos.company_economic_changes import build_changes
    from newscatalystos.theme_emergence import ThemeStore
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch)
    doc['schema']=SCHEMA_V3
    first,last=doc['notes'][0],doc['notes'][2]
    first.update(reported_date=None,evidence_kind='REPORTED_DELIVERY')
    first['execution'].update(evidence_stage='DELIVERY_COMPLETED',period_end=None)
    last['evidence_kind']='PLAN_ONLY'
    last['execution'].update(evidence_stage='DELIVERY_PLANNED',period_end=None)
    now=datetime.now(timezone.utc)
    assert publish_followups(root,doc,bases,metadata_resolver((ws,),now=now),now=now)['created']==3
    now=datetime.now(timezone.utc)
    view=read_discovery(root,as_of=now,now=now,include_common_causes=True,recent_workspaces=(ws,))
    reading=[r for g in view['theme_outlook']['candidates'] for r in g.get('recent_news_comparison',{}).get('notes',[])]
    assert any(r['note']==first for r in reading) and any(r['note']==last for r in reading)
    changes=build_changes(ThemeStore(root/'theme_history').search(as_of=now,now=now),view,None,as_of=now)
    exported=[e['recent']['note'] for v in changes.values() for e in v['entries']]
    assert exported and doc['notes'][1] in exported
    assert first not in exported and last not in exported
    assert all(n['reported_date'] is not None for n in exported)
