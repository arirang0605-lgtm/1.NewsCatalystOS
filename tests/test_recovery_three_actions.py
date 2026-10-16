"""Three complete source spans share one reported recovery cause, never three actors."""
from copy import deepcopy
from hashlib import sha256
from itertools import combinations,permutations
import pytest
from newscatalystos.economic_changes import extract_economic_changes,recovery_parallel_actions,investment_project,market_entry
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_price_parallel_service import OPERATIONS
from test_policy_parallel_service_investment import case as stored_case
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import observed_at
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER
from test_company_timeline import build as timeline

OPERATIONS=OPERATIONS+[('SUPPLY_RESUMPTION','공급 재개')]
PAIRS=list(combinations(OPERATIONS,2))
SERVICE='「별빛검사」 서비스 개시'
CAUSE='수요 회복으로'
PREFIX='가상전자, AI 서버용 HBM 수요 회복으로 '

@pytest.fixture(params=['수요 회복으로','주문 회복으로'],autouse=True)
def recovery_cause(request,monkeypatch):
 monkeypatch.setitem(globals(),'CAUSE',request.param)
 monkeypatch.setitem(globals(),'PREFIX','가상전자, AI 서버용 HBM '+request.param+' ')


def text(pair,scope='AI 서버',actor='가상전자',name='별빛검사',order=(0,1,2),product='HBM'):
 parts=[f'「{name}」 서비스 개시',pair[0][1],pair[1][1]]
 return f'{actor}, {scope+"용 " if scope else ""}{product} {CAUSE} '+' 및 '.join(parts[i] for i in order)

@pytest.mark.parametrize('pair',PAIRS)
@pytest.mark.parametrize('scope',['AI 서버',''])
def test_all_distinct_action_pairs_store_three_spans_under_one_recovery_theme(tmp_path,pair,scope):
 article=text(pair,scope);rows=extract_economic_changes(article)
 assert {r['action'] for r in rows}=={'BUSINESS_START',pair[0][0],pair[1][0]}
 assert recovery_parallel_actions(article,include_three_actions=False) is None
 assert extract_economic_changes(article,include_recovery_three_actions=False)==[]
 spans=[]
 for row in rows:
  validate_change(row);p=row['recovery_parallel_action'];spans.append(p['action_span'])
  assert row['economic_driver']=='DEMAND_RECOVERY' and row['phase']=='SOURCE_REPORTED'
  assert row['entity_ids']==p['actors']==['가상전자']
  assert article[slice(*p['action_span'])]==p['action_expression']
  assert article[slice(*p['cause_span'])]=='HBM '+CAUSE==row['demand_recovery_cause']['source_expression']
  assert p['source_expression']==article and p['expression_sha256']==sha256(article.encode()).hexdigest()
 assert sorted(spans)==spans and all(a[1]<b[0] for a,b in zip(spans,spans[1:]))
 articles=[article,text(pair,scope,actor='새빛소재',name='바다검사'),text(pair,scope,actor='미래장비',name='빛결검사')]
 store,themes,cs,comp,_=stored_case(tmp_path,articles);theme,=themes
 assert theme['scores']['company_breadth']==3 and theme['scores']['distinct_economic_events']==9 and theme['status']=='EMERGING'
 assert len(cs)==3 and comp[theme['theme_id']]['distinct_action_groups']==9
 assert view(themes,cs,comp)['groups']==run(store,activity='all')[0]['groups']==[]
 assert all(s['recovery_parallel_action'] for row in comp[theme['theme_id']]['rows'] for s in row['sources'])
 bundle=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 assert read_theme_bundle(bundle,sha256(bundle).hexdigest(),decision_at=END,now=END)['CompanyCandidates']==cs
 raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
 result=read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)
 assert result['product_comparisons']==comp
 assert store.search(query='별빛검사',now=END)==themes

