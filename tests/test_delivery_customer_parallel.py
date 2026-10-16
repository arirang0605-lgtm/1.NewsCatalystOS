"""An exact delivery/customer pair shares its reported cause, not a fake service."""
from copy import deepcopy
from hashlib import sha256
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_function_service_parallel import text,CAUSES,proof_key,driver
from test_policy_parallel_service_investment import case as stored_case
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import observed_at
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER

FORMS=[['납품 개시','신규 고객 확보'],['달빛전자에 HBM 납품 개시','빛결전자를 신규 고객으로 확보'],['「하늘고객」에 HBM 납품 개시','「바다고객」을 신규 고객으로 확보']]

def article(cause,parts=None,actor='가상전자',product='HBM',scope='AI 서버',reverse=False):
 s=text(cause,list(reversed(parts or FORMS[0])) if reverse else parts or FORMS[0],actor=actor,product=product,scope=scope)
 if cause=='정책' and not scope:s=s.replace('중국향 ','')
 return s

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('parts',FORMS)
@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('scope',['AI 서버',''])
def test_exact_pair_stores_two_source_actions_and_no_customer_company(tmp_path,cause,parts,reverse,scope):
 a=article(cause,parts,reverse=reverse,scope=scope);rows=extract_economic_changes(a)
 assert {r['action'] for r in rows}=={'DELIVERY_START','CUSTOMER_ACQUISITION'}
 assert extract_economic_changes(a,include_delivery_customer_parallel=False)==[]
 spans=[]
 for row in rows:
  validate_change(row);p=row[proof_key(cause)];spans.append(p['action_span'])
  assert row['economic_driver']==driver(cause) and row['phase']=='SOURCE_REPORTED'
  assert a[slice(*p['action_span'])]==p['action_expression'] and p['expression_sha256']==sha256(a.encode()).hexdigest()
  assert p['actors']==row['entity_ids']==['가상전자']
  assert not row['verified_economic_effect'] and all(k not in row for k in ['service_name','service_event_key','market_entry','investment_project'])
 assert spans==sorted(spans) and spans[0][1]<spans[1][0]
 articles=[a,article(cause,parts,reverse=reverse,scope=scope,actor='새빛소재'),article(cause,parts,reverse=reverse,scope=scope,actor='미래장비')]
 store,themes,cs,comp,_=stored_case(tmp_path,articles);theme,=themes
 assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3
 assert theme['scores']['distinct_economic_events']==6 and comp[theme['theme_id']]['distinct_action_groups']==6
 assert len(cs)==3 and {c['entity_id'] for c in cs}=={'가상전자','새빛소재','미래장비'}
 for row in comp[theme['theme_id']]['rows']:
  for source in row['sources']:
   assert source['impact_paths']==[] and not source.get('customer') and not source.get('verified_revenue')
 ctx=company_search_context(themes,cs)
 assert all(c['match_kind']=='TEXT_CONTEXT' for c in match_company_search(ctx,'빛결전자').values())
 assert store.search(query='신규 고객',now=END)==themes
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
@pytest.mark.parametrize('position',[0,1])
@pytest.mark.parametrize('fault',['계획','의향','부인','past','actor','product','other_scope','incomplete'])
def test_no_partial_actual_from_invalid_part(cause,position,fault):
 parts=list(FORMS[0])
 if fault=='past':parts[position]='지난해 '+parts[position]
 elif fault=='actor':parts[position]='달빛전자는 '+parts[position]
 elif fault=='product':parts[position]='NAND '+parts[position]
 elif fault=='other_scope':parts[position]='스마트폰용 HBM 수요 회복으로 '+parts[position]
 elif fault=='incomplete':parts[position]=parts[position].replace('개시','').replace('확보','')
 else:parts[position]+=' '+fault
 assert extract_economic_changes(article(cause,parts))==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('parts',[
 ['납품 개시','신규 고객 확보','생산 개시'],['납품 개시','신규 고객 확보','공급계약 체결'],
 ['납품 개시','신규 고객 확보',''],['납품 개시','납품 개시'],['신규 고객 확보','신규 고객 확보'],
 ['납품 개시','신규 고객 확보','납품 개시'],['납품 개시','또는 신규 고객 확보'],
 ['납품 개시했고 그 회사는 신규 고객 확보']])
def test_extra_duplicate_ambiguous_or_incomplete_list_cannot_promote_keyword(cause,parts):
 assert extract_economic_changes(article(cause,parts))==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('fault',['span','sha','actor','phase','driver'])
