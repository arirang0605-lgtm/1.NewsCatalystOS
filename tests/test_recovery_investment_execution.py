"""Synthetic recovery-driven execution reports, never verified expenditure."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
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
from test_service_realization import claim,T
from test_federated_news_search import fingerprint
from test_research_action_labels import present

CAUSE='HBM 수요 회복으로'
TITLE='가상전자, '+CAUSE+' 신규 공장 투자 집행'

@pytest.mark.parametrize('tail,phase',[
 ('신규 공장 투자 집행','SOURCE_REPORTED'),('시설 투자를 집행했다','SOURCE_REPORTED'),
 ('HBM 설비 투자 집행','SOURCE_REPORTED'),('「청해공장」 투자 집행','SOURCE_REPORTED'),
 ('신규 공장 투자 집행 예정','PLANNED'),('시설 투자 집행 계획','PLANNED'),
 ('설비 투자 집행 목표','PLANNED'),('신규 공장 투자를 집행한다','PLANNED'),
 ('설비 투자를 집행할 계획','PLANNED'),('신규 공장 투자 집행 결정','PLANNED'),
])
def test_phase_literal_recovery_and_actor(tail,phase):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['economic_driver'],c['phase'],c['entity_ids'])==('INVESTMENT_EXECUTION','DEMAND_RECOVERY',phase,['가상전자'])
 proof=c['demand_recovery_cause'];assert proof['source_expression']==CAUSE and proof['expression_sha256']==sha256(CAUSE.encode()).hexdigest()
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']
 assert extract_economic_changes(text,include_investment_execution=False)==[]

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 보도를 부인했다',TITLE+' 취소',TITLE+' 전망',
 TITLE+' 가능성',TITLE+'을 위한 기술 소개',TITLE+'률 발표',TITLE+' 여부 확인',
 TITLE.replace('회복으로','회복 예상으로'),TITLE.replace(CAUSE,'지난해 '+CAUSE),
 TITLE.replace('신규 공장','지난달 신규 공장'),TITLE.replace('신규 공장','새빛소재는 신규 공장'),
 TITLE.replace('신규 공장','DRAM 신규 공장'),TITLE.replace('신규 공장','「DRAM 전용 공장」'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 수요 회복으로 DRAM 주문 증가로'),
 '가상전자, AI 서버용 HBM 수요 회복으로 스마트폰용 HBM 신규 공장 투자 집행',
])
def test_denial_forecast_history_intro_or_borrowed_cause_rejected(text):
 assert not any(c['action']=='INVESTMENT_EXECUTION' for c in extract_economic_changes(text))


def mixed_titles():
 return [TITLE,'새빛소재, HBM 주문 회복으로 생산능력 확대','미래장비, HBM 수요 회복으로 공급계약 체결',
 '공급소재, HBM 주문 회복으로 공급 재개','생산전자, HBM 수요 회복으로 생산 시작',
 '투자전자, HBM 주문 회복으로 신규 공장 투자 결정',
 '별도전자, AI 서버용 HBM 수요 회복으로 신규 공장 투자 집행 계획',
 '다른소재, 스마트폰용 HBM 수요 회복으로 시설 투자 집행',
 '증가전자, HBM 수요 증가로 신규 공장 투자 집행','가격소재, HBM 가격 상승으로 신규 공장 투자 집행']


def test_six_actions_source_company_period_and_v3(tmp_path):
 theme,args,store,report,events,first,at=source_case(tmp_path,titles=mixed_titles()[:6])
 expected={'INVESTMENT_EXECUTION','INVESTMENT','CAPACITY_ADDITION','PRODUCTION_START','CONTRACT','SUPPLY_RESUMPTION'}
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==6
 assert {r['action'] for r in theme['source_refs']}==expected
 before=fingerprint(tmp_path);raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 c=next(c for c in data['CompanyCandidates'] if c['entity_id']=='가상전자');basis,=c['inclusion_basis']
 assert basis['action']=='INVESTMENT_EXECUTION' and '투자 집행' in basis['reason'] and basis['demand_recovery_cause']['change']=='RECOVERY'
 assert not c['verified_real_transaction'] and not c['verified_real_benefit']
 assert any('실제 지출액·집행 완료' in u for u in c['uncertainties'])
 assert company_evidence(theme,'가상전자',**args)['items'][0]['excerpt']==TITLE
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert {r['supporting_source']['action'] for r in diff['events']['added']}==expected
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_end_use_growth_price_and_named_project_stay_distinct(tmp_path):
 themes=ThemeStore(tmp_path/'themes').ingest([claim(t,i) for i,t in enumerate(mixed_titles())],now=T+timedelta(hours=12))
 assert len(themes)==5 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,6]
 text='AI 서버용 HBM 주문 회복으로 가상전자는 「청해공장」 투자를 집행했다'
 c,=extract_economic_changes(text);validate_change(c)
 assert c['entity_ids']==['가상전자'] and c['demand_scope']['destination']=='AI 서버'
 assert c['investment_project']['project_name']=='청해공장'


def test_recovery_decision_execution_followup_preserves_first_and_bytes(tmp_path):
 decision=claim('가상전자, '+CAUSE+' 「청해공장」 투자 결정',0)
 execution=claim('가상전자, '+CAUSE+' 「청해공장」 투자 집행',1)
 store=ThemeStore(tmp_path/'themes');first,=store.ingest([decision],now=T)
 raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 later=T+timedelta(hours=2);latest,=store.ingest([execution],now=later)
 assert latest['theme_id']==first['theme_id'] and latest['first_detected_at']==first['first_detected_at']
 assert latest['scores']['distinct_economic_events']==1
 link,=latest['investment_stage_links'];assert link['project_name']=='청해공장' and not link['is_execution_confirmed']
 diff,=compare_themes(store,since=T+timedelta(seconds=1),as_of=later,now=later)['ThemeChanges']
 assert diff['investment_stage_links_added']==[link] and diff['events']['independent_actions_added']==0
 assert store.search(as_of=T,now=later)==[first]
 assert raw==build_theme_bundle([first],decision_at=T,now=later,include_company_candidates=True)

@pytest.mark.parametrize('tail',[' 계획',' 예정',' 목표'])
def test_planned_execution_does_not_link_as_reported_execution(tmp_path,tail):
 rows=[claim('가상전자, '+CAUSE+' 「청해공장」 투자 결정',0),claim('가상전자, '+CAUSE+' 「청해공장」 투자 집행'+tail,1)]
 theme,=ThemeStore(tmp_path/'themes').ingest(rows,now=T+timedelta(hours=2))
 assert not theme.get('investment_stage_links') and theme['scores']['distinct_economic_events']==2

@pytest.mark.parametrize('field,value',[('phase','SOURCE_REPORTED'),('entity_ids',['다른전자'])])
def test_saved_plan_cannot_promote_or_replace_actor(tmp_path,field,value):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=source_case(tmp_path,titles=[TITLE+' 계획',mixed_titles()[1]])
 forged=deepcopy(report);row=next(r for r in forged['results'] if '계획' in r['headline']);row['economic_changes'][0][field]=value
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_semantic_execution_keeps_scope_project_phase():
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title=TITLE.replace('HBM','AI 서버용 HBM').replace('신규 공장','「청해공장」')+' 계획'
 event=dict(actors=['가상전자'],action='INVESTMENT_EXECUTION',phase='PLANNED',topic='HBM',driver='DEMAND_RECOVERY',quote=title,cause_quote='AI 서버용 '+CAUSE)
 c,=changes_from_events(parse_events(SimpleNamespace(claims=[json.dumps(event)]),title),sha256(title.encode()).hexdigest());validate_change(c)
 assert c['phase']=='PLANNED' and c['demand_scope']['destination']=='AI 서버' and c['investment_project']['project_name']=='청해공장'
 event['action']='INVESTMENT'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)


def test_licensed_body_execution_and_screen(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 지출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args);c,=report['economic_changes'];assert c['action']=='INVESTMENT_EXECUTION'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']
 screen=present(dict(headline='합성 자료',category=None,economic_changes=[c]),['투자 집행','수요 회복','투자 결정'])
 assert screen['label']=='투자 집행 · 출처 보도' and screen['matches']==[True,True,False] and screen['unchanged']


def test_period_http_execution_search_and_source(tmp_path,monkeypatch):
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
  with urlopen(url+'/api/themes?'+urlencode({'q':'INVESTMENT_EXECUTION'})) as response:found=json.load(response)
  assert theme in found['ThemeCandidates']
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']==TITLE
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_pre_recovery_execution_snapshot_id_source_pit_bytes(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc);report=run(info,now=at);row=report['results'][0]
 old,=extract_economic_changes(TITLE,include_demand_recovery=False);old['evidence_level']='REPORTED';row['economic_changes']=[old]
 assert old['economic_driver']=='CAPACITY_EXPANSION'
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');theme,=store.ingest([observation(row,old)],now=at);raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 item,=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
  feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
 assert item['status']=='READY' and item['excerpt']==TITLE
 assert '투자 집행 근거' in json.loads(raw)['CompanyCandidates'][0]['inclusion_basis'][0]['reason']
 later=at+timedelta(seconds=1);store.ingest([claim(TITLE,1,at=at)],now=later)
 assert store.search(as_of=at,now=later)==[theme] and raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)


@pytest.mark.parametrize('replacement',[
 ('청해공장','남해공장'),('가상전자','새빛소재'),('HBM','DRAM'),
 ('수요 회복','수요 증가'),('「청해공장」','신규 공장'),
])
def test_followup_cannot_borrow_project_actor_product_or_cause(tmp_path,replacement):
 decision=claim('가상전자, '+CAUSE+' 「청해공장」 투자 결정',0)
 title=('가상전자, '+CAUSE+' 「청해공장」 투자 집행').replace(*replacement)
 themes=ThemeStore(tmp_path/'themes').ingest([decision,claim(title,1)],now=T+timedelta(hours=2))
 assert not any(t.get('investment_stage_links') for t in themes)
