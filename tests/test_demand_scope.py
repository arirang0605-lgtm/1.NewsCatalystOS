"""Synthetic explicit end-use scopes, never customer/contract certification."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,validate_change,_service_key,_investment_key
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_service_realization import claim
from test_theme_emergence import T
from test_policy_company_actions import case as source_case

CAUSE='AI 서버용 HBM 수요 증가로'
TITLE='가상전자, '+CAUSE+' 납품 시작'

@pytest.mark.parametrize('tail,action,phase',[
 ('생산 시작','PRODUCTION_START','SOURCE_REPORTED'),
 ('생산능력 확대','CAPACITY_ADDITION','SOURCE_REPORTED'),
 ('공급계약 체결','CONTRACT','SOURCE_REPORTED'),
 ('신규 공장 투자 결정','INVESTMENT','SOURCE_REPORTED'),
 ('투자 집행','INVESTMENT_EXECUTION','SOURCE_REPORTED'),
 ('신규 고객 확보','CUSTOMER_ACQUISITION','SOURCE_REPORTED'),
 ('신규 고객 확보 예정','CUSTOMER_ACQUISITION','PLANNED'),
 ('기존 고객에 납품 시작','DELIVERY_START','SOURCE_REPORTED'),
 ('「고객알파」에 공급 개시 계획','DELIVERY_START','PLANNED'),
])
def test_explicit_qualifier_keeps_actor_action_proof(tail,action,phase):
 text='가상전자, '+CAUSE+' '+tail
 c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['phase'],c['entity_ids'])==(action,phase,['가상전자'])
 assert c['demand_scope']==dict(status='EXPLICIT',destination='AI 서버',source_expression=CAUSE,expression_sha256=sha256(CAUSE.encode()).hexdigest())
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
 assert not c['verified_economic_effect']

@pytest.mark.parametrize('text',[
 'AI 서버용 HBM 수요 증가로 가상전자는 신규 고객 확보',
 'AI 서버용 HBM 주문 증가로 가상전자는 납품 시작',
 '가상전자, AI 서버용 HBM 주문 증가로 납품 시작',
 '가상전자, AI 서버용 HBM 수요 감소로 생산 축소',
 '가상전자, AI  서버용  HBM 수요 증가에 대응해 생산 시작',
])
def test_cause_first_order_contraction_literal_whitespace(text):
 c,=extract_economic_changes(text);validate_change(c)
 assert c['demand_scope']['source_expression'] in text
 assert c['entity_ids']==['가상전자']

@pytest.mark.parametrize('scope',[
 'AI 서버 및 스마트폰용','AI 서버용 및 스마트폰용','AI 서버/스마트폰용',
 'AI 서버, 스마트폰용','AI 서버와 스마트폰용','AI 서버 또는 스마트폰용',
 '여러 산업용','해당 제품용','일부 기기용',
])
def test_multiple_unclear_scopes_cannot_merge_even_with_each_other(tmp_path,scope):
 rows=[claim(f'{actor}, {scope} HBM 수요 증가로 생산 시작',i) for i,actor in enumerate(['가상전자','새빛소재'])]
 assert all(r['change']['demand_scope']['status']=='UNRESOLVED' for r in rows)
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=T+timedelta(hours=3))
 assert len(themes)==2


def test_same_scope_connects_different_and_unspecified_scopes_stay_apart(tmp_path):
 titles=[TITLE,'새빛소재, '+CAUSE+' 생산 시작','미래장비, '+CAUSE+' 신규 공장 투자 결정',
  '다른전자, 스마트폰용 HBM 수요 증가로 생산 시작','기타소재, HBM 수요 증가로 생산 시작']
 rows=[claim(t,i) for i,t in enumerate(titles)]
 store=ThemeStore(tmp_path/'themes');at=T+timedelta(hours=6)
 themes=store.ingest(rows,now=at)
 assert len(themes)==3
 theme=next(t for t in themes if len(t['entity_ids'])==3)
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==3
 assert 'AI 서버용' in theme['provisional_name']
 assert store.search(query='AI 서버',now=at)==[theme]
 raw=build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)
 assert len(data['CompanyCandidates'])==5
 assert all(not c['verified_real_transaction'] and not c['verified_real_benefit'] for c in data['CompanyCandidates'])
 assert store.ingest(rows,now=at)==[]


def test_saved_source_company_period_bundle_and_no_io(tmp_path):
 theme,args,store,report,events,first,at=source_case(tmp_path,titles=[TITLE,'새빛소재, '+CAUSE+' 생산 시작','미래장비, '+CAUSE+' 공급계약 체결'])
 for actor in theme['entity_ids']:
  item,=company_evidence(theme,actor,**args)['items']
  assert item['status']=='READY' and CAUSE in item['excerpt']
 data=json.loads(build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
 assert all(CAUSE in c['inclusion_basis'][0]['reason'] and c['inclusion_basis'][0]['demand_scope']['destination']=='AI 서버' for c in data['CompanyCandidates'])
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert all(r['supporting_source']['demand_scope']['destination']=='AI 서버' for r in diff['events']['added'])
 assert report['source_fetch_calls']==report['new_ai_results']==0
 assert store.search(as_of=at,now=args['now'])==[first]


def test_legacy_event_id_first_seen_snapshot_and_v3_bytes_preserved(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 text=TITLE.replace('납품 시작','생산 시작');info=setup(tmp_path,text);at=datetime.now(timezone.utc)
 report=run(info,now=at);row=report['results'][0];current=deepcopy(row['economic_changes'][0])
 old,=extract_economic_changes(text,include_demand_scopes=False);old['evidence_level']='REPORTED';row['economic_changes']=[old]
 old_event=observation(row,old);new_event=observation(row,current)
 assert old_event['event_id']==new_event['event_id']
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 consume_feed_analysis(path,path.parent,pin,now=at)
 store=ThemeStore(docs/'theme_history');theme,=store.ingest([old_event],now=at)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 item,=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
  feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
 assert item['status']=='READY' and item['excerpt']==text
 later=at+timedelta(seconds=1);latest,=store.ingest([new_event],now=later)
 assert latest['theme_id']==theme['theme_id'] and latest['first_detected_at']==theme['first_detected_at']
 assert latest['event_ids']==theme['event_ids']
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)


@pytest.mark.parametrize('field,value',[('destination','스마트폰'),('status','UNRESOLVED'),('expression_sha256','0'*64)])
def test_tampered_scope_rejected(field,value):
 c,=extract_economic_changes(TITLE);c['demand_scope'][field]=value
 with pytest.raises(SourceShareError):validate_change(c)


def test_self_consistent_but_wrong_source_scope_rejected(tmp_path):
 from test_feed_analysis import setup,run
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc);report=run(info,now=at)
 report['results'][0]['economic_changes'][0]['demand_scope']=extract_economic_changes(TITLE.replace('AI 서버','스마트폰'))[0]['demand_scope']
 path,pin=publish_feed_analysis(report,tmp_path/'reports')
 with pytest.raises(SourceShareError):consume_feed_analysis(path,path.parent,pin,now=at)


def test_scope_is_not_customer_company():
 c,=extract_economic_changes('가상전자, 삼성전자용 HBM 수요 증가로 생산 시작')
 assert c['entity_ids']==['가상전자'] and c['demand_scope']['destination']=='삼성전자'


def test_conflicting_scopes_for_same_source_actor_action_do_not_pick_first():
 a='가상전자, AI 서버용 HBM 수요 증가로 생산 시작'
 b=a.replace('AI 서버용','스마트폰용')
 assert extract_economic_changes(a+'. '+b)==[]
 assert len(extract_economic_changes(a+'. '+b.replace('가상전자','새빛소재')))==2
 assert len(extract_economic_changes(a+'. '+b,include_demand_scopes=False))==1


@pytest.mark.parametrize('action,key_fn',[("‘별빛검사’ 서비스 개시",_service_key),("‘화성 제2공장’ 투자 결정",_investment_key)])
def test_followup_pair_cannot_bypass_scope_boundary(action,key_fn):
 a=claim('가상전자, '+CAUSE+' '+action,0)
 b=claim('가상전자, '+CAUSE.replace('AI 서버','스마트폰')+' '+action,1)
 assert key_fn(a) and key_fn(b) and key_fn(a)!=key_fn(b)


def test_licensed_body_scope(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 납품·매출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args)
 assert report['economic_changes'][0]['demand_scope']['destination']=='AI 서버'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']

import threading
from urllib.request import urlopen
from urllib.parse import urlencode
from test_federated_news_search import fingerprint


def test_period_http_and_company_excerpt(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 theme,args,*_=source_case(tmp_path,titles=[TITLE,'새빛소재, '+CAUSE+' 생산 시작','미래장비, '+CAUSE+' 공급계약 체결'])
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
  with urlopen(url+'/api/themes?'+urlencode({'q':'AI 서버'})) as response:found=json.load(response)
  assert found['ThemeCandidates']==[theme]
 finally:
  server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_scope_in_finding_and_theme_search():
 from test_research_action_labels import present
 c,=extract_economic_changes(TITLE)
 result=present(dict(headline='합성 자료',economic_changes=[c]),['AI 서버','스마트폰'])
 assert result['matches']==result['themes']==[True,False] and result['unchanged']
