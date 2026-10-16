"""Source-bounded price/service pairs; all positive examples are synthetic."""
from copy import deepcopy
from hashlib import sha256
import json,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,price_parallel_actions,demand_scope,_PRODUCT_PRICE,market_entry,investment_project,product_price_cause
from newscatalystos.theme_emergence import ThemeStore,validate_change,_bytes
from newscatalystos.source_share import SourceShareError
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.theme_changes import compare_themes
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import observed_at
from test_policy_parallel_service_investment import case as stored_case
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER
from test_company_timeline import build as timeline

OPERATIONS=[('PRODUCTION_START','생산 개시'),('CONTRACT','공급계약 체결'),
 ('CAPACITY_ADDITION','생산능력 확대'),('INVESTMENT_EXECUTION','신규 공장 투자 집행'),
 ('DELIVERY_START','납품 개시'),('CUSTOMER_ACQUISITION','신규 고객 확보'),('MARKET_ENTRY','「차량용 검사」 시장 진출')]
@pytest.fixture(params=OPERATIONS)
def operation(request):return request.param

def text(operation,product='HBM',actor='가상전자',name='별빛검사',scope='AI 서버',reverse=False,cause='가격 상승으로'):
 parts=[f'「{name}」 서비스 개시',operation[1]]
 if reverse:parts.reverse()
 return f'{actor}, {scope+"용 " if scope else ""}{product} {cause} '+' 및 '.join(parts)

def sources(operation,**kwargs):
 return [text(operation,**kwargs),text(operation,actor='새빛소재',name='바다검사',**kwargs),text(operation,actor='미래장비',name='빛결검사',**kwargs)]

def case(tmp_path,operation,articles=None):return stored_case(tmp_path,articles or sources(operation))

@pytest.mark.parametrize('scope',['AI 서버',''])
@pytest.mark.parametrize('reverse',[False,True])
def test_seven_stored_pairs_keep_price_cause_actor_and_literal_names(tmp_path,operation,scope,reverse):
 articles=sources(operation,scope=scope,reverse=reverse)
 for article in articles:
  rows=extract_economic_changes(article)
  assert {r['action'] for r in rows}=={'BUSINESS_START',operation[0]}
  assert extract_economic_changes(article,include_parallel_actions=False)==[]
  for row in rows:
   validate_change(row);p=row['price_parallel_action']
   assert row['economic_driver']=='PRODUCT_PRICE_INCREASE' and row['phase']=='SOURCE_REPORTED'
   assert len(row['entity_ids'])==1 and p['actors']==row['entity_ids']
   assert p['source_expression']==article and p['expression_sha256']==sha256(article.encode()).hexdigest()
   assert article[slice(*p['action_span'])]==p['action_expression']
   assert article[slice(*p['cause_span'])]==row['product_price_cause']['source_expression']
   if row['action']=='MARKET_ENTRY':assert row['market_entry']['market_name']=='차량용 검사'
   if row['action']=='BUSINESS_START':assert row['service_name'] in {'별빛검사','바다검사','빛결검사'}
 store,themes,cs,comp,_=case(tmp_path,operation,articles)
 theme,=themes
 assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3 and theme['scores']['distinct_economic_events']==6
 assert comp[theme['theme_id']]['distinct_action_groups']==6 and len(cs)==3
 assert view(themes,cs,comp)['groups']==[]
 assert all(s['price_parallel_action'] and s['product_price_cause'] for r in comp[theme['theme_id']]['rows'] for s in r['sources'])
 raw=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['CompanyCandidates']==cs
 assert store.search(query='가격 상승',now=END)==themes