@pytest.mark.parametrize('order',list(permutations(range(3))))
def test_each_service_market_project_name_uses_only_its_own_span(order):
 pair=(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'),('MARKET_ENTRY','「차량용 검사」 시장 진출'))
 article=text(pair,order=order);rows=extract_economic_changes(article);assert len(rows)==3
 for row in rows:
  validate_change(row)
  if row['action']=='BUSINESS_START':assert row['service_name']=='별빛검사' and 'investment_project' not in row and 'market_entry' not in row
  elif row['action']=='INVESTMENT_EXECUTION':assert row['investment_project']['project_name']=='청해공장' and 'service_name' not in row and 'market_entry' not in row
  else:assert row['market_entry']['market_name']=='차량용 검사' and 'service_name' not in row and 'investment_project' not in row
 assert extract_economic_changes(article,include_investment_projects=False)==[]

@pytest.mark.parametrize('position',[0,1,2])
@pytest.mark.parametrize('fault',['계획','목표','의향','취소','부인','past','actor','pronoun','product','other_price','other_demand','missing_verb','finite_new_clause'])
def test_no_partial_actuals_when_any_one_part_is_invalid(position,fault):
 parts=[SERVICE,'생산 개시','납품 개시']
 if fault=='past':parts[position]='지난해 '+parts[position]
 elif fault=='actor':parts[position]='달빛전자는 '+parts[position]
 elif fault=='pronoun':parts[position]='그 회사는 '+parts[position]
 elif fault=='product':parts[position]='NAND '+parts[position]
 elif fault=='other_price':parts[position]='스마트폰용 HBM 가격 상승으로 '+parts[position]
 elif fault=='other_demand':parts[position]='DRAM 수요 회복으로 '+parts[position]
 elif fault=='missing_verb':parts[position]=parts[position].replace('개시','')
 elif fault=='finite_new_clause':parts[position]+='했고 달빛전자도 생산 개시'
 else:parts[position]+=' '+fault
 article=PREFIX+' 및 '.join(parts)
 assert recovery_parallel_actions(article) is None
 assert extract_economic_changes(article)==[]

@pytest.mark.parametrize('parts',[
 [SERVICE,'생산 개시','생산 개시'],[SERVICE,'생산 개시','납품 개시','신규 고객 확보'],
 [SERVICE,'생산 개시',''],[SERVICE,'생산 개시','「스마트폰용 HBM」 시장 진출'],
 ['검사 서비스 개시','생산 개시','납품 개시'],[SERVICE,'생산 개시','또는 납품 개시']])
def test_duplicate_extra_incomplete_or_conflicting_scopes_are_not_inherited(parts):
 assert recovery_parallel_actions(PREFIX+' 및 '.join(parts)) is None
 assert extract_economic_changes(PREFIX+' 및 '.join(parts))==[]

@pytest.mark.parametrize('cause',['수요 증가로','주문 확대로','가격 상승으로','가격 하락으로','주가 상승으로','수요 회복 예상으로','수요 회복에 대비해'])
def test_other_driver_and_anticipation_cannot_gain_recovery_three_actions(cause):
 article=text((OPERATIONS[0],OPERATIONS[4])).replace(CAUSE,cause)
 assert recovery_parallel_actions(article) is None
 assert not any('recovery_parallel_action' in r for r in extract_economic_changes(article))

@pytest.mark.parametrize('position',[0,1,2])
@pytest.mark.parametrize('fault',['span','sha','phase','actor'])
def test_changed_single_span_rejected_before_storage_and_output(tmp_path,position,fault):
 article=text((OPERATIONS[0],OPERATIONS[4]));rows=extract_economic_changes(article);row=rows[position]
 if fault=='span':row['recovery_parallel_action']['action_span']=rows[(position+1)%3]['recovery_parallel_action']['action_span']
 elif fault=='sha':row['recovery_parallel_action']['expression_sha256']='f'*64
 elif fault=='phase':row['phase']='PLANNED'
 else:row['recovery_parallel_action']['actors']=['달빛전자']
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,_,_,_=stored_case(tmp_path,[article]);ref=next(s for s in themes[0]['source_refs'] if s['action']==row['action'])
 ref['recovery_parallel_action']=deepcopy(row['recovery_parallel_action']);ref['phase']=row['phase']
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('pair',[PAIRS[3],PAIRS[6],(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'),OPERATIONS[-1])])
def test_feed_raw_source_rebinding_and_stripping_cannot_drop_the_third_part(tmp_path,pair):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 article=text(pair);report=analyze(setup(tmp_path,article));row=report['results'][0];original=deepcopy(row['economic_changes']);assert len(original)==3
 p,h=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']
 for i in range(3):
  changes=deepcopy(original);changes[i].pop('recovery_parallel_action');row['economic_changes']=changes
  with pytest.raises(SourceShareError):
   p,h=publish_feed_analysis(report,tmp_path/f'strip{i}');consume_feed_analysis(p,p.parent,h)
 # A valid two-action proof cannot be substituted for the original three-part title.
 changes=extract_economic_changes(article.rsplit(' 및 ',1)[0])
 for c in changes:c.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
 row['economic_changes']=changes
 with pytest.raises(SourceShareError):
  p,h=publish_feed_analysis(report,tmp_path/'rebound');consume_feed_analysis(p,p.parent,h)
 row['economic_changes']=extract_economic_changes(article,include_recovery_three_actions=False)
 p,h=publish_feed_analysis(report,tmp_path/'legacy');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']

@pytest.mark.parametrize('pair',[(OPERATIONS[0],OPERATIONS[4]),(OPERATIONS[1],OPERATIONS[2])])
def test_pair_to_three_retains_existing_ids_first_detection_and_pit(tmp_path,pair):
 article=text(pair);prior_rows=extract_economic_changes(article.rsplit(' 및 ',1)[0]);current=extract_economic_changes(article)
 assert len(prior_rows)==2 and len(current)==3
 for row in prior_rows:assert observe(row,0)['event_id']==observe(next(r for r in current if r['action']==row['action']),0)['event_id']
 store=ThemeStore(tmp_path/'theme_history');old,=store.ingest([observe(r,0) for r in prior_rows],now=T)
 bundle=build_theme_bundle([old],decision_at=T,now=T,include_company_candidates=True)
 latest,=store.ingest([observe(r,0) for r in current],now=END)
 assert latest['theme_id']==old['theme_id'] and latest['first_detected_at']==old['first_detected_at']
 assert latest['scores']['distinct_economic_events']==3
 assert compare_themes(store,since=END,as_of=END,now=END)['ThemeChanges'][0]['events']['independent_actions_added']==1
 assert bundle==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)

def test_service_investment_followups_and_existing_third_action_add_zero_new(tmp_path):
 pair=(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'),OPERATIONS[4]);article=text(pair)
 store=ThemeStore(tmp_path/'theme_history');prior=[]
 for i,part in enumerate([SERVICE+' 계획','「청해공장」 투자 결정','납품 개시']):prior.extend(observe(c,i) for c in extract_economic_changes(PREFIX+part))
 store.ingest(prior,now=T);old=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
 rows=extract_economic_changes(article);actual=[]
 for row in rows:
  # Re-observing the known delivery retains its event key; stage links bind the other two.
  index=2 if row['action']=='DELIVERY_START' else 10
  actual.append(observed_at(row,index,END))
 store.ingest(actual,now=END);themes=store.search(now=END);theme,=themes
 assert theme['scores']['company_breadth']==1 and theme['scores']['distinct_economic_events']==3
 assert len(theme['event_followups'])==len(theme['investment_stage_links'])==1
 assert not theme['event_followups'][0]['is_realization_confirmed'] and not theme['investment_stage_links'][0]['is_execution_confirmed']
 assert compare_themes(store,since=END,as_of=END,now=END)['ThemeChanges'][0]['events']['independent_actions_added']==0
 tl,*_=timeline(themes,END,END);assert tl['companies'][0]['new_actions_in_period']==0
 assert old==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
 reprint=deepcopy(actual[0]);reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=LATER)
 assert compare_themes(store,since=LATER,as_of=LATER,now=LATER)['ThemeChanges'][0]['events']['independent_actions_added']==0


def test_customer_objects_and_named_siblings_do_not_add_companies(tmp_path):
 pair=(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'),('CUSTOMER_ACQUISITION','달빛전자를 신규 고객으로 확보'))
 a=text(pair);b=text((('INVESTMENT_EXECUTION','「바다공장」 투자 집행'),pair[1]),name='바다검사')
 rows=extract_economic_changes(a+'\n'+b);assert len(rows)==5 and all(r['entity_ids']==['가상전자'] for r in rows)
 for row in rows:validate_change(row)
 services=[r for r in rows if r['action']=='BUSINESS_START'];jobs=[r for r in rows if r['action']=='INVESTMENT_EXECUTION']
 assert services[1]['service_event_key']==sha256('바다검사'.encode()).hexdigest() and jobs[1]['investment_event_key']==sha256('바다공장'.encode()).hexdigest()
 store=ThemeStore(tmp_path/'theme_history');theme,=store.ingest([observe(r,0) for r in rows],now=T)
 assert theme['scores']['company_breadth']==1 and theme['scores']['distinct_economic_events']==5

@pytest.mark.parametrize('pair',[(OPERATIONS[0],OPERATIONS[4]),(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'),OPERATIONS[6]),(OPERATIONS[1],OPERATIONS[-1])])
def test_http_three_action_sources_and_fixed_json(tmp_path,pair):
 import json,subprocess,threading
 from urllib.parse import urlencode
 from urllib.request import urlopen
 from scripts import open_research_dashboard as dashboard
 articles=[text(pair),text(pair,product='DRAM',actor='새빛소재',name='바다검사')]
 store,*_=stored_case(tmp_path,articles)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**query):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(query)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
  group,=data['cross_product_demand']['groups'];assert group['distinct_action_groups']==6 and group['unresolved_company_contexts']==2
  assert not group['verified_real_transaction'] and not group['verified_real_benefit']
  pin=data['comparison_export'];raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
  assert sha256(raw).hexdigest()==pin['sha256']
  export=read_comparison_export(raw,pin['sha256'],decision_at=END,now=END)
  assert export['comparison']==data['cross_product_demand']
  assert {tid:export['product_comparisons'][tid] for tid in data['common_cause_comparisons']}==data['common_cause_comparisons']
  data['theme']=next(t for t in store.search(now=END) if t['theme_id']==data['CompanyCandidates'][0]['theme_id'])
  data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
  code="""const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input.cross_product_demand);renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));"""
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
  assert text(pair) in rendered and '별빛검사' in rendered and '회복 원인 범위' in rendered
  assert '같은 회사를 새 기업으로 세지 않습니다.' in rendered
  assert pair[0][1] in rendered and pair[1][1] in rendered
 finally:server.shutdown();server.server_close();thread.join(2)


def test_licensed_body_and_future_source(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 article=text((OPERATIONS[0],OPERATIONS[4]));_,args=body_case(tmp_path,article);report=analyze_motir_document(**args)
 assert len(report['economic_changes'])==3 and report['source_fetch_calls']==report['new_ai_results']==0
 p,h=publish_motir_document_analysis(report,tmp_path/'reports');assert consume_motir_document_analysis(p,h)['economic_changes']==report['economic_changes']
 _,themes,_,_,_=stored_case(tmp_path/'stored',[article]);themes[0]['source_refs'][2]['source_available_at']=LATER.isoformat()
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)


@pytest.mark.parametrize('first',[SERVICE,'생산 개시'])
def test_prior_standalone_clause_in_same_title_keeps_its_valid_source(tmp_path,first):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 article=PREFIX+first+'. '+text((OPERATIONS[0],OPERATIONS[4]))
 report=analyze(setup(tmp_path,article));rows=report['results'][0]['economic_changes']
 assert len(rows)==3 and sum('recovery_parallel_action' in r for r in rows)==2
 p,h=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']


def test_cross_product_period_has_no_new_actions_from_service_and_investment_stages(tmp_path):
 pair=(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'),OPERATIONS[4])
 store=ThemeStore(tmp_path/'theme_history');prior=[];actual=[]
 for i,(product,actor,name) in enumerate([('HBM','가상전자','별빛검사'),('DRAM','새빛소재','바다검사')]):
  article=text(pair,product=product,actor=actor,name=name)
  prefix=article.split('「')[0]
  for j,part in enumerate([f'「{name}」 서비스 개시 계획','「청해공장」 투자 결정','납품 개시']):
   prior.extend(observe(c,i*3+j) for c in extract_economic_changes(prefix+part))
  for row in extract_economic_changes(article):actual.append(observed_at(row,i*3+2 if row['action']=='DELIVERY_START' else i+10,END))
 store.ingest(prior,now=T);before=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
 store.ingest(actual,now=END);result,_,_=run(store,activity='all');group,=result['groups']
 assert group['distinct_action_groups']==6 and group['period_change']['new_action_group_ids']==[]
 assert len(group['period_change']['service_stage_contexts'])==len(group['period_change']['investment_stage_contexts'])==2
 assert before==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
 raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
 assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['comparison']==result


def test_prior_different_named_standalone_service_retains_first_identity(tmp_path):
 article=PREFIX+SERVICE+'. '+text((OPERATIONS[0],OPERATIONS[4]),name='바다검사')
 rows=extract_economic_changes(article);assert len(rows)==4
 services=[r for r in rows if r['action']=='BUSINESS_START']
 assert services[0]['service_name']=='별빛검사' and 'service_event_key' not in services[0]
 assert services[1]['service_name']=='바다검사' and services[1]['service_event_key']==sha256('바다검사'.encode()).hexdigest()
 for row in rows:validate_change(row)
 store=ThemeStore(tmp_path/'theme_history');theme,=store.ingest([observe(r,0) for r in rows],now=T)
 assert theme['scores']['company_breadth']==1 and theme['scores']['distinct_economic_events']==4


def test_prior_plan_keeps_existing_phase_without_actual_promotion():
 article=PREFIX+SERVICE+' 계획. '+text((OPERATIONS[0],OPERATIONS[4]))
 services=[r for r in extract_economic_changes(article) if r['action']=='BUSINESS_START']
 assert len(services)==1 and services[0]['phase']=='PLANNED'
 assert services[0]['service_name']=='별빛검사'
