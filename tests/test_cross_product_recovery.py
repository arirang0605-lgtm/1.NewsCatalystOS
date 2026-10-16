"""Synthetic recovery/resumption hypotheses; no volume, revenue or market certification."""
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
from test_adjacent_demand_scope import observe,text as growth
from test_adjacent_demand_reduction import text as decline
from test_cross_product_contraction import case as source_case
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER
from test_federated_news_search import fingerprint


def text(product='HBM',actor='가상전자',scope='AI 서버',basis='수요',tail='공급을 재개했다'):
 return f'{actor}, {scope+"용 " if scope else ""}{product} {basis} 회복으로 {tail}'

def case(tmp_path,**kw):return source_case(tmp_path,sources=kw.pop('sources',None) or [text(),text(product='DRAM',actor='새빛소재')])

@pytest.mark.parametrize('bases',[('수요','수요'),('주문','주문'),('수요','주문')])
def test_pinned_recovery_keeps_demand_order_proofs_and_canonical_themes(tmp_path,bases):
 store,themes,cs,comp,*_=case(tmp_path,sources=[text(basis=bases[0]),text(product='DRAM',actor='새빛소재',basis=bases[1],tail='생산을 재개했다')]);before=deepcopy((themes,cs,comp));disk=fingerprint(tmp_path)
 raw=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 group,=view(themes,cs,comp,since=END)['groups']
 assert group['economic_driver']=='DEMAND_RECOVERY' and group['status']=='COMMON_CAUSE_HYPOTHESIS'
 assert group['group_id']==sha256(_bytes(['CROSS_PRODUCT_DEMAND',group['destination_key'],'DEMAND_RECOVERY'])).hexdigest()
 assert group['distinct_action_groups']==2 and group['unresolved_company_contexts']==2
 for p in group['products']:
  assert p['theme_status']=='CANDIDATE' and not p['invalidated_event_ids']
  assert p['theme_snapshot_sha256']==comp[p['theme_id']]['theme_snapshot_sha256']
  for a in p['actions']:
   for s in a['sources']:
    proof=s['demand_recovery_cause'];assert proof['change']=='RECOVERY' and proof['product']==p['product']
    assert proof['basis']==('DEMAND' if bases[0 if p['product']=='HBM' else 1]=='수요' else 'ORDER')
    assert s['demand_scope']['source_expression'].endswith(proof['source_expression'])
    assert proof['expression_sha256']==sha256(proof['source_expression'].encode()).hexdigest()
    assert s['action']=='SUPPLY_RESUMPTION' and s['company_participation']=='SOURCE_EVENT_ACTOR' and s['source_binding']
 assert not group['verified_real_transaction'] and not group['verified_real_benefit']
 assert (themes,cs,comp)==before and disk==fingerprint(tmp_path)
 assert raw==build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)


def test_decline_bytes_and_existing_growth_pins_are_preserved(tmp_path):
 store,themes,cs,comp,*_=source_case(tmp_path)
 assert sha256(_bytes(view(themes,cs,comp,since=END))).hexdigest()=='e631f9f76e51f61167e1e64402292392390068c0fe7448877b6cc2738433bc99'
 assert sha256(_bytes(run(store)[0])).hexdigest()=='f3b3c6f21fddda59bf7a388834c8d2c50ee369d98492f8d65321aeab045edee9'
 assert sha256(query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)).hexdigest()=='33b423e911643371df21c07019ecaa8413e1792ea0765032646d55a521320a6c'

@pytest.mark.parametrize('other',[
 growth(product='DRAM',actor='새빛소재'),decline(product='DRAM',actor='새빛소재'),
 text(product='DRAM',actor='새빛소재',scope='모바일'),text(product='DRAM',actor='새빛소재',scope='AI 서버 및 모바일'),text(product='DRAM',actor='새빛소재',scope=''),
 text(product='DRAM',actor='새빛소재',tail='생산 재개 계획'),text(product='DRAM',actor='새빛소재',tail='생산 재개 결정'),text(product='DRAM',actor='새빛소재',tail='공급 재개 목표'),
 '새빛소재, DRAM 공급을 재개했다',
 '새빛소재, AI 서버용 DRAM 가격 하락으로 생산 축소',
 text(product='DRAM',actor='새빛소재',tail='생산능력을 확대했다'),
])
def test_growth_decline_plans_price_general_restart_or_other_scope_do_not_borrow_recovery(tmp_path,other):
 if other=='새빛소재, DRAM 공급을 재개했다':
  assert extract_economic_changes(other)==[] # Existing intake excludes restart without an economic cause.
  sources=[text()]
 else:sources=[text(),other]
 store,themes,cs,comp,*_=case(tmp_path,sources=sources)
 assert view(themes,cs,comp)['groups']==[] and run(store,activity='all')[0]['groups']==[]

