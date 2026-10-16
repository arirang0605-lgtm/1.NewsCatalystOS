"""Recovery market-entry claims: target markets do not imply demand destinations."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
from types import SimpleNamespace
import json
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.theme_changes import compare_themes
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from newscatalystos.source_share import SourceShareError
from test_policy_company_actions import case as source_case
from test_research_action_labels import present
from test_service_realization import claim,T
from test_federated_news_search import fingerprint

CAUSE='HBM 수요 회복으로'
TITLE='가상전자, '+CAUSE+' AI 서버 시장 진출'

@pytest.mark.parametrize('tail,market,phase',[
 ('AI 서버 시장 진출','AI 서버','SOURCE_REPORTED'),('일본 시장에 진출했다','일본','SOURCE_REPORTED'),
 ('유럽 시장으로 본격 진출','유럽','SOURCE_REPORTED'),('「일본 HBM」 시장 신규 진출','일본 HBM','SOURCE_REPORTED'),
 ('AI 서버 시장 진출 예정','AI 서버','PLANNED'),('일본 시장 진출 계획','일본','PLANNED'),
 ('유럽 시장 진출 목표','유럽','PLANNED'),('일본 시장에 진출한다','일본','PLANNED'),
 ('일본 시장에 진출할 계획이다','일본','PLANNED'),
])
def test_reported_market_and_phase_not_inferred_demand_scope(tail,market,phase):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['economic_driver'],c['phase'],c['entity_ids'])==('MARKET_ENTRY','DEMAND_RECOVERY',phase,['가상전자'])
 proof=c['market_entry'];assert proof['market_name']==market and proof['source_expression'] in text
 assert proof['expression_sha256']==sha256(proof['source_expression'].encode()).hexdigest()
 assert c['demand_recovery_cause']['source_expression']==CAUSE
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']
 assert 'demand_scope' not in c and extract_economic_changes(text,include_market_entry=False)==[]

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+' 보도를 부인했다',TITLE+' 취소',TITLE+' 전망',TITLE+' 가능성',TITLE+'를 위한 기술 소개',
 TITLE+' 여부 확인',TITLE.replace('회복으로','회복 예상으로'),TITLE.replace(CAUSE,'지난해 '+CAUSE),
 TITLE.replace('AI 서버 시장','지난달 일본 시장'),TITLE.replace('AI 서버 시장','새빛소재는 일본 시장'),
 TITLE.replace('AI 서버 시장','DRAM 시장'),TITLE.replace('AI 서버 시장','새빛소재 시장'),
 TITLE.replace('AI 서버 시장','신규 시장'),TITLE.replace('AI 서버 시장','일본 및 미국 시장'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 수요 회복으로 DRAM 주문 증가로'),
 '가상전자, AI 서버용 HBM 수요 회복으로 스마트폰용 HBM 시장 진출',
])
def test_denied_ambiguous_historical_or_borrowed_entry_rejected(text):
 assert not any(c['action']=='MARKET_ENTRY' for c in extract_economic_changes(text))


def mixed_titles():
 from test_recovery_customer_acquisition import mixed_titles as prior
 return [TITLE,*prior()[:8],
 '별도전자, AI 서버용 HBM 수요 회복으로 일본 시장 진출 계획',
 '다른소재, 스마트폰용 HBM 수요 회복으로 일본 시장 진출',
 '증가전자, HBM 수요 증가로 AI 서버 시장 진출',
 '가격소재, HBM 가격 상승으로 AI 서버 시장 진출']


def test_nine_actions_common_recovery_source_company_period_and_standard(tmp_path):
 theme,args,store,report,events,first,at=source_case(tmp_path,titles=mixed_titles()[:9])
 expected={'MARKET_ENTRY','CUSTOMER_ACQUISITION','DELIVERY_START','INVESTMENT_EXECUTION','INVESTMENT','CAPACITY_ADDITION','PRODUCTION_START','CONTRACT','SUPPLY_RESUMPTION'}
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==9
 assert {r['action'] for r in theme['source_refs']}==expected
 before=fingerprint(tmp_path);raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 c=next(c for c in data['CompanyCandidates'] if c['entity_id']=='가상전자');basis=next(b for b in c['inclusion_basis'] if b.get('action')=='MARKET_ENTRY')
 assert '시장 진출' in basis['reason'] and basis['market_entry']['market_name']=='AI 서버' and 'demand_scope' not in basis
 assert not c['verified_real_transaction'] and not c['verified_real_benefit']
 assert any('고객·계약·실제 판매·매출·수혜' in u for u in c['uncertainties'])
 assert any(i['excerpt']==TITLE and i['status']=='READY' for i in company_evidence(theme,'가상전자',**args)['items'])
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert {r['supporting_source']['action'] for r in diff['events']['added']}==expected
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_market_name_and_explicit_end_use_are_separate(tmp_path):
 text='AI 서버용 HBM 주문 회복으로 가상전자는 일본 시장 진출 목표'
 c,=extract_economic_changes(text);validate_change(c)
 assert c['entity_ids']==['가상전자'] and c['demand_scope']['destination']=='AI 서버'
 assert c['market_entry']['market_name']=='일본' and c['phase']=='PLANNED'
 same,=extract_economic_changes(text.replace('일본 시장','AI 서버용 HBM 시장'));validate_change(same)
 assert same['market_entry']['market_name']=='AI 서버용 HBM' and same['demand_scope']['destination']=='AI 서버'
 themes=ThemeStore(tmp_path/'themes').ingest([claim(t,i) for i,t in enumerate(mixed_titles())],now=T+timedelta(hours=14))
 assert len(themes)==5 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,6]

@pytest.mark.parametrize('field,value',[
 ('phase','SOURCE_REPORTED'),('entity_ids',['새빛소재']),
 ('market_entry',{'market_name':'미국','source_expression':'미국 시장 진출','expression_sha256':sha256('미국 시장 진출'.encode()).hexdigest()}),
])
def test_saved_plan_actor_or_market_cannot_be_forged(tmp_path,field,value):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=source_case(tmp_path,titles=[TITLE+' 계획',mixed_titles()[2]])
 forged=deepcopy(report);row=next(r for r in forged['results'] if '계획' in r['headline']);row['economic_changes'][0][field]=value
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_semantic_market_proof_and_plan():
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title='가상전자, AI 서버용 '+CAUSE+' 일본 시장 진출 계획'
 event=dict(actors=['가상전자'],action='MARKET_ENTRY',phase='PLANNED',topic='HBM',driver='DEMAND_RECOVERY',quote=title,cause_quote='AI 서버용 '+CAUSE)
 c,=changes_from_events(parse_events(SimpleNamespace(claims=[json.dumps(event)]),title),sha256(title.encode()).hexdigest());validate_change(c)
 assert c['demand_scope']['destination']=='AI 서버' and c['market_entry']['market_name']=='일본'
 event['action']='CUSTOMER_ACQUISITION'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)


def test_licensed_body_and_korean_screen_search(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 계약과 매출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args);c,=report['economic_changes'];assert c['action']=='MARKET_ENTRY'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']
 screen=present(dict(headline='합성 자료',category=None,economic_changes=[c]),['시장 진출','수요 회복','계약 체결'])
 assert screen['label']=='시장 진출 · 출처 보도' and screen['matches']==[True,True,False] and screen['unchanged']


def test_pre_recovery_market_snapshot_pit_and_bytes(tmp_path):
 title=TITLE.replace('회복','증가')
 first,args,store,*_=source_case(tmp_path,titles=[title,'새빛소재, HBM 수요 증가로 생산 시작'])
 raw=build_theme_bundle([first],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 later=args['now']+timedelta(seconds=1);store.ingest([claim(TITLE,1,at=args['now'])],now=later);before=fingerprint(tmp_path)
 assert first in store.search(as_of=args['as_of'],now=later)
 assert raw==build_theme_bundle([first],decision_at=args['as_of'],now=later,include_company_candidates=True)
 assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=later)['ThemeCandidates']==[first]
 item,=company_evidence(first,'가상전자',**{**args,'now':later})['items'];assert item['status']=='READY' and item['excerpt']==title
 assert fingerprint(tmp_path)==before


def test_period_http_search_and_company_source(tmp_path,monkeypatch):
 import threading
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,*_=source_case(tmp_path,titles=mixed_titles())
 theme=next(t for t in store.search(as_of=args['as_of'],now=args['now']) if len(t['entity_ids'])==6)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock);monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();before=fingerprint(args['document_root']);url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert len(data['company_candidates'])==10 and len(data['themes'])==5
  with urlopen(url+'/api/themes?'+urlencode({'q':'MARKET_ENTRY'})) as response:found=json.load(response)
  assert theme in found['ThemeCandidates']
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert any(i['status']=='READY' and i['excerpt']==TITLE for i in detail['items'])
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before
