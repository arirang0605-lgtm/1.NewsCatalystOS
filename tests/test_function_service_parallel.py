"""Concrete service functions share explicit causes without inventing brand identity."""
from copy import deepcopy
from hashlib import sha256
from itertools import permutations
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.source_share import SourceShareError
from test_policy_parallel_service_investment import case as stored_case
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import observed_at
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER

CAUSES=['수요 증가로','주문 확대로','수요 회복으로','가격 상승으로','정책']
SERVICE='HBM 검사 서비스 개시'
GROUPS=[['생산 개시'],['달빛전자를 신규 고객으로 확보'],['「청해공장」 투자 집행','「차량용 검사」 시장 진출'],['공급계약 체결','생산능력 확대']]

def text(cause,parts=None,product='HBM',actor='가상전자',scope='AI 서버'):
 parts=parts or [SERVICE,'생산 개시']
 prefix=(f'미국 ‘첨단칩통제법’ 중국향 {product} 수출 규제 완화로' if cause=='정책'
         else f'{scope+"용 " if scope else ""}{product} {cause}')
 return f'{actor}, {prefix} '+' 및 '.join(p.replace('HBM',product) for p in parts)

def proof_key(cause):
 return ('policy' if cause=='정책' else 'price' if cause=='가격 상승으로' else 'recovery' if cause=='수요 회복으로' else 'growth')+'_parallel_action'

def driver(cause):
 return {'정책':'POLICY_ENABLEMENT','가격 상승으로':'PRODUCT_PRICE_INCREASE','수요 회복으로':'DEMAND_RECOVERY'}.get(cause,'DEMAND_EXPANSION')

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('operations',GROUPS)
def test_stored_function_actions_keep_source_scope_and_existing_output_paths(tmp_path,cause,operations):
 parts=[SERVICE,*operations];a=text(cause,parts);rows=extract_economic_changes(a);assert len(rows)==len(parts)
 assert extract_economic_changes(a,include_function_parallel=False)==[]
 for row in rows:
  validate_change(row);p=row[proof_key(cause)]
  assert row['economic_driver']==driver(cause) and row['phase']=='SOURCE_REPORTED'
  assert row['entity_ids']==p['actors']==['가상전자'] and not row['verified_economic_effect']
  assert a[slice(*p['action_span'])]==p['action_expression']
  assert p['expression_sha256']==sha256(a.encode()).hexdigest()
  assert 'service_name' not in row and 'service_event_key' not in row
 articles=[a,text(cause,parts,actor='새빛소재'),text(cause,parts,actor='미래장비')]
 store,themes,cs,comp,_=stored_case(tmp_path,articles);theme,=themes
 assert theme['scores']['company_breadth']==3 and theme['scores']['distinct_economic_events']==3*len(parts)
 assert theme['status']=='EMERGING' and len(cs)==3
 assert comp[theme['theme_id']]['distinct_action_groups']==3*len(parts)
 assert store.search(query='HBM 검사',now=END)==themes
 bundle=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 assert read_theme_bundle(bundle,sha256(bundle).hexdigest(),decision_at=END,now=END)['CompanyCandidates']==cs
 raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
 assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['product_comparisons']==comp
 # Same explicit cause across products retains two source actors, never six.
 other=text(cause,parts,product='DRAM',actor='새빛소재')
 store,themes,cs,comp,_=stored_case(tmp_path/'cross',[a,other])
 if cause=='가격 상승으로':
  assert view(themes,cs,comp)['groups']==run(store,activity='all')[0]['groups']==[]
  return # Price remains a separate comparison driver, not shared demand.
 group,=view(themes,cs,comp)['groups']
 assert group['distinct_action_groups']==2*len(parts) and group['unresolved_company_contexts']==2
 assert not group['verified_real_transaction'] and not group['verified_real_benefit']
 assert run(store,activity='all')[0]['groups'][0]['distinct_action_groups']==2*len(parts)

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('order',list(permutations(range(3))))
def test_each_name_and_function_is_read_from_its_own_source_slice(cause,order):
 parts=[SERVICE,'「청해공장」 투자 집행','「차량용 검사」 시장 진출']
 rows=extract_economic_changes(text(cause,[parts[i] for i in order]));assert len(rows)==3
 for row in rows:
  validate_change(row)
  assert 'service_name' not in row and 'service_event_key' not in row
  if row['action']=='BUSINESS_START':assert row[proof_key(cause)]['action_expression']==SERVICE
  if row['action']=='INVESTMENT_EXECUTION':assert row['investment_project']['project_name']=='청해공장'
  if row['action']=='MARKET_ENTRY':assert row['market_entry']['market_name']=='차량용 검사'

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('position',[0,1,2])
@pytest.mark.parametrize('fault',['계획','의향','부인','past','actor','product','cause','incomplete'])
def test_incomplete_or_conflicting_part_cannot_promote_actual_siblings(cause,position,fault):
 parts=[SERVICE,'생산 개시','납품 개시']
 if fault=='past':parts[position]='지난해 '+parts[position]
 elif fault=='actor':parts[position]='달빛전자는 '+parts[position]
 elif fault=='product':parts[position]='NAND '+parts[position]
 elif fault=='cause':parts[position]='일본 ‘별도통제법’ DRAM 수출 규제 완화로 '+parts[position]
 elif fault=='incomplete':parts[position]=parts[position].replace('개시','')
 else:parts[position]+=' '+fault
 assert extract_economic_changes(text(cause,parts))==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('parts',[
 ['검사 서비스 개시','생산 개시'],['AI 검사 서비스 개시','생산 개시'],
 ['HBM 서비스 개시','생산 개시'],['스마트폰용 HBM 검사 서비스 개시','생산 개시'],
 [SERVICE,'생산 개시','생산 개시'],[SERVICE,'생산 개시','납품 개시','생산능력 확대'],
 [SERVICE,'생산 개시','또는 납품 개시'],[SERVICE,'생산 개시',''],
 [SERVICE,'생산 개시했고 그 회사는 납품 개시']])
