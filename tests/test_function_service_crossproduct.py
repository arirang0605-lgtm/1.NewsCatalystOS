"""Standalone functional services retain bounded causes without named identities."""
from copy import deepcopy
from hashlib import sha256
import pytest
from newscatalystos.economic_changes import extract_economic_changes,function_service_actions
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.company_search import company_search_context
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.source_share import SourceShareError
from test_function_service_parallel import text,SERVICE
from test_policy_parallel_service_investment import case as stored_case
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import observed_at
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER

CAUSES=['수요 회복으로','주문 회복으로','정책']

def article(cause,function='HBM 검사',actor='가상전자',product='HBM',phase='',subject_first=True):
 s=text(cause,[function+' 서비스 개시'+phase],actor=actor,product=product)
 if not subject_first:s=s.replace(actor+', ','').replace('로 '+function.replace('HBM',product),'로 '+actor+'는 '+function.replace('HBM',product))
 return s

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('function',['HBM 검사','HBM 결함 분석','반도체 장비 관리'])
@pytest.mark.parametrize('subject_first',[True,False])
def test_stored_function_source_forms_group_and_retains_exact_scope(tmp_path,cause,function,subject_first):
 a=article(cause,function,subject_first=subject_first);row,=extract_economic_changes(a);validate_change(row)
 old,=extract_economic_changes(a,include_function_service_actions=False)
 p=row.pop('function_service_action');assert row==old;row['function_service_action']=p
 assert p==function_service_actions(a)['BUSINESS_START']
 assert a[slice(*p['action_span'])]==p['action_expression']
 assert p['expression_sha256']==sha256(a.encode()).hexdigest() and p['actors']==row['entity_ids']==['가상전자']
 assert row['phase']=='SOURCE_REPORTED' and 'service_name' not in row and 'service_event_key' not in row
 if cause=='정책':assert row['policy_cause']['destination']=='중국' and row['policy_cause']['jurisdiction']=='미국'
 else:assert row['demand_scope']['destination']=='AI 서버'
 b=article(cause,function,actor='새빛소재',product='DRAM',subject_first=subject_first)
 store,themes,cs,comp,_=stored_case(tmp_path,[a,b]);group,=view(themes,cs,comp)['groups']
 assert group['distinct_action_groups']==2 and group['unresolved_company_contexts']==2
 assert not group['verified_real_transaction'] and not group['verified_real_benefit']
 assert all('function_service_action' in s and 'service_name' not in s for product in group['products'] for act in product['actions'] for s in act['sources'])
 period,_,_=run(store,activity='all');assert period['groups'][0]['period_change']['formed_in_period']
 assert store.search(query=function,now=END)
 context=company_search_context(themes,cs)
 assert 'function_service_action' in str(context)
 raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
 export=read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)
 assert export['comparison']==period and export['product_comparisons']==comp
 # Three companies create an early theme, not three services certified identical.
 store,themes,cs,comp,_=stored_case(tmp_path/'same',[a,article(cause,function,actor='새빛소재'),article(cause,function,actor='미래장비')])
 theme,=themes;assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3
 assert theme['scores']['distinct_economic_events']==3 and not theme.get('event_followups')

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('tail',['계획','예정','목표','검토'])
def test_planned_service_retains_phase_and_cannot_form_actual_group(tmp_path,cause,tail):
 a=article(cause,phase=' '+tail);rows=extract_economic_changes(a);assert len(rows)==1
 assert rows[0]['phase']=='PLANNED' and rows[0]['function_service_action']['phase']=='PLANNED'
 store,themes,cs,comp,_=stored_case(tmp_path,[a,article(cause,actor='새빛소재',product='DRAM',phase=' '+tail)])
 assert view(themes,cs,comp)['groups']==run(store,activity='all')[0]['groups']==[]

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('fault',['취소','부인','past','other_product','other_actor','other_cause','generic','incomplete','finite','ambiguous'])
def test_invalid_or_unresolved_clause_has_no_function_source_proof(cause,fault):
 a=article(cause)
 if fault=='past':a=a.replace(SERVICE,'지난해 '+SERVICE)
 elif fault=='other_product':a=a.replace(SERVICE,'NAND 검사 서비스 개시')
 elif fault=='other_actor':a=a.replace(SERVICE,'달빛전자는 '+SERVICE)
 elif fault=='other_cause':a=a.replace(SERVICE,'일본 ‘별도통제법’ DRAM 수출 규제 완화로 '+SERVICE)
 elif fault=='generic':a=a.replace(SERVICE,'AI 검사 서비스 개시')
 elif fault=='incomplete':a=a.replace('서비스 개시','서비스')
 elif fault=='finite':a+='했고 그 회사는 생산 개시'
 elif fault=='ambiguous':a=a.replace('HBM 검사','HBM 검사 또는 분석')
 else:a+=' '+fault
 assert function_service_actions(a) is None
 assert not any('function_service_action' in r for r in extract_economic_changes(a))

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('fault',['span','cause_span','sha','actor','phase','name','service_key','topic','driver','delete_expression'])
def test_changed_proof_rejected_before_storage_and_delivery(tmp_path,cause,fault):
 a=article(cause);row,=extract_economic_changes(a)
 if fault in {'span','cause_span'}:row['function_service_action']['action_span' if fault=='span' else 'cause_span']=[0,4]
 elif fault=='sha':row['function_service_action']['expression_sha256']='f'*64
 elif fault=='actor':row['function_service_action']['actors']=['달빛전자']
 elif fault=='phase':row['phase']='PLANNED'
 elif fault=='name':row['service_name']='HBM 검사'
 elif fault=='service_key':row['service_event_key']=sha256('HBM 검사'.encode()).hexdigest()
 elif fault=='topic':row['topic']='DRAM'
 elif fault=='driver':row['economic_driver']='DEMAND_EXPANSION'
 else:row['function_service_action'].pop('action_expression')
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,*_=stored_case(tmp_path,[a]);ref=themes[0]['source_refs'][0]
 for key in ['function_service_action','phase','service_name','service_event_key','topic','economic_driver']:
  if key in row:ref[key]=deepcopy(row[key])
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
def test_feed_rebind_partial_proof_and_legacy_report_without_enrichment(tmp_path,cause):
 from test_feed_analysis import setup,run as analyze
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 a=article(cause);report=analyze(setup(tmp_path,a));row=report['results'][0];original=deepcopy(row['economic_changes'])
 assert len(original)==1 and 'function_service_action' in original[0]
 p,h=publish_feed_analysis(report,tmp_path/'reports');assert consume_feed_analysis(p,p.parent,h)['results']==report['results']
 for mode in ['rebind','partial','plan_promoted']:
  change=extract_economic_changes(article(cause,function='HBM 분석' if mode=='rebind' else 'HBM 검사',phase=' 계획' if mode=='plan_promoted' else ''))[0]
  change.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
  if mode=='partial':change['function_service_action'].pop('cause_span')
  if mode=='plan_promoted':change.pop('function_service_action') # Removing the proof cannot certify an actual plan.
  row['economic_changes']=[change]
  with pytest.raises(SourceShareError):
   p,h=publish_feed_analysis(report,tmp_path/mode);consume_feed_analysis(p,p.parent,h)
 # A wholly old record remains readable, but cannot enter the new comparison.
 old=extract_economic_changes(a,include_function_service_actions=False)
 for c in old:c.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
 row['economic_changes']=old;p,h=publish_feed_analysis(report,tmp_path/'legacy')
 assert consume_feed_analysis(p,p.parent,h)['results']==report['results']

