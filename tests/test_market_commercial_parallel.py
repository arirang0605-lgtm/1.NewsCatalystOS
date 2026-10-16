"""Market names stay inside their own delivery/customer shared source spans."""
from copy import deepcopy
from hashlib import sha256
import pytest
from newscatalystos.economic_changes import extract_economic_changes,market_entry
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_delivery_customer_parallel import article,CAUSES,proof_key,driver
from test_policy_parallel_service_investment import case as stored_case
from test_adjacent_demand_scope import observe
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER

PARTNERS=[('DELIVERY_START','달빛전자에 HBM 납품 개시'),('CUSTOMER_ACQUISITION','달빛전자를 신규 고객으로 확보')]
MARKETS=['「차량용 검사」 시장 진출','일본 시장 진출']

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('partner',PARTNERS)
@pytest.mark.parametrize('market',MARKETS)
@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('scope',['AI 서버',''])
def test_market_pair_stores_names_from_own_spans_without_customer_actor(tmp_path,cause,partner,market,reverse,scope):
 parts=[partner[1],market];a=article(cause,parts,reverse=reverse,scope=scope);rows=extract_economic_changes(a)
 assert {r['action'] for r in rows}=={partner[0],'MARKET_ENTRY'}
 assert extract_economic_changes(a,include_market_commercial_parallel=False)==[]
 for row in rows:
  validate_change(row);p=row[proof_key(cause)]
  assert row['economic_driver']==driver(cause) and row['phase']=='SOURCE_REPORTED'
  assert p['actors']==row['entity_ids']==['가상전자'] and p['expression_sha256']==sha256(a.encode()).hexdigest()
  assert a[slice(*p['action_span'])]==p['action_expression']
  assert all(k not in row for k in ['service_name','service_event_key','investment_project'])
  if row['action']=='MARKET_ENTRY':assert row['market_entry']==market_entry(market)
  else:assert 'market_entry' not in row
 articles=[a,article(cause,parts,reverse=reverse,scope=scope,actor='새빛소재'),article(cause,parts,reverse=reverse,scope=scope,actor='미래장비')]
 store,themes,cs,comp,_=stored_case(tmp_path,articles);theme,=themes
 assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3 and theme['scores']['distinct_economic_events']==6
 assert comp[theme['theme_id']]['distinct_action_groups']==6 and len(cs)==3
 assert all(c['entity_id']!='달빛전자' for c in cs)
 assert all(c['match_kind']=='TEXT_CONTEXT' for c in match_company_search(company_search_context(themes,cs),'달빛전자').values())
 assert store.search(query=market_entry(market)['market_name'],now=END)==themes
 raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
 assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['product_comparisons']==comp
 store,themes,cs,comp,_=stored_case(tmp_path/'cross',[a,article(cause,parts,reverse=reverse,scope=scope,actor='새빛소재',product='DRAM')])
 if cause=='가격 상승으로' or (not scope and cause!='정책'):
  assert view(themes,cs,comp)['groups']==run(store,activity='all')[0]['groups']==[]
 else:
  group,=view(themes,cs,comp)['groups'];assert group['distinct_action_groups']==4 and group['unresolved_company_contexts']==2
  assert not group['verified_real_transaction'] and not group['verified_real_benefit']
  assert run(store,activity='all')[0]['groups'][0]['distinct_action_groups']==4

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('partner',PARTNERS)
@pytest.mark.parametrize('position',[0,1])
@pytest.mark.parametrize('fault',['계획','부인','past','actor','product','incomplete'])
def test_each_invalid_part_cannot_promote_siblings(cause,partner,position,fault):
 parts=[partner[1],MARKETS[0]]
 if fault=='past':parts[position]='지난해 '+parts[position]
 elif fault=='actor':parts[position]='빛결전자는 '+parts[position]
 elif fault=='product':parts[position]='NAND '+parts[position]
 elif fault=='incomplete':parts[position]=parts[position].replace('개시','').replace('확보','').replace('진출','')
 else:parts[position]+=' '+fault
 assert extract_economic_changes(article(cause,parts))==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('parts',[
 ['납품 개시',MARKETS[0],'생산 개시'],['신규 고객 확보',MARKETS[0],'공급계약 체결'],
 ['납품 개시',MARKETS[0],''],[MARKETS[0],MARKETS[0]],['납품 개시','또는 '+MARKETS[0]],
 ['납품 개시','「NAND」 시장 진출'],['납품 개시','그 시장 진출'],
 ['납품 개시','일본 또는 미국 시장 진출'],['납품 개시',MARKETS[0]+' 의향'],
 ['납품 개시','일본 ‘다른통제법’ HBM 수출 규제 완화로 '+MARKETS[0]]])
def test_duplicate_extra_ambiguous_or_conflicting_market_is_not_inherited(cause,parts):
 assert extract_economic_changes(article(cause,parts))==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('fault',['different_market','missing_market','span','sha','actor','phase'])
