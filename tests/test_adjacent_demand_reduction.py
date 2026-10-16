"""Synthetic source-reported demand decline -> production reduction, not losses."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,parse_demand_scope
from newscatalystos.theme_emergence import ThemeStore,validate_change,economic_observation
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.feed_analysis_delivery import _source_changes
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_scope import observe
from test_theme_emergence import T
from test_federated_news_search import fingerprint


def text(product='HBM',actor='가상전자',scope='AI 서버',verb='축소했다'):
 return f'{scope+"용 " if scope else ""}{product} 수요가 감소했다. 이에 따라 {actor}는 {product} 생산을 {verb}.'

@pytest.mark.parametrize('product',['HBM','DRAM','NAND'])
@pytest.mark.parametrize('scope',['','AI 서버'])
def test_exact_cause_action_spans_bind_to_single_reported_reduction(product,scope):
 source=text(product=product,scope=scope);row,=extract_economic_changes(source);validate_change(row)
 assert (row['economic_driver'],row['action'],row['phase'])==('DEMAND_CONTRACTION','SUPPLY_REDUCTION','SOURCE_REPORTED')
 assert not row['verified_economic_effect'] and row['entity_ids']==['가상전자']
 proof=row['adjacent_demand_cause'];assert proof['action']=='SUPPLY_REDUCTION'
 for part in ('cause','action'):
  start,end=proof[part+'_span'];assert source[start:end]==proof[part+'_expression']
  assert sha256(source[start:end].encode()).hexdigest()==proof[part+'_sha256']
 assert proof['paragraph_sha256']==row['source_paragraph_sha256']==sha256(source.encode()).hexdigest()
 assert bool(row.get('demand_scope'))==bool(scope)
 if scope:assert parse_demand_scope(proof['cause_expression'])==(product,'DEMAND_CONTRACTION',row['demand_scope'])
 assert _source_changes(source,row)==[row]

@pytest.mark.parametrize('source',[
 text(verb='축소할 계획이다'),text(verb='축소하지 않았다'),text(verb='축소하지 못했다'),
 text(verb='축소할 전망이다'),text(verb='축소했다는 소문이다'),text(verb='지난해 축소했다'),
 text().replace('감소했다','감소할 전망이다'),text().replace('감소했다','감소하지 않았다'),
 text().replace('감소했다','지난달 감소했다'),text().replace('수요가','가격이'),
 text().replace('수요가','매출이'),text().replace('수요가','계약금액이'),
 text().replace('. 이에','.\n이에'),text().replace('HBM 생산','DRAM 생산'),
 text(actor='이회사'),text(actor='가상전자와 새빛소재'),text(actor='가상전자와새빛전자'),
 text().replace('이에 따라','한편'),text().replace('AI 서버용','AI 서버용 HBM 수요 증가와 모바일용'),
 text().replace('감소했다.','감소했다. 주문도 감소했다.'),
 text().replace('생산을 축소했다','생산능력을 확대했다'),text().replace('감소했다','증가했다'),
])
def test_uncertain_competing_or_unrelated_sources_cannot_borrow_decline(source):
 assert all('adjacent_demand_cause' not in r for r in extract_economic_changes(source))

@pytest.mark.parametrize('field',['cause_span','action','cause_sha256','source_actor','paragraph_sha256'])
def test_proof_tampering_is_rejected_before_identity_creation(field):
 row,=extract_economic_changes(text());row['adjacent_demand_cause'][field]=[0,1] if field=='cause_span' else 'wrong'
 with pytest.raises(SourceShareError):observe(row,0)

@pytest.mark.parametrize('scope',[None,'RSS_TITLE_METADATA'])
def test_same_legacy_event_theme_and_history_survive_context_addition(tmp_path,scope):
 old,=extract_economic_changes(text(),include_adjacent_reductions=False);new,=extract_economic_changes(text())
 assert old['economic_driver']=='SUPPLY_CONTRACTION' and 'adjacent_demand_cause' not in old
 def observation(c):
  c=deepcopy(c)
  if scope:c['evidence_level']='REPORTED'
  r=observe(c,0)
  return economic_observation(c,**{k:v for k,v in r.items() if k not in {'change','event_id'}},content_scope=scope) if scope else r
 a,b=observation(old),observation(new);assert a['event_id']==b['event_id']
 store=ThemeStore(tmp_path/'themes');first,=store.ingest([a],now=T)
 before=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 later=T+timedelta(hours=1);latest,=store.ingest([b],now=later)
 assert latest['theme_id']==first['theme_id'] and latest['economic_driver']=='SUPPLY_CONTRACTION'
 assert latest['scores']==first['scores'] and latest['first_detected_at']==first['first_detected_at']
 assert len(store.search(now=later))==1 and store.ingest([b],now=later)==[]
 assert before==build_theme_bundle(store.search(as_of=T,now=later),decision_at=T,now=later,include_company_candidates=True)
 assert common_cause_comparisons([latest])[latest['theme_id']]['excluded_incompatible_refs']==1
 assert _source_changes(text(),old)==[old]


def test_actual_reduction_wording_and_grouped_source_scope_without_growth(tmp_path):
 store=ThemeStore(tmp_path/'theme_history');rows=[]
 for n,(scope,actor) in enumerate([('AI 서버','가상전자'),('AI 서버','새빛소재'),('모바일','빛결반도체')]):
  row,=extract_economic_changes(text(actor=actor,scope=scope,verb='감산했다'));rows.append(observe(row,n))
 themes=store.ingest(rows,now=T);assert len(themes)==2
 assert sorted(t['scores']['distinct_economic_events'] for t in themes)==[1,2]
 raw=query_comparison_export(store,as_of=T,now=T,query='가상전자')
 value=read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=T,now=T)
 assert value['comparison']['groups']==[] # Demand reduction is never borrowed as demand growth.
 products=value['product_comparisons'];assert sum(len(p['rows']) for p in products.values())==3
 assert all(s['cause']['kind']=='adjacent_demand_cause' for p in products.values() for row in p['rows'] for s in row['sources'])
 disk=fingerprint(tmp_path);assert raw==query_comparison_export(store,as_of=T,now=T,query='가상전자') and fingerprint(tmp_path)==disk
 # Mixed metadata for one event in the same batch keeps one assignment/action.
 old,=extract_economic_changes(text(),include_adjacent_reductions=False);new,=extract_economic_changes(text())
 batch=ThemeStore(tmp_path/'batch').ingest([observe(old,0),observe(new,0)],now=T)
 assert len(batch)==1 and batch[0]['scores']['distinct_economic_events']==1


def test_normal_feed_producer_consumer_and_rebinding_rejection(tmp_path):
 from test_federated_news_search import setup_workspace,collect,GOV
 from test_new_source_adapter import registry
 from scripts import run_feed_analysis as producer
 from test_feed_analysis_delivery import read,republish
 source=setup_workspace(tmp_path,'source',registry())
 collect(source,registry(),GOV,[('a',text(),'https://gov.example.org/a')],at=datetime.now(timezone.utc))
 opts=producer.parser().parse_args(['--registry',str(source.registry_path),'--state',str(source.poll_state),'--inbox-root',str(source.inbox_root),'--analysis-root',str(tmp_path/'derived'),'--limit','10'])
 code,report=producer.evaluate(opts);assert code==0
 row=read(report)['results'][0]['economic_changes'][0]
 assert row['adjacent_demand_cause']['action']=='SUPPLY_REDUCTION'
 def tamper(data):data['results'][0]['economic_changes']=[extract_economic_changes(text(actor='새빛소재'))[0]]
 with pytest.raises(SourceShareError):read(republish(report,tamper))


def test_publisher_bound_actor_and_document_proof(tmp_path,monkeypatch):
 from test_publisher_theme_events import case,events
 source=text(actor='Alpha Devices')
 info=case(tmp_path/'source',monkeypatch,line='Alpha Devices는 Beta Systems와 DRAM 공급 계약을 체결했다.\n'+source)
 row,=[r for r in events(info) if r['change'].get('adjacent_demand_cause',{}).get('action')=='SUPPLY_REDUCTION']
 assert row['company_mappings'][0]['entity_id']=='SEC_CIK:111111' and row['source_binding']['document_sha256']
 assert row['change']['economic_driver']=='DEMAND_CONTRACTION'


def test_http_search_screen_and_export_keep_same_source_claim(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store=ThemeStore(tmp_path/'theme_history');store.ingest([observe(extract_economic_changes(text(actor=a))[0],n) for n,a in enumerate(['가상전자','새빛소재'])],now=T)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return T.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**q):
  with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(q)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=T.isoformat(),since=T.isoformat()))
  assert len(data['CompanyCandidates'])==2 and data['cross_product_demand']['groups']==[]
  assert sum(c['match_kind']=='DIRECT_COMPANY' for c in data['company_search']['candidates'].values())==1
  entry=data['company_timelines']['companies'][0]['entries'][0]
  assert entry['action']=='SUPPLY_REDUCTION' and entry['cause']['cause_expression'] in text()
  exported=json.loads(fetch('/api/comparison-export',q='가상전자',as_of=T.isoformat(),since=T.isoformat()))
  tid=data['CompanyCandidates'][0]['theme_id'];assert len(exported['product_comparisons'][tid]['rows'])==2
  assert fetch('/api/themes',as_of=T.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
  data['theme']=store.search(now=T)[0];data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
  assert rendered.count('보도된 수요 감소→감산 연결')==3 and '실제 생산량·매출·손실을 독립 확인한 결과는 아닙니다.' in rendered
  assert '감소했다' in rendered and '생산을 축소했다' in rendered and '출처 가용:' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
