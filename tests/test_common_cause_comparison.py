"""Synthetic stored-cause comparisons, never independent benefit confirmation."""
from copy import deepcopy
from datetime import datetime,timedelta
from pathlib import Path
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.theme_company_candidates import company_candidates
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle
from test_service_realization import claim,T
from test_federated_news_search import fingerprint


def case(tmp_path):
 a=claim('가상전자, HBM 수요 회복으로 생산 재개',0)
 a['change']['extraction_method']='AI_SOURCE_SPAN_MATCHED'
 duplicate=deepcopy(a);duplicate['source_url']='https://example.org/reprint';duplicate['source_id']='reprint'
 b=claim('새빛소재, HBM 주문 회복으로 공급계약 체결 계획',1)
 store=ThemeStore(tmp_path/'theme_history');first,=store.ingest([a],now=T)
 at=T+timedelta(hours=2);theme,=store.ingest([duplicate,b],now=at)
 return theme,store,first,at


def test_two_companies_causes_actions_phases_sources_no_snapshot_or_canonical_change(tmp_path):
 theme,store,first,at=case(tmp_path);before=deepcopy(theme);disk=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 comparison=common_cause_comparisons([theme])[theme['theme_id']]
 assert comparison['distinct_action_groups']==2 and len(comparison['rows'])==2
 assert comparison['verified_real_transaction'] is comparison['verified_real_benefit'] is False
 a,b=comparison['rows'];assert (a['entity_id'],b['entity_id'])==('가상전자','새빛소재')
 assert len(a['sources'])==2 and a['distinct_event_count']==1
 assert {s['cause']['source_expression'] for s in a['sources']}=={'HBM 수요 회복으로'}
 assert {s['source_url'] for s in a['sources']}=={'https://example.org/0','https://example.org/reprint'}
 assert {s['extraction_method'] for s in a['sources']}=={'AI_SOURCE_SPAN_MATCHED'}
 assert [(s['cause']['source_expression'],s['phase'],s['action'],s['source_url']) for s in b['sources']]==[('HBM 주문 회복으로','PLANNED','CONTRACT','https://example.org/1')]
 assert theme==before and fingerprint(tmp_path)==disk
 assert raw==build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 old=common_cause_comparisons(store.search(as_of=T,now=at))[first['theme_id']]
 assert len(old['rows'])==1 and len(old['rows'][0]['sources'])==1 and old['decision_at']==first['decision_at']
 assert old['theme_snapshot_sha256']!=comparison['theme_snapshot_sha256']


def test_recorded_investment_followups_are_one_action_not_two(tmp_path):
 store=ThemeStore(tmp_path/'themes')
 decision=claim('가상전자, HBM 수요 회복으로 「청해공장」 투자 결정',0)
 execution=claim('가상전자, HBM 수요 회복으로 「청해공장」 투자 집행',1)
 store.ingest([decision],now=T);theme,=store.ingest([execution],now=T+timedelta(hours=2))
 v=common_cause_comparisons([theme])[theme['theme_id']]
 assert v['distinct_action_groups']==1
 row,=v['rows'];assert row['distinct_event_count']==2
 assert [s['action'] for s in row['sources']]==['INVESTMENT','INVESTMENT_EXECUTION']
 assert not v['verified_real_transaction']

@pytest.mark.parametrize('title,driver,expression',[
 ('증가전자, HBM 수요 증가로 생산 시작','DEMAND_EXPANSION',None),
 ('범위전자, AI 서버용 HBM 수요 증가로 생산 시작','DEMAND_EXPANSION','AI 서버용 HBM 수요 증가로'),
 ('가격전자, HBM 가격 상승으로 생산 시작','PRODUCT_PRICE_INCREASE','HBM 가격 상승으로'),
 ('하락전자, HBM 가격 하락으로 공급 축소','PRODUCT_PRICE_DECREASE','HBM 가격 하락으로'),
 ('정책전자, 미국 ‘첨단칩통제법’ HBM 수출 규제 완화로 생산 시작','POLICY_ENABLEMENT','미국 ‘첨단칩통제법’ HBM 수출 규제 완화로'),
])
def test_cause_kinds_kept_separate_and_absent_expression_not_fabricated(tmp_path,title,driver,expression):
 obs=claim(title,0);store=ThemeStore(tmp_path/'themes');theme,=store.ingest([obs],now=T)
 v=common_cause_comparisons([theme])[theme['theme_id']];assert v['economic_driver']==driver
 cause=v['rows'][0]['sources'][0]['cause'];assert cause['source_expression']==expression
 assert cause['status']==('STORED_EXPRESSION' if expression else 'SOURCE_EXPRESSION_UNAVAILABLE')