@pytest.mark.parametrize('cause',CAUSES)
def test_legacy_ids_pit_no_reinterpretation_and_no_unnamed_followup(tmp_path,cause):
 a=article(cause);old,=extract_economic_changes(a,include_function_service_actions=False);new,=extract_economic_changes(a)
 assert observe(old,0)['event_id']==observe(new,0)['event_id']
 store=ThemeStore(tmp_path/'theme_history');store.ingest([observe(old,0)],now=T)
 before=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
 assert before==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
 # Legacy service remains context, not retroactively assigned a new source proof.
 b=article(cause,actor='새빛소재',product='DRAM');row,=extract_economic_changes(b)
 store.ingest([observed_at(row,1,END)],now=END)
 assert run(store,activity='all')[0]['groups']==[]
 enriched,=store.ingest([observe(new,0)],now=END)
 assert enriched['scores']['distinct_economic_events']==1
 assert enriched['first_detected_at']==T.isoformat()
 assert len(enriched['source_refs'])==2
 assert store.ingest([observe(new,0)],now=END)==[]
 group,=run(store,activity='all')[0]['groups'];assert group['distinct_action_groups']==2
 assert {c['kind'] for c in group['period_change']['service_stage_contexts']}=={'EXISTING_EVENT_UPDATE'}
 assert observe(new,0)['event_id'] not in group['period_change']['new_action_group_ids']
 plan,=extract_economic_changes(article(cause,function='HBM 분석',phase=' 계획'))
 store.ingest([observed_at(plan,3,END)],now=END)
 assert all(not t.get('event_followups') for t in store.search(now=END))
 assert before==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