def test_changed_pair_proof_rejected_before_storage_and_output(tmp_path,cause,fault):
 a=article(cause);rows=extract_economic_changes(a);row=rows[0]
 if fault=='span':row[proof_key(cause)]['action_span']=rows[1][proof_key(cause)]['action_span']
 elif fault=='sha':row[proof_key(cause)]['expression_sha256']='f'*64
 elif fault=='actor':row[proof_key(cause)]['actors']=['달빛전자']
 elif fault=='phase':row['phase']='PLANNED'
 else:row['economic_driver']='DEMAND_CONTRACTION'
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,*_=stored_case(tmp_path,[a]);ref=next(r for r in themes[0]['source_refs'] if r['action']==row['action'])
 for key in [proof_key(cause),'phase','economic_driver']:ref[key]=deepcopy(row[key])
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('parts',[FORMS[0],FORMS[1]])
def test_feed_raw_binding_partial_strip_and_prior_standalone(tmp_path,cause,parts):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 a=article(cause,parts);report=analyze(setup(tmp_path,a));r=report['results'][0];original=deepcopy(r['economic_changes']);assert len(original)==2
 p,h=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']
 for i in range(2):
  changes=deepcopy(original);changes[i].pop(proof_key(cause));r['economic_changes']=changes
  with pytest.raises(SourceShareError):
   p,h=publish_feed_analysis(report,tmp_path/f'strip{i}');consume_feed_analysis(p,p.parent,h)
 changed=extract_economic_changes(article(cause,list(reversed(parts))))
 for c in changed:c.update(evidence_level='REPORTED',source_paragraph_sha256=r['source_title_sha256'])
 r['economic_changes']=changed
 with pytest.raises(SourceShareError):
  p,h=publish_feed_analysis(report,tmp_path/'rebound');consume_feed_analysis(p,p.parent,h)
 # Earlier complete standalone claims keep their original ID/source proof.
 a=article(cause,[parts[0]])+'. '+a
 report=analyze(setup(tmp_path/'prior',a));rows=report['results'][0]['economic_changes']
 assert len(rows)==2 and sum(proof_key(cause) in c for c in rows)==1
 p,h=publish_feed_analysis(report,tmp_path/'prior_reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']

@pytest.mark.parametrize('cause',CAUSES)
def test_existing_single_ids_and_first_times_keep_pit_and_add_only_customer(tmp_path,cause):
 first,=extract_economic_changes(article(cause,['납품 개시']));rows=extract_economic_changes(article(cause))
 assert observe(first,0)['event_id']==observe(rows[0],0)['event_id']
 store=ThemeStore(tmp_path/'theme_history');old,=store.ingest([observe(first,0)],now=T)
 before=build_theme_bundle([old],decision_at=T,now=T,include_company_candidates=True)
 latest,=store.ingest([observe(r,0) for r in rows],now=END)
 assert latest['theme_id']==old['theme_id'] and latest['first_detected_at']==old['first_detected_at']
 assert latest['scores']['distinct_economic_events']==2 and latest['scores']['company_breadth']==1
 assert compare_themes(store,since=END,as_of=END,now=END)['ThemeChanges'][0]['events']['independent_actions_added']==1
 assert before==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=T,include_company_candidates=True)
 assert store.ingest([observe(r,0) for r in rows],now=END)==[]
 latest['source_refs'][-1]['source_available_at']=LATER.isoformat()
 with pytest.raises(SourceShareError):build_theme_bundle([latest],decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
def test_synthetic_licensed_body_keeps_two_actions(tmp_path,cause):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 a=article(cause)+'. 이 본문은 합성 시험용이며 실제 기업의 보도 자료가 아닙니다.'
 _,args=body_case(tmp_path,a);report=analyze_motir_document(**args)
 assert len(report['economic_changes'])==2 and report['source_fetch_calls']==report['new_ai_results']==0
 assert {c['action'] for c in report['economic_changes']}=={'DELIVERY_START','CUSTOMER_ACQUISITION'}
 p,h=publish_motir_document_analysis(report,tmp_path/'reports');assert consume_motir_document_analysis(p,h)['economic_changes']==report['economic_changes']

@pytest.mark.parametrize('changed',['country','policy','destination','restriction','change','scope','driver'])
def test_different_scope_keeps_candidates_separate(changed,tmp_path):
 cause='수요 회복으로' if changed in {'scope','driver'} else '정책'
 a=article(cause);b=article(cause,actor='새빛소재',product='DRAM')
 before,after={'country':('미국','일본'),'policy':('첨단칩통제법','다른통제법'),'destination':('중국향','일본향'),'restriction':('수출 규제','생산 규제'),'change':('완화','폐지'),'scope':('AI 서버용','스마트폰용'),'driver':('수요 회복으로','수요 증가로')}[changed]
 b=b.replace(before,after)
 if changed=='restriction':b=b.replace('중국향 ','')
 _,themes,cs,comp,_=stored_case(tmp_path,[a,b]);assert view(themes,cs,comp)['groups']==[]

@pytest.mark.parametrize('cause',CAUSES)
def test_http_delivery_customer_sources_three_views_and_fixed_json(tmp_path,cause):
 import json,subprocess,threading
 from urllib.parse import urlencode
 from urllib.request import urlopen
 from scripts import open_research_dashboard as dashboard
 parts=FORMS[1]
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
  assert articles[0] in rendered and '달빛전자에 HBM 납품 개시' in rendered and '빛결전자를 신규 고객으로 확보' in rendered
  assert '서비스 개시' not in rendered
  if cause!='가격 상승으로':assert '같은 회사를 새 기업으로 세지 않습니다.' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
