"""Synthetic new-customer reports, without inferred contracts or customers."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.theme_changes import compare_themes
from newscatalystos.company_evidence import company_evidence
from newscatalystos.source_share import SourceShareError
from test_policy_company_actions import case as source_case
from test_federated_news_search import fingerprint
from test_research_action_labels import present

TITLE='가상전자, HBM 수요 증가로 신규 고객 확보'
POLICY='미국의 「첨단칩통제법」 중국향 HBM 수출 규제 완화로'

@pytest.mark.parametrize('text,phase,actor',[
 (TITLE,'SOURCE_REPORTED','가상전자'),
 (TITLE.replace('고객 확보','고객사를 확보했다'),'SOURCE_REPORTED','가상전자'),
 (TITLE.replace('고객 확보','고객 확보에 성공했다'),'SOURCE_REPORTED','가상전자'),
 (TITLE.replace('수요','주문'),'SOURCE_REPORTED','가상전자'),
 (TITLE.replace('HBM 수요 증가로',POLICY),'SOURCE_REPORTED','가상전자'),
 (POLICY+' 가상전자는 신규 고객 확보','SOURCE_REPORTED','가상전자'),
 (TITLE.replace('신규 고객 확보','새빛소재를 신규 고객으로 확보했다'),'SOURCE_REPORTED','가상전자'),
 (TITLE.replace('신규 고객 확보','「고객알파」를 신규 고객사로 확보'),'SOURCE_REPORTED','가상전자'),
 (TITLE.replace('신규 고객 확보','새빛소재를 신규 고객으로 확보').replace('HBM 수요 증가로',POLICY),'SOURCE_REPORTED','가상전자'),
 (TITLE+' 계획','PLANNED','가상전자'),(TITLE+' 예정','PLANNED','가상전자'),
 (TITLE+' 목표','PLANNED','가상전자'),(TITLE+'한다','PLANNED','가상전자'),(TITLE.replace('확보','확보할 계획'),'PLANNED','가상전자'),
 (TITLE.replace('증가로','증가에 대비해'),'PLANNED','가상전자'),
])
def test_source_action_phase_actor_and_sha(text,phase,actor):
 row,=extract_economic_changes(text)
 assert (row['action'],row['phase'],row['entity_ids'])==('CUSTOMER_ACQUISITION',phase,[actor])
 assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
 assert not row['verified_economic_effect']
 assert not any('customer' in key for key in row)  # No invented customer identity field.

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 보도를 부인했다',TITLE+' 취소',
 TITLE+' 여부 확인',TITLE+'을 위한 기술 소개',TITLE+' 설명회 개최',TITLE+' 전망',
 TITLE.replace('신규','기존'),TITLE.replace('확보','관리'),TITLE.replace('확보','확보 방법 소개'),
 TITLE.replace('신규 고객','미확보 고객'),TITLE.replace('확보','확보 실패'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace('신규 고객','새빛소재는 신규 고객'),
 TITLE.replace('신규 고객','DRAM 신규 고객'),
 TITLE.replace('HBM 수요 증가로','HBM 기술 소개로'),
 TITLE.replace('HBM 수요 증가로','HBM 주가 상승으로'),
 TITLE.replace('HBM 수요 증가로','HBM 수요 감소로'),
 TITLE.replace('HBM 수요 증가로','지난해 HBM 수요 증가로'),
 TITLE.replace('신규 고객','지난달 신규 고객'),
 TITLE.replace('신규 고객 확보','신규 고객 확보했고 그 회사는 생산 시작'),
 TITLE.replace('HBM 수요 증가로','HBM 수요 증가. 새빛소재는'),
])
def test_no_denied_existing_technical_or_borrowed_customer_action(text):
 assert not any(c['action']=='CUSTOMER_ACQUISITION' for c in extract_economic_changes(text))


def test_company_clauses_do_not_share_causes_or_objects():
 text='가상전자는 HBM 수요 증가로 신규 고객 확보했고 새빛소재는 DRAM 수요 증가로 생산 시작'
 rows=extract_economic_changes(text)
 assert [(r['entity_ids'],r['topic'],r['action']) for r in rows]==[
  (['가상전자'],'HBM','CUSTOMER_ACQUISITION'),(['새빛소재'],'DRAM','PRODUCTION_START')]
 assert not extract_economic_changes(TITLE,include_new_customers=False)


def case(tmp_path):
 return source_case(tmp_path,titles=[TITLE,'새빛소재, HBM 수요 증가로 생산 시작',
                                   '미래장비, HBM 수요 증가로 공급 계약 체결'])


def test_saved_reports_common_cause_emerging_theme_sources_pit_and_standard_output(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==3
 assert theme['entity_ids']==['가상전자','미래장비','새빛소재']
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 actor=next(c for c in data['CompanyCandidates'] if c['entity_id']=='가상전자')
 assert actor['inclusion_basis'][0]['action']=='CUSTOMER_ACQUISITION'
 assert '신규 고객 확보' in actor['inclusion_basis'][0]['reason']
 assert any('계약 체결·매출' in s for s in actor['uncertainties'])
 assert not actor['verified_real_transaction'] and not actor['verified_real_benefit']
 assert actor['benefit_paths']==[] and actor['revenue_contribution'] is None
 detail=company_evidence(theme,'가상전자',**args)
 assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']==TITLE
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert diff['events']['independent_actions_added']==3
 assert any(r['supporting_source']['action']=='CUSTOMER_ACQUISITION' for r in diff['events']['added'])
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_named_customer_is_source_object_not_second_beneficiary(tmp_path):
 text=TITLE.replace('신규 고객 확보','「고객알파」를 신규 고객으로 확보')
 theme,args,*_=source_case(tmp_path,titles=[text,'새빛소재, HBM 수요 증가로 생산 시작'])
 data=json.loads(build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
 assert {c['entity_id'] for c in data['CompanyCandidates']}=={'가상전자','새빛소재'}
 item,=company_evidence(theme,'가상전자',**args)['items']
 assert item['status']=='READY' and '「고객알파」' in item['excerpt']
 assert not any(c['benefit_paths'] for c in data['CompanyCandidates'])


def test_saved_title_cannot_promote_plan_or_replace_actor(tmp_path):
 from newscatalystos.feed_analysis_delivery import _validate_report
 theme,args,store,report,*_=source_case(tmp_path,titles=[TITLE+' 계획','새빛소재, HBM 수요 증가로 생산 시작'])
 for field,value in [('phase','SOURCE_REPORTED'),('entity_ids',['없는전자'])]:
  forged=deepcopy(report);row=next(r for r in forged['results'] if '계획' in r['headline'])
  row['economic_changes'][0][field]=value
  with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


@pytest.mark.parametrize('phase,label',[('SOURCE_REPORTED','신규 고객 확보 · 출처 보도'),('PLANNED','신규 고객 확보 · 계획 단계')])
def test_shared_js_label_and_search(phase,label):
 item=dict(headline='합성 자료',category=None,economic_changes=[dict(action='CUSTOMER_ACQUISITION',phase=phase)])
 result=present(item,['신규 고객 확보','계약 체결'])
 assert result['label']==label and result['matches']==result['themes']==[True,False] and result['unchanged']


def test_period_http_customer_and_company_excerpt(tmp_path,monkeypatch):
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
  assert data['counts']['items']==3 and len(data['themes'])==1 and len(data['company_candidates'])==3
  assert data['themes'][0]['status']=='EMERGING'
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['action']=='CUSTOMER_ACQUISITION'
  with urlopen(url+'/api/themes?'+urlencode({'q':'CUSTOMER_ACQUISITION'})) as response:found=json.load(response)
  assert found['ThemeCandidates']==[theme]
 finally:
  server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_licensed_body_customer_action(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 계약·매출은 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args)
 assert [(c['action'],c['entity_ids']) for c in report['economic_changes']]==[('CUSTOMER_ACQUISITION',['가상전자'])]
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_legacy_unsplit_investment_and_old_snapshot_keep_evidence(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 text='가상전자는 HBM 수요 증가로 신규 고객 확보했고 새빛소재는 HBM 신규 공장 투자 결정'
 info=setup(tmp_path,text);at=datetime.now(timezone.utc);report=run(info,now=at);row=report['results'][0]
 current=deepcopy(row['economic_changes']);old,=extract_economic_changes(text,include_new_customers=False)
 old['evidence_level']='REPORTED';row['economic_changes']=[old]
 assert old['entity_ids']==['가상전자','새빛소재'] and old['action']=='INVESTMENT'
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');theme=store.ingest([observation(row,old)],now=at)[0]
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 for actor in old['entity_ids']:
  item,=company_evidence(theme,actor,reports_root=root,document_root=docs,as_of=at,now=at,
   feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
  assert item['status']=='READY' and item['excerpt']==text
 later=at+timedelta(seconds=1);store.ingest([observation(row,c) for c in current],now=later)
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)