def test_future_source_and_synthetic_licensed_body(tmp_path,cause):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 a=article(cause)+'. 이 본문은 합성 시험용으로 만들었으며 실제 기업의 보도 자료가 아닙니다.'
 _,args=body_case(tmp_path,a);report=analyze_motir_document(**args)
 assert len(report['economic_changes'])==1 and 'function_service_action' in report['economic_changes'][0]
 assert report['source_fetch_calls']==report['new_ai_results']==0
 p,h=publish_motir_document_analysis(report,tmp_path/'reports');assert consume_motir_document_analysis(p,h)['economic_changes']==report['economic_changes']
 _,themes,*_=stored_case(tmp_path/'stored',[article(cause)]);themes[0]['source_refs'][0]['source_available_at']=LATER.isoformat()
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('changed',['country','policy','destination','restriction','change','scope','driver'])
def test_different_policy_or_demand_scope_does_not_merge(changed,tmp_path):
 cause='수요 회복으로' if changed in {'scope','driver'} else '정책'
 a=article(cause);b=article(cause,actor='새빛소재',product='DRAM')
 before,after={'country':('미국','일본'),'policy':('첨단칩통제법','다른통제법'),'destination':('중국향','일본향'),'restriction':('수출 규제','생산 규제'),'change':('완화','폐지'),'scope':('AI 서버용','스마트폰용'),'driver':('수요 회복으로','수요 증가로')}[changed]
 b=b.replace(before,after)
 if changed=='restriction':b=b.replace('중국향 ','')
 _,themes,cs,comp,_=stored_case(tmp_path,[a,b]);assert view(themes,cs,comp)['groups']==[]

@pytest.mark.parametrize('cause',CAUSES)
def test_http_standalone_function_sources_three_views_and_fixed_json(tmp_path,cause):
 import json,subprocess,threading
 from urllib.parse import urlencode
 from urllib.request import urlopen
 from scripts import open_research_dashboard as dashboard
 parts=[SERVICE]
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
   group,=data['cross_product_demand']['groups'];assert group['distinct_action_groups']==2 and group['unresolved_company_contexts']==2
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
  assert '기능으로 설명된 서비스 개시 보도' in rendered
  assert ('정책 범위' if cause=='정책' else '회복 원인 범위') in rendered
  assert '원문 서비스명: HBM 검사' not in rendered
 finally:server.shutdown();server.server_close();thread.join(2)

@pytest.mark.parametrize('cause',CAUSES)
def test_missing_new_proof_does_not_admit_old_unnamed_services(tmp_path,cause):
 a=article(cause);b=article(cause,actor='새빛소재',product='DRAM')
 store,themes,cs,comp,_=stored_case(tmp_path,[a,b]);assert len(view(themes,cs,comp)['groups'])==1
 for theme in themes:
  for ref in theme['source_refs']:ref.pop('function_service_action')
 import json
 cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 comp=common_cause_comparisons(themes,cs)
 assert view(themes,cs,comp)['groups']==[]

@pytest.mark.parametrize('cause',CAUSES)
def test_valid_but_different_cause_cannot_replace_its_source_scope(tmp_path,cause):
 a=article(cause);row,=extract_economic_changes(a)
 other=article(cause).replace('중국향','일본향') if cause=='정책' else article(cause).replace('AI 서버용','스마트폰용')
 replacement,=extract_economic_changes(other)
 key='policy_cause' if cause=='정책' else 'demand_scope'
 row[key]=replacement[key]
 with pytest.raises(SourceShareError):validate_change(row)
 _,themes,*_=stored_case(tmp_path,[a]);themes[0]['source_refs'][0][key]=deepcopy(replacement[key])
 with pytest.raises(SourceShareError):build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('cause',CAUSES)
@pytest.mark.parametrize('operations',[['생산 개시'],['생산 개시','납품 개시']])
def test_function_at_end_of_action_list_keeps_only_parallel_proof(cause,operations):
 a=text(cause,[*operations,SERVICE]);assert function_service_actions(a) is None
 rows=extract_economic_changes(a);assert len(rows)==len(operations)+1
 for row in rows:
  assert 'function_service_action' not in row
  validate_change(row)