@pytest.mark.parametrize('fault',['candidate_sha','comparison_sha','future_source','relation_only'])
def test_unpinned_future_or_relationship_context_cannot_add_product(tmp_path,fault):
 store,themes,cs,comp,*_=case(tmp_path);tid=themes[0]['theme_id']
 if fault=='candidate_sha':next(c for c in cs if c['theme_id']==tid)['theme_snapshot_sha256']='f'*64
 elif fault=='comparison_sha':comp[tid]['theme_snapshot_sha256']='f'*64
 elif fault=='future_source':comp[tid]['rows'][0]['sources'][0]['source_available_at']=LATER.isoformat()
 else:
  for row in comp[tid]['rows']:
   for source in row['sources']:source['company_participation']='SUPPLY_CHAIN_CONTEXT'
 assert view(themes,cs,comp)['groups']==[]


def test_proof_basis_must_match_same_literal_scoped_recovery(tmp_path):
 first=extract_economic_changes(text())[0]
 # Independently valid ORDER proof cannot be borrowed into a DEMAND-scoped source.
 first['demand_recovery_cause']=demand_recovery_cause('HBM 주문 회복으로')
 store=ThemeStore(tmp_path/'theme_history');store.ingest([observe(first,0),observe(extract_economic_changes(text(product='DRAM',actor='새빛소재'))[0],1)],now=END)
 assert json.loads(query_comparison_export(store,as_of=END,now=END))['comparison']['groups']==[]


def test_period_formation_extension_reprint_and_old_export(tmp_path):
 store,*rest=case(tmp_path);result,selected,current=run(store);group,=result['groups']
 assert len(selected)==1 and not current['groups'] and group['period_change']['formed_in_period']
 assert group['period_change']['before']['products']==['HBM'] and group['period_change']['new_products']==['DRAM']
 assert next(p for p in group['products'] if p['product']=='HBM')['context_kind']=='EXISTING_PRODUCT_CONTEXT'
 old=query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)
 rows=[observe(extract_economic_changes(text(product=p,actor=a,basis='주문'))[0],n+10) for n,(p,a) in enumerate([('NAND','빛결반도체'),('HBM','별빛전자')])]
 reprint=deepcopy(rest[-1][0]);reprint['source_url']='https://example.org/reprint'
 store.ingest(rows+[reprint],now=LATER);group,=run(store,since=LATER,as_of=LATER)[0]['groups'];change=group['period_change']
 assert change['new_products']==['NAND'] and len(change['new_action_group_ids'])==2 and not change['formed_in_period']
 assert group['distinct_action_groups']==4 and len(group['products'])==3
 assert old==query_comparison_export(store,as_of=END,since=END,activity='changed',now=LATER)
 with pytest.raises(SourceShareError):read_comparison_export(old+b' ',sha256(old).hexdigest(),decision_at=LATER,now=LATER)


def test_all_three_directions_coexist_at_same_destination_without_period_overwrite(tmp_path):
 store=ThemeStore(tmp_path/'theme_history')
 for fn,offset in [(growth,0),(decline,2),(text,4)]:
  store.ingest([observe(extract_economic_changes(fn(product=p,actor=a))[0],n+offset) for n,(p,a) in enumerate([('HBM','가상전자'),('DRAM','새빛소재')])],now=T if fn!=text else END)
 groups=run(store,activity='all')[0]['groups'];assert len(groups)==3
 assert len({g['group_id'] for g in groups})==3 and len({g['destination_key'] for g in groups})==1
 assert {g.get('economic_driver','DEMAND_EXPANSION') for g in groups}=={'DEMAND_EXPANSION','DEMAND_CONTRACTION','DEMAND_RECOVERY'}
 assert sum(g['period_change']['formed_in_period'] for g in groups)==1
 assert next(g for g in groups if g.get('economic_driver')=='DEMAND_RECOVERY')['period_change']['formed_in_period']

