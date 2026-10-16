"""Synthetic recovery services; source starts never certify sales or benefit."""
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
TITLE='가상전자, '+CAUSE+' 「HBM 검사」 서비스를 개시했다'

@pytest.mark.parametrize('tail,phase,named',[
 ('「HBM 검사」 서비스를 개시했다','SOURCE_REPORTED',True),
 ('사업 「HBM 검사」 정식 개시','SOURCE_REPORTED',True),
 ('「HBM 검사」 사업 본격 시작','SOURCE_REPORTED',True),
 ('HBM 검사 서비스 개시','SOURCE_REPORTED',False),
 ('서비스 「HBM 검사」 출시','SOURCE_REPORTED',True),
 ('「HBM 검사」 서비스 개시 예정','PLANNED',True),
 ('「HBM 검사」 서비스 개시 계획','PLANNED',True),
 ('「HBM 검사」 서비스 개시 목표','PLANNED',True),
 ('「HBM 검사」 서비스를 개시한다','PLANNED',True),
 ('「HBM 검사」 서비스를 개시할 계획','PLANNED',True),
])
def test_named_service_or_function_and_phase(tail,phase,named):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['economic_driver'],c['phase'],c['entity_ids'])==('BUSINESS_START','DEMAND_RECOVERY',phase,['가상전자'])
 assert c['demand_recovery_cause']['expression_sha256']==sha256(CAUSE.encode()).hexdigest()
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']
 assert ('service_name' in c)==named
 if named:assert c['service_name']=='HBM 검사'

@pytest.mark.parametrize('text',[
 TITLE+' 보도를 부인했다',TITLE+' 취소',TITLE+' 전망',TITLE+' 가능성',
 TITLE.replace('개시했다','개시하지 않았다'),TITLE.replace('개시했다','개시를 위한 기술 소개'),
 TITLE.replace('개시했다','개시 기념행사'),TITLE+' 광고',
 TITLE.replace('서비스를','시범 서비스를'),TITLE.replace('서비스를','시험 서비스를'),
 TITLE.replace(CAUSE,'지난해 '+CAUSE),
 TITLE.replace('「HBM 검사」','지난달 「HBM 검사」'),TITLE.replace('「HBM 검사」','새빛소재는 「HBM 검사」'),
 TITLE.replace('「HBM 검사」','「DRAM 검사」'),TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 수요 회복으로 DRAM 주문 증가로'),
 '가상전자, AI 서버용 HBM 수요 회복으로 「스마트폰용 HBM 검사」 서비스 개시',
 TITLE.replace('「HBM 검사」','신규'),TITLE.replace('「HBM 검사」','AI 분석'),
 TITLE.replace('「HBM 검사」','「HBM 검사」 및 「새 검사」'),
])
def test_no_intro_plan_promotion_history_or_borrowed_service(text):
 assert not any(c['action']=='BUSINESS_START' for c in extract_economic_changes(text))


def mixed_titles():
 from test_recovery_market_entry import mixed_titles as prior
 return [TITLE,*prior()[:9],
 '별도전자, AI 서버용 HBM 수요 회복으로 「HBM 검사」 서비스 개시 계획',
 '다른소재, 스마트폰용 HBM 수요 회복으로 「HBM 검사」 서비스 개시',
 '증가전자, HBM 수요 증가로 「HBM 검사」 서비스 개시',
 '가격소재, HBM 가격 상승으로 AI 서버 시장 진출']


def test_ten_actions_common_recovery_company_evidence_and_standard(tmp_path):
 theme,args,store,report,events,first,at=source_case(tmp_path,titles=mixed_titles()[:10])
 expected={'BUSINESS_START','MARKET_ENTRY','CUSTOMER_ACQUISITION','DELIVERY_START','INVESTMENT_EXECUTION','INVESTMENT','CAPACITY_ADDITION','PRODUCTION_START','CONTRACT','SUPPLY_RESUMPTION'}
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==10
 assert {r['action'] for r in theme['source_refs']}==expected
 before=fingerprint(tmp_path);raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 c=next(c for c in data['CompanyCandidates'] if c['entity_id']=='가상전자');basis=next(b for b in c['inclusion_basis'] if b.get('action')=='BUSINESS_START')
 assert '사업·서비스 시작' in basis['reason'] and 'HBM 검사' in basis['reason'] and basis['service_name']=='HBM 검사'
 assert not c['verified_real_transaction'] and not c['verified_real_benefit']
 assert any('실제 고객·계약·매출·수혜' in u for u in c['uncertainties'])
 assert any(i['excerpt']==TITLE and i['status']=='READY' for i in company_evidence(theme,'가상전자',**args)['items'])
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert {r['supporting_source']['action'] for r in diff['events']['added']}==expected
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_scope_cause_first_and_unnamed_function(tmp_path):
 text='AI 서버용 HBM 주문 회복으로 가상전자는 「HBM 검사」 서비스 개시 목표'
 c,=extract_economic_changes(text);validate_change(c)
 assert c['entity_ids']==['가상전자'] and c['demand_scope']['destination']=='AI 서버' and c['phase']=='PLANNED'
 same,=extract_economic_changes(text.replace('「HBM 검사」','「AI 서버용 HBM 검사」'));validate_change(same)
 unnamed,=extract_economic_changes(text.replace('「HBM 검사」','HBM 검사'));assert 'service_name' not in unnamed
 themes=ThemeStore(tmp_path/'themes').ingest([claim(t,i) for i,t in enumerate(mixed_titles())],now=T+timedelta(hours=15))
 assert len(themes)==5 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,6]

