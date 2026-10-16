"""Synthetic PIT multi-theme company timelines; no new economic facts."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.company_timeline import company_timelines,select_timelines
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.article_company_identity import resolve_names
from test_article_company_identity import context
from test_service_realization import claim,T
from test_theme_emergence import event
from test_event_supply_impact import case as supply_case
from test_federated_news_search import fingerprint


def identified(title,n):
 row=claim(title,n)
 mappings,_=resolve_names(['가상전자'],{'a':context(T,'가상전자','00000001')},at=T)
 return economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'change','event_id'}},company_mappings=[{k:m[k] for k in ('source_name','entity_id','evidence_sha256')} for m in mappings],source_binding={'source_event_sha256':sha256(str(n).encode()).hexdigest(),'document_sha256':row['change']['source_paragraph_sha256']})


def case(tmp_path):
 store=ThemeStore(tmp_path/'theme_history')
 decision=identified('가상전자, HBM 수요 회복으로 「청해공장」 투자 결정',0)
 first,=store.ingest([decision],now=T)
 duplicate=deepcopy(decision);duplicate['source_url']='https://example.org/reprint'
 execution=identified('가상전자, HBM 수요 회복으로 「청해공장」 투자 집행',1)
 at=T+timedelta(hours=2)
 store.ingest([duplicate,execution,event(2,topic='DRAM',company='DART_CORP:00000001')],now=at)
 return store.search(now=at),store,first,at


def build(themes,at,since=None):
 cs=json.loads(build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True))['CompanyCandidates']
 ctx=company_search_context(themes,cs);comparisons=common_cause_comparisons(themes,cs)
 return company_timelines(themes,cs,ctx,comparisons,as_of=at,since=since),cs,ctx,comparisons


def test_same_identified_company_two_themes_new_action_followup_and_more_sources(tmp_path):
 themes,store,first,at=case(tmp_path);disk=fingerprint(tmp_path);old=deepcopy(themes)
 raw=build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True)
 timeline,cs,ctx,comparisons=build(themes,at,T+timedelta(hours=1))
 company,=timeline['companies'];entries=company['entries']
 assert company['entity_id']=='DART_CORP:00000001' and company['identity_status']=='IDENTIFIED'
 assert len(company['candidate_ids'])==2 and len(entries)==4
 assert company['distinct_economic_actions']==2 and company['new_actions_in_period']==1
 assert sorted(e['change_kind'] for e in entries)==['ADDITIONAL_SOURCE','ECONOMIC_ACTION_FIRST_OBSERVED','ECONOMIC_ACTION_FIRST_OBSERVED','SOURCE_REPORTED_FOLLOWUP']
 assert len({e['theme_id'] for e in entries})==2
 followup=next(e for e in entries if e['change_kind']=='SOURCE_REPORTED_FOLLOWUP')
 assert followup['action']=='INVESTMENT_EXECUTION' and followup['cause']['source_expression']=='HBM 수요 회복으로'
 assert any(e['source_available_at']!=e['observed_at'] for e in entries)
 assert sum(not e['in_period'] for e in entries)==1
 assert not company['verified_real_transaction'] and not company['verified_real_benefit']
 assert themes==old and fingerprint(tmp_path)==disk
 assert raw==build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True)
 past,*_=build(store.search(as_of=T,now=at),T)
 assert len(past['companies'][0]['entries'])==1 and past['companies'][0]['distinct_economic_actions']==1


def test_source_names_are_not_merged_across_themes_without_identity(tmp_path):
 store=ThemeStore(tmp_path/'themes');at=T+timedelta(hours=1)
 themes=store.ingest([event(1,topic='HBM',company='가상전자'),event(2,topic='DRAM',company='가상전자')],now=at)
 timeline,cs,ctx,*_=build(themes,at)
 assert len(timeline['companies'])==2
 assert all(c['identity_status']=='SOURCE_NAME_ONLY' and c['distinct_economic_actions']==1 for c in timeline['companies'])
 selected=select_timelines(timeline,match_company_search(ctx,'가상'), '가상')
 assert selected['companies']==[] and selected['status']=='NO_EXACT_COMPANY_MATCH'


def test_ambiguous_name_does_not_select_a_merged_company(tmp_path):
 at=T;themes=ThemeStore(tmp_path/'themes').ingest([event(1,company='DART_CORP:00000001'),event(2,company='DART_CORP:00000002')],now=at)
 timeline,cs,ctx,comparisons=build(themes,at)
 for c in cs:c['display_name']='동명전자'
 matches=match_company_search(company_search_context(themes,cs),'동명전자')
 selected=select_timelines(timeline,matches,'동명전자')
 assert selected['status']=='AMBIGUOUS_NAME' and selected['companies']==[]
 selected=select_timelines(timeline,match_company_search(ctx,'DART_CORP:00000001'),'DART_CORP:00000001')
 assert len(selected['companies'])==1


def test_supply_relationship_is_not_own_action_and_observation_starts_when_linked(tmp_path):
 theme,cs,store,first,at,info=supply_case(tmp_path)
 timeline,*_=build([theme],at)
 supplier=next(c for c in timeline['companies'] if c['entity_id']=='SEC_CIK:111111')
 assert supplier['distinct_economic_actions']==supplier['new_actions_in_period']==0
 assert supplier['related_action_contexts']==1
 entry,=supplier['entries'];assert entry['observed_at']==at.isoformat()
 assert entry['change_kind']=='RELATION_CONTEXT_ADDED' and entry['company_participation']=='SUPPLY_CHAIN_CONTEXT'
 assert entry['cause']['source_expression'] is None
 assert entry['recorded_at']!=entry['observed_at']
 assert len(build([first],info[-1])[0]['companies'])==1

@pytest.mark.parametrize('fault',['snapshot','context_company','future_observation','future_source','future_snapshot'])
def test_other_version_company_or_future_source_cannot_enter_timeline(tmp_path,fault):
 themes,store,first,at=case(tmp_path);_,cs,ctx,comparisons=build(themes,at)
 if fault=='snapshot':
  for c in cs:c['theme_snapshot_sha256']='f'*64
 if fault=='context_company':
  for v in ctx.values():v['entity_id']='DART_CORP:99999999'
 if fault in {'future_observation','future_source'}:
  for v in ctx.values():
   for source in v['sources']:source['recorded_at' if fault=='future_observation' else 'source_available_at']=(at+timedelta(days=1)).isoformat()
 if fault=='future_snapshot':at=T-timedelta(seconds=1)
 assert company_timelines(themes,cs,ctx,comparisons,as_of=at)['companies']==[]


def test_mismatched_comparison_cannot_lend_quotation_and_empty_days_do_not_weaken(tmp_path):
 themes,store,first,at=case(tmp_path);_,cs,ctx,comparisons=build(themes,at)
 for view in comparisons.values():view['theme_snapshot_sha256']='f'*64
 future=at+timedelta(days=1)
 timeline=company_timelines(themes,cs,ctx,comparisons,as_of=future,since=at+timedelta(hours=1))
 c,=timeline['companies'];assert c['new_actions_in_period']==0 and len(c['entries'])==4
 assert all(not e['in_period'] and e['cause']['source_expression'] is None for e in c['entries'])
 assert all(e['change_kind'] not in {'WEAKENING','INVALIDATED'} for e in c['entries'])



def test_directory_name_metadata_cannot_add_actions_or_leak_a_future_name(tmp_path):
 themes,store,first,at=case(tmp_path);baseline,cs,ctx,comparisons=build(themes,at)
 for c in cs:
  c['official_name_context']={'status':'MATCHED','decision_at':(at+timedelta(days=1)).isoformat(),
   'proof':{'entity_id':c['entity_id'],'issuer_name':'미래명칭전자','available_at':(at+timedelta(days=1)).isoformat()}}
 current=company_timelines(themes,cs,ctx,comparisons,as_of=at)
 assert current==baseline
 for c in cs:c['official_name_context']['decision_at']=at.isoformat();c['official_name_context']['proof']['available_at']=at.isoformat()
 current=company_timelines(themes,cs,ctx,comparisons,as_of=at)
 assert current['companies'][0]['entries']==baseline['companies'][0]['entries']
 assert current['companies'][0]['distinct_economic_actions']==2



def test_later_identity_join_does_not_create_a_new_economic_action(tmp_path):
 themes=ThemeStore(tmp_path/'themes').ingest([event(1,topic='HBM',company='가상전자'),event(2,topic='DRAM',company='가상전자')],now=T)
 baseline,cs,ctx,comparisons=build(themes,T);later=T+timedelta(hours=1)
 for c in cs:c['resolved_entity_id']='DART_CORP:00000001';c['identity_context']={'status':'MATCHED','decision_at':later.isoformat()}
 current=company_timelines(themes,cs,ctx,comparisons,as_of=later,since=T+timedelta(minutes=30))
 company,=current['companies'];assert company['distinct_economic_actions']==2 and company['new_actions_in_period']==0
 assert all(e['observed_at']==T.isoformat() and e['identity_available_at']==later.isoformat() for e in company['entries'])
 past=company_timelines(themes,cs,ctx,comparisons,as_of=T)
 assert len(past['companies'])==2 and all(c['identity_status']=='SOURCE_NAME_ONLY' for c in past['companies'])


def test_ui_displays_multitheme_timeline_on_exact_company_search(tmp_path):
 themes,store,first,at=case(tmp_path);timeline,cs,ctx,*_=build(themes,at)
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCompanyTimelines(parent,input.timeline,input.query,companySearchResults(input.context,input.query));',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 def render(query):return subprocess.check_output(['node','-e',code],input=json.dumps(dict(timeline=timeline,context=ctx,query=query)).encode()).decode()
 text=render('DART_CORP:00000001')
 assert '기업별 경제 변화 타임라인' in text and '같은 행동의 후속 단계 보도' in text and '같은 사건의 추가 근거' in text
 assert 'DRAM' in text and 'HBM' in text and '출처 가용:' in text and '선택 판본:' in text
 assert json.loads(render('가상'))['children']==[]


def test_http_period_and_company_research_timelines_keep_pit_and_standard_v3(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 themes,store,first,at=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  q='DART_CORP:00000001'
  r=json.loads(fetch('/api/company-research',q=q,as_of=at.isoformat()))
  p=json.loads(fetch('/api/period',q=q,date=at.astimezone(dashboard.KST).date().isoformat()))
  assert len(r['company_timelines']['companies'])==len(p['company_timelines']['companies'])==1
  assert len(r['company_timelines']['companies'][0]['entries'])==4
  old=json.loads(fetch('/api/company-research',q=q,as_of=T.isoformat()))
  assert len(old['company_timelines']['companies'][0]['entries'])==1
  assert json.loads(fetch('/api/company-research',q='DRAM',as_of=at.isoformat()))['company_timelines']['companies']==[]
  assert fetch('/api/themes',as_of=at.isoformat(),company_candidates='1')==build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True)
  def unavailable(*a,**kw):raise OSError('synthetic unavailable store')
  monkeypatch.setattr(dashboard.ThemeStore,'search',unavailable)
  failed=json.loads(fetch('/api/period',date=at.astimezone(dashboard.KST).date().isoformat()))
  assert failed['theme_status']=='UNAVAILABLE' and failed['company_timelines']=={'status':'UNAVAILABLE','companies':[]}
 finally:server.shutdown();server.server_close();worker.join(2)
