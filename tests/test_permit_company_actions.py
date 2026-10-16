"""Synthetic permit reports; approvals are not certified effects or shared permits."""
from datetime import datetime,timezone
import json,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation,theme_presentation
from newscatalystos.company_evidence import company_evidence
from newscatalystos.standard_delivery import build_theme_bundle
from test_policy_company_actions import case
from test_new_source_adapter import NOW
from test_federated_news_search import fingerprint

CAUSE='미국 HBM 수출 허가 승인으로'
TITLE='가상전자, '+CAUSE+' 생산 시작'

@pytest.mark.parametrize('text,actor,action,phase',[
 (TITLE,'가상전자','PRODUCTION_START','SOURCE_REPORTED'),
 (CAUSE+' 가상전자는 생산 시작','가상전자','PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE.replace('미국 ',''),'가상전자','PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE.replace('수출','수입'),'가상전자','PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE.replace('수출','생산'),'가상전자','PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE+' 계획','가상전자','PRODUCTION_START','PLANNED'),
 (TITLE.replace('승인으로','승인에 대비해'),'가상전자','PRODUCTION_START','PLANNED'),
 (TITLE.replace('생산 시작','생산능력 확대'),'가상전자','CAPACITY_ADDITION','SOURCE_REPORTED'),
])
def test_permit_cause_and_company_response(text,actor,action,phase):
 from hashlib import sha256
 row,=extract_economic_changes(text)
 assert (row['entity_ids'],row['action'],row['phase'])==([actor],action,phase)
 assert row['policy_cause']['change']=='승인' and row['policy_cause']['restriction'].endswith('허가')
 assert row['policy_cause']['source_expression'] in text
 assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
 assert not row['verified_economic_effect']
 economic_observation(row,origin_reference='https://gov.example.org/permit',source_url='https://gov.example.org/permit',source_id='synthetic',source_available_at=NOW.isoformat())

@pytest.mark.parametrize('text',[
 TITLE+' 보도를 부인했다',TITLE+' 취소',TITLE.replace('승인으로','승인 없이'),
 CAUSE+' 생산 시작',CAUSE+' 그 회사는 생산 시작',
 '가상전자, '+CAUSE+' 새빛소재는 생산 시작',
 TITLE.replace('생산 시작','DRAM 생산 시작'),
 TITLE.replace('미국','지난해 미국'),
 TITLE.replace('생산 시작','일본 HBM 수출 허가 승인으로 생산 시작'),
])
def test_ambiguous_permit_does_not_claim_response(text):
 assert not any(r.get('policy_cause') for r in extract_economic_changes(text))


def test_separate_subjects_and_parallel_actions():
 rows=extract_economic_changes(TITLE+' 및 생산능력 확대')
 assert [r['action'] for r in rows]==['PRODUCTION_START','CAPACITY_ADDITION']
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 일본 HBM 수입 허가 승인으로 생산능력 확대')
 assert [(r['entity_ids'],r['policy_cause']['jurisdiction']) for r in rows]==[(['가상전자'],'미국'),(['새빛소재'],'일본')]
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 HBM 생산능력 확대')
 assert len(rows)==2 and 'policy_cause' not in rows[1]

@pytest.mark.parametrize('other',[
 '미국 ‘첨단칩통제법’ HBM 수출 허가 승인으로',
 '일본 ‘첨단칩통제법’ HBM 수출 허가 승인으로',
 '미국 ‘첨단칩통제법’ HBM 수입 허가 승인으로',
 '미국 ‘첨단칩통제법’ HBM 수출 규제 완화로',
])
def test_law_name_is_not_identity_of_an_individual_permit(tmp_path,other):
 store=ThemeStore(tmp_path/'themes');events=[]
 for i,(actor,cause) in enumerate([('가상전자','미국 ‘첨단칩통제법’ HBM 수출 허가 승인으로'),('새빛소재',other)]):
  change,=extract_economic_changes(f'{actor}, {cause} 생산 시작')
  events.append(economic_observation(change,origin_reference=f'https://gov.example.org/{i}',source_url=f'https://gov.example.org/{i}',source_id='synthetic',source_available_at=NOW.isoformat()))
 assert len(store.ingest(events,now=datetime.now(timezone.utc)))==2


def test_saved_permit_through_period_search_and_company_evidence(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,report,events,first,at=case(tmp_path,titles=[TITLE,'새빛소재, '+CAUSE+' 생산능력 확대'])
 rows=store.search(now=args['now']);assert len(rows)==2
 target=next(t for t in rows if t['entity_ids']==['가상전자'])
 assert store.search(as_of=at,now=args['now'])==[first]
 assert store.ingest(events,now=args['now'])==[]
 assert len(store.search(query='수출허가',now=args['now']))==2
 before=fingerprint(tmp_path)
 detail=company_evidence(target,'가상전자',**args)
 assert detail['items'][0]['status']=='READY' and TITLE in detail['items'][0]['excerpt']
 bundle=json.loads(build_theme_bundle(rows,decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
 assert all(CAUSE in c['inclusion_basis'][0]['reason'] and not c['verified_real_benefit'] for c in bundle['CompanyCandidates'])
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
  assert data['counts']['items']==2 and len(data['themes'])==2
  assert data['theme_presentations'][target['theme_id']]==theme_presentation(target)
  with urlopen(url+'/api/themes?'+urlencode({'q':'수출허가'})) as response:found=json.load(response)
  assert len(found['ThemeCandidates'])==2
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':target['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:found=json.load(response)
  assert found['items'][0]['status']=='READY'
 finally:
  server.shutdown();server.server_close();thread.join(timeout=2)
 assert fingerprint(tmp_path)==before
 assert report['source_fetch_calls']==report['new_ai_results']==0


def test_legacy_permit_report_remains_readable(tmp_path,monkeypatch):
 import test_policy_company_actions as previous
 monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_legacy_policy_record_keeps_id_and_source_readable(tmp_path)


def test_licensed_permit_body_and_unchanged_standalone_policy(tmp_path,monkeypatch):
 import test_policy_company_actions as previous
 monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_licensed_body_and_standalone_policy_preserve_scopes(tmp_path)
