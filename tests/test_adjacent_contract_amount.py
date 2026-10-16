"""Synthetic single KRW contract-total wording; source claim, never revenue."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.feed_analysis_delivery import _source_changes
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_scope import observe
from test_adjacent_demand_contract import text as plain_contract
from test_adjacent_demand import TEXT as CAPACITY
from test_theme_emergence import T
from test_federated_news_search import fingerprint


def text(amount='3000억원',product='HBM',actor='가상전자'):
 return f'AI 서버용 {product} 수요가 증가했다. 이에 따라 {actor}는 {product} {amount} 공급계약을 체결했다.'


@pytest.mark.parametrize('amount',['3000억원','3,000억원','1.5조원','150만원','100원','₩ 3000억원'])
def test_literal_single_total_preserves_decimal_whitespace_and_exact_span(amount):
 source=text(amount);row,=extract_economic_changes(source);validate_change(row)
 proof=row['adjacent_demand_cause'];money=proof['contract_amount']
 assert (row['economic_driver'],row['action'])==('DEMAND_EXPANSION','CONTRACT')
 assert money['source_expression']==amount and proof['source_expression'][money['span'][0]:money['span'][1]]==amount
 assert money['expression_sha256']==sha256(amount.encode()).hexdigest() and money['currency']=='KRW'
 assert not money['verified_real_transaction'] and not money['verified_revenue']
 assert 'value' not in money and 'percent_change' not in money


@pytest.mark.parametrize('amount',[
 '3000억원 및 2000억원','3000억원/2000억원','약 3000억원','최대 3000억원',
 '$3000억원','3000USD','30 million','0원','9999999999999999억원',
 '감액분 3000억원','투자금 3000억원','연매출 3000억원','목표 3000억원',
 '3000억원으로 감액한','3000억원 규모의 별도',
])
def test_multiple_fx_other_amount_roles_or_unclear_totals_are_not_attached(amount):
 rows=extract_economic_changes(text(amount))
 assert all('contract_amount' not in r.get('adjacent_demand_cause',{}) for r in rows)
 assert all('adjacent_demand_cause' not in r for r in rows)


@pytest.mark.parametrize('source',[
 text().replace('체결했다','체결할 계획이다'),text().replace('체결했다','체결하지 않았다'),
 text().replace('. 이에','.\n이에'),text().replace('HBM 3000','DRAM 3000'),
 text().replace('가상전자','이회사'),text().replace('가상전자','가상전자와 새빛소재'),
 text().replace('AI 서버용','연매출 2000억원, AI 서버용'),
 text().replace('증가했다','증가할 전망이다'),
])
def test_future_other_source_actor_product_and_competing_amounts_do_not_borrow(source):
 assert all('adjacent_demand_cause' not in r for r in extract_economic_changes(source))


@pytest.mark.parametrize('fault',['expression','hash','span','removed','revenue'])
def test_money_is_pinned_to_its_original_action_and_standard_source_ref(tmp_path,fault):
 row,=extract_economic_changes(text())
 if fault=='removed':row['adjacent_demand_cause'].pop('contract_amount')
 else:
  m=row['adjacent_demand_cause']['contract_amount']
  if fault=='expression':m['source_expression']='2000억원'
  elif fault=='hash':m['expression_sha256']='f'*64
  elif fault=='span':m['span']=row['adjacent_demand_cause']['cause_span']
  else:m['verified_revenue']=True
 with pytest.raises(SourceShareError):validate_change(row)
 original,=extract_economic_changes(text());theme,=ThemeStore(tmp_path/'themes').ingest([observe(original,0)],now=T)
 theme['source_refs'][0]['adjacent_demand_cause']=row['adjacent_demand_cause']
 with pytest.raises(SourceShareError):build_theme_bundle([theme],decision_at=T,now=T)


def test_legacy_contract_and_capacity_proofs_and_prior_pit_bytes_are_unchanged(tmp_path):
 old,=extract_economic_changes(text(),include_adjacent_amounts=False);new,=extract_economic_changes(text())
 assert old['economic_driver']=='UNKNOWN' and observe(old,0)['event_id']==observe(new,0)['event_id']
 assert _source_changes(text(),old)==[old] and _source_changes(text(),new)==[new]
 for source in (CAPACITY,plain_contract()):
  assert extract_economic_changes(source)==extract_economic_changes(source,include_adjacent_amounts=False)
 store=ThemeStore(tmp_path/'themes');first,=store.ingest([observe(old,0)],now=T)
 raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 at=T+timedelta(hours=1);latest,=store.ingest([observe(new,0)],now=at)
 assert latest['theme_id']==first['theme_id'] and latest['economic_driver']=='UNKNOWN'
 assert latest['scores']['distinct_economic_events']==1 and len(store.search(now=at))==1
 assert build_theme_bundle(store.search(as_of=T,now=at),decision_at=T,now=at,include_company_candidates=True)==raw


def test_multicompany_cross_product_sources_keep_separate_reported_amounts(tmp_path):
 observations=[]
 for n,(amount,product,actor) in enumerate([('3000억원','HBM','가상전자'),('2000억원','HBM','새빛소재'),('1.5조원','DRAM','빛결반도체')]):
  observations.append(observe(extract_economic_changes(text(amount,product,actor))[0],n))
 themes=ThemeStore(tmp_path/'themes').ingest(observations,now=T);disk=fingerprint(tmp_path)
 cs=json.loads(build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True))['CompanyCandidates']
 group,=cross_product_demand(themes,cs,common_cause_comparisons(themes,cs),as_of=T)['groups']
 amounts={s['cause']['contract_amount']['source_expression'] for p in group['products'] for a in p['actions'] for s in a['sources']}
 assert amounts=={'3000억원','2000억원','1.5조원'} and group['distinct_action_groups']==3
 assert not group['verified_real_benefit'] and fingerprint(tmp_path)==disk


def test_normal_feed_producer_consumer_and_rebound_amount_rejection(tmp_path):
 from datetime import timezone
 from test_federated_news_search import setup_workspace,collect,GOV
 from test_new_source_adapter import registry
 from scripts import run_feed_analysis as producer
 from test_feed_analysis_delivery import read,republish
 source=setup_workspace(tmp_path,'source',registry())
 collect(source,registry(),GOV,[('a',text(),'https://gov.example.org/a')],at=datetime.now(timezone.utc))
 opts=producer.parser().parse_args(['--registry',str(source.registry_path),'--state',str(source.poll_state),'--inbox-root',str(source.inbox_root),'--analysis-root',str(tmp_path/'derived'),'--limit','10'])
 code,report=producer.evaluate(opts);assert code==0
 row=read(report)['results'][0]
 assert row['economic_changes'][0]['adjacent_demand_cause']['contract_amount']['source_expression']=='3000억원'
 assert row['source_amount_mentions']==['3000억원']
 def tamper(data):data['results'][0]['economic_changes']=[extract_economic_changes(text('2000억원'))[0]]
 with pytest.raises(SourceShareError):read(republish(report,tamper))


def test_publisher_document_pinned_actor_and_amount(tmp_path,monkeypatch):
 from test_publisher_theme_events import case,events
 source=text(actor='Alpha Devices')
 info=case(tmp_path/'source',monkeypatch,line='Alpha Devices는 Beta Systems와 DRAM 공급 계약을 체결했다.\n'+source)
 row,=[r for r in events(info) if r['change'].get('adjacent_demand_cause',{}).get('contract_amount')]
 assert row['company_mappings'][0]['entity_id']=='SEC_CIK:111111'
 assert row['source_binding']['document_sha256']
 assert row['change']['adjacent_demand_cause']['contract_amount']['source_expression']=='3000억원'


def test_http_and_ui_show_reported_total_without_revenue_or_execution_certification(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 observations=[observe(extract_economic_changes(text('3000억원',p,a))[0],n) for n,(p,a) in enumerate([('HBM','가상전자'),('DRAM','새빛소재')])]
 store=ThemeStore(tmp_path/'theme_history');store.ingest(observations,now=T)
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
  entry=data['company_timelines']['companies'][0]['entries'][0]
  assert entry['cause']['contract_amount']['source_expression']=='3000억원'
  assert fetch('/api/themes',as_of=T.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input.cross_product_demand);renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  data['theme']=next(t for t in store.search(now=T) if t['theme_id']==data['CompanyCandidates'][0]['theme_id'])
  data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
  assert '보도된 계약 총액: 3000억원' in rendered and '실제 이행·매출·수혜 확인 아님' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
