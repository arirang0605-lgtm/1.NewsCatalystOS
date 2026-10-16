"""Synthetic stored versions: period formation, expansion and retained context."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,subprocess,sqlite3,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.cross_product_period import period_cross_product
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from test_cross_product_demand import case,T,END
from test_adjacent_demand_scope import text,observe
from test_federated_news_search import fingerprint

LATER=END+timedelta(hours=1)


def run(store,*,since=END,as_of=END,activity='changed',query='',identity_root=None):
 selected=store.search(as_of=as_of,now=as_of,since=since,activity=activity)
 cs=json.loads(build_theme_bundle(selected,decision_at=as_of,now=as_of,include_company_candidates=True))['CompanyCandidates']
 current=cross_product_demand(selected,cs,common_cause_comparisons(selected,cs),as_of=as_of,since=since,query=query)
 return period_cross_product(store,selected,current,since=since,as_of=as_of,now=as_of,query=query,identity_root=identity_root),selected,current


def test_single_product_baseline_forms_group_with_old_context_outside_activity_filter(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path);disk=fingerprint(tmp_path)
 result,selected,current=run(store,identity_root=tmp_path/'identity')
 assert len(selected)==1 and current['groups']==[]
 group,=result['groups'];change=group['period_change']
 assert result['period_status']=='READY' and change['status']=='READY' and change['formed_in_period']
 assert change['before']['products']==['HBM'] and change['after']['products']==['DRAM','HBM']
 assert change['new_products']==['DRAM'] and len(change['new_action_group_ids'])==1
 old=next(p for p in group['products'] if p['product']=='HBM')
 assert old['context_kind']=='EXISTING_PRODUCT_CONTEXT'
 assert not old['actions'][0]['sources'][0]['in_period']
 assert change['before']['theme_snapshots'][0]['decision_at']==T.isoformat()
 assert disk==fingerprint(tmp_path)


def test_existing_group_expands_to_new_product_and_new_action_without_rewriting(tmp_path):
 store,*_=case(tmp_path);before=store.search(now=END)
 raw=build_theme_bundle(before,decision_at=END,now=END,include_company_candidates=True)
 row,=extract_economic_changes(text(actor='빛결반도체',product='NAND'))
 store.ingest([observe(row,10)],now=LATER)
 result,selected,*_=run(store,since=LATER,as_of=LATER)
 group,=result['groups'];change=group['period_change']
 assert not change['formed_in_period'] and change['new_products']==['NAND']
 assert len(change['new_action_group_ids'])==1 and change['removed_action_group_ids']==[]
 assert len(selected)==1 and sum(p['context_kind']=='EXISTING_PRODUCT_CONTEXT' for p in group['products'])==2
 assert raw==build_theme_bundle(store.search(as_of=END,now=LATER),decision_at=END,now=LATER,include_company_candidates=True)


def test_new_action_on_existing_product_is_distinct_from_product_expansion(tmp_path):
 store,*_=case(tmp_path)
 row,=extract_economic_changes(text(actor='별빛전자'))
 store.ingest([observe(row,10)],now=LATER)
 result,*_=run(store,since=LATER,as_of=LATER)
 change=result['groups'][0]['period_change']
 assert change['new_products']==[] and len(change['new_action_group_ids'])==1 and not change['formed_in_period']


def test_reprint_and_empty_period_are_not_action_or_product_growth(tmp_path):
 store,*rest=case(tmp_path);original=rest[-1][0]
 reprint=deepcopy(original);reprint['source_url']='https://example.org/reprint'
 store.ingest([reprint],now=LATER)
 result,*_=run(store,since=LATER,as_of=LATER)
 change=result['groups'][0]['period_change']
 assert change['new_products']==[] and change['new_action_group_ids']==[] and not change['formed_in_period']
 empty,*_=run(store,since=LATER+timedelta(seconds=1),as_of=LATER+timedelta(hours=1),activity='all')
 assert empty['groups'][0]['period_change']['new_action_group_ids']==[]


def test_project_followup_does_not_look_like_an_independent_action(tmp_path):
 from test_service_realization import claim
 store=ThemeStore(tmp_path/'theme_history')
 plan=claim('가상전자, AI 서버용 HBM 수요 증가로 ‘별빛검사’ 서비스 개시 예정',0,at=T)
 start=claim('가상전자, AI 서버용 HBM 수요 증가로 ‘별빛검사’ 서비스 정식 개시',1,at=END)
 other=extract_economic_changes(text(actor='새빛소재',product='DRAM'))[0]
 # Explicit semiconductor context is retained for the service's source claim.
 for r in (plan,start):r['change']['industry_tags']=['SEMICONDUCTOR']
 # Rebuild identity after adding only the source industry tag.
 def rebuilt(r):return economic_observation(r['change'],**{k:v for k,v in r.items() if k not in {'change','event_id'}})
 store.ingest([rebuilt(plan),observe(other,4)],now=T)
 store.ingest([rebuilt(start)],now=END)
 result,*_=run(store)
 change=result['groups'][0]['period_change']
 assert change['new_action_group_ids']==[] and change['new_products']==[]


@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_removed_product_and_target_sources_or_conflict_stay_visible(tmp_path,polarity):
 store,*rest=case(tmp_path);base=rest[-1][0]
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([negative],now=LATER)
 result,*_=run(store,since=LATER,as_of=LATER)
 group,=result['groups'];change=group['period_change']
 if polarity=='RETRACT':
  assert group['status']=='PERIOD_CONTEXT_ONLY' and not change['is_current_candidate']
  assert change['removed_product_codes']==['HBM'] and len(change['removed_action_group_ids'])==1
  old,=group['removed_products'];assert old['context_kind']=='HISTORICAL_REMOVED_PRODUCT'
  assert old['actions'][0]['sources'][0]['source_url']==base['source_url']
  assert old['current_theme_status']=='INVALIDATED' and old['counterevidence'][0]['source_url']=='https://example.org/correction'
 else:
  assert group['status']=='COMMON_CAUSE_HYPOTHESIS' and change['removed_product_codes']==[]
  assert any(s['conflicting'] for p in group['products'] for a in p['actions'] for s in a['sources'])


def test_removed_action_keeps_its_original_source_when_product_still_exists(tmp_path):
 store,*rest=case(tmp_path);base=rest[-1][0]
 extra=extract_economic_changes(text(actor='별빛전자'))[0];store.ingest([observe(extra,5)],now=END)
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity='RETRACT',supersedes_event_id=base['event_id'])
 store.ingest([negative],now=LATER)
 result,*_=run(store,since=LATER,as_of=LATER)
 group,=result['groups'];assert group['status']=='COMMON_CAUSE_HYPOTHESIS'
 old,=group['removed_action_contexts'];assert old['context_kind']=='HISTORICAL_REMOVED_ACTION'
 assert old['actions'][0]['sources'][0]['source_url']==base['source_url']
 assert len(group['period_change']['removed_action_group_ids'])==1


@pytest.mark.parametrize('fault',['read_error','corrupt_digest','selected_mismatch'])
def test_history_failure_only_marks_period_unknown_preserving_current(tmp_path,monkeypatch,fault):
 store,themes,cs,comp,*_=case(tmp_path)
 current=cross_product_demand(themes,cs,comp,as_of=END,since=END)
 if fault=='read_error':
  def fail(**kw):raise OSError('synthetic unreadable history')
  monkeypatch.setattr(store,'period_versions',fail)
 elif fault=='corrupt_digest':
  with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute('UPDATE versions SET digest=? WHERE decision_at=?',('f'*64,T.isoformat()))
 else:themes[0]['scores']['company_breadth']+=1
 result=period_cross_product(store,themes,current,since=END,as_of=END,now=END)
 assert result['period_status']=='UNAVAILABLE'
 assert result['groups'][0]['products']==current['groups'][0]['products']
 assert result['groups'][0]['period_change']['status']=='UNAVAILABLE'


def test_missing_baseline_is_not_zero_growth_or_fabricated_first_formation(tmp_path):
 store,*_=case(tmp_path)
 # A post-period observation retains a first_detected_at before since, but its baseline was lost.
 reprint=deepcopy(observe(extract_economic_changes(text())[0],0));reprint['source_url']='https://example.org/reprint'
 store.ingest([reprint],now=END)
 with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute('DELETE FROM versions WHERE decision_at=?',(T.isoformat(),))
 result,*_=run(store,activity='all')
 group,=result['groups'];assert group['period_change']['status']=='UNAVAILABLE'
 assert 'new_action_group_ids' not in group['period_change'] and group['products']


def test_all_first_observed_in_period_has_no_prior_recorded_scope(tmp_path):
 store,*_=case(tmp_path)
 result,*_=run(store,since=T)
 change=result['groups'][0]['period_change']
 assert change['baseline']=='NO_PRIOR_RECORDED_SCOPE' and change['formed_in_period']
 assert change['before']['products']==[]


def test_historical_query_future_and_company_search_boundaries(tmp_path):
 store,*_=case(tmp_path)
 assert run(store,since=T,as_of=T)[0]['groups']==[]
 result,*_=run(store,query='가상전자')
 assert len(result['groups'])==1 and result['groups'][0]['search_match']=='DIRECT_COMPANY_CONTEXT'
 assert run(store,query='무관 기업')[0]['groups']==[]
 current={'groups':[]};future=period_cross_product(store,[],current,since=LATER,as_of=END,now=END)
 assert future['period_status']=='NOT_STARTED'
 assert period_cross_product(store,[],current,since=None,as_of=END,now=END)['period_status']=='PERIOD_NOT_SPECIFIED'


def test_ui_labels_old_context_baseline_and_new_period_actions(tmp_path):
 store,*_=case(tmp_path);data,*_=run(store)
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
 assert '기간 내 복수 제품 형성' in rendered and '새 제품: DRAM' in rendered
 assert '기존 비교 맥락 · 활동 필터의 새 테마로 세지 않음' in rendered
 assert '기간 직전 제품·판본 기준' in rendered and '기간 내 새 독립 행동' in rendered
 assert T.isoformat() in rendered and END.isoformat() in rendered


def test_http_period_retains_old_product_without_promoting_to_selected_theme(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,*_=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  research=json.loads(fetch('/api/company-research',q='가상전자',since=END.isoformat(),as_of=END.isoformat(),activity='new'))
  group,=research['cross_product_demand']['groups']
  assert group['period_change']['formed_in_period'] and len(group['products'])==2
  assert not research['CompanyCandidates'] # New-theme filter excludes the old searched company; comparison context is explicit.
  data=json.loads(fetch('/api/period',date='2026-10-15',theme_activity='changed'))
  assert data['cross_product_demand']['period_status']=='READY'
  assert fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
 finally:server.shutdown();server.server_close();thread.join(2)


def test_identity_mapping_update_is_not_new_product_action_or_formation(tmp_path):
 store,*rest=case(tmp_path);base=rest[-1][0]
 mapped=economic_observation(base['change'],**{k:v for k,v in base.items() if k not in {'event_id','change'}},company_mappings=[{'source_name':'가상전자','entity_id':'SEC_CIK:111111','evidence_sha256':'a'*64}])
 assert mapped['event_id']==base['event_id']
 store.ingest([mapped],now=LATER)
 result,*_=run(store,since=LATER,as_of=LATER)
 change=result['groups'][0]['period_change']
 assert change['new_products']==[] and change['new_action_group_ids']==[] and not change['formed_in_period']


def test_unresolved_same_names_across_products_remain_separate_in_period(tmp_path):
 store,*_=case(tmp_path,actors=('동명전자','동명전자'))
 result,*_=run(store)
 group,=result['groups'];keys={a['company_key'] for p in group['products'] for a in p['actions']}
 assert len(keys)==2 and group['identified_company_count']==0
 assert len(group['period_change']['new_action_group_ids'])==1
