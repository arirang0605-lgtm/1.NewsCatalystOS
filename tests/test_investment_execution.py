"""Reported investment execution is distinct from decisions and planned execution."""
from datetime import datetime,timezone
from hashlib import sha256
import json,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import economic_observation,ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from test_new_source_adapter import NOW
from test_policy_company_actions import case as policy_case
from test_federated_news_search import fingerprint
from test_research_action_labels import present

CAUSE='미국의 「첨단칩통제법」 중국향 HBM 수출 규제 완화로'
TITLE='가상전자, HBM 수요 증가로 신규 공장 투자 집행'

@pytest.mark.parametrize('text,phase,driver',[
 (TITLE,'SOURCE_REPORTED','DEMAND_EXPANSION'),
 (TITLE.replace('수요','주문'),'SOURCE_REPORTED','DEMAND_EXPANSION'),
 (TITLE.replace('HBM 수요 증가로',CAUSE),'SOURCE_REPORTED','POLICY_ENABLEMENT'),
 (CAUSE+' 가상전자는 신규 공장 투자 집행','SOURCE_REPORTED','POLICY_ENABLEMENT'),
 (TITLE+' 예정','PLANNED','DEMAND_EXPANSION'),
 (TITLE+' 계획','PLANNED','DEMAND_EXPANSION'),
 (TITLE+' 검토','PLANNED','DEMAND_EXPANSION'),
 (TITLE.replace('증가로','증가에 대비해'),'PLANNED','DEMAND_EXPANSION'),
 ('가상전자, HBM 설비 투자를 집행했다','SOURCE_REPORTED','CAPACITY_EXPANSION'),
])
def test_execution_action_and_stage(text,phase,driver):
 row,=extract_economic_changes(text)
 assert (row['action'],row['phase'],row['economic_driver'],row['entity_ids'])==('INVESTMENT_EXECUTION',phase,driver,['가상전자'])
 assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
 assert not row['verified_economic_effect']
 economic_observation(row,origin_reference='https://gov.example.org/1',source_url='https://gov.example.org/1',source_id='synthetic',source_available_at=NOW.isoformat())

@pytest.mark.parametrize('text',[
 TITLE+' 취소',TITLE+' 보도를 부인했다',TITLE+' 보류',TITLE+' 중단',TITLE+' 지연',
 TITLE+' 전망',TITLE.replace('집행','미집행'),TITLE+'하지 않았다',TITLE+'하지 못했다',
 TITLE+'에 관한 설명회 개최',TITLE.replace('집행','집행 기준 발표'),
 TITLE+'을 위한 설명회',TITLE+' 여부 확인',TITLE+'률 발표',
 TITLE.replace('신규 공장','DRAM 신규 공장'),
 TITLE.replace('신규 공장','새빛소재는 신규 공장'),
 TITLE+'했고 그 회사는 생산 시작',
 TITLE.replace('신규 공장','지난달 신규 공장'),
 TITLE.replace('HBM 수요','지난해 HBM 수요'),
 TITLE.replace('HBM 수요','지난 3월 HBM 수요'),
 TITLE+'을 검토 중이다',
])
def test_no_denied_or_borrowed_execution(text):
 assert not any(c['action']=='INVESTMENT_EXECUTION' for c in extract_economic_changes(text))


def test_decisions_keep_old_contract_and_parallel_stages():
 for tail in ['신규 공장 투자 결정','신규 공장 투자 확정','신규 공장 투자 집행 결정']:
  text='가상전자, HBM 수요 증가로 '+tail
  rows=extract_economic_changes(text)
  assert rows==extract_economic_changes(text,include_investment_execution=False)
  assert rows[0]['action']=='INVESTMENT'
 rows=extract_economic_changes(TITLE+' 및 신규 공장 투자 결정')
 assert [(c['action'],c['phase']) for c in rows]==[('INVESTMENT_EXECUTION','SOURCE_REPORTED'),('INVESTMENT','SOURCE_REPORTED')]
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 DRAM 수요 증가로 신규 공장 투자 집행 계획')
 assert [(c['entity_ids'],c['phase']) for c in rows]==[(['가상전자'],'SOURCE_REPORTED'),(['새빛소재'],'PLANNED')]


