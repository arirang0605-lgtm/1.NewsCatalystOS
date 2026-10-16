"""Synthetic existing graph -> exact event/company impact presentation."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
from pathlib import Path
import json,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.theme_company_candidates import company_candidates
from newscatalystos.theme_emergence import _bytes
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.source_share import SourceShareError
from test_theme_supply_chain import setup,attach,observation
from test_publisher_beneficiary_delivery import publish
from test_federated_news_search import fingerprint
from test_common_cause_comparison import dom


def case(tmp_path,relation='REPORTED_DIRECT_TRANSACTION',direction='POSITIVE'):
 info,out,pub,store,original,first=setup(tmp_path,relation_kind=relation)
 if direction!='POSITIVE':_,out,pub=publish(info,tmp_path,direction=direction)
 at=info[-1]+timedelta(seconds=5);theme,=attach(store,out,pub,at)
 return theme,company_candidates(theme),store,first,at,info


def rows(theme,cs=None):return common_cause_comparisons([theme],cs)[theme['theme_id']]['rows']

@pytest.mark.parametrize('relation,direction,category',[
 ('REPORTED_DIRECT_TRANSACTION','POSITIVE','POTENTIAL_BENEFICIARY_UNVERIFIED'),
 ('REPORTED_DIRECT_TRANSACTION','NEGATIVE','POTENTIAL_DAMAGE_UNVERIFIED'),
 ('ANNOUNCED_SUPPLY_PLAN','POSITIVE','ANNOUNCED_SUPPLY_PLAN_UNVERIFIED'),
])
def test_supplier_context_and_customer_action_have_exact_roles_and_unverified_impacts(tmp_path,relation,direction,category):
 theme,cs,store,first,at,info=case(tmp_path,relation,direction)
 before=deepcopy((theme,cs));disk=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 supplier,customer=rows(theme,cs)
 assert supplier['entity_id']=='SEC_CIK:111111' and customer['entity_id']=='SEC_CIK:222222'
 a,=supplier['sources'];b,=customer['sources']
 assert a['company_participation']=='SUPPLY_CHAIN_CONTEXT' and a['event_entity_ids']==['SEC_CIK:222222']
 assert a['cause']==dict(status='COUNTERPARTY_CAUSE_NOT_ATTRIBUTED',source_expression=None)
 assert b['company_participation']=='SOURCE_EVENT_ACTOR'
 assert a['impact_path_status']==b['impact_path_status']=='LINKED'
 for source,role,other,impact in [(a,'supplier',customer,category),(b,'customer',supplier,'EFFECT_DIRECTION_UNKNOWN')]:
  path,=source['impact_paths'];assert path['role']==role and path['counterparty_id']==other['entity_id']
  assert path['event_id']==source['event_id'] and path['entity_id']!=(path['counterparty_id'])
  assert path['product_stage']=='ADVANCED_PACKAGING' and path['relation_kind']==relation
  assert path['impact_category']==impact
  assert path['source_urls']==[source['source_url']]
  assert path['linked_at']==at.isoformat() and path['source_available_at']==info[-1].isoformat()
  assert len(path['graph_sha256'])==len(path['relation_sha256'])==64
  assert not path['verified_real_transaction'] and not path['verified_real_benefit'] and path['revenue_contribution'] is None
 assert (theme,cs)==before and fingerprint(tmp_path)==disk
 assert raw==build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 assert common_cause_comparisons([theme],cs)[theme['theme_id']]['distinct_action_groups']==1
 assert rows(first)[0]['sources'][0]['impact_path_status']=='UNKNOWN'
 assert store.search(as_of=info[-1],now=at)==[first]


def test_different_event_and_company_do_not_borrow_links_or_source_urls(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path)
 # Same actor/topic, but a different source version has no pinned relationship.
 later=at+timedelta(seconds=1)
 foreign=observation(info,number=2,binding={'source_event_sha256':'f'*64,'document_sha256':'e'*64})
 other=observation(info,number=3,company='SEC_CIK:333333',binding={'source_event_sha256':'d'*64,'document_sha256':'c'*64})
 current,=store.ingest([foreign,other],now=later)
 result=rows(current)
 supplier=next(r for r in result if r['entity_id']=='SEC_CIK:111111')
 assert len(supplier['sources'])==1
 for row in result:
  for source in row['sources']:
   if source['event_id'] in {foreign['event_id'],other['event_id']}:
    assert source['impact_paths']==[] and source['impact_path_status']=='UNKNOWN'
   for path in source['impact_paths']:assert path['source_urls']==[source['source_url']] and path['event_id']==source['event_id']
 # Later candidate projections cannot lend a link to an earlier selected version.
 assert all(not source['impact_paths'] for row in rows(first,company_candidates(current)) for source in row['sources'])


def test_two_events_in_one_graph_keep_each_events_own_source_url(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path)
 another=observation(info,number=2)
 latest,=store.ingest([another],now=at+timedelta(seconds=1))
 result=rows(latest)
 assert common_cause_comparisons([latest])[latest['theme_id']]['distinct_action_groups']==2
 assert len(result)==4  # Two roles for each of the two independent actions.
 for row in result:
  for source in row['sources']:
   assert source['impact_path_status']=='LINKED'
   assert all(path['source_urls']==[source['source_url']] and path['event_id']==source['event_id'] for path in source['impact_paths'])



def test_same_event_and_url_with_another_document_cannot_borrow_graph(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path)
 altered=observation(info);altered['source_binding']={'source_event_sha256':'f'*64,'document_sha256':'e'*64}
 latest,=store.ingest([altered],now=at+timedelta(seconds=1))
 result=rows(latest)
 supplier=next(r for r in result if r['entity_id']=='SEC_CIK:111111')
 customer=next(r for r in result if r['entity_id']=='SEC_CIK:222222')
 assert len(supplier['sources'])==1
 assert sorted(s['impact_path_status'] for s in customer['sources'])==['LINKED','UNKNOWN']
 assert all(not s['impact_paths'] for s in customer['sources'] if s.get('source_binding')==altered['source_binding'])


@pytest.mark.parametrize('fault',['snapshot','decision','entity','basis','projection'])
def test_stale_or_mismatched_candidate_cannot_lend_a_path(tmp_path,fault):
 theme,cs,*_=case(tmp_path)
 for c in cs:
  if fault=='snapshot':c['theme_snapshot_sha256']='f'*64
  if fault=='decision':c['decision_at']='2099-01-01T00:00:00+00:00'
  if fault=='entity':c['entity_id']='SEC_CIK:999999'
  if fault=='basis':c['inclusion_basis']=[]
  if fault=='projection':c['benefit_paths']=[]
 assert all(not s['impact_paths'] for row in rows(theme,cs) for s in row['sources'])


@pytest.mark.parametrize('fault',['counterparty','future'])
def test_forged_link_or_future_relationship_is_not_a_presentation_input(tmp_path,fault):
 theme,cs,*_=case(tmp_path)
 link=theme['company_links'][0]['supply_chain_links'][0]
 if fault=='counterparty':link['counterparty_id']='SEC_CIK:999999'
 else:link['linked_at']='2099-01-01T00:00:00+00:00'
 with pytest.raises(SourceShareError):rows(theme,cs)


def test_browser_renders_role_plan_hypothesis_proof_and_missing_path(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path,relation='ANNOUNCED_SUPPLY_PLAN')
 tree=dom(theme,cs,common_cause_comparisons([theme],cs))
 text=json.dumps(tree,ensure_ascii=False)
 assert '발표된 공급 계획' in text and '계획 단계 · 실현 미확인' in text
 assert '첨단 패키징 · 공급자 · 상대 기업 SEC_CIK:222222' in text
 assert '첨단 패키징 · 고객 · 상대 기업 SEC_CIK:111111' in text
 assert '독립 확인된 실거래·매출 기여·수혜 아님' in text
 assert '이 기업의 직접 행동 확인 아님' in text and '관계 출처 가용:' in text and '원본 그래프 SHA:' in text
 old=dom(first,company_candidates(first),common_cause_comparisons([first]))
 assert '분석상 테마 연관 · 영향 경로 미확인' in json.dumps(old,ensure_ascii=False)


def test_http_period_and_research_receive_same_paths_while_v3_bytes_stay_exact(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 from newscatalystos.theme_emergence import ThemeStore
 theme,cs,store,first,at,info=case(tmp_path)
 docs=tmp_path/'documents';docs.mkdir();store.root.rename(docs/'theme_history')
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  period=json.loads(fetch('/api/period',date=at.astimezone(dashboard.KST).date().isoformat()))
  research=json.loads(fetch('/api/company-research',q='SEC_CIK:111111',as_of=at.isoformat()))
  expected=common_cause_comparisons([theme],cs)
  assert period['common_cause_comparisons']==research['common_cause_comparisons']==expected
  for snapshot,when in [(first,info[-1]),(theme,at)]:
   assert fetch('/api/themes',as_of=when.isoformat(),company_candidates='1')==build_theme_bundle([snapshot],decision_at=when,now=at,include_company_candidates=True)
 finally:server.shutdown();server.server_close();worker.join(2)
