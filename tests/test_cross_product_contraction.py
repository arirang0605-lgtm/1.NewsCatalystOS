"""Synthetic shared end-use decline, separate from growth and evidence withdrawal."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
import json,sqlite3,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation,_bytes
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_reduction import text
from test_adjacent_demand_scope import observe,text as growth
from test_cross_product_demand import case as growth_case,view
from test_cross_product_period import run,T,END,LATER
from test_federated_news_search import fingerprint


def case(tmp_path,*,sources=None):
 store=ThemeStore(tmp_path/'theme_history')
 inputs=sources or [text(),text(product='DRAM',actor='새빛소재')]
 observations=[observe(extract_economic_changes(s)[0],n) for n,s in enumerate(inputs)]
 store.ingest(observations[:1],now=T);store.ingest(observations[1:],now=END)
 themes=store.search(now=END)
 cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 return store,themes,cs,common_cause_comparisons(themes,cs),observations


def test_decline_group_pins_direct_sources_and_preserves_canonical_themes(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path);disk=fingerprint(tmp_path);old=deepcopy((themes,cs,comp))
 standard=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 group,=view(themes,cs,comp,since=END)['groups']
 assert group['economic_driver']=='DEMAND_CONTRACTION' and group['status']=='COMMON_CAUSE_HYPOTHESIS'
 assert group['distinct_action_groups']==2 and group['unresolved_company_contexts']==2
 assert group['group_id']==sha256(_bytes(['CROSS_PRODUCT_DEMAND',group['destination_key'],'DEMAND_CONTRACTION'])).hexdigest()
 assert {p['product'] for p in group['products']}=={'HBM','DRAM'}
 for p in group['products']:
  assert p['theme_status']=='CANDIDATE' and not p['invalidated_event_ids']
  assert p['theme_snapshot_sha256']==comp[p['theme_id']]['theme_snapshot_sha256']
  for a in p['actions']:
   for s in a['sources']:
    assert s['action']=='SUPPLY_REDUCTION' and s['company_participation']=='SOURCE_EVENT_ACTOR'
    assert s['source_binding'] and '감소했다' in s['cause']['source_expression']
    assert s['demand_scope']['destination']=='AI 서버' and s['in_period']==(p['product']=='DRAM')
 assert not group['verified_real_transaction'] and not group['verified_real_benefit']
 assert (themes,cs,comp)==old and disk==fingerprint(tmp_path)
 assert standard==build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)


def test_growth_current_period_and_export_bytes_remain_exactly_compatible(tmp_path):
 # SHA pins captured before this extension, from the existing public synthetic fixture.
 store,themes,cs,comp,*_=growth_case(tmp_path)
 assert sha256(_bytes(view(themes,cs,comp,since=END))).hexdigest()=='c29d8e27d4add50e8b4fe2041567a71c4ba86261a073ab402b34e0ff9e6b2fee'
 assert sha256(_bytes(run(store)[0])).hexdigest()=='d83ed870437266a7aa9d97e3fd305c0d63f57f84da787e23b1c82770c9530289'
 assert sha256(query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)).hexdigest()=='45dadccada69fc1a5d48d79bc03838c18650d823c5aa0268dc9279d2fb9b6f07'

@pytest.mark.parametrize('sources',[
 [growth(),text(product='DRAM',actor='새빛소재')],
 [text(),text(product='DRAM',actor='새빛소재',scope='모바일')],
 [text(scope='AI 서버 및 모바일'),text(product='DRAM',actor='새빛소재')],
 [text(scope=''),text(product='DRAM',actor='새빛소재')],
 [text(), '새빛소재는 DRAM 생산을 축소했다.'],
 [text(), '새빛소재, AI 서버용 DRAM 가격 하락으로 생산 축소'],
])
def test_mixed_direction_scope_general_supply_or_price_is_not_shared_demand_decline(tmp_path,sources):
 store,themes,cs,comp,*_=case(tmp_path,sources=sources)
 assert view(themes,cs,comp)['groups']==[]
 assert run(store,activity='all')[0]['groups']==[]


def test_same_destination_retains_separate_growth_and_decline_groups_in_period(tmp_path):
 store=ThemeStore(tmp_path/'theme_history')
 for at,fn,offset in [(T,growth,0),(END,text,2)]:
  store.ingest([observe(extract_economic_changes(fn(product=p,actor=a))[0],n+offset) for n,(p,a) in enumerate([('HBM','가상전자'),('DRAM','새빛소재')])],now=at)
 result,selected,_=run(store,activity='all');assert len(result['groups'])==2
 up=next(g for g in result['groups'] if 'economic_driver' not in g);down=next(g for g in result['groups'] if g.get('economic_driver')=='DEMAND_CONTRACTION')
 assert up['destination_key']==down['destination_key'] and up['group_id']!=down['group_id']
 assert not up['period_change']['formed_in_period'] and up['period_change']['new_action_group_ids']==[]
 assert down['period_change']['formed_in_period'] and down['period_change']['before']['products']==[]
 assert len(run(store)[0]['groups'])==1 and run(store)[0]['groups'][0]['economic_driver']=='DEMAND_CONTRACTION'

@pytest.mark.parametrize('fault',['candidate_sha','source_sha','future_source','relation_only','planned'])
def test_mismatched_future_relationship_or_planned_sources_cannot_add_declining_product(tmp_path,fault):
 store,themes,cs,comp,observations=case(tmp_path);tid=themes[0]['theme_id']
 if fault=='candidate_sha':next(c for c in cs if c['theme_id']==tid)['theme_snapshot_sha256']='f'*64
 elif fault=='source_sha':comp[tid]['rows'][0]['sources'][0]['evidence_sha256']='f'*64
 elif fault=='future_source':comp[tid]['rows'][0]['sources'][0]['recorded_at']=LATER.isoformat()
 elif fault=='relation_only':
  for r in comp[tid]['rows']:
   for s in r['sources']:s['company_participation']='SUPPLY_CHAIN_CONTEXT'
 else:
  change,=extract_economic_changes('가상전자는 AI 서버용 HBM 수요 감소로 반도체 생산을 축소할 계획이다.')
  assert change['phase']=='PLANNED'
  planned=observe(change,10)
  other=ThemeStore(tmp_path/'planned');themes=other.ingest([planned,observations[1]],now=END)
  cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates'];comp=common_cause_comparisons(themes,cs)
 assert view(themes,cs,comp)['groups']==[]


def test_singleton_period_formation_and_related_product_context(tmp_path):
 store,*_=case(tmp_path);result,selected,current=run(store)
 group,=result['groups'];change=group['period_change']
 assert len(selected)==1 and not current['groups'] and change['formed_in_period']
 assert change['before']['products']==['HBM'] and change['new_products']==['DRAM']
 old=next(p for p in group['products'] if p['product']=='HBM')
 assert old['context_kind']=='EXISTING_PRODUCT_CONTEXT' and not old['actions'][0]['sources'][0]['in_period']
 assert len(run(store,query='가상전자')[0]['groups'])==1
 assert run(store,query='무관한 기업')[0]['groups']==[]


def test_product_and_action_expansion_reprint_and_historical_export(tmp_path):
 store,*rest=case(tmp_path);first=query_comparison_export(store,as_of=END,since=END,now=END)
 before=build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
 rows=[observe(extract_economic_changes(text(product=p,actor=a))[0],n+10) for n,(p,a) in enumerate([('NAND','빛결반도체'),('HBM','별빛전자')])]
 reprint=deepcopy(rest[-1][0]);reprint['source_url']='https://example.org/reprint'
 store.ingest(rows+[reprint],now=LATER)
 group,=run(store,since=LATER,as_of=LATER)[0]['groups'];change=group['period_change']
 assert change['new_products']==['NAND'] and len(change['new_action_group_ids'])==2 and not change['formed_in_period']
 assert len(group['products'])==3 and group['distinct_action_groups']==4
 assert first==query_comparison_export(store,as_of=END,since=END,now=LATER)
 assert before==build_theme_bundle(store.search(as_of=END,now=LATER),decision_at=END,now=LATER,include_company_candidates=True)
 with pytest.raises(SourceShareError):read_comparison_export(first+b' ',sha256(first).hexdigest(),decision_at=LATER,now=LATER)

@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_evidence_withdrawal_or_conflict_is_distinct_from_economic_decline(tmp_path,polarity):
 store,*rest=case(tmp_path);base=rest[-1][0]
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([negative],now=LATER)
 group,=run(store,since=LATER,as_of=LATER)[0]['groups'];change=group['period_change']
 assert group['economic_driver']=='DEMAND_CONTRACTION'
 if polarity=='RETRACT':
  assert group['status']=='PERIOD_CONTEXT_ONLY' and change['removed_product_codes']==['HBM']
  removed,=group['removed_products'];assert removed['current_theme_status']=='INVALIDATED'
  assert removed['actions'][0]['sources'][0]['source_url']==base['source_url']
  assert removed['counterevidence'][0]['source_url']=='https://example.org/correction'
 else:
  assert group['status']=='COMMON_CAUSE_HYPOTHESIS' and not change['removed_product_codes']
  assert any(s['conflicting'] for p in group['products'] for a in p['actions'] for s in a['sources'])
  assert any(p['theme_status']=='WEAKENING' for p in group['products'])

@pytest.mark.parametrize('failure',['read','missing'])
def test_baseline_failure_marks_only_change_unknown_and_keeps_current(tmp_path,monkeypatch,failure):
 store,*_=case(tmp_path)
 if failure=='read':
  def broken(**kw):raise OSError('synthetic missing history')
  monkeypatch.setattr(store,'period_versions',broken)
 else:
  reprint=deepcopy(observe(extract_economic_changes(text())[0],0));reprint['source_url']='https://example.org/reprint'
  store.ingest([reprint],now=END)
  with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute('DELETE FROM versions WHERE decision_at=?',(T.isoformat(),))
 result,selected,current=run(store,activity='all');group,=result['groups']
 assert group['period_change']['status']=='UNAVAILABLE' and group['products']
 assert [p['theme_snapshot_sha256'] for p in group['products']]==[p['theme_snapshot_sha256'] for p in current['groups'][0]['products']]


def test_unresolved_identical_names_stay_separate_and_exact_search_keeps_source_scope(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path,sources=[text(actor='동명전자'),text(product='DRAM',actor='동명전자')])
 group,=view(themes,cs,comp,query='동명전자')['groups']
 assert group['unresolved_company_contexts']==2 and group['identified_company_count']==0
 assert len({a['company_key'] for p in group['products'] for a in p['actions']})==2
 assert group['search_match']=='DIRECT_COMPANY_CONTEXT'


def test_http_ui_and_pinned_export_match_decline_period_result(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,*_=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**q):
  with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(q)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='new'))
  group,=data['cross_product_demand']['groups'];assert group['economic_driver']=='DEMAND_CONTRACTION' and group['period_change']['formed_in_period']
  pin=data['comparison_export'];q={k:v for k,v in pin['query'].items() if v is not None}
  raw=fetch('/api/comparison-export',**q);assert sha256(raw).hexdigest()==pin['sha256']
  assert json.loads(raw)['comparison']==data['cross_product_demand']
  period=json.loads(fetch('/api/period',date='2026-10-15',theme_activity='all'))
  assert period['cross_product_demand']['groups'][0]['economic_driver']=='DEMAND_CONTRACTION'
  assert fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data['cross_product_demand']).encode()).decode()
  assert '복수 제품 수요 감소 공통 원인 후보' in rendered and '경제적 감소 방향과 근거 철회' in rendered
  assert '수요 증가 보도' not in rendered and '새 제품: DRAM' in rendered and '실제 생산량·매출·손실' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)


def test_removed_decline_action_retains_source_when_same_product_remains(tmp_path):
 store,*rest=case(tmp_path);base=rest[-1][0]
 extra=observe(extract_economic_changes(text(actor='별빛전자'))[0],5);store.ingest([extra],now=END)
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity='RETRACT',supersedes_event_id=base['event_id'])
 store.ingest([negative],now=LATER)
 group,=run(store,since=LATER,as_of=LATER)[0]['groups'];change=group['period_change']
 assert group['economic_driver']=='DEMAND_CONTRACTION' and group['status']=='COMMON_CAUSE_HYPOTHESIS'
 assert change['removed_product_codes']==[] and len(change['removed_action_group_ids'])==1
 old,=group['removed_action_contexts'];assert old['context_kind']=='HISTORICAL_REMOVED_ACTION'
 assert old['actions'][0]['sources'][0]['source_url']==base['source_url']
 assert old['counterevidence'][0]['source_url']=='https://example.org/correction'
