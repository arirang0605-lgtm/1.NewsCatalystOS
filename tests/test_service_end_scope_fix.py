"""A trailing function service never owns another economic action's source span."""
from copy import deepcopy
from hashlib import sha256
from itertools import permutations
import pytest
from newscatalystos.economic_changes import extract_economic_changes,price_service_actions,order_service_actions
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_function_service_parallel import text,SERVICE
from test_price_parallel_service import OPERATIONS
from test_policy_parallel_service_investment import case as stored_case
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import observed_at
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER

CAUSES=['가격 상승으로','주문 확대로']

def key(cause):return 'price_parallel_action' if cause=='가격 상승으로' else 'growth_parallel_action'
def single(cause):return price_service_actions if cause=='가격 상승으로' else order_service_actions

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('scope',['AI 서버',''])
@pytest.mark.parametrize('operation',OPERATIONS[:6])
def test_previously_rejected_twelve_price_and_twelve_order_cases_store(tmp_path,cause,scope,operation):
 a=text(cause,[operation[1],SERVICE],scope=scope);rows=extract_economic_changes(a)
 assert {r['action'] for r in rows}=={operation[0],'BUSINESS_START'}
 assert single(cause)(a) is None
 for row in rows:
  validate_change(row);proof=row[key(cause)]
  assert a[slice(*proof['action_span'])]==proof['action_expression']
  assert proof['expression_sha256']==sha256(a.encode()).hexdigest()
  assert all(field not in row for field in ('price_service_action','order_service_action','function_service_action','service_name','service_event_key'))
  assert row['entity_ids']==proof['actors']==['가상전자'] and row['phase']=='SOURCE_REPORTED'
 articles=[a,text(cause,[operation[1],SERVICE],scope=scope,actor='새빛소재'),text(cause,[operation[1],SERVICE],scope=scope,actor='미래장비')]
 store,themes,cs,comp,_=stored_case(tmp_path,articles);theme,=themes
 assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3
 assert theme['scores']['distinct_economic_events']==6 and comp[theme['theme_id']]['distinct_action_groups']==6
 raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
 assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['product_comparisons']==comp
 assert store.search(query='HBM 검사',now=END)==themes

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('operations',[
 ['생산 개시','납품 개시'],['공급계약 체결','생산능력 확대'],
 ['「청해공장」 투자 집행','「차량용 검사」 시장 진출']])
@pytest.mark.parametrize('order',list(permutations(range(3))))
def test_service_first_middle_last_preserves_own_spans_and_event_ids(tmp_path,cause,operations,order):
 parts=[SERVICE,*operations];source=text(cause,[parts[i] for i in order]);rows=extract_economic_changes(source)
 baseline=extract_economic_changes(text(cause,parts));assert len(rows)==3
 assert single(cause)(source) is None
 by_action={r['action']:r for r in baseline}
 for row in rows:
  validate_change(row);p=row[key(cause)]
  assert observe(row,0)['event_id']==observe(by_action[row['action']],0)['event_id']
  assert p['action_expression']==parts[0 if row['action']=='BUSINESS_START' else 1 if row['action']==baseline[1]['action'] else 2]
  assert source[slice(*p['action_span'])]==p['action_expression']
  assert 'price_service_action' not in row and 'order_service_action' not in row and 'service_name' not in row
  if row['action']=='INVESTMENT_EXECUTION':assert row['investment_project']['project_name']=='청해공장'
  if row['action']=='MARKET_ENTRY':assert row['market_entry']['market_name']=='차량용 검사'
 store,themes,cs,comp,_=stored_case(tmp_path,[source,text(cause,[parts[i] for i in order],product='DRAM',actor='새빛소재')])
 if cause=='가격 상승으로':assert view(themes,cs,comp)['groups']==run(store,activity='all')[0]['groups']==[]
 else:
  group,=view(themes,cs,comp)['groups'];assert group['distinct_action_groups']==6 and group['unresolved_company_contexts']==2
  assert run(store,activity='all')[0]['groups'][0]['distinct_action_groups']==6

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('position',[0,1,2])
@pytest.mark.parametrize('fault',['계획','의향','부인','past','other_product','other_actor','other_scope','incomplete'])
def test_invalid_part_never_becomes_service_object_or_actual_sibling(cause,position,fault):
 parts=['생산 개시',SERVICE,'납품 개시']
 if fault=='past':parts[position]='지난해 '+parts[position]
 elif fault=='other_product':parts[position]='NAND '+parts[position]
 elif fault=='other_actor':parts[position]='달빛전자는 '+parts[position]
 elif fault=='other_scope':parts[position]='스마트폰용 HBM 수요 회복으로 '+parts[position]
 elif fault=='incomplete':parts[position]=parts[position].replace('개시','')
 else:parts[position]+=' '+fault
 assert extract_economic_changes(text(cause,parts))==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('tail',['',' 계획'])
