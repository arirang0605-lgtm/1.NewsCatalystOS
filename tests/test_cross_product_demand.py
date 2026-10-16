"""Synthetic shared-end-use hypotheses; no merged canonical themes or benefits."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore
from test_adjacent_demand_scope import text,observe
from test_theme_emergence import T
from test_federated_news_search import fingerprint

END=T+timedelta(hours=1)


def case(tmp_path,*,scopes=('AI 서버','AI 서버'),actors=('가상전자','새빛소재')):
 store=ThemeStore(tmp_path/'theme_history');observations=[]
 for n,(product,scope,actor) in enumerate(zip(['HBM','DRAM'],scopes,actors)):
  row,=extract_economic_changes(text(scope,actor,product));observations.append(observe(row,n))
 store.ingest(observations[:1],now=T);store.ingest(observations[1:],now=END)
 themes=store.search(now=END)
 cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 comp=common_cause_comparisons(themes,cs)
 return store,themes,cs,comp,observations


def view(themes,cs,comp,**kw):return cross_product_demand(themes,cs,comp,as_of=kw.pop('as_of',END),**kw)


def test_cross_product_positive_pins_all_products_sources_and_keeps_canonical(tmp_path):
 store,themes,cs,comp,observations=case(tmp_path);before=deepcopy((themes,cs,comp));disk=fingerprint(tmp_path)
 raw=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 data=view(themes,cs,comp,since=END);group,=data['groups']
 assert group['status']=='COMMON_CAUSE_HYPOTHESIS' and group['distinct_action_groups']==2
 assert {p['product'] for p in group['products']}=={'HBM','DRAM'}
 assert group['identified_company_count']==0 and group['unresolved_company_contexts']==2
 for product in group['products']:
  assert product['theme_snapshot_sha256']==comp[product['theme_id']]['theme_snapshot_sha256']
  action,=product['actions'];source,=action['sources']
  assert source['demand_scope']['destination']=='AI 서버' and source['source_binding']
  assert source['in_period']==(product['product']=='DRAM')
  assert source['cause']['source_expression'] and source['company_participation']=='SOURCE_EVENT_ACTOR'
 assert not group['verified_real_benefit'] and not data['orders_enabled']
 assert (themes,cs,comp)==before and fingerprint(tmp_path)==disk
 assert raw==build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)


@pytest.mark.parametrize('scopes',[('AI 서버','모바일'),('AI 서버','AI 서버 및 모바일')])
def test_other_or_unresolved_destination_is_not_borrowed(tmp_path,scopes):
 store,themes,cs,comp,*_=case(tmp_path,scopes=scopes)
 assert view(themes,cs,comp)['groups']==[]


def test_missing_scope_or_same_product_alone_cannot_form_group(tmp_path):
 from test_adjacent_demand import TEXT
 store,themes,cs,comp,observations=case(tmp_path)
 row,=extract_economic_changes(TEXT.replace('가상전자','새빛소재').replace('HBM','DRAM'))
 other=ThemeStore(tmp_path/'other');other.ingest([observations[0],observe(row,10)],now=END)
 themes=other.search(now=END);cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 assert view(themes,cs,common_cause_comparisons(themes,cs))['groups']==[]
 themes=[t for t in themes if 'HBM' in t['topic_aliases']]
 assert view(themes,cs,common_cause_comparisons(themes,cs))['groups']==[]


@pytest.mark.parametrize('fault',['candidate_sha','comparison_sha','future_decision','future_source','other_industry','other_driver','relation_only'])
def test_mismatched_future_unrelated_or_relation_only_evidence_cannot_add_product(tmp_path,fault):
 store,themes,cs,comp,*_=case(tmp_path);tid=themes[0]['theme_id']
 if fault=='candidate_sha':next(c for c in cs if c['theme_id']==tid)['theme_snapshot_sha256']='f'*64
 elif fault=='comparison_sha':comp[tid]['theme_snapshot_sha256']='f'*64
 elif fault=='future_decision':themes[0]['decision_at']=(END+timedelta(hours=1)).isoformat()
 elif fault=='future_source':comp[tid]['rows'][0]['sources'][0]['source_available_at']=(END+timedelta(hours=1)).isoformat()
 elif fault=='other_industry':themes[0]['industry_tags']=['OTHER']
 elif fault=='other_driver':themes[0]['economic_driver']='CAPACITY_EXPANSION'
 else:
  for r in comp[tid]['rows']:
   for s in r['sources']:s['company_participation']='SUPPLY_CHAIN_CONTEXT'
 result=view(themes,cs,comp)
 assert result['groups']==[]


def test_reprints_do_not_raise_independent_actions_or_company_count(tmp_path):
 store,themes,cs,comp,observations=case(tmp_path)
 reprint=deepcopy(observations[0]);reprint['source_url']='https://example.org/reprint'
 store.ingest([reprint],now=END);themes=store.search(now=END)
 cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 group,=view(themes,cs,common_cause_comparisons(themes,cs))['groups']
 assert group['distinct_action_groups']==2 and group['unresolved_company_contexts']==2
 assert sum(len(a['sources']) for p in group['products'] for a in p['actions'])==3


def test_identical_unresolved_names_remain_separate_company_contexts(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path,actors=('동명전자','동명전자'))
 group,=view(themes,cs,comp)['groups']
 keys={a['company_key'] for p in group['products'] for a in p['actions']}
 assert len(keys)==2 and all(k.startswith('UNRESOLVED:') for k in keys)
 assert group['identified_company_count']==0 and group['unresolved_company_contexts']==2


def test_official_identity_merges_only_company_count_not_actions_or_products(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path)
 # Existing valid identity contexts are as-of metadata, independent of theme snapshots.
 for c in cs:c['resolved_entity_id']='SEC_CIK:111111';c['identity_context']={'status':'MATCHED','decision_at':T.isoformat()}
 group,=view(themes,cs,comp)['groups']
 assert group['identified_company_count']==1 and group['distinct_action_groups']==2
 for c in cs:c['identity_context']['decision_at']=(END+timedelta(hours=1)).isoformat()
 group,=view(themes,cs,comp)['groups']
 assert group['identified_company_count']==0 and group['unresolved_company_contexts']==2


@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_negative_reports_exclude_retracted_product_or_remain_visible_as_conflict(tmp_path,polarity):
 from newscatalystos.theme_emergence import economic_observation
 store,themes,cs,comp,observations=case(tmp_path)
 base=observations[0];negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=END.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([negative],now=END);themes=store.search(now=END)
 cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 result=view(themes,cs,common_cause_comparisons(themes,cs))
 if polarity=='RETRACT':assert result['groups']==[]
 else:
  group,=result['groups'];product=next(p for p in group['products'] if p['product']=='HBM')
  assert product['theme_status']=='WEAKENING' and product['counterevidence'][0]['source_url']=='https://example.org/correction'
  assert product['actions'][0]['sources'][0]['conflicting']


def test_historical_period_and_search_retain_related_product_context_without_borrowing(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path)
 first=store.search(as_of=T,now=END)
 assert view(first,[c for c in cs if c['theme_id']==first[0]['theme_id']],common_cause_comparisons(first),as_of=T)['groups']==[]
 assert view(themes,cs,comp,since=END+timedelta(seconds=1))['status']=='NOT_STARTED'
 assert len(view(themes,cs,comp,query='가상전자')['groups'])==1
 assert view(themes,cs,comp,query='AI 서버')['groups'][0]['search_match']=='TEXT_CONTEXT'
 assert view(themes,cs,comp,query='다른 수요처')['groups']==[]


@pytest.mark.parametrize('alias',['','명부표시명'])
def test_ui_displays_products_bound_sources_times_and_uncertainty(tmp_path,alias):
 store,themes,cs,comp,*_=case(tmp_path);data=view(themes,cs,comp);data['test_alias']=alias
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input,input.test_alias,{[input.groups[0].products[0].actions[0].candidate_id]:{match_kind:"DIRECT_COMPANY"}});',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
 assert '복수 제품 공통 원인 후보 · AI 서버' in rendered
 assert 'HBM' in rendered and 'DRAM' in rendered and '원문 원인:' in rendered
 assert '출처 가용:' in rendered and '관측:' in rendered and '같은 명시 수요처' in rendered
 assert '미식별 기업 맥락 2개' in rendered and '거래·수혜·대장주 확정이 아닙니다.' in rendered


def test_http_search_period_filters_keep_related_products_and_standard_bytes(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,themes,cs,comp,*_=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  research=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat()))
  group,=research['cross_product_demand']['groups']
  assert len(group['products'])==2 and group['search_match']=='DIRECT_COMPANY_CONTEXT'
  assert len({c['theme_id'] for c in research['CompanyCandidates']})==1 # Related product is a separate explicit comparison context.
  for activity in ('all','new','changed'):
   data=json.loads(fetch('/api/period',date='2026-10-15',theme_activity=activity))
   assert len(data['cross_product_demand']['groups'])==1
  assert json.loads(fetch('/api/period',date='2026-10-15',theme_activity='updated'))['cross_product_demand']['groups']==[]
  old=json.loads(fetch('/api/company-research',as_of=T.isoformat()))
  assert old['cross_product_demand']['groups']==[]
  assert json.loads(fetch('/api/company-research',q='무관한 수요처',as_of=END.isoformat()))['cross_product_demand']['groups']==[]
  future=json.loads(fetch('/api/period',date='2099-01-01',theme_activity='all'))
  assert future['cross_product_demand']['status']=='NOT_STARTED'
  assert fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')==build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 finally:server.shutdown();server.server_close();thread.join(2)


def test_korean_product_alias_reuses_existing_canonical_topic(tmp_path):
 store=ThemeStore(tmp_path/'theme_history');observations=[]
 for n,(product,actor) in enumerate([('HBM','가상전자'),('디램','새빛소재')]):
  source=f'{actor}, AI 서버용 {product} 수요 증가로 반도체 생산능력 확대'
  row,=extract_economic_changes(source);observations.append(observe(row,n))
 themes=store.ingest(observations,now=T)
 cs=json.loads(build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True))['CompanyCandidates']
 group,=view(themes,cs,common_cause_comparisons(themes,cs))['groups']
 assert {p['product'] for p in group['products']}=={'HBM','DRAM'}
