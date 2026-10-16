"""Synthetic policy responses across products; no independent legal or benefit confirmation."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json,sqlite3,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,policy_cause_key
from newscatalystos.theme_emergence import ThemeStore,economic_observation,_bytes
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.cross_product_demand import cross_product_demand
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_scope import observe,text as growth
from test_cross_product_recovery import case as source_case
from test_recovery_service_comparison import case as service_case
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER
from test_federated_news_search import fingerprint


def text(product='HBM',actor='가상전자',country='미국',name='첨단칩통제법',restriction='수출 규제',change='완화',destination='',tail='생산 시작'):
 return f'{actor}, {country+" " if country else ""}{"‘"+name+"’ " if name else ""}{destination+"향 " if destination else ""}{product} {restriction} {change}로 {tail}'


def case(tmp_path,sources=None):return source_case(tmp_path,sources=sources or [text(),text(product='DRAM',actor='새빛소재')])

@pytest.mark.parametrize('restriction,change,destination',[('수출 규제','완화',''),('수출 규제','폐지',''),('생산 규제','완화',''),('수입 규제','완화',''),('수출 허가','승인',''),('생산 허가','취득',''),('수출 규제','완화','중국')])
def test_pinned_policy_production_has_own_identity_and_literal_proofs(tmp_path,restriction,change,destination):
 args=dict(restriction=restriction,change=change,destination=destination)
 store,themes,cs,comp,*_=case(tmp_path,[text(**args),text(product='DRAM',actor='새빛소재',**args)]);before=deepcopy((themes,cs,comp));disk=fingerprint(tmp_path)
 standard=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 group,=view(themes,cs,comp,since=END)['groups']
 assert group['economic_driver']=='POLICY_ENABLEMENT' and group['status']=='COMMON_CAUSE_HYPOTHESIS'
 assert 'destination_key' not in group and 'destination_expressions' not in group
 assert group['distinct_action_groups']==2 and group['source_actor_name_count']==2 and group['identified_company_count']==0
 assert group['group_id']==sha256(_bytes(['CROSS_PRODUCT_POLICY',group['policy_cause_key']])).hexdigest()
 for p in group['products']:
  assert p['theme_snapshot_sha256']==comp[p['theme_id']]['theme_snapshot_sha256']
  for a in p['actions']:
   for s in a['sources']:
    proof=s['policy_cause'];assert policy_cause_key(proof)==group['policy_cause_key']
    assert p['product'] in proof['source_expression'] and 'demand_scope' not in s
    assert proof['expression_sha256']==sha256(proof['source_expression'].encode()).hexdigest()
    assert s['action']=='PRODUCTION_START' and s['phase']=='SOURCE_REPORTED' and s['company_participation']=='SOURCE_EVENT_ACTOR'
    assert s['cause']['kind']=='policy_cause' and s['cause']['source_expression']==proof['source_expression']
    assert s['source_binding'] and s['impact_path_status']=='UNKNOWN' and s['impact_paths']==[]
 assert not group['verified_real_transaction'] and not group['verified_real_benefit']
 assert (themes,cs,comp)==before and fingerprint(tmp_path)==disk
 assert standard==build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

@pytest.mark.parametrize('other',[
 text(product='DRAM',actor='새빛소재',country='일본'),text(product='DRAM',actor='새빛소재',name='별도통제법'),
 text(product='DRAM',actor='새빛소재',restriction='수입 규제'),text(product='DRAM',actor='새빛소재',change='폐지'),
 text(product='DRAM',actor='새빛소재',destination='중국'),text(product='DRAM',actor='새빛소재',country=''),
 text(product='DRAM',actor='새빛소재',name=''),text(product='DRAM',actor='새빛소재',tail='생산 시작 계획'),
 text(product='DRAM',actor='새빛소재',tail='생산 시작 예정'),text(product='DRAM',actor='새빛소재',tail='생산 시작 전망'),
 text(product='DRAM',actor='새빛소재',tail='생산 시작 취소'),text(product='DRAM',actor='새빛소재',tail='생산 시작 보도를 부인했다'),
 text(product='DRAM',actor='그 회사'),text(product='DRAM',actor='새빛소재',tail='공급계약 체결'),
 text(product='DRAM',actor='새빛소재',tail='신규 공장 투자 결정'),growth(product='DRAM',actor='새빛소재'),
 text(product='DRAM',actor='새빛소재').replace('완화로','완화에 대비해'),
 '미국 ‘첨단칩통제법’ DRAM 수출 규제 완화로 생산 시작',
])
def test_other_policy_scopes_unclear_plans_and_other_actions_do_not_join(tmp_path,other):
 sources=[text(),other] if extract_economic_changes(other) else [text()]
 store,themes,cs,comp,*_=case(tmp_path,sources)
 assert view(themes,cs,comp)['groups']==[] and run(store,activity='all')[0]['groups']==[]

@pytest.mark.parametrize('field,value',[('name','별도통제법'),('destination','중국')])
def test_distinct_destination_or_name_groups_coexist_in_period(tmp_path,field,value):
 kw={'name':'별도통제법'} if field=='name' else {'destination':'중국'}
 store,*_=case(tmp_path,[text(),text(product='DRAM',actor='새빛소재'),text(actor='별빛전자',**kw),text(product='DRAM',actor='달빛전자',**kw)])
 groups=run(store,activity='all')[0]['groups'];assert len(groups)==2
 assert len({g['group_id'] for g in groups})==2 and all(g['distinct_action_groups']==2 for g in groups)
 assert sorted(g['period_change']['new_products'] for g in groups)==[['DRAM'],['DRAM','HBM']]

@pytest.mark.parametrize('fault',['candidate_sha','comparison_sha','future','relation','hash','borrow'])
def test_unpinned_future_related_or_invalid_policy_cannot_add_product(tmp_path,fault):
 store,themes,cs,comp,*_=case(tmp_path);tid=themes[0]['theme_id']
 if fault=='candidate_sha':next(c for c in cs if c['theme_id']==tid)['theme_snapshot_sha256']='f'*64
 elif fault=='comparison_sha':comp[tid]['theme_snapshot_sha256']='f'*64
 elif fault in {'future','relation'}:
  for r in comp[tid]['rows']:
   for s in r['sources']:
    if fault=='future':s['source_available_at']=LATER.isoformat()
    else:s['company_participation']='SUPPLY_CHAIN_CONTEXT'
 else:
  target=themes[0];ref=target['source_refs'][0]
  if fault=='hash':ref['policy_cause']['expression_sha256']='f'*64
  else:ref['policy_cause']=extract_economic_changes(text(product='HBM' if ref['topic']=='DRAM' else 'DRAM'))[0]['policy_cause']
  digest=sha256(_bytes(target)).hexdigest()
  for c in cs:
   if c['theme_id']==tid:c['theme_snapshot_sha256']=digest
  comp=common_cause_comparisons(themes,cs)
 assert view(themes,cs,comp)['groups']==[]
 assert not cross_product_demand(themes,cs,comp,as_of=END,_min_products=1)['groups'][0]['products'][0]['theme_id']==tid


def test_period_formation_expansion_reprint_and_old_pins(tmp_path):
 store,themes,*rest=case(tmp_path);old=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 group,=run(store)[0]['groups'];change=group['period_change']
 assert change['formed_in_period'] and change['before']['products']==['HBM'] and change['new_products']==['DRAM']
 assert len(change['new_action_group_ids'])==1
 assert next(p for p in group['products'] if p['product']=='HBM')['context_kind']=='EXISTING_PRODUCT_CONTEXT'
 base=rest[-1][0];reprint=deepcopy(base);reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=LATER)
 group,=run(store,since=LATER,as_of=LATER,activity='all')[0]['groups']
 assert group['period_change']['new_action_group_ids']==[] and group['period_change']['new_products']==[]
 store.ingest([observe(extract_economic_changes(text(product='NAND',actor='빛결반도체'))[0],10)],now=LATER)
 group,=run(store,since=LATER,as_of=LATER,activity='all')[0]['groups']
 assert group['period_change']['new_products']==['NAND'] and len(group['period_change']['new_action_group_ids'])==1
 assert old==build_theme_bundle(store.search(as_of=END,now=LATER),decision_at=END,now=LATER,include_company_candidates=True)

@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_counterevidence_is_not_policy_repeal_or_confirmed_loss(tmp_path,polarity):
 store,*rest=case(tmp_path);base=rest[-1][0]
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=LATER.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([negative],now=LATER);group,=run(store,since=LATER,as_of=LATER)[0]['groups']
 if polarity=='RETRACT':
  assert group['status']=='PERIOD_CONTEXT_ONLY' and group['period_change']['removed_product_codes']==['HBM']
  source=group['removed_products'][0]['actions'][0]['sources'][0];assert source['policy_cause']['policy_name']=='첨단칩통제법'
 else:assert group['status']=='COMMON_CAUSE_HYPOTHESIS' and any(s['conflicting'] for p in group['products'] for a in p['actions'] for s in a['sources'])
 assert not group['verified_real_benefit']

@pytest.mark.parametrize('failure',['read','missing'])
def test_missing_baseline_keeps_current_candidates(tmp_path,monkeypatch,failure):
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


def test_same_name_and_one_article_dont_create_resolved_independent_companies(tmp_path):
 store,themes,cs,comp,observations=case(tmp_path,[text(actor='동명전자'),text(product='DRAM',actor='동명전자')])
 group,=view(themes,cs,comp,query='동명전자')['groups']
 assert group['source_actor_name_count']==1 and group['identified_company_count']==0 and group['unresolved_company_contexts']==2
 assert group['search_match']=='DIRECT_COMPANY_CONTEXT' and run(store,query='무관 기업')[0]['groups']==[]
 # Multiple product actions in one source retain one literal actor name, no created company IDs.
 same=economic_observation(observations[1]['change'],**{k:v for k,v in observations[0].items() if k not in {'change','event_id'}})
 another=ThemeStore(tmp_path/'same-article');another.ingest([observations[0],same],now=END)
 group,=run(another,activity='all')[0]['groups'];assert group['source_actor_name_count']==1 and group['identified_company_count']==0


def test_service_only_prechange_bytes_and_export_binding(tmp_path):
 store,themes,cs,comp,*_=service_case(tmp_path)
 assert sha256(_bytes(view(themes,cs,comp,since=END))).hexdigest()=='9ffd384d9494d2aa99fb6a3932b9a47e7c6c6089ed1cf4cac04532fb1b1def84'
 assert sha256(_bytes(run(store)[0])).hexdigest()=='018b4a472e42dc1112570e0a6ab53c1f0063bad019c7d09d7e59ade9f5f79890'
 assert sha256(query_comparison_export(store,as_of=END,since=END,activity='changed',now=END)).hexdigest()=='924664838aa9af3062afb8f16eb06d5ed8a99b87f0970e334647036074e1d093'


def test_normal_feed_rejects_valid_other_policy_proof_at_same_source(tmp_path):
 from test_feed_analysis import setup,run as analysis
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 info=setup(tmp_path,text());report=analysis(info)
 source=next(r for r in report['results'] if r['economic_changes'])
 source['economic_changes'][0]['policy_cause']=extract_economic_changes(text(name='별도통제법'))[0]['policy_cause']
 with pytest.raises(SourceShareError):
  path,pin=publish_feed_analysis(report,tmp_path/'reports');consume_feed_analysis(path,path.parent,pin)


def test_http_policy_search_period_three_views_and_fixed_json(tmp_path,monkeypatch):
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
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
  group,=data['cross_product_demand']['groups'];assert group['economic_driver']=='POLICY_ENABLEMENT' and group['period_change']['formed_in_period']
  pin=data['comparison_export'];raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
  assert sha256(raw).hexdigest()==pin['sha256'] and read_comparison_export(raw,pin['sha256'],decision_at=END,now=END)['comparison']==data['cross_product_demand']
  with pytest.raises(SourceShareError):read_comparison_export(raw,'f'*64,decision_at=END,now=END)
  assert json.loads(fetch('/api/period',date='2026-10-15',theme_activity='all'))['cross_product_demand']['groups'][0]['economic_driver']=='POLICY_ENABLEMENT'
  assert fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
  data['theme']=next(t for t in store.search(now=END) if t['theme_id']==data['CompanyCandidates'][0]['theme_id']);data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
  code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input.cross_product_demand);renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
  rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
  assert rendered.count('정책 원인의 실제 생산 개시 보도')==4 # two cross-product sources + direct company in two existing views
  assert '법적 효력·이전 장벽 해소·거래·매출·수혜' in rendered and '복수 제품 동일 정책 반응 후보' in rendered
  assert '대상국: 원문 미명시' in rendered and all(s['policy_cause']['expression_sha256'] in rendered for p in group['products'] for a in p['actions'] for s in a['sources'])
 finally:server.shutdown();server.server_close();thread.join(2)


def test_known_policy_event_phase_update_is_not_new_action_or_certified_realization(tmp_path):
 store=ThemeStore(tmp_path/'theme_history')
 plan=observe(extract_economic_changes(text(tail='생산 시작 계획'))[0],0)
 start=observe(extract_economic_changes(text())[0],0)
 assert plan['event_id']==start['event_id']
 store.ingest([plan],now=T);before=store.search(now=T)
 baseline=build_theme_bundle(before,decision_at=T,now=T,include_company_candidates=True)
 other=observe(extract_economic_changes(text(product='DRAM',actor='새빛소재'))[0],1)
 store.ingest([start,other],now=END)
 group,=run(store,activity='all')[0]['groups'];change=group['period_change']
 assert change['baseline']=='RECORDED_POLICY_EVENT_CONTEXT' and len(change['new_action_group_ids'])==1
 context,=change['existing_policy_action_contexts'];assert len(context['sources'])==2
 assert {s['phase'] for s in context['sources']}=={'PLANNED','SOURCE_REPORTED'}
 assert context['action_group_id'] not in change['new_action_group_ids']
 assert context['before_snapshot']['sha256']==sha256(_bytes(before[0])).hexdigest()
 assert not any(t.get('event_followups') for t in store.search(now=END))
 assert baseline==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)


def test_policy_and_three_demand_directions_remain_separate(tmp_path):
 from test_cross_product_recovery import text as recovery
 from test_adjacent_demand_reduction import text as decline
 sources=[f(product=p,actor=a) for f in (text,growth,recovery,decline) for p,a in [('HBM','가상전자'),('DRAM','새빛소재')]]
 store,themes,cs,comp,*_=case(tmp_path,sources)
 current=view(themes,cs,comp)['groups'];period=run(store,activity='all')[0]['groups']
 assert len(current)==len(period)==4
 assert {g.get('economic_driver','DEMAND_EXPANSION') for g in period}=={'POLICY_ENABLEMENT','DEMAND_EXPANSION','DEMAND_RECOVERY','DEMAND_CONTRACTION'}
 assert len({g['group_id'] for g in period})==4
 assert all('policy_cause_key' not in g for g in period if g.get('economic_driver')!='POLICY_ENABLEMENT')
 assert not any(s.get('demand_scope') for g in period if g.get('economic_driver')=='POLICY_ENABLEMENT' for p in g['products'] for a in p['actions'] for s in a['sources'])


def test_two_explicit_destination_countries_never_join(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path,[text(destination='중국'),text(product='DRAM',actor='새빛소재',destination='일본')])
 assert view(themes,cs,comp)['groups']==[] and run(store,activity='all')[0]['groups']==[]


def test_policy_original_expression_variants_reuse_existing_key(tmp_path):
 first=text();second=text(product='DRAM',actor='새빛소재').replace('미국 ‘첨단칩통제법’','미국의 「첨단칩통제법」')
 store,themes,cs,comp,*_=case(tmp_path,[first,second]);group,=view(themes,cs,comp)['groups']
 proofs=[s['policy_cause'] for p in group['products'] for a in p['actions'] for s in a['sources']]
 assert len({p['source_expression'] for p in proofs})==2
 assert all(policy_cause_key(p)==group['policy_cause_key'] for p in proofs)



def test_legacy_policy_without_product_aliases_does_not_hide_other_themes(tmp_path):
 store,themes,cs,comp,*_=case(tmp_path)
 legacy=deepcopy(themes[0]);legacy.pop('topic_aliases');tid=legacy['theme_id']
 remaining=[legacy]+themes[1:]
 result=cross_product_demand(remaining,cs,comp,as_of=END,_min_products=1)
 assert result['status']=='READY' and all(p['theme_id']!=tid for g in result['groups'] for p in g['products'])
 assert len(result['groups'])==1
