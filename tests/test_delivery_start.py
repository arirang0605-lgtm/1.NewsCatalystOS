"""Synthetic delivery-start reports; no independent delivery/revenue certification."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.theme_changes import compare_themes
from newscatalystos.company_evidence import company_evidence
from newscatalystos.source_share import SourceShareError
from test_policy_company_actions import case as source_case
from test_federated_news_search import fingerprint
from test_research_action_labels import present

PREFIX='가상전자, HBM 수요 증가로 '
TITLE=PREFIX+'신규 고객에 납품 시작'
POLICY='미국의 「첨단칩통제법」 중국향 HBM 수출 규제 완화로'

@pytest.mark.parametrize('tail,phase',[
 ('납품 시작','SOURCE_REPORTED'),('공급 개시','SOURCE_REPORTED'),
 ('신규 고객에 납품 시작','SOURCE_REPORTED'),('고객사에 공급을 시작했다','SOURCE_REPORTED'),
 ('기존 고객에 납품 시작','SOURCE_REPORTED'),('기존 고객사에게 공급 개시','SOURCE_REPORTED'),
 ('새빛소재에 HBM 공급을 개시했다','SOURCE_REPORTED'),('「고객알파」에 정식 납품 시작','SOURCE_REPORTED'),
 ('HBM을 본격 공급 개시했다','SOURCE_REPORTED'),('고대역폭 메모리를 납품 시작','SOURCE_REPORTED'),
 ('납품 시작 예정','PLANNED'),('공급 개시 계획','PLANNED'),('납품 시작 목표','PLANNED'),
 ('공급 개시한다','PLANNED'),('납품 시작할 계획','PLANNED'),('기존 고객에 공급 시작 예정','PLANNED'),
])
def test_explicit_delivery_actor_phase_and_sha(tail,phase):
 text=PREFIX+tail;row,=extract_economic_changes(text)
 assert (row['action'],row['phase'],row['entity_ids'],row['topic'])==('DELIVERY_START',phase,['가상전자'],'HBM')
 assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not row['verified_economic_effect']
 assert not any('customer' in key for key in row)

@pytest.mark.parametrize('text',[
 TITLE.replace('수요','주문'),TITLE.replace('HBM 수요 증가로',POLICY),
 POLICY+' 가상전자는 새빛소재에 납품 시작',
])
def test_reported_demand_order_policy_causes(text):
 row,=extract_economic_changes(text)
 assert row['action']=='DELIVERY_START' and row['entity_ids']==['가상전자']

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 취소',TITLE+' 보류',TITLE+' 지연',
 TITLE+' 보도를 부인했다',TITLE+' 여부 확인',TITLE+'을 위한 기술 소개',TITLE+' 설명회',TITLE+' 전망',
 TITLE.replace('납품 시작','납품 준비 시작'),TITLE.replace('납품 시작','납품 가능성'),
 TITLE.replace('납품 시작','시범 공급 개시'),TITLE.replace('신규 고객에','DRAM을'),
 TITLE.replace('신규 고객에','새빛소재는'),TITLE.replace('가상전자, ','그 회사는 '),
 TITLE.replace('가상전자, ',''),TITLE.replace('HBM 수요 증가로','HBM 기술 소개로'),
 TITLE.replace('HBM 수요 증가로','HBM 가격 상승으로'),TITLE.replace('HBM 수요 증가로','HBM 수요 감소로'),
 TITLE.replace('HBM 수요 증가로','지난해 HBM 수요 증가로'),TITLE.replace('신규 고객에','지난달 고객에'),
 TITLE.replace('HBM 수요 증가로','HBM 수요 증가. 새빛소재는'),TITLE+'했고 그 회사는 생산 시작',
 PREFIX+'신규 고객 확보',PREFIX+'공급 계약 체결',PREFIX+'생산 시작',
])
def test_no_other_action_denial_history_or_borrowed_delivery(text):
 assert not any(c['action']=='DELIVERY_START' for c in extract_economic_changes(text))


def test_explicit_company_clauses_preserve_separate_actions():
 rows=extract_economic_changes('가상전자는 HBM 수요 증가로 납품 시작했고 새빛소재는 DRAM 수요 증가로 신규 고객 확보')
 assert [(r['entity_ids'],r['topic'],r['action']) for r in rows]==[
  (['가상전자'],'HBM','DELIVERY_START'),(['새빛소재'],'DRAM','CUSTOMER_ACQUISITION')]
 assert not extract_economic_changes(TITLE,include_delivery_start=False)


def case(tmp_path):
 return source_case(tmp_path,titles=[TITLE,'새빛소재, HBM 수요 증가로 생산 시작',
                                   '미래장비, HBM 수요 증가로 공급 계약 체결'])


def test_reports_to_common_theme_company_sources_period_and_readonly_output(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==3
 assert theme['entity_ids']==['가상전자','미래장비','새빛소재']
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 c=next(c for c in data['CompanyCandidates'] if c['entity_id']=='가상전자')
 assert c['inclusion_basis'][0]['action']=='DELIVERY_START' and '납품·공급 개시' in c['inclusion_basis'][0]['reason']
 assert any('실제 납품·계약 이행·매출' in s for s in c['uncertainties'])
 assert c['benefit_paths']==[] and not c['verified_real_transaction'] and not c['verified_real_benefit']
 item,=company_evidence(theme,'가상전자',**args)['items']
 assert item['status']=='READY' and item['excerpt']==TITLE
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert diff['events']['independent_actions_added']==3
 assert any(r['supporting_source']['action']=='DELIVERY_START' for r in diff['events']['added'])
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_named_customer_stays_in_source_not_second_beneficiary(tmp_path):
 title=PREFIX+'「고객알파」에 납품 시작'
 theme,args,*_=source_case(tmp_path,titles=[title,'새빛소재, HBM 수요 증가로 생산 시작'])
 data=json.loads(build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
 assert {c['entity_id'] for c in data['CompanyCandidates']}=={'가상전자','새빛소재'}
 item,=company_evidence(theme,'가상전자',**args)['items']
 assert item['status']=='READY' and '「고객알파」' in item['excerpt']


def test_saved_title_cannot_promote_plan_or_replace_actor(tmp_path):
 from newscatalystos.feed_analysis_delivery import _validate_report
 theme,args,store,report,*_=source_case(tmp_path,titles=[TITLE+' 계획','새빛소재, HBM 수요 증가로 생산 시작'])
 for field,value in [('phase','SOURCE_REPORTED'),('entity_ids',['없는전자'])]:
  forged=deepcopy(report);row=next(r for r in forged['results'] if '계획' in r['headline'])
  row['economic_changes'][0][field]=value
  with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


@pytest.mark.parametrize('phase,label',[('SOURCE_REPORTED','납품·공급 개시 · 출처 보도'),('PLANNED','납품·공급 개시 · 계획 단계')])
def test_js_label_and_delivery_supply_search(phase,label):
 item=dict(headline='합성 자료',category=None,economic_changes=[dict(action='DELIVERY_START',phase=phase)])
 result=present(item,['납품 시작','공급 개시','계약 체결'])
 assert result['label']==label and result['matches']==result['themes']==[True,True,False] and result['unchanged']


def test_period_http_and_company_excerpt(tmp_path,monkeypatch):
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
  assert data['counts']['items']==3 and len(data['company_candidates'])==3 and data['themes'][0]['status']=='EMERGING'
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['action']=='DELIVERY_START'
  with urlopen(url+'/api/themes?'+urlencode({'q':'DELIVERY_START'})) as response:found=json.load(response)
  assert found['ThemeCandidates']==[theme]
 finally:
  server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_licensed_body_delivery(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 납품·매출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args)
 assert [(c['action'],c['entity_ids']) for c in report['economic_changes']]==[('DELIVERY_START',['가상전자'])]
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_legacy_unsplit_investment_and_old_snapshot_keep_evidence(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 text='가상전자는 HBM 수요 증가로 납품 시작했고 새빛소재는 HBM 신규 공장 투자 결정'
 info=setup(tmp_path,text);at=datetime.now(timezone.utc);report=run(info,now=at);row=report['results'][0]
 current=deepcopy(row['economic_changes']);old,=extract_economic_changes(text,include_delivery_start=False)
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
