"""Synthetic reported production starts, distinct from expansion and commercial delivery."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json,sqlite3,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,demand_recovery_cause
from newscatalystos.theme_emergence import ThemeStore,economic_observation,_bytes
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.source_share import SourceShareError
from test_cross_product_recovery import case as recovery_case,text as recovery
from test_recovery_contract_comparison import text as contract
from test_recovery_delivery_comparison import case as delivery_case,text as delivery
from test_adjacent_demand_scope import observe,text as growth
from test_adjacent_demand_reduction import text as decline
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER
from test_federated_news_search import fingerprint


def text(product='HBM',actor='가상전자',scope='AI 서버',basis='수요',tail='생산을 시작했다'):
 return recovery(product,actor,scope,basis,tail)

def case(tmp_path,sources=None):return recovery_case(tmp_path,sources=sources or [text(),text(product='DRAM',actor='새빛소재',basis='주문')])

@pytest.mark.parametrize('tail',['생산을 시작했다','양산을 개시했다','공급계약을 체결했다','공급을 재개했다','납품을 시작했다'])
def test_actual_production_or_mixed_contract_resumption_delivery_keep_source_stages_and_proofs(tmp_path,tail):
 store,themes,cs,comp,*_=case(tmp_path,[text(),text(product='DRAM',actor='새빛소재',basis='주문',tail=tail)]);before=deepcopy((themes,cs,comp));disk=fingerprint(tmp_path)
 standard=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 group,=view(themes,cs,comp,since=END)['groups']
 assert group['economic_driver']=='DEMAND_RECOVERY' and group['status']=='COMMON_CAUSE_HYPOTHESIS'
 assert group['distinct_action_groups']==2 and group['unresolved_company_contexts']==2
 assert {p['product'] for p in group['products']}=={'HBM','DRAM'}
 for p in group['products']:
  assert p['theme_snapshot_sha256']==comp[p['theme_id']]['theme_snapshot_sha256']
  for a in p['actions']:
   for s in a['sources']:
    proof=s['demand_recovery_cause'];assert proof['basis']==('DEMAND' if p['product']=='HBM' else 'ORDER')
    assert proof['expression_sha256']==sha256(proof['source_expression'].encode()).hexdigest()
    assert s['action']==({'공급을 재개했다':'SUPPLY_RESUMPTION','공급계약을 체결했다':'CONTRACT','납품을 시작했다':'DELIVERY_START'}.get(tail,'PRODUCTION_START') if p['product']=='DRAM' else 'PRODUCTION_START')
    assert s['phase']=='SOURCE_REPORTED' and s['company_participation']=='SOURCE_EVENT_ACTOR' and s['source_binding']
    assert not s.get('verified_revenue',False) and not s.get('delivery_confirmed',False)
 assert not group['verified_real_transaction'] and not group['verified_real_benefit']
 assert (themes,cs,comp)==before and fingerprint(tmp_path)==disk
 assert standard==build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)


def test_recovery_delivery_only_current_period_and_export_bytes_are_preserved(tmp_path):
 store,themes,cs,comp,*_=delivery_case(tmp_path)
 assert sha256(_bytes(view(themes,cs,comp,since=END))).hexdigest()=='c525cda73dd1965486d1de5b84dc5641e2c2e435baf7017a768b2220a356b59b'
 assert sha256(_bytes(run(store)[0])).hexdigest()=='57646a39263e562360f9c8f537a3d382c51d6af88f16d7b1537c1ef7921f0e87'
 assert sha256(query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)).hexdigest()=='4b3a96f03b7523fb31461fabe27bf37e860f1ecd8acbcbba727c0cde4bdb7f8b'

@pytest.mark.parametrize('other',[
 text(product='DRAM',actor='새빛소재',tail='생산 개시 계획'),text(product='DRAM',actor='새빛소재',tail='양산 개시 목표'),
 text(product='DRAM',actor='새빛소재',tail='생산 개시 결정'),text(product='DRAM',actor='새빛소재',tail='생산을 시작하지 않았다'),
 text(product='DRAM',actor='새빛소재',tail='생산 개시 의향'),text(product='DRAM',actor='새빛소재',tail='양산 개시 의향'),
 text(product='DRAM',actor='새빛소재',tail='생산 개시 취소'),text(product='DRAM',actor='새빛소재',tail='생산 개시 전망'),
 text(product='DRAM',actor='그 회사'),text(product='DRAM',actor='새빛소재',scope='모바일'),text(product='DRAM',actor='새빛소재',scope='AI 서버 및 모바일'),
 growth(product='DRAM',actor='새빛소재'),decline(product='DRAM',actor='새빛소재'),
 '새빛소재, AI 서버용 DRAM 가격 하락으로 생산 축소',
 '새빛소재, DRAM 생산 개시',text(product='DRAM',actor='새빛소재',tail='생산능력을 확대했다'),
])
def test_plans_intentions_denials_other_drivers_scopes_or_unclear_actors_do_not_join_actual_production(tmp_path,other):
 rows=extract_economic_changes(other)
 sources=[text(),other] if rows else [text()]
 store,themes,cs,comp,*_=case(tmp_path,sources)
 assert view(themes,cs,comp)['groups']==[] and run(store,activity='all')[0]['groups']==[]

@pytest.mark.parametrize('fault',['candidate_sha','comparison_sha','future_source','relation_only','proof_basis'])
def test_unpinned_future_relation_or_borrowed_proof_cannot_add_production_product(tmp_path,fault):
 store,themes,cs,comp,*_=case(tmp_path);tid=themes[0]['theme_id']
 if fault=='candidate_sha':next(c for c in cs if c['theme_id']==tid)['theme_snapshot_sha256']='f'*64
 elif fault=='comparison_sha':comp[tid]['theme_snapshot_sha256']='f'*64
 elif fault=='future_source':comp[tid]['rows'][0]['sources'][0]['recorded_at']=LATER.isoformat()
 elif fault=='relation_only':
  for row in comp[tid]['rows']:
   for source in row['sources']:source['company_participation']='SUPPLY_CHAIN_CONTEXT'
 else:
  first=extract_economic_changes(text())[0];first['demand_recovery_cause']=demand_recovery_cause('HBM 주문 회복으로')
  other=ThemeStore(tmp_path/'borrowed');other.ingest([observe(first,0),observe(extract_economic_changes(text(product='DRAM',actor='새빛소재'))[0],1)],now=END)
  assert json.loads(query_comparison_export(other,as_of=END,now=END))['comparison']['groups']==[];return
 assert view(themes,cs,comp)['groups']==[]


def test_period_formation_and_production_addition_keep_old_snapshot_and_no_reprint_growth(tmp_path):
 store,*rest=case(tmp_path,[recovery(),text(product='DRAM',actor='새빛소재')])
 result,selected,current=run(store);group,=result['groups'];change=group['period_change']
 assert len(selected)==1 and not current['groups'] and change['formed_in_period'] and change['new_products']==['DRAM']
 assert change['before']['products']==['HBM'] and next(p for p in group['products'] if p['product']=='HBM')['context_kind']=='EXISTING_PRODUCT_CONTEXT'
 old=query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)
 rows=[observe(extract_economic_changes(text(product=p,actor=a))[0],n+10) for n,(p,a) in enumerate([('NAND','빛결반도체'),('HBM','별빛전자')])]
 reprint=deepcopy(rest[-1][1]);reprint['source_url']='https://example.org/reprint'
 store.ingest(rows+[reprint],now=LATER);group,=run(store,since=LATER,as_of=LATER)[0]['groups'];change=group['period_change']
 assert change['new_products']==['NAND'] and len(change['new_action_group_ids'])==2 and not change['formed_in_period']
 assert group['distinct_action_groups']==4 and len(group['products'])==3
 assert old==query_comparison_export(store,as_of=END,since=END,activity='changed',now=LATER)
 with pytest.raises(SourceShareError):read_comparison_export(old+b' ',sha256(old).hexdigest(),decision_at=LATER,now=LATER)

@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_production_evidence_withdrawal_or_conflict_preserves_original_sources(tmp_path,polarity):
 store,*rest=case(tmp_path);base=rest[-1][0]
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([negative],now=LATER);group,=run(store,since=LATER,as_of=LATER)[0]['groups'];change=group['period_change']
 if polarity=='RETRACT':
  assert group['status']=='PERIOD_CONTEXT_ONLY' and change['removed_product_codes']==['HBM']
  old,=group['removed_products'];assert old['actions'][0]['sources'][0]['action']=='PRODUCTION_START'
  assert old['actions'][0]['sources'][0]['source_url']==base['source_url'] and old['current_theme_status']=='INVALIDATED'
  assert old['counterevidence'][0]['source_url']=='https://example.org/correction'
 else:
  assert group['status']=='COMMON_CAUSE_HYPOTHESIS' and not change['removed_product_codes']
  assert any(s['conflicting'] for p in group['products'] for a in p['actions'] for s in a['sources'])

@pytest.mark.parametrize('failure',['read','missing'])
def test_baseline_failure_keeps_current_production_candidates_and_only_unknown_change(tmp_path,monkeypatch,failure):
 store,*_=case(tmp_path)
 if failure=='read':
  def broken(**kw):raise OSError('synthetic unavailable history')
  monkeypatch.setattr(store,'period_versions',broken)
 else:
  reprint=deepcopy(observe(extract_economic_changes(text())[0],0));reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=END)
  with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute('DELETE FROM versions WHERE decision_at=?',(T.isoformat(),))
 result,_,current=run(store,activity='all');group,=result['groups']
 assert group['period_change']['status']=='UNAVAILABLE' and group['products']
 assert [p['theme_snapshot_sha256'] for p in group['products']]==[p['theme_snapshot_sha256'] for p in current['groups'][0]['products']]


def test_same_name_contexts_exact_search_and_metadata_variants_do_not_merge_or_count_new_actions(tmp_path):
 store,themes,cs,comp,observations=case(tmp_path,[text(actor='동명전자'),text(product='DRAM',actor='동명전자')])
 group,=view(themes,cs,comp,query='동명전자')['groups']
 assert group['identified_company_count']==0 and group['unresolved_company_contexts']==2 and group['search_match']=='DIRECT_COMPANY_CONTEXT'
 assert len({a['company_key'] for p in group['products'] for a in p['actions']})==2
 assert run(store,query='무관 기업')[0]['groups']==[]
 store.ingest(observations,now=LATER);assert store.ingest(observations,now=LATER)==[]
 assert run(store,since=LATER,as_of=LATER,activity='all')[0]['groups'][0]['period_change']['new_action_group_ids']==[]


def test_http_three_views_and_fixed_export_separate_production_from_other_three_stages(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,*_=case(tmp_path,[text(),delivery(product='DRAM',actor='새빛소재',basis='주문'),contract(product='NAND',actor='빛결반도체'),recovery(product='HBM',actor='별빛전자')])
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**q):
  with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(q)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
  group,=data['cross_product_demand']['groups'];assert group['economic_driver']=='DEMAND_RECOVERY' and group['period_change']['formed_in_period']
  assert {s['action'] for p in group['products'] for a in p['actions'] for s in a['sources']}=={'PRODUCTION_START','CONTRACT','SUPPLY_RESUMPTION','DELIVERY_START'}
  pin=data['comparison_export'];raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
  assert sha256(raw).hexdigest()==pin['sha256'] and json.loads(raw)['comparison']==data['cross_product_demand']
  assert json.loads(fetch('/api/period',date='2026-10-15',theme_activity='all'))['cross_product_demand']['groups'][0]['economic_driver']=='DEMAND_RECOVERY'
  assert fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
  data['theme']=next(t for t in store.search(now=END) if t['theme_id']==data['CompanyCandidates'][0]['theme_id']);data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input.cross_product_demand);renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
  assert rendered.count('회복 원인의 생산·양산 개시 보도')==3
  assert '생산능력·물량·상업 납품·매출·수혜 확인이 아닙니다.' in rendered and '회복 원문 근거: 주문' in rendered
  assert '생산 개시·체결·재개·납품 근거를 단계별로 비교한 가설' in rendered and '생산·공급 재개' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