@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_economic_recovery_does_not_erase_withdrawal_or_conflict(tmp_path,polarity):
 store,*rest=case(tmp_path);base=rest[-1][0]
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([negative],now=LATER);group,=run(store,since=LATER,as_of=LATER)[0]['groups'];change=group['period_change']
 assert group['economic_driver']=='DEMAND_RECOVERY'
 if polarity=='RETRACT':
  assert group['status']=='PERIOD_CONTEXT_ONLY' and change['removed_product_codes']==['HBM']
  removed,=group['removed_products'];assert removed['current_theme_status']=='INVALIDATED'
  assert removed['actions'][0]['sources'][0]['demand_recovery_cause']['basis']=='DEMAND'
  assert removed['counterevidence'][0]['source_url']=='https://example.org/correction'
 else:
  assert group['status']=='COMMON_CAUSE_HYPOTHESIS' and not change['removed_product_codes']
  assert any(p['theme_status']=='WEAKENING' for p in group['products'])
  assert any(s['conflicting'] for p in group['products'] for a in p['actions'] for s in a['sources'])

@pytest.mark.parametrize('failure',['read','missing'])
def test_baseline_unavailable_keeps_current_recovery_and_local_unknown_change(tmp_path,monkeypatch,failure):
 store,*_=case(tmp_path)
 if failure=='read':
  def broken(**kw):raise OSError('synthetic missing history')
  monkeypatch.setattr(store,'period_versions',broken)
 else:
  reprint=deepcopy(observe(extract_economic_changes(text())[0],0));reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=END)
  with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute('DELETE FROM versions WHERE decision_at=?',(T.isoformat(),))
 result,_,current=run(store,activity='all');group,=result['groups']
 assert group['period_change']['status']=='UNAVAILABLE' and group['products']
 assert [p['theme_snapshot_sha256'] for p in group['products']]==[p['theme_snapshot_sha256'] for p in current['groups'][0]['products']]


def test_exact_search_and_unresolved_identical_names_are_not_merged(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path,sources=[text(actor='동명전자'),text(product='DRAM',actor='동명전자',basis='주문')])
 group,=view(themes,cs,comp,query='동명전자')['groups']
 assert group['search_match']=='DIRECT_COMPANY_CONTEXT' and group['unresolved_company_contexts']==2 and not group['identified_company_count']
 assert len({a['company_key'] for p in group['products'] for a in p['actions']})==2
 assert len(run(store,query='동명전자')[0]['groups'])==1 and run(store,query='무관한 기업')[0]['groups']==[]


def test_http_ui_and_export_keep_same_recovery_basis_and_period_pins(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,*_=case(tmp_path,sources=[text(),text(product='DRAM',actor='새빛소재',basis='주문')])
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**q):
  with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(q)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='new'))
  group,=data['cross_product_demand']['groups'];assert group['economic_driver']=='DEMAND_RECOVERY' and group['period_change']['formed_in_period']
  pin=data['comparison_export'];raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
  assert sha256(raw).hexdigest()==pin['sha256'] and json.loads(raw)['comparison']==data['cross_product_demand']
  period=json.loads(fetch('/api/period',date='2026-10-15',theme_activity='all'))
  assert period['cross_product_demand']['groups'][0]['economic_driver']=='DEMAND_RECOVERY'
  assert fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data['cross_product_demand']).encode()).decode()
  assert '복수 제품 수요·주문 회복 공통 원인 후보' in rendered and '회복 원문 근거: 주문' in rendered and '회복 원문 근거: 수요' in rendered
  assert '시장 전체 회복의 독립 확인이 아닙니다.' in rendered and '경제 회복과 근거의 재활성화' in rendered
  assert '수요 증가 보도' not in rendered and '새 제품: DRAM' in rendered
 finally:server.shutdown();server.server_close();thread.join(2)
