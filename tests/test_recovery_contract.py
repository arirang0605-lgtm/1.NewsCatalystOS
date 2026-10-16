"""Recovery-linked reported contracts alongside independent resumption events."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from types import SimpleNamespace
import json
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import validate_change,ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_policy_company_actions import case as source_case
from test_federated_news_search import fingerprint
from test_service_realization import claim
from test_theme_emergence import T

CAUSE='HBM 수요 회복으로'
TITLE='가상전자, '+CAUSE+' 공급계약 체결'

@pytest.mark.parametrize('tail,phase',[
 ('공급계약 체결','SOURCE_REPORTED'),('납품 계약을 체결했다','SOURCE_REPORTED'),
 ('HBM 공급계약 체결','SOURCE_REPORTED'),('새빛소재와 HBM 공급계약 체결','SOURCE_REPORTED'),
 ('공급계약 체결 계획','PLANNED'),('납품계약 체결 예정','PLANNED'),
 ('공급계약 체결 목표','PLANNED'),('공급계약 체결한다','PLANNED'),('납품계약 체결 결정','PLANNED'),
])
def test_recovery_contract_literal_actor_phase_and_sha(tail,phase):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['economic_driver'],c['phase'],c['entity_ids'])==('CONTRACT','DEMAND_RECOVERY',phase,['가상전자'])
 assert c['demand_recovery_cause']['source_expression']==CAUSE and c['demand_recovery_cause']['expression_sha256']==sha256(CAUSE.encode()).hexdigest()
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 보도를 부인했다',TITLE+' 취소',
 TITLE+' 전망',TITLE+' 가능성',TITLE+'을 위한 기술 소개',TITLE.replace('회복으로','회복 예상으로'),
 TITLE.replace(CAUSE,'지난해 '+CAUSE),TITLE.replace('공급계약 체결','지난달 납품계약 체결'),
 TITLE.replace('공급계약 체결','새빛소재는 공급계약 체결'),TITLE.replace('공급계약 체결','DRAM 공급계약 체결'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 수요 회복으로 DRAM 주문 증가로'),
 '가상전자, AI 서버용 HBM 수요 회복으로 스마트폰용 HBM 공급계약 체결',
])
def test_no_unrealized_historical_or_borrowed_contract(text):
 assert not any(c['action']=='CONTRACT' and c['economic_driver']=='DEMAND_RECOVERY' for c in extract_economic_changes(text))


def mixed_titles():
 return [TITLE,'새빛소재, HBM 주문 회복으로 납품계약 체결 계획','미래장비, HBM 수요 회복으로 생산 재개',
 '다른전자, AI 서버용 HBM 수요 회복으로 공급계약 체결','별도소재, 스마트폰용 HBM 수요 회복으로 납품계약 체결',
 '증가전자, HBM 수요 증가로 공급계약 체결','가격소재, HBM 가격 상승으로 공급계약 체결']


def case(tmp_path):return source_case(tmp_path,titles=mixed_titles()[:3])


def test_contract_resumption_theme_company_sources_period_and_standard(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==3
 assert {r['action'] for r in theme['source_refs']}=={'CONTRACT','SUPPLY_RESUMPTION'}
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 for c in data['CompanyCandidates']:
  basis,=c['inclusion_basis'];assert basis['demand_recovery_cause']['change']=='RECOVERY'
  assert not c['verified_real_transaction'] and not c['verified_real_benefit']
  item,=company_evidence(theme,c['entity_id'],**args)['items'];assert item['status']=='READY' and '회복' in item['excerpt']
  if basis['action']=='CONTRACT':assert any('실제 납품·계약 이행·매출·수혜' in u for u in c['uncertainties'])
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert {r['supporting_source']['action'] for r in diff['events']['added']}=={'CONTRACT','SUPPLY_RESUMPTION'}
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_growth_price_and_end_use_separate(tmp_path):
 rows=[claim(t,i) for i,t in enumerate(mixed_titles())]
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=T+timedelta(hours=8))
 assert len(themes)==5 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,3]


def test_cause_first_and_counterparty_not_added_as_actor(tmp_path):
 title='HBM 주문 회복으로 가상전자는 새빛소재와 납품계약을 체결했다'
 c,=extract_economic_changes(title);assert c['entity_ids']==['가상전자'] and c['demand_recovery_cause']['basis']=='ORDER'
 theme,args,*_=source_case(tmp_path,titles=[title,'미래장비, HBM 수요 회복으로 공급 재개'])
 data=json.loads(build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
 assert {c['entity_id'] for c in data['CompanyCandidates']}=={'가상전자','미래장비'}
 assert company_evidence(theme,'가상전자',**args)['items'][0]['excerpt']==title


def test_resumption_then_contract_clause_source_preserved(tmp_path):
 title='가상전자는 HBM 수요 회복으로 생산을 재개했고 새빛소재는 HBM 주문 회복으로 납품계약 체결'
 theme,args,*_=source_case(tmp_path,titles=[title,'미래장비, HBM 수요 회복으로 공급 재개'])
 item,=company_evidence(theme,'새빛소재',**args)['items']
 assert item['status']=='READY' and item['excerpt']=='새빛소재는 HBM 주문 회복으로 납품계약 체결'


@pytest.mark.parametrize('field,value',[('phase','SOURCE_REPORTED'),('entity_ids',['다른전자'])])
def test_saved_plan_cannot_promote_phase_or_replace_actor(tmp_path,field,value):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=case(tmp_path);forged=deepcopy(report)
 row=next(r for r in forged['results'] if '계획' in r['headline']);row['economic_changes'][0][field]=value
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_semantic_recovery_contract_keeps_proof_scope_and_phase():
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title=TITLE.replace('HBM','AI 서버용 HBM')
 event=dict(actors=['가상전자'],action='CONTRACT',phase='SOURCE_REPORTED',topic='HBM',driver='DEMAND_RECOVERY',quote=title,cause_quote='AI 서버용 '+CAUSE)
 events=parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)
 c,=changes_from_events(events,sha256(title.encode()).hexdigest());validate_change(c)
 assert c['demand_scope']['destination']=='AI 서버' and c['demand_recovery_cause']['source_expression']==CAUSE
 event['quote']=title.replace('공급계약 체결','공급계약 체결 목표');event['phase']='SOURCE_REPORTED'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),event['quote'])


def test_licensed_body_recovery_contract(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 납품은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args);assert report['economic_changes'][0]['action']=='CONTRACT'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_period_http_mixed_recovery_contract_company_source(tmp_path,monkeypatch):
 import threading
 from datetime import datetime
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,*_=source_case(tmp_path,titles=mixed_titles())
 theme=next(t for t in store.search(as_of=args['as_of'],now=args['now']) if len(t['entity_ids'])==3)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock);monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();before=fingerprint(args['document_root']);url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert len(data['company_candidates'])==7 and len(data['themes'])==5
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'새빛소재','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and '납품계약 체결 계획' in detail['items'][0]['excerpt']
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before
