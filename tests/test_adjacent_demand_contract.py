"""Synthetic literal demand-to-supply-contract claims; no execution certification."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation,validate_change
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.company_timeline import company_timelines,select_timelines
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.feed_analysis_delivery import _source_changes
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_scope import observe
from test_adjacent_demand import TEXT as CAPACITY
from test_theme_emergence import T
from test_federated_news_search import fingerprint


def text(product='HBM',actor='가상전자',scope='AI 서버'):
 return f'{scope+"용 " if scope else ""}{product} 수요가 증가했다. 이에 따라 {actor}는 {product} 공급계약을 체결했다.'


@pytest.mark.parametrize('product',['HBM','DRAM','NAND'])
@pytest.mark.parametrize('scope',['','AI 서버'])
def test_explicit_contract_with_exact_source_spans_and_no_invented_counterparty(product,scope):
 source=text(product=product,scope=scope);row,=extract_economic_changes(source);validate_change(row)
 proof=row['adjacent_demand_cause']
 assert (row['economic_driver'],row['action'],row['phase'])==('DEMAND_EXPANSION','CONTRACT','SOURCE_REPORTED')
 assert proof['action']=='CONTRACT' and row['entity_ids']==['가상전자']
 for part in ('cause','action'):
  start,end=proof[part+'_span'];expression=proof['source_expression'][start:end]
  assert expression==proof[part+'_expression'] and sha256(expression.encode()).hexdigest()==proof[part+'_sha256']
 assert row['source_paragraph_sha256']==proof['paragraph_sha256']==sha256(source.encode()).hexdigest()
 assert not row['verified_economic_effect'] and 'customer' not in row
 assert bool(row.get('demand_scope'))==bool(scope)


@pytest.mark.parametrize('tail',[
 '공급계약을 체결할 계획이다','공급계약을 체결할 예정이다','공급계약을 체결할 전망이다',
 '공급계약을 체결하지 않았다','공급계약을 체결하지 못했다','공급계약을 검토했다',
 '공급 협약을 체결했다','공급 의향서를 체결했다','공급계약을 체결했다고 추정했다',
 '공급계약을 체결했다는 소문이다','공급계약을 체결할 가능성이 있다',
])
def test_plans_intentions_agreements_negation_and_speculation_are_not_linked(tail):
 rows=extract_economic_changes(text().replace('공급계약을 체결했다',tail))
 assert all('adjacent_demand_cause' not in r for r in rows)


@pytest.mark.parametrize('source',[
 text().replace('. 이에','.\n이에'),text().replace('HBM 공급','DRAM 공급'),
 text().replace('가상전자','이회사'),text().replace('가상전자','가상전자와 새빛소재'),
 text().replace('가상전자','가상전자와새빛전자'),text().replace('이에 따라','한편'),
 text().replace('증가했다','지난해 증가했다'),text().replace('증가했다','증가할 전망이다'),
 text().replace('AI 서버용','AI 서버용 HBM 수요 감소와 모바일용'),
 text().replace('HBM 공급','고객알파와 HBM 공급'),
])
def test_other_paragraph_product_actor_or_competing_cause_cannot_be_borrowed(source):
 assert all('adjacent_demand_cause' not in r for r in extract_economic_changes(source))


@pytest.mark.parametrize('field',['action','action_span','cause_sha256'])
def test_proof_action_or_source_tamper_cannot_change_legacy_event_identity(field):
 row,=extract_economic_changes(text())
 row['adjacent_demand_cause'][field]=[0,1] if field=='action_span' else 'CAPACITY_ADDITION'
 with pytest.raises(SourceShareError):observe(row,0)


@pytest.mark.parametrize('scope',['RSS_TITLE_METADATA',None])
def test_legacy_unknown_contract_id_assignment_and_prior_bytes_are_preserved(tmp_path,scope):
 source=text();old,=extract_economic_changes(source,include_adjacent_contracts=False);new,=extract_economic_changes(source)
 assert old['economic_driver']=='UNKNOWN' and old['action']=='CONTRACT'
 def observation(c):
  c=deepcopy(c)
  if scope:c['evidence_level']='REPORTED'
  r=observe(c,0)
  if scope:r=economic_observation(c,**{k:v for k,v in r.items() if k not in {'event_id','change'}},content_scope=scope)
  return r
 a,b=observation(old),observation(new);assert a['event_id']==b['event_id']
 store=ThemeStore(tmp_path/'themes');first,=store.ingest([a],now=T)
 raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 later=T+timedelta(hours=1);latest,=store.ingest([b],now=later)
 assert latest['theme_id']==first['theme_id'] and latest['economic_driver']=='UNKNOWN'
 assert latest['scores']['distinct_economic_events']==1 and len(store.search(now=later))==1
 assert store.ingest([b],now=later)==[]
 assert build_theme_bundle(store.search(as_of=T,now=later),decision_at=T,now=later,include_company_candidates=True)==raw
 assert _source_changes(source,old)==[old] and _source_changes(source,new)==[new]


def test_multicompany_contract_theme_and_cross_product_comparison_reach_exact_search(tmp_path):
 store=ThemeStore(tmp_path/'themes');observations=[]
 for n,(product,actor) in enumerate([('HBM','가상전자'),('HBM','새빛소재'),('DRAM','빛결반도체')]):
  observations.append(observe(extract_economic_changes(text(product,actor))[0],n))
 themes=store.ingest(observations,now=T);disk=fingerprint(tmp_path)
 assert len(themes)==2 and sorted(t['scores']['distinct_economic_events'] for t in themes)==[1,2]
 cs=json.loads(build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True))['CompanyCandidates']
 comp=common_cause_comparisons(themes,cs);ctx=company_search_context(themes,cs)
 group,=cross_product_demand(themes,cs,comp,as_of=T)['groups'];assert group['distinct_action_groups']==3
 timeline=company_timelines(themes,cs,ctx,comp,as_of=T)
 company,=select_timelines(timeline,match_company_search(ctx,'가상전자'),'가상전자')['companies']
 entry,=company['entries'];assert entry['action']=='CONTRACT' and entry['cause']['kind']=='adjacent_demand_cause'
 assert entry['impact_paths']==[] and entry['cause']['demand_scope']['destination']=='AI 서버'
 assert all(s['company_participation']=='SOURCE_EVENT_ACTOR' for p in group['products'] for a in p['actions'] for s in a['sources'])
 assert not group['verified_real_transaction'] and not group['verified_real_benefit'] and fingerprint(tmp_path)==disk


def test_capacity_and_single_sentence_results_remain_byte_equal():
 assert extract_economic_changes(CAPACITY)==extract_economic_changes(CAPACITY,include_adjacent_contracts=False)
 row,=extract_economic_changes(CAPACITY);assert 'action' not in row['adjacent_demand_cause']
 source='가상전자, AI 서버용 HBM 수요 증가로 공급계약 체결'
 assert extract_economic_changes(source)==extract_economic_changes(source,include_adjacent_contracts=False)


@pytest.mark.parametrize('plan',[False,True])
def test_publisher_document_bound_names_and_existing_supply_plan_precedence(tmp_path,monkeypatch,plan):
 from test_publisher_theme_events import case,events
 source=text(actor='Alpha Devices')
 info=case(tmp_path/'source',monkeypatch,line='Alpha Devices는 Beta Systems와 DRAM 공급 계약을 체결했다.\n'+source,plan=plan)
 rows=events(info)
 matched=[r for r in rows if r['change']['source_paragraph_sha256']==sha256(source.encode()).hexdigest()]
 row,=matched
 assert row['source_binding']['document_sha256'] and row['company_mappings'][0]['entity_id']=='SEC_CIK:111111'
 assert row['change']['entity_ids']==['Alpha Devices']
 if plan:
  assert row['change']['phase']=='PLANNED' and row['change']['economic_driver']=='UNKNOWN'
  assert 'adjacent_demand_cause' not in row['change']
 else:assert row['change']['adjacent_demand_cause']['action']=='CONTRACT'


def test_directory_named_actor_and_duplicate_batch_preserve_identity(tmp_path):
 source=text(actor='Alpha Devices')
 new,=extract_economic_changes(source,company_names=['Alpha Devices'])
 old,=extract_economic_changes(source,company_names=['Alpha Devices'],include_adjacent_contracts=False)
 validate_change(new)
 assert observe(old,0)['event_id']==observe(new,0)['event_id']
 themes=ThemeStore(tmp_path/'themes').ingest([observe(old,0),observe(new,0)],now=T)
 assert len(themes)==1 and themes[0]['scores']['distinct_economic_events']==1


def test_normal_feed_producer_consumer_and_source_rebinding_rejection(tmp_path):
 from datetime import timezone
 from test_federated_news_search import setup_workspace,collect,GOV
 from test_new_source_adapter import registry
 from scripts import run_feed_analysis as producer
 from test_feed_analysis_delivery import read,republish
 source=setup_workspace(tmp_path,'source',registry())
 collect(source,registry(),GOV,[('a',text(),'https://gov.example.org/a')],at=datetime.now(timezone.utc))
 opts=producer.parser().parse_args(['--registry',str(source.registry_path),'--state',str(source.poll_state),'--inbox-root',str(source.inbox_root),'--analysis-root',str(tmp_path/'derived'),'--limit','10'])
 code,report=producer.evaluate(opts);assert code==0
 row=read(report)['results'][0]['economic_changes'][0]
 assert row['action']=='CONTRACT' and row['adjacent_demand_cause']['action']=='CONTRACT'
 def tamper(data):data['results'][0]['economic_changes']=[extract_economic_changes(text(actor='새빛소재'))[0]]
 with pytest.raises(SourceShareError):read(republish(report,tamper))


def test_http_contract_comparison_and_ui_keep_source_claim_uncertainty(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 observations=[observe(extract_economic_changes(text(product,actor))[0],n) for n,(product,actor) in enumerate([('HBM','가상전자'),('DRAM','새빛소재')])]
 store=ThemeStore(tmp_path/'theme_history');themes=store.ingest(observations,now=T)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return T.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=T.isoformat(),since=T.isoformat()))
  group,=data['cross_product_demand']['groups'];assert len(group['products'])==2
  assert group['period_change']['formed_in_period'] and not group['verified_real_transaction']
  assert fetch('/api/themes',as_of=T.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data['cross_product_demand']).encode()).decode()
  assert '공급계약을 체결했다' in rendered and '거래·수혜·대장주 확정이 아닙니다.' in rendered
  assert '출처 가용:' in rendered and '관측:' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
