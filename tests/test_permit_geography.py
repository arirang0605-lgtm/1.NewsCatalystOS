"""Explicit permit jurisdiction and destination; no inferred geography or permit identity."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import pytest
from newscatalystos.economic_changes import extract_economic_changes,policy_cause_key
from newscatalystos.theme_emergence import ThemeStore,theme_presentation,economic_observation,_bytes
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.company_evidence import company_evidence
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.source_share import SourceShareError
from test_feed_analysis import setup,run
from test_order_growth import observation
from test_federated_news_search import fingerprint
from test_new_source_adapter import NOW

CAUSE='미국의 중국향 HBM 수출 허가 취득으로'
TITLE='가상전자, '+CAUSE+' 생산 시작'

@pytest.mark.parametrize('cause,jurisdiction,destination',[
 (CAUSE,'미국','중국'),(CAUSE.replace('미국의 ','미국 '),'미국','중국'),
 (CAUSE.replace('미국의 ',''),None,'중국'),
 (CAUSE.replace('중국향','일본향'),'미국','일본'),
 (CAUSE.replace('미국의','일본의'),'일본','중국'),
 (CAUSE.replace('취득','승인'),'미국','중국'),
 (CAUSE.replace('중국향 ','‘첨단칩통제법’ 중국향 '),'미국','중국'),
])
def test_literal_scope_preserved(cause,jurisdiction,destination):
 text='가상전자, '+cause+' 생산 시작';row,=extract_economic_changes(text)
 assert row['action']=='PRODUCTION_START' and row['entity_ids']==['가상전자']
 proof=row['policy_cause']
 assert (proof['jurisdiction'],proof['destination'])==(jurisdiction,destination)
 assert proof['source_expression']==cause and proof['expression_sha256']==sha256(cause.encode()).hexdigest()
 assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
 assert not row['verified_economic_effect']
 economic_observation(row,origin_reference='https://gov.example.org/1',source_url='https://gov.example.org/1',source_id='synthetic',source_available_at=NOW.isoformat())

@pytest.mark.parametrize('text',[
 TITLE+' 취소',TITLE+' 보도를 부인했다',
 TITLE.replace('생산 시작','DRAM 생산 시작'),
 TITLE.replace('생산 시작','일본의 중국향 HBM 수출 허가 취득으로 생산 시작'),
 '가상전자, '+CAUSE+' 새빛소재는 생산 시작',
 CAUSE+' 그 회사는 생산 시작',
 TITLE.replace('중국향','중국향 및 일본향'),
 TITLE.replace('중국향','캐나다향'),
 TITLE.replace('수출 허가','수입 허가'),
])
def test_unresolved_scope_does_not_borrow_geography(text):
 assert not any(r.get('policy_cause',{}).get('destination') for r in extract_economic_changes(text))


def test_following_subject_parallel_plan_and_other_actor():
 row,=extract_economic_changes(CAUSE+' 가상전자는 생산 시작')
 assert row['entity_ids']==['가상전자'] and row['policy_cause']['jurisdiction']=='미국'
 row,=extract_economic_changes(TITLE+' 계획');assert row['phase']=='PLANNED'
 row,=extract_economic_changes(TITLE.replace('취득으로','취득에 대비해'));assert row['phase']=='PLANNED'
 rows=extract_economic_changes(TITLE+' 및 생산능력 확대')
 assert [r['action'] for r in rows]==['PRODUCTION_START','CAPACITY_ADDITION']
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 일본의 한국향 HBM 수출 허가 승인으로 생산능력 확대')
 assert [(r['entity_ids'],r['policy_cause']['jurisdiction'],r['policy_cause']['destination']) for r in rows]==[(['가상전자'],'미국','중국'),(['새빛소재'],'일본','한국')]
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 HBM 생산능력 확대')
 assert 'policy_cause' not in rows[1]


def test_destination_identity_display_and_search(tmp_path):
 events=[]
 for i,(actor,destination) in enumerate([('가상전자','중국'),('가상전자','일본'),('새빛소재','중국')]):
  row,=extract_economic_changes(TITLE.replace('가상전자',actor).replace('중국향',destination+'향'))
  events.append(economic_observation(row,origin_reference='https://gov.example.org/same',source_url='https://gov.example.org/same',source_id='synthetic',source_available_at=NOW.isoformat()))
 store=ThemeStore(tmp_path/'themes');themes=store.ingest(events,now=datetime.now(timezone.utc))
 assert len(themes)==3 and len({e['event_id'] for e in events})==3
 assert len(store.search(query='수출 목적지 중국'))==2
 assert len(store.search(query='수출 목적지 일본'))==1
 assert all('미국' in theme_presentation(t)['name'] for t in themes)


def test_period_and_company_source_path(tmp_path,monkeypatch):
 import test_permit_company_actions as previous
 monkeypatch.setattr(previous,'CAUSE',CAUSE);monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_saved_permit_through_period_search_and_company_evidence(tmp_path,monkeypatch)


def test_old_partial_policy_record_and_v3_bytes_remain_readable(tmp_path):
 info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc)+timedelta(seconds=1)
 report=run(info,now=at);row=report['results'][0]
 old,=extract_economic_changes(TITLE,include_policy_destinations=False);old['evidence_level']='REPORTED'
 assert old['action']=='PRODUCTION_START' and old['policy_cause']['jurisdiction'] is None
 assert 'destination' not in old['policy_cause'] and len(policy_cause_key(old['policy_cause']))==4
 row['economic_changes']=[old]
 root=tmp_path/'reports';docs=tmp_path/'documents'
 path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 event=observation(row,old);store=ThemeStore(docs/'theme_history');theme=store.ingest([event],now=at)[0]
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 before=fingerprint(tmp_path)
 detail=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
  feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])
 assert detail['items'][0]['status']=='READY' and detail['items'][0]['event_id']==event['event_id']
 assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)['ThemeCandidates']==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 assert fingerprint(tmp_path)==before
 new,=extract_economic_changes(TITLE);new['evidence_level']='REPORTED'
 store.ingest([observation(row,new)],now=at+timedelta(seconds=1))
 assert store.search(as_of=at,now=at+timedelta(seconds=1))==[theme]

@pytest.mark.parametrize('field,value',[('destination','일본'),('jurisdiction','일본'),('destination',None)])
def test_source_geography_cannot_be_forged(tmp_path,field,value):
 info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc)+timedelta(seconds=1)
 report=run(info,now=at);proof=report['results'][0]['economic_changes'][0]['policy_cause']
 if value is None:del proof[field]
 else:proof[field]=value
 path,pin=publish_feed_analysis(report,tmp_path/'reports')
 with pytest.raises(SourceShareError):consume_feed_analysis(path,path.parent,pin,now=at)


def test_licensed_body_retains_full_geography(tmp_path,monkeypatch):
 import test_policy_company_actions as previous
 monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_licensed_body_and_standalone_policy_preserve_scopes(tmp_path)