@pytest.mark.parametrize('variant',['계획','목표','의향','취소','부인','past','actor','pronoun','product','scope','service_scope','recovery','demand','second_price','duplicate','unnamed','anticipation','service_plan','market_scope'])
def test_ambiguous_or_planned_pair_does_not_inherit_actuals(operation,variant):
 article=text(operation)
 if variant=='past':article=article.replace('「별빛검사」','지난해 「별빛검사」')
 elif variant=='actor':article=article.replace('및 ','및 달빛전자는 ')
 elif variant=='pronoun':article=article.replace('및 ','및 그 회사는 ')
 elif variant=='product':article=article.replace('및 ','및 NAND ')
 elif variant=='scope':article=article.replace('AI 서버용','AI 서버 및 스마트폰용')
 elif variant=='service_scope':article=article.replace('별빛검사','스마트폰용 HBM 검사')
 elif variant=='recovery':article=article.replace('및 ','및 DRAM 수요 회복으로 ')
 elif variant=='demand':article=article.replace('및 ','및 DRAM 수요 증가로 ')
 elif variant=='second_price':article=article.replace('및 ','및 DRAM 가격 상승으로 ')
 elif variant=='duplicate':article+=' 및 '+operation[1]
 elif variant=='unnamed':article=article.replace('「별빛검사」','검사')
 elif variant=='anticipation':article=article.replace('상승으로','상승에 대비해')
 elif variant=='service_plan':article=article.replace('서비스 개시','서비스 개시 계획')
 elif variant=='market_scope':article=text(('MARKET_ENTRY','「스마트폰용 HBM」 시장 진출'))
 else:article+=' '+variant
 assert price_parallel_actions(article) is None
 assert not any(r.get('price_parallel_action') for r in extract_economic_changes(article))
 assert not any(r['phase']=='SOURCE_REPORTED' for r in extract_economic_changes(article))

@pytest.mark.parametrize('cause',['주가 상승으로','ETF 가격 상승으로','가격 하락으로','가격 상승 예상으로'])
def test_other_price_claims_do_not_gain_price_pairs(cause):
 assert price_parallel_actions(text(OPERATIONS[0],cause=cause)) is None
 assert not any(r.get('price_parallel_action') for r in extract_economic_changes(text(OPERATIONS[0],cause=cause)))

@pytest.mark.parametrize('fault',['span','sha','actor','scope','market','service','phase','driver','cause','project','missing_project','key'])
def test_mutated_source_cannot_enter_storage_or_standard_output(tmp_path,fault):
 op=('INVESTMENT_EXECUTION','「청해공장」 투자 집행') if fault in {'project','missing_project','key'} else OPERATIONS[-1]
 rows=extract_economic_changes(text(op));row=next(r for r in rows if r['action']==('BUSINESS_START' if fault=='service' else op[0]))
 if fault=='span':row['price_parallel_action']['action_span']=[0,3]
 elif fault=='sha':row['price_parallel_action']['expression_sha256']='f'*64
 elif fault=='actor':row['price_parallel_action']['actors']=['달빛전자']
 elif fault=='scope':
  a=text(op,scope='스마트폰');row['demand_scope']=demand_scope(a,_PRODUCT_PRICE.search(a))
 elif fault=='market':row['market_entry']=market_entry('「항공 검사」 시장 진출')
 elif fault=='service':row['service_name']='다른검사'
 elif fault=='phase':row['phase']='PLANNED'
 elif fault=='driver':row['economic_driver']='DEMAND_EXPANSION'
 elif fault=='cause':row['product_price_cause']=product_price_cause('HBM 가격 급등으로')
 elif fault=='project':row['investment_project']=investment_project('「바다공장」 투자 집행','INVESTMENT_EXECUTION')
 elif fault=='missing_project':row.pop('investment_project')
 else:row['investment_event_key']='f'*64
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,cs,_,_=case(tmp_path,op,[text(op)])
 ref=next(r for r in themes[0]['source_refs'] if r['action']==row['action'])
 for k in ['price_parallel_action','demand_scope','market_entry','service_name','phase','economic_driver','product_price_cause','investment_project','investment_event_key']:
  if k in row:ref[k]=deepcopy(row[k])
  else:ref.pop(k,None)
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('operation',[('DELIVERY_START','달빛전자에 납품 개시'),('CUSTOMER_ACQUISITION','달빛전자를 신규 고객으로 확보')])
def test_customer_object_is_source_context_not_additional_company(tmp_path,operation):
 rows=extract_economic_changes(text(operation));assert len(rows)==2 and all(r['entity_ids']==['가상전자'] for r in rows)
 store,themes,cs,_,_=case(tmp_path,operation,[text(operation)])
 assert len(cs)==1 and cs[0]['entity_id']=='가상전자' and themes[0]['scores']['company_breadth']==1
 assert store.search(query='달빛전자',now=END)==themes

