"""Shared policy clauses retain literal spans and two actions, not two new companies."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json,subprocess,threading,sqlite3
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,policy_investment_action
from newscatalystos.theme_emergence import ThemeStore,economic_observation,_bytes,validate_change
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_scope import observe
from test_policy_service_comparison import service
from test_policy_parallel_service_capacity import case as capacity_case
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER
from test_federated_news_search import fingerprint


def text(product='HBM',actor='가상전자',name='별빛검사',reverse=False,**policy):
 s=service(product=product,actor=actor,name=name,**policy)
 return s.replace(f'「{name}」 서비스 개시',f'신규 공장 투자 집행 및 「{name}」 서비스 개시') if reverse else s+' 및 신규 공장 투자 집행'


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
  rows=extract_economic_changes(source);assert {r['action'] for r in rows}=={'BUSINESS_START','INVESTMENT_EXECUTION'}
  old,=extract_economic_changes(source,include_policy_parallel=False)
  actual=next(r for r in rows if r['action']=='INVESTMENT_EXECUTION')
  assert economic_observation(old,origin_reference='https://example.org/x',source_url='https://example.org/x',source_id='synthetic',source_available_at=T.isoformat())['event_id']==economic_observation(actual,origin_reference='https://example.org/x',source_url='https://example.org/x',source_id='synthetic',source_available_at=T.isoformat())['event_id']
  assert 'policy_parallel_action' not in old and 'policy_investment_action' not in old
  for r in rows:
   validate_change(r);p=r['policy_parallel_action'];a,b=p['action_span'];c,d=p['cause_span']
   assert p['source_expression']==source and p['expression_sha256']==sha256(source.encode()).hexdigest()
   assert source[a:b]==p['action_expression'] and source[c:d]==r['policy_cause']['source_expression']
   assert p['actors']==r['entity_ids'] and p['action']==r['action'] and p['phase']==r['phase']=='SOURCE_REPORTED'
   assert p['action_expression'] in source and not(a<d and c<b)
   if r['action']=='INVESTMENT_EXECUTION':assert r['policy_investment_action']==p
   else:assert r['service_name'] in p['action_expression'] and 'service_event_key' not in r
 store,themes,cs,comp,*_=case(tmp_path,sources);before=deepcopy((themes,cs,comp));disk=fingerprint(tmp_path)
 group,=view(themes,cs,comp)['groups'];assert group['distinct_action_groups']==4 and group['source_actor_name_count']==2 and group['identified_company_count']==0
 assert group['unresolved_company_contexts']==2 and len(cs)==2
 assert all(t['scores']['distinct_economic_events']==2 and t['scores']['company_breadth']==1 for t in themes)
 assert all(s['impact_paths']==[] and not s.get('customer') and not s.get('usage') and not s.get('verified_revenue') for p in group['products'] for a in p['actions'] for s in a['sources'])
 assert not group['verified_real_transaction'] and not group['verified_real_benefit'] and fingerprint(tmp_path)==disk and (themes,cs,comp)==before

@pytest.mark.parametrize('tail',[
 '「별빛검사」 서비스 개시 계획 및 신규 공장 투자 집행','「별빛검사」 서비스 개시 및 신규 공장 투자 집행 목표',
 '「별빛검사」 서비스 개시 및 신규 공장 투자 집행 결정','「별빛검사」 서비스 개시 및 신규 공장 투자 집행 의향',
 '「별빛검사」 서비스 개시 및 새빛소재는 신규 공장 투자 집행','「별빛검사」 서비스 개시 및 그 회사는 신규 공장 투자 집행',
 '「별빛검사」 서비스 개시 및 DRAM 신규 공장 투자 집행','「별빛검사」 서비스 개시 및 신규 공장 투자 집행 취소',
 '지난해 「별빛검사」 서비스 개시 및 신규 공장 투자 집행','「별빛검사」 서비스 개시 및 신규 공장 투자 집행 전망',
 '「별빛검사」 서비스 개시 및 신규 공장 투자 집행 및 신규 공장 투자 집행','검사 서비스 개시 및 신규 공장 투자 집행',
 '「별빛검사」 서비스 개시했고 신규 공장 투자 집행','「별빛검사」 서비스 개시 및 일본 ‘별도통제법’ HBM 생산 규제 완화로 신규 공장 투자 집행'])
def test_ambiguous_plan_scope_actor_product_or_cause_is_not_inherited(tmp_path,tail):
 from test_policy_production_comparison import text as policy_text
 source=policy_text(tail=tail);rows=extract_economic_changes(source)
 assert not any('policy_parallel_action' in r for r in rows)
 assert policy_investment_action(source) is None

@pytest.mark.parametrize('fault',['action_span','cause_span','expression','hash','actor','service_name','action'])
def test_mutated_shared_proof_is_rejected_and_only_bad_product_removed(tmp_path,fault):
 store,themes,cs,comp,*_=case(tmp_path);target=themes[0];tid=target['theme_id'];ref=next(r for r in target['source_refs'] if r['action']=='BUSINESS_START');p=ref['policy_parallel_action']
 if fault=='action_span':p['action_span']=[0,3]
 elif fault=='cause_span':p['cause_span']=[0,3]
 elif fault=='expression':p['action_expression']='다른 서비스 개시'
 elif fault=='hash':p['expression_sha256']='f'*64
 elif fault=='actor':p['actors']=['달빛전자']
 elif fault=='service_name':ref['service_name']='다른검사'
 else:p['action']='INVESTMENT_EXECUTION'
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
  assert {s['action'] for p in group['products'] if p['product']=='HBM' for a in p['actions'] for s in a['sources']}=={'INVESTMENT_EXECUTION'}
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
  assert text() in rendered and '「별빛검사」 서비스 개시' in rendered and '신규 공장 투자 집행' in rendered
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


def test_service_capacity_prechange_pins_are_exact(tmp_path):
 store,themes,cs,comp,*_=capacity_case(tmp_path)
 assert sha256(_bytes(view(themes,cs,comp,since=END))).hexdigest()=='9887d94426093ad3d3eec6b14c61de5df60554d75a3e911202c96a01e654b0b8'
 assert sha256(_bytes(run(store)[0])).hexdigest()=='0249c7bddd7e81478a7efcff3672afe77a1426a428389d0bac4f18ee03d60561'
 assert sha256(query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)).hexdigest()=='faf10b19aec520865285033a60d58bffa3a40f06c605f75e91863e4dce2f9acc'


@pytest.mark.parametrize('reverse',[False,True])
def test_named_investment_is_bound_to_its_own_slice_and_keeps_first_id(tmp_path,reverse):
 sources=[text(reverse=reverse).replace('신규 공장','「청해공장」'),text(product='DRAM',actor='새빛소재',name='바다검사',reverse=not reverse).replace('신규 공장','「바다공장」')]
 for source in sources:
  rows=extract_economic_changes(source);execution=next(r for r in rows if r['action']=='INVESTMENT_EXECUTION')
  old,=extract_economic_changes(source,include_policy_parallel=False)
  assert execution['investment_project']==execution['policy_investment_action']['investment_project']
  assert execution['investment_project']['project_name'] in {'청해공장','바다공장'}
  assert execution['investment_project']['source_expression'] in execution['policy_parallel_action']['action_expression']
  assert 'investment_event_key' not in execution
  assert observe(execution,0)['event_id']==observe(old,0)['event_id']
 store,themes,cs,comp,*_=case(tmp_path,sources);group,=view(themes,cs,comp)['groups']
 assert group['distinct_action_groups']==4
 assert {s['investment_project']['project_name'] for p in group['products'] for a in p['actions'] for s in a['sources'] if s['action']=='INVESTMENT_EXECUTION'}=={'청해공장','바다공장'}
 raw=query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)
 assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['comparison']==run(store)[0]


def test_two_named_projects_in_one_source_reuse_existing_optional_keys():
 source=text().replace('신규 공장','「청해공장」')+'. '+text(name='바다검사').replace('신규 공장','「바다공장」')
 rows=extract_economic_changes(source);assert len(rows)==4
 investments=[r for r in rows if r['action']=='INVESTMENT_EXECUTION'];services=[r for r in rows if r['action']=='BUSINESS_START']
 assert 'investment_event_key' not in investments[0] and investments[1]['investment_event_key']==sha256('바다공장'.encode()).hexdigest()
 assert 'service_event_key' not in services[0] and services[1]['service_event_key']==sha256('바다검사'.encode()).hexdigest()
 for r in rows:validate_change(r)


@pytest.mark.parametrize('fault',['project','wrapper_span','wrapper_project'])
def test_execution_project_or_wrapper_tamper_is_rejected(fault):
 row=next(r for r in extract_economic_changes(text().replace('신규 공장','「청해공장」')) if r['action']=='INVESTMENT_EXECUTION')
 if fault=='project':row['investment_project']['project_name']='별빛검사'
 elif fault=='wrapper_span':row['policy_investment_action']['action_span']=[0,3]
 else:row['policy_investment_action']['investment_project']['project_name']='별빛검사'
 with pytest.raises(SourceShareError):validate_change(row)


def test_service_and_investment_followups_reuse_both_stored_links_without_new_actions(tmp_path):
 from test_policy_investment_comparison import named
 from test_recovery_investment_comparison import observed_at
 store=ThemeStore(tmp_path/'theme_history');specs=[('HBM','가상전자','별빛검사','청해공장'),('DRAM','새빛소재','바다검사','바다공장')]
 plans=[]
 for i,(p,a,n,j) in enumerate(specs):
  plans.extend(observe(c,i*2+k) for k,source in enumerate((service(product=p,actor=a,name=n,ending='개시 계획'),named(p,a,j,verb='결정'))) for c in extract_economic_changes(source))
 store.ingest(plans,now=T);old=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
 actual=[]
 for i,(p,a,n,j) in enumerate(specs):
  source=text(product=p,actor=a,name=n).replace('신규 공장',f'「{j}」')
  actual.extend(observed_at(c,i+10,END) for c in extract_economic_changes(source))
 store.ingest(actual,now=END);result,selected,*_=run(store,activity='all');group,=result['groups'];change=group['period_change']
 assert group['distinct_action_groups']==4 and change['new_action_group_ids']==[]
 assert len(change['investment_stage_contexts'])==len(change['service_stage_contexts'])==2
 for context in change['investment_stage_contexts']:
  link=context['stored_stage_link'];assert not link['is_execution_confirmed'] and len(link['sources'])==2
  assert {link['decision_event_id'],link['execution_event_id']}<={r['event_id'] for r in plans+actual}
 for context in change['service_stage_contexts']:
  link=context['stored_followup'];assert not link['is_realization_confirmed'] and len(context['sources'])==2
  assert {link['planned_event_id'],link['realization_event_id']}<={r['event_id'] for r in plans+actual}
 for context in change['investment_stage_contexts']+change['service_stage_contexts']:
  assert context['before_snapshot']['decision_at']==T.isoformat() and context['after_snapshot']['decision_at']==END.isoformat()
 assert all(t['scores']['distinct_economic_events']==2 for t in selected)
 assert old==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
 raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
 assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['comparison']==result


@pytest.mark.parametrize('project',[False,True])
def test_named_or_unnamed_feed_binds_investment_fragment(tmp_path,project):
 from test_feed_analysis import setup,run as analysis
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 source=text().replace('신규 공장','「청해공장」') if project else text()
 report=analysis(setup(tmp_path,source));row=next(r for r in report['results'] if r['economic_changes'])
 assert len(row['economic_changes'])==2
 path,pin=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(path,path.parent,pin)['results']==report['results']
 if project:
  changed=deepcopy(report);bad=next(r for r in changed['results'] if r['economic_changes']);bad['economic_changes']=extract_economic_changes(source.replace('청해공장','다른공장'))
  for c in bad['economic_changes']:c['evidence_level']='REPORTED';c['source_paragraph_sha256']=bad['source_title_sha256']
  with pytest.raises(SourceShareError):
   path,pin=publish_feed_analysis(changed,tmp_path/'bad');consume_feed_analysis(path,path.parent,pin)


def test_old_native_execution_disabled_mode_stays_disabled():
 rows=extract_economic_changes(text(),include_investment_execution=False)
 assert not any(r['action']=='INVESTMENT_EXECUTION' for r in rows)