@pytest.mark.parametrize('service',['HBM 검사','HBM 검사 및 결함 분석','「검사 및 분석」'])
def test_complete_single_service_and_multiple_objects_keep_literal_proofs(cause,tail,service):
 source=text(cause,[service+' 서비스 개시'+tail]);row,=extract_economic_changes(source);validate_change(row)
 p=single(cause)(source)['BUSINESS_START'];assert row['price_service_action' if cause=='가격 상승으로' else 'order_service_action']==p
 assert p['action_expression']==service+' 서비스 개시'+tail
 assert row['phase']==('PLANNED' if tail else 'SOURCE_REPORTED')
 assert key(cause) not in row
 if service.startswith('「'):assert row['service_name']=='검사 및 분석'
 else:assert 'service_name' not in row and 'service_event_key' not in row

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('parts',[
 ['생산 개시',SERVICE],['생산 개시','납품 개시',SERVICE],
 ['달빛전자를 신규 고객으로 확보',SERVICE],['「청해공장」 투자 집행',SERVICE]])
def test_feed_reads_bound_actions_and_rejects_partial_strip_and_rebind(tmp_path,cause,parts):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 a=text(cause,parts);report=analyze(setup(tmp_path,a));r=report['results'][0];original=deepcopy(r['economic_changes']);assert len(original)==len(parts)
 assert all(c['entity_ids']==['가상전자'] for c in original)
 p,h=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']
 for i in range(len(parts)):
  modified=deepcopy(original);modified[i].pop(key(cause));r['economic_changes']=modified
  with pytest.raises(SourceShareError):
   p,h=publish_feed_analysis(report,tmp_path/f'strip{i}');consume_feed_analysis(p,p.parent,h)
 changed=extract_economic_changes(a.replace('HBM 검사 서비스','HBM 분석 서비스'))
 for c in changed:c.update(evidence_level='REPORTED',source_paragraph_sha256=r['source_title_sha256'])
 r['economic_changes']=changed
 with pytest.raises(SourceShareError):
  p,h=publish_feed_analysis(report,tmp_path/'rebound');consume_feed_analysis(p,p.parent,h)

@pytest.mark.parametrize('cause',CAUSES)
def test_same_origin_order_change_keeps_first_id_pit_and_zero_new_actions(tmp_path,cause):
 store=ThemeStore(tmp_path/'theme_history')
 prior=extract_economic_changes(text(cause,[SERVICE,'생산 개시']))
 original,=store.ingest([observe(r,0) for r in prior],now=T)
 before=build_theme_bundle([original],decision_at=T,now=T,include_company_candidates=True)
 current=extract_economic_changes(text(cause,['생산 개시',SERVICE]))
 updated,=store.ingest([observe(r,0) for r in current],now=END)
 assert updated['theme_id']==original['theme_id'] and updated['first_detected_at']==original['first_detected_at']
 assert updated['scores']['distinct_economic_events']==2
 assert compare_themes(store,since=END,as_of=END,now=END)['ThemeChanges'][0]['events']['independent_actions_added']==0
 assert before==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
 assert store.ingest([observe(r,0) for r in current],now=END)==[]
 updated['source_refs'][-1]['source_available_at']=LATER.isoformat()
 with pytest.raises(SourceShareError):build_theme_bundle([updated],decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
def test_synthetic_licensed_body_uses_own_parallel_spans(tmp_path,cause):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 a=text(cause,['생산 개시',SERVICE])+'. 이 본문은 합성 시험용이며 실제 기업의 보도 자료가 아닙니다.'
 _,args=body_case(tmp_path,a);report=analyze_motir_document(**args)
 assert len(report['economic_changes'])==2 and report['source_fetch_calls']==report['new_ai_results']==0
 assert all(key(cause) in c and 'price_service_action' not in c and 'order_service_action' not in c for c in report['economic_changes'])
 p,h=publish_motir_document_analysis(report,tmp_path/'reports');assert consume_motir_document_analysis(p,h)['economic_changes']==report['economic_changes']

@pytest.mark.parametrize('cause',CAUSES)
def test_http_service_last_sources_three_views_and_fixed_json(tmp_path,cause):
 import json,subprocess,threading
 from urllib.parse import urlencode
 from urllib.request import urlopen
 from scripts import open_research_dashboard as dashboard
 parts=['생산 개시','납품 개시',SERVICE]
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
  assert articles[0] in rendered and SERVICE in rendered
  if cause!='가격 상승으로':assert '같은 회사를 새 기업으로 세지 않습니다.' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