def test_feed_roundtrip_source_rebind_strip_and_legacy_read(tmp_path,operation):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 report=analyze(setup(tmp_path,text(operation)));row=report['results'][0];original=deepcopy(row['economic_changes']);assert len(original)==2
 path,pin=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(path,path.parent,pin)['results']==report['results']
 for variant in ['strip','rebind','phase']:
  changes=deepcopy(original)
  if variant=='strip':changes[0].pop('price_parallel_action')
  elif variant=='rebind':changes=extract_economic_changes(text(operation,name='다른검사'))
  else:changes[0]['phase']='PLANNED'
  for c in changes:c.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
  row['economic_changes']=changes
  with pytest.raises(SourceShareError):
   p,h=publish_feed_analysis(report,tmp_path/variant);consume_feed_analysis(p,p.parent,h)
 row['economic_changes']=extract_economic_changes(row['headline'],include_price_parallel=False)
 for c in row['economic_changes']:c.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
 p,h=publish_feed_analysis(report,tmp_path/'legacy');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']

def test_existing_action_identity_first_detection_and_pit(tmp_path,operation):
 article=text(operation);current=extract_economic_changes(article)
 single,=extract_economic_changes(article.split(' 및 ')[0])
 service=next(r for r in current if r['action']=='BUSINESS_START')
 assert observe(single,0)['event_id']==observe(service,0)['event_id']
 old=extract_economic_changes(article,include_price_parallel=False)
 if old:
  assert len(old)==1 and observe(old[0],0)['event_id']==observe(next(r for r in current if r['action']==old[0]['action']),0)['event_id']
 store=ThemeStore(tmp_path/'theme_history');prior,=store.ingest([observe(r,0) for r in old or [single]],now=T)
 raw=build_theme_bundle([prior],decision_at=T,now=T,include_company_candidates=True)
 latest,=store.ingest([observe(r,0) for r in current],now=END)
 assert latest['theme_id']==prior['theme_id'] and latest['first_detected_at']==prior['first_detected_at']
 assert latest['scores']['distinct_economic_events']==2
 assert raw==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)

@pytest.mark.parametrize('reverse',[False,True])
def test_named_project_and_service_followups_add_zero_new_actions(tmp_path,reverse):
 op=('INVESTMENT_EXECUTION','「청해공장」 투자 집행');article=text(op,reverse=reverse)
 prefix='가상전자, AI 서버용 HBM 가격 상승으로 '
 store=ThemeStore(tmp_path/'theme_history');plans=[]
 for i,s in enumerate([prefix+'「별빛검사」 서비스 개시 계획',prefix+'「청해공장」 투자 결정']):plans.extend(observe(c,i) for c in extract_economic_changes(s))
 assert len(plans)==2;store.ingest(plans,now=T)
 old=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
 rows=extract_economic_changes(article)
 assert next(r for r in rows if r['action']=='INVESTMENT_EXECUTION')['investment_project']['project_name']=='청해공장'
 assert extract_economic_changes(article,include_investment_projects=False)==[]
 store.ingest([observed_at(c,10,END) for c in rows],now=END);themes=store.search(now=END)
 assert themes[0]['scores']['distinct_economic_events']==2
 changes=compare_themes(store,since=END,as_of=END,now=END)['ThemeChanges']
 assert changes[0]['events']['independent_actions_added']==0
 tl,*_=timeline(themes,END,END);assert tl['companies'][0]['new_actions_in_period']==0
 assert len(themes[0]['event_followups'])==len(themes[0]['investment_stage_links'])==1
 assert not themes[0]['event_followups'][0]['is_realization_confirmed']
 assert not themes[0]['investment_stage_links'][0]['is_execution_confirmed']
 assert old==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
 reprint=observed_at(rows[0],10,END);reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=LATER)
 assert compare_themes(store,since=LATER,as_of=LATER,now=LATER)['ThemeChanges'][0]['events']['independent_actions_added']==0
 assert run(store,activity='all')[0]['groups']==[]

