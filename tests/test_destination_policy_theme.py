"""Destination-scoped regulations form hypotheses only from the same explicit policy."""
from datetime import datetime,timezone
from hashlib import sha256
import json,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation,theme_presentation
from test_new_source_adapter import NOW
from test_federated_news_search import fingerprint
import test_policy_company_actions as policy

CAUSE='미국의 「첨단칩통제법」 중국향 HBM 수출 규제 완화로'
TITLE='가상전자, '+CAUSE+' 생산 시작'

@pytest.mark.parametrize('text,action,phase',[
 (TITLE,'PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE.replace('완화','폐지'),'PRODUCTION_START','SOURCE_REPORTED'),
 (CAUSE+' 가상전자는 생산 시작','PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE+' 계획','PRODUCTION_START','PLANNED'),
 (TITLE.replace('완화로','완화에 대비해'),'PRODUCTION_START','PLANNED'),
 (TITLE.replace('생산 시작','생산능력 확대'),'CAPACITY_ADDITION','SOURCE_REPORTED'),
])
def test_regulation_scope_and_company_action(text,action,phase):
 row,=extract_economic_changes(text);proof=row['policy_cause']
 assert (row['action'],row['phase'],row['entity_ids'])==(action,phase,['가상전자'])
 assert (proof['jurisdiction'],proof['destination'],proof['policy_name'],proof['restriction'])==('미국','중국','첨단칩통제법','수출규제')
 assert proof['source_expression'] in text and proof['expression_sha256']==sha256(proof['source_expression'].encode()).hexdigest()
 assert not row['verified_economic_effect']

@pytest.mark.parametrize('text',[
 TITLE+' 취소',TITLE+' 보도를 부인했다',
 TITLE.replace('생산 시작','DRAM 생산 시작'),
 TITLE.replace('생산 시작','일본의 중국향 HBM 수출 규제 폐지로 생산 시작'),
 '가상전자, '+CAUSE+' 새빛소재는 생산 시작',
 CAUSE+' 그 회사는 생산 시작',
 TITLE.replace('중국향','중국향 및 일본향'),
 TITLE.replace('수출 규제','수입 규제'),
])
def test_no_ambiguous_or_unrelated_destination_response(text):
 assert not any(r.get('policy_cause',{}).get('destination') for r in extract_economic_changes(text))

@pytest.mark.parametrize('other',[
 CAUSE.replace('중국향','일본향'),CAUSE.replace('중국향 ',''),
 CAUSE.replace('미국의 ',''),CAUSE.replace('「첨단칩통제법」 ',''),
 CAUSE.replace('첨단칩통제법','별도통제법'),CAUSE.replace('미국의','일본의'),
 CAUSE.replace('완화','폐지'),CAUSE.replace('규제 완화로','허가 승인으로'),
])
def test_other_scope_or_permit_never_joins_known_policy(tmp_path,other):
 store=ThemeStore(tmp_path/'themes');events=[]
 for i,(actor,cause) in enumerate([('가상전자',CAUSE),('새빛소재',other)]):
  row,=extract_economic_changes(f'{actor}, {cause} 생산 시작')
  events.append(economic_observation(row,origin_reference=f'https://gov.example.org/{i}',source_url=f'https://gov.example.org/{i}',source_id='synthetic',source_available_at=NOW.isoformat()))
 assert len(store.ingest(events,now=datetime.now(timezone.utc)))==2


def test_same_scope_saved_theme_sources_and_pit(tmp_path,monkeypatch):
 monkeypatch.setattr(policy,'TITLE',TITLE);monkeypatch.setattr(policy,'CAUSE',CAUSE)
 policy.test_saved_sources_common_policy_theme_company_reasons_and_pit(tmp_path)


def test_separate_company_clauses_and_parallel_actions():
 rows=extract_economic_changes(TITLE+' 및 생산능력 확대')
 assert [r['action'] for r in rows]==['PRODUCTION_START','CAPACITY_ADDITION']
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 '+CAUSE.replace('중국향','일본향')+' 생산능력 확대')
 assert [(r['entity_ids'],r['policy_cause']['destination']) for r in rows]==[(['가상전자'],'중국'),(['새빛소재'],'일본')]


def test_period_search_three_companies_in_one_theme(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 monkeypatch.setattr(policy,'TITLE',TITLE);monkeypatch.setattr(policy,'CAUSE',CAUSE)
 theme,args,store,*_=policy.case(tmp_path)
 assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3
 before=fingerprint(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert data['counts']['items']==3 and data['themes']==[theme] and len(data['company_candidates'])==3
  title=theme_presentation(theme)['name']
  assert data['theme_presentations'][theme['theme_id']]['name']==title and '수출 목적지 중국' in title
  with urlopen(url+'/api/themes?'+urlencode({'q':title,'company_candidates':'1'})) as response:data=json.load(response)
  assert data['ThemeCandidates']==[theme] and len(data['CompanyCandidates'])==3
  for actor in ('가상전자','새빛소재','미래장비'):
   with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':actor,'as_of':args['as_of'].isoformat()})) as response:data=json.load(response)
   assert data['items'][0]['status']=='READY' and CAUSE in data['items'][0]['excerpt']
 finally:
  server.shutdown();server.server_close();thread.join(timeout=2)
 assert fingerprint(tmp_path)==before


def test_legacy_policy_only_record_and_body(tmp_path,monkeypatch):
 monkeypatch.setattr(policy,'TITLE',TITLE)
 (tmp_path/'old').mkdir();(tmp_path/'body').mkdir()
 policy.test_legacy_policy_record_keeps_id_and_source_readable(tmp_path/'old')
 policy.test_licensed_body_and_standalone_policy_preserve_scopes(tmp_path/'body')


def test_old_partial_destination_policy_record_preserved(tmp_path,monkeypatch):
 import test_permit_geography as previous
 monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_old_partial_policy_record_and_v3_bytes_remain_readable(tmp_path)