def test_no_generic_service_or_ambiguous_inheritance(cause,parts):
 if cause=='정책' and parts[0].startswith('스마트폰용'):
  rows=extract_economic_changes(text(cause,parts));assert len(rows)==2
  assert all(r['policy_cause']['destination']=='중국' for r in rows)
  return # Policy destination is geographic, not end use.
 assert extract_economic_changes(text(cause,parts))==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('count',[2,3])
def test_feed_roundtrip_partial_proof_strip_raw_rebind_and_prior_single_clause(tmp_path,cause,count):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 parts=[SERVICE,'생산 개시','납품 개시'][:count];article=text(cause,parts)
 report=analyze(setup(tmp_path,article));row=report['results'][0];original=deepcopy(row['economic_changes']);assert len(original)==count
 p,h=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']
 for i in range(count):
  changes=deepcopy(original);changes[i].pop(proof_key(cause));row['economic_changes']=changes
  with pytest.raises(SourceShareError):
   p,h=publish_feed_analysis(report,tmp_path/f'strip{i}');consume_feed_analysis(p,p.parent,h)
 changed=extract_economic_changes(article.replace('HBM 검사 서비스','HBM 분석 서비스'))
 for c in changed:c.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
 row['economic_changes']=changed
 with pytest.raises(SourceShareError):
  p,h=publish_feed_analysis(report,tmp_path/'rebound');consume_feed_analysis(p,p.parent,h)
 # A real earlier standalone action can legitimately retain its first source.
 article=text(cause,['생산 개시'])+'. '+article
 report=analyze(setup(tmp_path/'single',article));assert len(report['results'][0]['economic_changes'])==count
 p,h=publish_feed_analysis(report,tmp_path/'single_reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('fault',['invented_name','span','sha','phase'])
def test_mutated_service_rejected_before_storage_and_standard_delivery(tmp_path,cause,fault):
 article=text(cause);row=extract_economic_changes(article)[0]
 if fault=='invented_name':row['service_name']='HBM 검사'
 elif fault=='span':row[proof_key(cause)]['action_span']=[0,5]
 elif fault=='sha':row[proof_key(cause)]['expression_sha256']='a'*64
 else:row['phase']='PLANNED'
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,*_=stored_case(tmp_path,[article]);ref=next(s for s in themes[0]['source_refs'] if s['action']=='BUSINESS_START')
 for key in (proof_key(cause),'service_name','phase'):
  if key in row:ref[key]=deepcopy(row[key])
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
def test_function_descriptions_do_not_create_named_service_followups_and_keep_pit(tmp_path,cause):
 store=ThemeStore(tmp_path/'theme_history')
 plan=extract_economic_changes(text(cause,[SERVICE+' 계획']));assert len(plan)==1 and plan[0]['phase']=='PLANNED'
 store.ingest([observe(plan[0],0)],now=T)
 before=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
 # A different function is not evidence of the same service being launched.
 rows=extract_economic_changes(text(cause,['HBM 분석 서비스 개시','생산 개시']))
 latest,=store.ingest([observed_at(r,10,END) for r in rows],now=END)
 assert all('service_name' not in r and 'service_event_key' not in r for r in rows)
 assert not latest.get('event_followups')
 assert before==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
 old_id=observe(rows[0],10)['event_id'];assert old_id==observe(extract_economic_changes(text(cause,['HBM 분석 서비스 개시','생산 개시','납품 개시']))[0],10)['event_id']
 replay=store.ingest([observed_at(r,10,END) for r in rows],now=END)
 assert replay==[] and store.search(now=END)==[latest]

@pytest.mark.parametrize('cause',CAUSES)
def test_licensed_body_is_synthetic_and_future_source_remains_blocked(tmp_path,cause):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 article=text(cause)+'。 이 문서는 기능 검증을 위해 만든 합성 보도 자료이며 실제 기업의 발표가 아닙니다.';_,args=body_case(tmp_path,article);report=analyze_motir_document(**args)
 assert len(report['economic_changes'])==2 and report['source_fetch_calls']==report['new_ai_results']==0
 p,h=publish_motir_document_analysis(report,tmp_path/'reports');assert consume_motir_document_analysis(p,h)['economic_changes']==report['economic_changes']
 _,themes,*_=stored_case(tmp_path/'stored',[article]);themes[0]['source_refs'][0]['source_available_at']=LATER.isoformat()
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
def test_http_function_sources_three_views_and_fixed_json(tmp_path,cause):
 import json,subprocess,threading
 from urllib.parse import urlencode
 from urllib.request import urlopen
 from scripts import open_research_dashboard as dashboard
 parts=[SERVICE,'「청해공장」 투자 집행','「차량용 검사」 시장 진출']
 articles=[text(cause,parts),text(cause,parts,product='DRAM',actor='새빛소재')]
 store,*_=stored_case(tmp_path,articles)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**query):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(query)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
  if cause=='가격 상승으로':assert data['cross_product_demand']['groups']==[]
  else:
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
  assert articles[0] in rendered and SERVICE in rendered and '청해공장' in rendered and '차량용 검사' in rendered
  if cause!='가격 상승으로':assert '같은 회사를 새 기업으로 세지 않습니다.' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('count',[2,3])
@pytest.mark.parametrize('fault',['different','missing'])
def test_named_project_stays_bound_when_specialized_proof_is_absent(tmp_path,cause,count,fault):
 from newscatalystos.economic_changes import investment_project
 article=text(cause,[SERVICE,'「청해공장」 투자 집행','생산 개시'][:count])
 row=next(r for r in extract_economic_changes(article) if r['action']=='INVESTMENT_EXECUTION')
 row.pop('policy_investment_action',None)
 if fault=='different':row['investment_project']=investment_project('「바다공장」 투자 집행','INVESTMENT_EXECUTION')
 else:row.pop('investment_project')
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,*_=stored_case(tmp_path,[article]);ref=next(r for r in themes[0]['source_refs'] if r['action']=='INVESTMENT_EXECUTION')
 ref.pop('policy_investment_action',None)
 if fault=='different':ref['investment_project']=deepcopy(row['investment_project'])
 else:ref.pop('investment_project')
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