@pytest.mark.parametrize('field,value',[('phase','SOURCE_REPORTED'),('entity_ids',['새빛소재']),('service_name','다른 검사')])
def test_saved_plan_actor_or_service_cannot_be_forged(tmp_path,field,value):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=source_case(tmp_path,titles=[TITLE.replace('개시했다','개시 예정'),mixed_titles()[2]])
 forged=deepcopy(report);row=next(r for r in forged['results'] if '예정' in r['headline']);row['economic_changes'][0][field]=value
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_semantic_service_keeps_literal_name_scope_and_phase():
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title=TITLE.replace('HBM 수요','AI 서버용 HBM 수요').replace('개시했다','개시 예정')
 event=dict(actors=['가상전자'],action='BUSINESS_START',phase='PLANNED',topic='HBM',driver='DEMAND_RECOVERY',quote=title,cause_quote='AI 서버용 '+CAUSE)
 c,=changes_from_events(parse_events(SimpleNamespace(claims=[json.dumps(event)]),title),sha256(title.encode()).hexdigest());validate_change(c)
 assert c['demand_scope']['destination']=='AI 서버' and c['service_name']=='HBM 검사'
 event['action']='PRODUCTION_START'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)


def test_licensed_body_and_korean_screen_search(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 고객과 매출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args);c,=report['economic_changes'];assert c['action']=='BUSINESS_START' and c['service_name']=='HBM 검사'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']
 screen=present(dict(headline='합성 자료',category=None,economic_changes=[c]),['사업·서비스 개시','수요 회복','계약 체결'])
 assert screen['label']=='사업·서비스 개시 · 출처 보도' and screen['matches']==[True,True,False] and screen['unchanged']


def test_named_plan_followup_preserves_initial_candidate_and_bytes(tmp_path):
 plan=claim(TITLE.replace('개시했다','개시 예정'),0);start=claim(TITLE,1)
 store=ThemeStore(tmp_path/'themes');first,=store.ingest([plan],now=T)
 assert first['status']=='CANDIDATE' and not first.get('event_followups')
 raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 at=T+timedelta(hours=2);latest,=store.ingest([start],now=at)
 assert latest['theme_id']==first['theme_id'] and latest['first_detected_at']==first['first_detected_at']
 assert latest['scores']['distinct_economic_events']==1
 link,=latest['event_followups'];assert link['service_name']=='HBM 검사' and not link['is_realization_confirmed']
 assert link['planned_event_id']==plan['event_id'] and link['realization_event_id']==start['event_id']
 assert store.search(as_of=T,now=at)==[first]
 assert raw==build_theme_bundle([first],decision_at=T,now=at,include_company_candidates=True)
 current=build_theme_bundle([latest],decision_at=at,now=at,include_company_candidates=True)
 assert read_theme_bundle(current,sha256(current).hexdigest(),decision_at=at,now=at)['ThemeCandidates']==[latest]

@pytest.mark.parametrize('mutation',['service','actor','topic','scope','future','unnamed'])
def test_nonmatching_service_or_time_not_linked(tmp_path,mutation):
 p=TITLE.replace('개시했다','개시 예정');s=TITLE
 if mutation=='service':s=s.replace('HBM 검사','새 검사')
 if mutation=='actor':s=s.replace('가상전자','새빛소재')
 if mutation=='topic':s=s.replace('HBM','DRAM')
 if mutation=='scope':s=s.replace(CAUSE,'AI 서버용 '+CAUSE)
 if mutation=='unnamed':p=p.replace('「HBM 검사」','HBM 검사');s=s.replace('「HBM 검사」','HBM 검사')
 plan=claim(p,0);start=claim(s,1)
 if mutation=='future':plan['source_available_at']=(T+timedelta(hours=2)).isoformat()
 themes=ThemeStore(tmp_path/'themes').ingest([plan,start],now=T+timedelta(hours=3))
 assert not any(t.get('event_followups') for t in themes)


def test_pre_recovery_service_snapshot_bytes(tmp_path):
 title=TITLE.replace('회복','증가')
 first,args,store,*_=source_case(tmp_path,titles=[title,'새빛소재, HBM 수요 증가로 생산 시작'])
 raw=build_theme_bundle([first],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 later=args['now']+timedelta(seconds=1);store.ingest([claim(TITLE,1,at=args['now'])],now=later);before=fingerprint(tmp_path)
 assert first in store.search(as_of=args['as_of'],now=later)
 assert raw==build_theme_bundle([first],decision_at=args['as_of'],now=later,include_company_candidates=True)
 assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=later)['ThemeCandidates']==[first]
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
  with urlopen(url+'/api/themes?'+urlencode({'q':'BUSINESS_START'})) as response:found=json.load(response)
  assert theme in found['ThemeCandidates']
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert any(i['status']=='READY' and i['excerpt']==TITLE for i in detail['items'])
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_recovery_forecast_is_not_a_confirmed_common_cause():
 # Preserve a source-reported service under UNKNOWN, as before this feature.
 text=TITLE.replace('회복으로','회복 예상으로')
 assert not any(c['economic_driver']=='DEMAND_RECOVERY' for c in extract_economic_changes(text))
 assert extract_economic_changes(text)==extract_economic_changes(text,include_demand_recovery=False)


def test_company_reference_cannot_substitute_service_name(tmp_path):
 theme,args,*_=source_case(tmp_path,titles=[TITLE,mixed_titles()[2]])
 forged=deepcopy(theme)
 ref=next(r for r in forged['source_refs'] if r['action']=='BUSINESS_START');ref['service_name']='다른 검사'
 assert not any(i.get('status')=='READY' and i.get('excerpt')==TITLE for i in company_evidence(forged,'가상전자',**args)['items'])
