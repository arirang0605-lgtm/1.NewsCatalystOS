"""Shared policy clauses retain literal spans and two actions, not two new companies."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json,subprocess,threading,sqlite3
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,policy_capacity_action
from newscatalystos.theme_emergence import ThemeStore,economic_observation,_bytes,validate_change
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_scope import observe
from test_policy_service_comparison import service,case as single_case
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER
from test_federated_news_search import fingerprint


def text(product='HBM',actor='가상전자',name='별빛검사',reverse=False,**policy):
 s=service(product=product,actor=actor,name=name,**policy)
 return s.replace(f'「{name}」 서비스 개시',f'생산능력 확대 및 「{name}」 서비스 개시') if reverse else s+' 및 생산능력 확대'


def case(tmp_path,sources=None):
 sources=sources or [text(),text(product='DRAM',actor='새빛소재',name='바다검사')]
 store=ThemeStore(tmp_path/'theme_history');observations=[]
 for i,source in enumerate(sources):
  rows=extract_economic_changes(source);events=[observe(c,i) for c in rows]
  observations.extend(events);store.ingest(events,now=T if i==0 else END)
 themes=store.search(now=END);cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 return store,themes,cs,common_cause_comparisons(themes,cs),observations

@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('destination',['','중국'])
def test_original_spans_two_actions_first_legacy_id_and_no_extra_company(tmp_path,reverse,destination):
 sources=[text(reverse=reverse,destination=destination),text(product='DRAM',actor='새빛소재',name='바다검사',reverse=not reverse,destination=destination)]
 for source in sources:
  rows=extract_economic_changes(source);assert {r['action'] for r in rows}=={'BUSINESS_START','CAPACITY_ADDITION'}
  old,=extract_economic_changes(source,include_policy_parallel=False)
  actual=next(r for r in rows if r['action']=='CAPACITY_ADDITION')
  assert economic_observation(old,origin_reference='https://example.org/x',source_url='https://example.org/x',source_id='synthetic',source_available_at=T.isoformat())['event_id']==economic_observation(actual,origin_reference='https://example.org/x',source_url='https://example.org/x',source_id='synthetic',source_available_at=T.isoformat())['event_id']
  assert 'policy_parallel_action' not in old and 'policy_capacity_action' not in old
  for r in rows:
   validate_change(r);p=r['policy_parallel_action'];a,b=p['action_span'];c,d=p['cause_span']
   assert p['source_expression']==source and p['expression_sha256']==sha256(source.encode()).hexdigest()
   assert source[a:b]==p['action_expression'] and source[c:d]==r['policy_cause']['source_expression']
   assert p['actors']==r['entity_ids'] and p['action']==r['action'] and p['phase']==r['phase']=='SOURCE_REPORTED'
   assert p['action_expression'] in source and not(a<d and c<b)
   if r['action']=='CAPACITY_ADDITION':assert r['policy_capacity_action']==p
   else:assert r['service_name'] in p['action_expression'] and 'service_event_key' not in r
 store,themes,cs,comp,*_=case(tmp_path,sources);before=deepcopy((themes,cs,comp));disk=fingerprint(tmp_path)
 group,=view(themes,cs,comp)['groups'];assert group['distinct_action_groups']==4 and group['source_actor_name_count']==2 and group['identified_company_count']==0
 assert group['unresolved_company_contexts']==2 and len(cs)==2
 assert all(t['scores']['distinct_economic_events']==2 and t['scores']['company_breadth']==1 for t in themes)
 assert all(s['impact_paths']==[] and not s.get('customer') and not s.get('usage') and not s.get('verified_revenue') for p in group['products'] for a in p['actions'] for s in a['sources'])
 assert not group['verified_real_transaction'] and not group['verified_real_benefit'] and fingerprint(tmp_path)==disk and (themes,cs,comp)==before

@pytest.mark.parametrize('tail',[
 '「별빛검사」 서비스 개시 계획 및 생산능력 확대','「별빛검사」 서비스 개시 및 생산능력 확대 목표',
 '「별빛검사」 서비스 개시 및 생산능력 확대 결정','「별빛검사」 서비스 개시 및 생산능력 확대 의향',
 '「별빛검사」 서비스 개시 및 새빛소재는 생산능력 확대','「별빛검사」 서비스 개시 및 그 회사는 생산능력 확대',
 '「별빛검사」 서비스 개시 및 DRAM 생산능력 확대','「별빛검사」 서비스 개시 및 생산능력 확대 취소',
 '지난해 「별빛검사」 서비스 개시 및 생산능력 확대','「별빛검사」 서비스 개시 및 생산능력 확대 전망',
 '「별빛검사」 서비스 개시 및 생산능력 확대 및 생산 시작','검사 서비스 개시 및 생산능력 확대',
 '「별빛검사」 서비스 개시했고 생산능력 확대','「별빛검사」 서비스 개시 및 일본 ‘별도통제법’ HBM 생산 규제 완화로 생산능력 확대'])
def test_ambiguous_plan_scope_actor_product_or_cause_is_not_inherited(tmp_path,tail):
 from test_policy_production_comparison import text as policy_text
 source=policy_text(tail=tail);rows=extract_economic_changes(source)
 assert not any('policy_parallel_action' in r for r in rows)
 assert policy_capacity_action(source) is None

@pytest.mark.parametrize('fault',['action_span','cause_span','expression','hash','actor','service_name','action'])
def test_mutated_shared_proof_is_rejected_and_only_bad_product_removed(tmp_path,fault):
 store,themes,cs,comp,*_=case(tmp_path);target=themes[0];tid=target['theme_id'];ref=next(r for r in target['source_refs'] if r['action']=='BUSINESS_START');p=ref['policy_parallel_action']
 if fault=='action_span':p['action_span']=[0,3]
 elif fault=='cause_span':p['cause_span']=[0,3]
 elif fault=='expression':p['action_expression']='다른 서비스 개시'
 elif fault=='hash':p['expression_sha256']='f'*64
 elif fault=='actor':p['actors']=['달빛전자']
 elif fault=='service_name':ref['service_name']='다른검사'
 else:p['action']='CAPACITY_ADDITION'
 digest=sha256(_bytes(target)).hexdigest()
 for c in cs:
  if c['theme_id']==tid:c['theme_snapshot_sha256']=digest
 comp=common_cause_comparisons(themes,cs);result=cross_product_demand(themes,cs,comp,as_of=END,_min_products=1)
 assert tid in result['unavailable_theme_ids'] and result['groups'][0]['products'][0]['theme_id']!=tid
 assert view(themes,cs,comp)['groups']==[]


def test_period_formation_reprint_new_action_and_old_bytes(tmp_path):
 store,themes,cs,comp,observations=case(tmp_path);old=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 group,=run(store)[0]['groups'];change=group['period_change']
 assert change['formed_in_period'] and change['before']['products']==['HBM'] and change['new_products']==['DRAM'] and len(change['new_action_group_ids'])==2
 reprint=deepcopy(observations[0]);reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=LATER)
 group,=run(store,since=LATER,as_of=LATER,activity='all')[0]['groups'];assert group['period_change']['new_action_group_ids']==[]
 new=[observe(c,9) for c in extract_economic_changes(text(product='NAND',actor='빛결반도체',name='구름검사'))];store.ingest(new,now=LATER)
 group,=run(store,since=LATER,as_of=LATER,activity='all')[0]['groups'];assert group['period_change']['new_products']==['NAND'] and len(group['period_change']['new_action_group_ids'])==2
 assert old==build_theme_bundle(store.search(as_of=END,now=LATER),decision_at=END,now=LATER,include_company_candidates=True)

@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_one_action_counterevidence_does_not_cancel_its_sibling(tmp_path,polarity):
 store,*rest=case(tmp_path);base=rest[-1][0]
 counter=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([counter],now=LATER);group,=run(store,since=LATER,as_of=LATER)[0]['groups']
 assert group['status']=='COMMON_CAUSE_HYPOTHESIS'
 if polarity=='RETRACT':
  assert len(group['period_change']['removed_action_group_ids'])==1 and group['period_change']['removed_product_codes']==[]
  assert {s['action'] for p in group['products'] if p['product']=='HBM' for a in p['actions'] for s in a['sources']}=={'CAPACITY_ADDITION'}
 else:assert any(s['conflicting'] for p in group['products'] for a in p['actions'] for s in a['sources'])


def test_baseline_error_keeps_current_and_same_name_is_not_new_firm(tmp_path,monkeypatch):
 store,themes,cs,comp,*_=case(tmp_path,[text(actor='동명전자'),text(product='DRAM',actor='동명전자',name='바다검사')])
 group,=view(themes,cs,comp,query='동명전자')['groups'];assert group['source_actor_name_count']==1 and group['identified_company_count']==0
 assert run(store,query='무관 회사')[0]['groups']==[]
 def broken(**kw):raise OSError('synthetic history unavailable')
 monkeypatch.setattr(store,'period_versions',broken);result,*_=run(store,activity='all')
 assert result['groups'][0]['period_change']['status']=='UNAVAILABLE' and result['groups'][0]['products']

@pytest.mark.parametrize('legacy',[False,True])
def test_feed_roundtrip_preserves_new_spans_or_legacy_single_action(tmp_path,legacy):
 from test_feed_analysis import setup,run as analysis
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 info=setup(tmp_path,text());report=analysis(info);row=next(r for r in report['results'] if r['economic_changes'])
 if legacy:
  row['economic_changes']=extract_economic_changes(row['headline'],include_policy_parallel=False)
  for c in row['economic_changes']:c['evidence_level']='REPORTED'
 before=deepcopy(report);path,pin=publish_feed_analysis(report,tmp_path/'reports')
 assert consume_feed_analysis(path,path.parent,pin)['results']==before['results'] and report==before
 assert len(row['economic_changes'])==(1 if legacy else 2)


def test_feed_cannot_rebind_valid_other_service_pair(tmp_path):
 from test_feed_analysis import setup,run as analysis
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 info=setup(tmp_path,text());report=analysis(info);row=next(r for r in report['results'] if r['economic_changes'])
 other=extract_economic_changes(text(name='다른검사'))
 for c in other:c['evidence_level']='REPORTED';c['source_paragraph_sha256']=row['source_title_sha256']
 row['economic_changes']=other
 with pytest.raises(SourceShareError):
  path,pin=publish_feed_analysis(report,tmp_path/'bad');consume_feed_analysis(path,path.parent,pin)


def test_http_period_search_three_views_and_fixed_json_use_original_spans(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,*_=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**q):
  with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(q)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
  group,=data['cross_product_demand']['groups'];assert group['distinct_action_groups']==4 and group['period_change']['formed_in_period']
  pin=data['comparison_export'];raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
  assert sha256(raw).hexdigest()==pin['sha256'] and read_comparison_export(raw,pin['sha256'],decision_at=END,now=END)['comparison']==data['cross_product_demand']
  assert json.loads(fetch('/api/period',date='2026-10-15',theme_activity='all'))['cross_product_demand']['groups'][0]['distinct_action_groups']==4
  assert fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
  data['theme']=next(t for t in store.search(now=END) if t['theme_id']==data['CompanyCandidates'][0]['theme_id']);data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input.cross_product_demand);renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
  assert rendered.count('같은 원인·당사자의 병렬 행동')==8 and '같은 회사를 새 기업으로 세지 않습니다.' in rendered
  assert text() in rendered and '「별빛검사」 서비스 개시' in rendered and '생산능력 확대' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)

@pytest.mark.parametrize('fault',['candidate','comparison','future','relation'])
def test_unpinned_future_or_related_context_cannot_add_shared_product(tmp_path,fault):
 store,themes,cs,comp,*_=case(tmp_path);target=themes[0];tid=target['theme_id']
 if fault=='candidate':next(c for c in cs if c['theme_id']==tid)['theme_snapshot_sha256']='f'*64
 elif fault=='comparison':comp[tid]['theme_snapshot_sha256']='f'*64
 elif fault=='relation':
  for row in comp[tid]['rows']:
   for source in row['sources']:source['company_participation']='SUPPLY_CHAIN_CONTEXT'
 else:
  for ref in target['source_refs']:ref['source_available_at']=LATER.isoformat()
  digest=sha256(_bytes(target)).hexdigest()
  for c in cs:
   if c['theme_id']==tid:c['theme_snapshot_sha256']=digest
  comp=common_cause_comparisons(themes,cs)
 assert view(themes,cs,comp)['groups']==[]
 assert cross_product_demand(themes,cs,comp,as_of=END,_min_products=1)['groups'][0]['products'][0]['theme_id']!=tid

@pytest.mark.parametrize('variant',['cause_first','whitespace'])
def test_original_coordinates_survive_explicit_cause_first_actor_or_spacing(variant):
 source=text()
 if variant=='cause_first':source=source.replace('가상전자, ','').replace('완화로 ','완화로 가상전자는 ')
 else:source=source.replace(' 및 ','  및  ')
 rows=extract_economic_changes(source);assert len(rows)==2
 for r in rows:
  validate_change(r);p=r['policy_parallel_action']
  assert p['source_expression']==source and source[slice(*p['action_span'])]==p['action_expression']


def test_service_only_prechange_pins_are_exact(tmp_path):
 store,themes,cs,comp,*_=single_case(tmp_path)
 assert sha256(_bytes(view(themes,cs,comp,since=END))).hexdigest()=='f250f99e5c8e9149320b647597981a10302660548752226f585d58a67a7e235a'
 assert sha256(_bytes(run(store)[0])).hexdigest()=='c56a0e4ab6333823dadc6c4d3b38f1d7ad478154b9875f8b324e3a6d940fdc1d'
 assert sha256(query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)).hexdigest()=='abf62ee08f1d0efd254bd3a90a775b5ecc498b44bed2b6c3699b2b8c03bb8d12'