def test_mutated_market_proof_rejected_before_storage_and_output(tmp_path,cause,fault):
 a=article(cause,['납품 개시',MARKETS[0]]);rows=extract_economic_changes(a);row=next(r for r in rows if r['action']=='MARKET_ENTRY')
 if fault=='different_market':row['market_entry']=market_entry(MARKETS[1])
 elif fault=='missing_market':row.pop('market_entry')
 elif fault=='span':row[proof_key(cause)]['action_span']=rows[0][proof_key(cause)]['action_span']
 elif fault=='sha':row[proof_key(cause)]['expression_sha256']='f'*64
 elif fault=='actor':row[proof_key(cause)]['actors']=['빛결전자']
 else:row['phase']='PLANNED'
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,*_=stored_case(tmp_path,[a]);ref=next(r for r in themes[0]['source_refs'] if r['action']=='MARKET_ENTRY')
 for key in [proof_key(cause),'phase','market_entry']:
  if key in row:ref[key]=deepcopy(row[key])
  else:ref.pop(key,None)
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('partner',PARTNERS)
def test_feed_binding_partial_strip_and_prior_single_market(tmp_path,cause,partner):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 parts=[partner[1],MARKETS[0]];a=article(cause,parts);report=analyze(setup(tmp_path,a));r=report['results'][0];original=deepcopy(r['economic_changes']);assert len(original)==2
 p,h=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']
 for i in range(2):
  changes=deepcopy(original);changes[i].pop(proof_key(cause));r['economic_changes']=changes
  with pytest.raises(SourceShareError):
   p,h=publish_feed_analysis(report,tmp_path/f'strip{i}');consume_feed_analysis(p,p.parent,h)
 changes=extract_economic_changes(article(cause,[partner[1],MARKETS[1]]))
 for c in changes:c.update(evidence_level='REPORTED',source_paragraph_sha256=r['source_title_sha256'])
 r['economic_changes']=changes
 with pytest.raises(SourceShareError):
  p,h=publish_feed_analysis(report,tmp_path/'rebind');consume_feed_analysis(p,p.parent,h)
 a=article(cause,[MARKETS[0]])+'. '+a
 report=analyze(setup(tmp_path/'prior',a));rows=report['results'][0]['economic_changes']
 assert len(rows)==2 and sum(proof_key(cause) in c for c in rows)==1
 p,h=publish_feed_analysis(report,tmp_path/'prior_reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']

@pytest.mark.parametrize('cause',CAUSES)
def test_market_names_distinct_ids_prior_single_pit_and_new_partner_only(tmp_path,cause):
 first,=extract_economic_changes(article(cause,[MARKETS[0]]));pair=extract_economic_changes(article(cause,['납품 개시',MARKETS[0]]))
 current=next(r for r in pair if r['action']=='MARKET_ENTRY');assert observe(first,0)['event_id']==observe(current,0)['event_id']
 store=ThemeStore(tmp_path/'theme_history');old,=store.ingest([observe(first,0)],now=T)
 before=build_theme_bundle([old],decision_at=T,now=T,include_company_candidates=True)
 latest,=store.ingest([observe(r,0) for r in pair],now=END)
 assert latest['theme_id']==old['theme_id'] and latest['first_detected_at']==old['first_detected_at']
 assert compare_themes(store,since=END,as_of=END,now=END)['ThemeChanges'][0]['events']['independent_actions_added']==1
 assert before==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=T,include_company_candidates=True)
 assert store.ingest([observe(r,0) for r in pair],now=END)==[]
 multi=article(cause,['납품 개시',MARKETS[0]])+'. '+article(cause,['납품 개시',MARKETS[1]])
 rows=extract_economic_changes(multi);assert len(rows)==3
 assert {r['market_entry']['market_name'] for r in rows if r['action']=='MARKET_ENTRY'}=={'차량용 검사','일본'}
 assert all(r['entity_ids']==['가상전자'] for r in rows)
 latest['source_refs'][-1]['source_available_at']=LATER.isoformat()
 with pytest.raises(SourceShareError):build_theme_bundle([latest],decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
def test_synthetic_licensed_body_and_no_external_calls(tmp_path,cause):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 a=article(cause,[PARTNERS[1][1],MARKETS[0]])+'. 이 본문은 합성 시험용이며 실제 기업의 보도 자료가 아닙니다.'
 _,args=body_case(tmp_path,a);report=analyze_motir_document(**args)
 assert len(report['economic_changes'])==2 and report['source_fetch_calls']==report['new_ai_results']==0
 p,h=publish_motir_document_analysis(report,tmp_path/'reports');assert consume_motir_document_analysis(p,h)['economic_changes']==report['economic_changes']

@pytest.mark.parametrize('cause',CAUSES)
def test_other_market_end_use_cannot_rewrite_demand_destination(cause):
 a=article(cause,['납품 개시','「스마트폰용 HBM」 시장 진출'])
 rows=extract_economic_changes(a)
 if cause=='정책':assert len(rows)==2 and all(r['policy_cause']['destination']=='중국' for r in rows)
 else:assert rows==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('partner',PARTNERS)
def test_http_market_commercial_sources_three_views_and_fixed_json(tmp_path,cause,partner):
 import json,subprocess,threading
 from urllib.parse import urlencode
 from urllib.request import urlopen
 from scripts import open_research_dashboard as dashboard
 parts=[partner[1],MARKETS[0]]
 articles=[article(cause,parts),article(cause,parts,product='DRAM',actor='새빛소재')]
 store,*_=stored_case(tmp_path,articles)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**query):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(query)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
  if cause=='가격 상승으로':assert data['cross_product_demand']['groups']==[]
  else:
   group,=data['cross_product_demand']['groups'];assert group['distinct_action_groups']==4 and group['unresolved_company_contexts']==2
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
  assert articles[0] in rendered and partner[1] in rendered and '차량용 검사' in rendered
  assert '서비스 개시' not in rendered
  if cause!='가격 상승으로':assert '같은 회사를 새 기업으로 세지 않습니다.' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