def test_no_borrow_from_other_company_or_mixed_driver_or_invalidated_event(tmp_path):
 theme,*_=case(tmp_path);refs=theme['source_refs']
 for r in refs:
  if '새빛소재' in r['entity_ids']:r.pop('demand_recovery_cause')
 v=common_cause_comparisons([theme])[theme['theme_id']]
 assert v['rows'][1]['sources'][0]['cause']['source_expression'] is None
 wrong=deepcopy(refs[0]);wrong['economic_driver']='PRODUCT_PRICE_INCREASE';wrong['source_url']='https://example.org/wrong';refs.append(wrong)
 v=common_cause_comparisons([theme])[theme['theme_id']]
 assert v['excluded_incompatible_refs']==1 and all(s['source_url']!='https://example.org/wrong' for r in v['rows'] for s in r['sources'])
 theme['invalidated_event_ids'].extend(r['event_id'] for r in refs if '가상전자' in r['entity_ids'])
 v=common_cause_comparisons([theme])[theme['theme_id']]
 assert [r['entity_id'] for r in v['rows']]==['새빛소재']


def test_wrong_stored_cause_product_or_sha_cannot_be_quoted(tmp_path):
 theme,*_=case(tmp_path)
 for r in theme['source_refs']:r['demand_recovery_cause']['expression_sha256']='f'*64
 v=common_cause_comparisons([theme])[theme['theme_id']]
 assert all(s['cause']['source_expression'] is None for row in v['rows'] for s in row['sources'])



def test_legacy_refs_without_driver_or_topic_never_invent_an_expression(tmp_path):
 theme,*_=case(tmp_path)
 for r in theme['source_refs']:
  r.pop('economic_driver');r.pop('topic');r.pop('demand_recovery_cause')
 before=deepcopy(theme)
 v=common_cause_comparisons([theme])[theme['theme_id']]
 assert len(v['rows'])==2 and v['distinct_action_groups']==2
 assert all(s['cause']['source_expression'] is None and s['economic_driver'] is None and s['topic'] is None for row in v['rows'] for s in row['sources'])
 assert theme==before


def dom(theme,candidates,comparison):
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},card=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCommonCauseComparison(card,input.theme,input.candidates,input.comparison)',{input,document,card});process.stdout.write(JSON.stringify(card));'''
 return json.loads(subprocess.check_output(['node','-e',code],input=json.dumps(dict(theme=theme,candidates=candidates,comparison=comparison)).encode()))


def test_browser_comparison_quotes_links_ai_phase_and_stale_version(tmp_path):
 theme,store,first,at=case(tmp_path);cs=company_candidates(theme);views=common_cause_comparisons([theme])
 tree=dom(theme,cs,views)
 def nodes(n):
  yield n
  for c in n.get('children',[]):yield from nodes(c)
 text=' '.join(n.get('textContent','') for n in nodes(tree))
 assert 'HBM 수요 회복으로' in text and 'HBM 주문 회복으로' in text and '계획 단계' in text
 assert 'AI 해석의 원문 근거 · 독립 사실 확인 아님' in text
 assert '출처 보도 · 독립 사실 확인 아님' in text
 groups=[c for c in tree['children'][0]['children'] if c['tag']=='div']
 assert [{n['href'] for n in nodes(g) if 'href' in n} for g in groups]==[{'https://example.org/0','https://example.org/reprint'},{'https://example.org/1'}]
 assert dom(first,company_candidates(first),views)['children']==[]
 wrong=deepcopy(views);wrong[theme['theme_id']]['theme_snapshot_sha256']='f'*64
 assert dom(theme,cs,wrong)['children']==[]
 missing=deepcopy(views)
 for row in missing[theme['theme_id']]['rows']:
  for source in row['sources']:source['cause']={'status':'SOURCE_EXPRESSION_UNAVAILABLE','source_expression':None}
 assert '원문 근거 미확인' in json.dumps(dom(theme,cs,missing),ensure_ascii=False)


def test_http_selected_query_snapshot_comparisons_and_standard_v3(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 theme,store,first,at=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(path,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{path}?'+urlencode(params)) as r:return r.read()
 try:
  p=json.loads(fetch('/api/period',date=at.astimezone(dashboard.KST).date().isoformat()))
  assert p['common_cause_comparisons']==common_cause_comparisons([theme])
  for snapshot,when in [(first,T),(theme,at)]:
   r=json.loads(fetch('/api/company-research',q='가상전자',as_of=when.isoformat()))
   assert r['common_cause_comparisons']==common_cause_comparisons([snapshot])
   from newscatalystos.catalyst_material import materials_for_store,attach_material,default_since
   materials=materials_for_store(store,since=default_since(when),as_of=when,scope='base',now=at)
   expected=attach_material([snapshot],materials)
   assert fetch('/api/themes',company_candidates='1',as_of=when.isoformat())==build_theme_bundle(expected,decision_at=when,now=at,include_company_candidates=True)
  assert json.loads(fetch('/api/company-research',q='없는기업',as_of=at.isoformat()))['common_cause_comparisons']=={}
 finally:server.shutdown();server.server_close();worker.join(2)
