"""Reported investment decisions are distinct from execution and spending."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
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
TITLE='가상전자, '+CAUSE+' 신규 공장 투자 결정'

@pytest.mark.parametrize('tail,phase',[
 ('신규 공장 투자 결정','SOURCE_REPORTED'),('설비 투자를 확정했다','SOURCE_REPORTED'),
 ('HBM 신규 공장 투자 결정','SOURCE_REPORTED'),('「청주P7공장」 투자 결정','SOURCE_REPORTED'),
 ('신규 공장 투자 결정 계획','PLANNED'),('시설 투자 확정 예정','PLANNED'),
 ('신규 공장 투자 결정 목표','PLANNED'),('신규 공장 투자를 결정한다','PLANNED'),
 ('신규 공장 투자를 확정할 계획','PLANNED'),
])
def test_investment_decision_phase_actor_and_recovery(tail,phase):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['economic_driver'],c['phase'],c['entity_ids'])==('INVESTMENT','DEMAND_RECOVERY',phase,['가상전자'])
 assert c['demand_recovery_cause']['source_expression']==CAUSE and c['demand_recovery_cause']['expression_sha256']==sha256(CAUSE.encode()).hexdigest()
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']
 assert ('investment_project' in c)==('청주P7공장' in text)

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 보도를 부인했다',TITLE+' 취소',TITLE+' 전망',
 TITLE+' 가능성',TITLE+'을 위한 기술 소개',TITLE.replace('회복으로','회복 예상으로'),
 TITLE.replace(CAUSE,'지난해 '+CAUSE),TITLE.replace('신규 공장','지난달 신규 공장'),
 TITLE.replace('신규 공장','새빛소재는 신규 공장'),TITLE.replace('신규 공장','DRAM 신규 공장'),
 TITLE.replace('신규 공장','「DRAM 전용 공장」'),TITLE.replace('가상전자, ','그 회사는 '),
 TITLE.replace('가상전자, ',''),TITLE.replace(CAUSE,'HBM 수요 회복으로 DRAM 주문 증가로'),
 TITLE.replace('투자 결정','투자 집행'),TITLE.replace('투자 결정','투자 집행 결정'),
 '가상전자, AI 서버용 HBM 수요 회복으로 스마트폰용 HBM 신규 공장 투자 결정',
])
def test_unrealized_historical_borrowed_or_execution_is_not_decision(text):
 assert not any(c['action']=='INVESTMENT' and c['economic_driver']=='DEMAND_RECOVERY' for c in extract_economic_changes(text))


def mixed_titles():
 return [TITLE,'새빛소재, HBM 주문 회복으로 생산능력 확대','미래장비, HBM 수요 회복으로 공급계약 체결',
 '공급소재, HBM 주문 회복으로 공급 재개','생산전자, HBM 수요 회복으로 생산 시작',
 '별도전자, AI 서버용 HBM 수요 회복으로 신규 공장 투자 결정 계획',
 '다른소재, 스마트폰용 HBM 수요 회복으로 시설 투자 확정',
 '증가전자, HBM 수요 증가로 신규 공장 투자 결정','가격소재, HBM 가격 상승으로 신규 공장 투자 결정']


def case(tmp_path):return source_case(tmp_path,titles=mixed_titles()[:5])


def test_five_actions_common_recovery_theme_company_source_and_standard(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==5
 expected={'INVESTMENT','CAPACITY_ADDITION','PRODUCTION_START','CONTRACT','SUPPLY_RESUMPTION'}
 assert {r['action'] for r in theme['source_refs']}==expected
 before=fingerprint(tmp_path);raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 c=next(c for c in data['CompanyCandidates'] if c['entity_id']=='가상전자');basis,=c['inclusion_basis']
 assert basis['action']=='INVESTMENT' and '투자 결정' in basis['reason'] and basis['demand_recovery_cause']['change']=='RECOVERY'
 assert not c['verified_real_transaction'] and not c['verified_real_benefit']
 assert any('실제 집행·지출·투자금' in u for u in c['uncertainties'])
 assert company_evidence(theme,'가상전자',**args)['items'][0]['excerpt']==TITLE
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges'];assert {r['supporting_source']['action'] for r in diff['events']['added']}==expected
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_growth_price_end_use_and_named_project_separate(tmp_path):
 rows=[claim(t,i) for i,t in enumerate(mixed_titles())]
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=T+timedelta(hours=10))
 assert len(themes)==5 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,5]
 title='AI 서버용 HBM 주문 회복으로 가상전자는 「청주P7공장」 투자를 결정했다'
 theme,args,*_=source_case(tmp_path/'named',titles=[title,mixed_titles()[1]])
 ref=next(r for r in theme['source_refs'] if r['action']=='INVESTMENT')
 assert ref['investment_project']['project_name']=='청주P7공장' and ref['demand_scope']['destination']=='AI 서버'
 assert company_evidence(theme,'가상전자',**args)['items'][0]['excerpt']==title


@pytest.mark.parametrize('field,value',[('phase','SOURCE_REPORTED'),('entity_ids',['다른전자'])])
def test_saved_investment_plan_cannot_promote_or_replace_actor(tmp_path,field,value):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=source_case(tmp_path,titles=[TITLE+' 계획',mixed_titles()[1]])
 forged=deepcopy(report);row=next(r for r in forged['results'] if '계획' in r['headline']);row['economic_changes'][0][field]=value
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_semantic_recovery_investment_keeps_proof_scope_and_project():
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title=TITLE.replace('HBM','AI 서버용 HBM').replace('신규 공장','「청주P7공장」')
 event=dict(actors=['가상전자'],action='INVESTMENT',phase='SOURCE_REPORTED',topic='HBM',driver='DEMAND_RECOVERY',quote=title,cause_quote='AI 서버용 '+CAUSE)
 c,=changes_from_events(parse_events(SimpleNamespace(claims=[json.dumps(event)]),title),sha256(title.encode()).hexdigest());validate_change(c)
 assert c['demand_scope']['destination']=='AI 서버' and c['investment_project']['project_name']=='청주P7공장'
 event['action']='INVESTMENT_EXECUTION'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)


def test_licensed_body_recovery_investment(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 지출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args);assert report['economic_changes'][0]['action']=='INVESTMENT'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_pre_recovery_investment_id_source_pit_and_bytes(tmp_path):
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
 assert '투자 근거' in json.loads(raw)['CompanyCandidates'][0]['inclusion_basis'][0]['reason']
 later=at+timedelta(seconds=1);store.ingest([claim(TITLE,1,at=at)],now=later)
 assert store.search(as_of=at,now=later)==[theme] and raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)


def test_period_http_recovery_investment_company_source(tmp_path,monkeypatch):
 import threading
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,*_=source_case(tmp_path,titles=mixed_titles())
 theme=next(t for t in store.search(as_of=args['as_of'],now=args['now']) if len(t['entity_ids'])==5)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock);monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();before=fingerprint(args['document_root']);url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert len(data['company_candidates'])==9 and len(data['themes'])==5
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']==TITLE
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before