def test_sibling_service_and_project_keys_and_no_brand_borrowing(tmp_path):
 a=text(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'));b=text(('INVESTMENT_EXECUTION','「바다공장」 투자 집행'),name='바다검사')
 rows=extract_economic_changes(a+'\n'+b+'\n'+a);assert len(rows)==4
 for row in rows:validate_change(row)
 starts=[r for r in rows if r['action']=='BUSINESS_START'];jobs=[r for r in rows if r['action']=='INVESTMENT_EXECUTION']
 assert 'service_event_key' not in starts[0] and 'investment_event_key' not in jobs[0]
 assert starts[1]['service_event_key']==sha256('바다검사'.encode()).hexdigest()
 assert jobs[1]['investment_event_key']==sha256('바다공장'.encode()).hexdigest()
 store=ThemeStore(tmp_path/'theme_history');theme,=store.ingest([observe(r,0) for r in rows],now=T)
 assert theme['scores']['company_breadth']==1 and theme['scores']['distinct_economic_events']==4
 rows=extract_economic_changes(text(OPERATIONS[3],name='별빛공장'));assert len(rows)==2 and all('investment_project' not in r for r in rows)

def test_future_scope_and_driver_separation(tmp_path):
 articles=[text(OPERATIONS[0]),text(OPERATIONS[0],actor='새빛소재',scope='스마트폰'),text(OPERATIONS[0],actor='주문전자',cause='주문 확대로')]
 _,themes,cs,comp,_=case(tmp_path,OPERATIONS[0],articles)
 assert len(themes)==3 and all(t['scores']['company_breadth']==1 for t in themes)
 assert view(themes,cs,comp)['groups']==[]
 themes[0]['source_refs'][0]['source_available_at']=LATER.isoformat()
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

def test_http_ui_and_fixed_json(tmp_path,operation):
 from scripts import open_research_dashboard as dashboard
 store,*_=case(tmp_path,operation)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**query):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(query)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
  assert data['cross_product_demand']['groups']==[]
  pin=data['comparison_export'];raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
  assert sha256(raw).hexdigest()==pin['sha256']
  export=read_comparison_export(raw,pin['sha256'],decision_at=END,now=END)
  assert export['comparison']==data['cross_product_demand']
  assert {tid:export['product_comparisons'][tid] for tid in data['common_cause_comparisons']}==data['common_cause_comparisons']
  data['theme']=next(t for t in store.search(now=END) if t['theme_id']==data['CompanyCandidates'][0]['theme_id'])
  data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
  assert text(operation) in rendered and '별빛검사' in rendered and '제품 가격 원인 범위' in rendered
  assert '같은 회사를 새 기업으로 세지 않습니다.' in rendered and operation[1] in rendered
 finally:server.shutdown();server.server_close();thread.join(2)

def test_licensed_body_uses_same_price_spans(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 article=text(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'))
 _,args=body_case(tmp_path,article);report=analyze_motir_document(**args)
 assert len(report['economic_changes'])==2 and all(r['price_parallel_action']['source_expression']==article for r in report['economic_changes'])
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']
 assert report['source_fetch_calls']==report['new_ai_results']==0