def case(tmp_path):
 return policy_case(tmp_path,titles=[
  '가상전자, '+CAUSE+' 신규 공장 투자 결정',
  '새빛소재, '+CAUSE+' 신규 공장 투자 집행',
  '미래장비, '+CAUSE+' 신규 공장 투자 집행 예정'])


def test_saved_stages_source_reasons_pit_and_standard_output(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert len(events)==3 and theme['scores']['company_breadth']==3
 assert store.search(as_of=at,now=args['now'])==[first]
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 bundle=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 candidates={c['entity_id']:c for c in bundle['CompanyCandidates']}
 for actor,action,phase in [('가상전자','INVESTMENT','SOURCE_REPORTED'),('새빛소재','INVESTMENT_EXECUTION','SOURCE_REPORTED'),('미래장비','INVESTMENT_EXECUTION','PLANNED')]:
  c=candidates[actor];basis=c['inclusion_basis'][0]
  assert (basis['action'],basis['phase'])==(action,phase)
  if action=='INVESTMENT_EXECUTION':assert '투자 집행' in basis['reason']
  assert not c['verified_real_transaction'] and not c['verified_real_benefit']
  detail=company_evidence(theme,actor,**args)
  assert detail['items'][0]['status']=='READY'
  assert actor in detail['items'][0]['excerpt'] and CAUSE in detail['items'][0]['excerpt']
 assert fingerprint(tmp_path)==before
 assert report['source_fetch_calls']==report['new_ai_results']==0

@pytest.mark.parametrize('phase,label',[('SOURCE_REPORTED','투자 집행 · 출처 보도'),('PLANNED','투자 집행 · 계획 단계')])
def test_screen_labels_and_execution_search(phase,label):
 item=dict(headline='합성 자료',category=None,economic_changes=[dict(action='INVESTMENT_EXECUTION',phase=phase)])
 result=present(item,['투자 집행','투자 결정'])
 assert result['label']==label and result['matches']==result['themes']==[True,False] and result['unchanged']


def test_period_api_and_company_evidence_show_both_stages(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 theme,args,*_=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 before=fingerprint(args['document_root']);url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert data['counts']['items']==3 and len(data['company_candidates'])==3
  refs=data['themes'][0]['source_refs']
  assert {(r['action'],r['phase']) for r in refs}=={('INVESTMENT','SOURCE_REPORTED'),('INVESTMENT_EXECUTION','SOURCE_REPORTED'),('INVESTMENT_EXECUTION','PLANNED')}
  with urlopen(url+'/api/themes?'+urlencode({'q':'INVESTMENT_EXECUTION'})) as response:found=json.load(response)
  assert found['ThemeCandidates']==[theme]
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'미래장비','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and '예정' in detail['items'][0]['excerpt']
 finally:
  server.shutdown();server.server_close();thread.join(timeout=2)
 assert fingerprint(args['document_root'])==before


def test_licensed_body_execution(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 지출 금액은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args)
 assert [(c['action'],c['phase']) for c in report['economic_changes']]==[('INVESTMENT_EXECUTION','SOURCE_REPORTED')]
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_old_investment_clause_and_snapshot_remain_readable(tmp_path):
 from test_feed_analysis import setup,run
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 from test_order_growth import observation
 text='가상전자는 HBM 수요 증가로 신규 공장 투자 집행했고 새빛소재는 HBM 신규 공장 투자 결정'
 info=setup(tmp_path,text);at=datetime.now(timezone.utc)
 report=run(info,now=at);row=report['results'][0];current=row['economic_changes']
 old,=extract_economic_changes(text,include_investment_execution=False);old['evidence_level']='REPORTED'
 assert old['action']=='INVESTMENT' and old['entity_ids']==['가상전자','새빛소재']
 row['economic_changes']=[old];root=tmp_path/'reports';docs=tmp_path/'documents'
 path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');event=observation(row,old);theme=store.ingest([event],now=at)[0]
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 before=fingerprint(tmp_path)
 for actor in old['entity_ids']:
  detail=company_evidence(theme,actor,reports_root=root,document_root=docs,as_of=at,now=at,
   feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['event_id']==event['event_id']
 assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)['ThemeCandidates']==[theme]
 assert fingerprint(tmp_path)==before
 from datetime import timedelta
 later=at+timedelta(seconds=1)
 store.ingest([observation(row,c) for c in current],now=later)
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)
