"""Acquisition is a literal source claim, not proof of a shared permit or benefit."""
from datetime import datetime,timezone
from hashlib import sha256
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation,theme_presentation
from test_new_source_adapter import NOW

CAUSE='미국 HBM 수출 허가 취득으로'
TITLE='가상전자, '+CAUSE+' 생산 시작'

@pytest.mark.parametrize('text,action,phase',[
 (TITLE,'PRODUCTION_START','SOURCE_REPORTED'),
 (CAUSE+' 가상전자는 생산 시작','PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE.replace('미국 ',''),'PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE.replace('수출','수입'),'PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE.replace('수출','생산'),'PRODUCTION_START','SOURCE_REPORTED'),
 (TITLE+' 계획','PRODUCTION_START','PLANNED'),
 (TITLE.replace('취득으로','취득에 대비해'),'PRODUCTION_START','PLANNED'),
 (TITLE.replace('생산 시작','생산능력 확대'),'CAPACITY_ADDITION','SOURCE_REPORTED'),
 (TITLE.replace('생산 시작','공급계약 체결'),'CONTRACT','SOURCE_REPORTED'),
 (TITLE.replace('생산 시작','신규 공장 투자 결정'),'INVESTMENT','SOURCE_REPORTED'),
])
def test_acquisition_preserves_literal_cause_and_actor(text,action,phase):
 row,=extract_economic_changes(text)
 assert (row['action'],row['phase'],row['entity_ids'])==(action,phase,['가상전자'])
 assert row['policy_cause']['change']=='취득'
 assert row['policy_cause']['source_expression'] in text
 assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
 assert not row['verified_economic_effect']

@pytest.mark.parametrize('text',[
 TITLE+' 보도를 부인했다', TITLE+' 취소',
 CAUSE+' 그 회사는 생산 시작',CAUSE+' 생산 시작',
 TITLE.replace('생산 시작','DRAM 생산 시작'),
 TITLE.replace('미국','지난해 미국'),
 '가상전자, '+CAUSE+' 새빛소재는 생산 시작',
 TITLE.replace('생산 시작','일본 HBM 수출 허가 취득으로 생산 시작'),
 TITLE.replace('취득으로','미취득으로'),
 TITLE.replace('취득으로','취득 없이'),
])
def test_no_causal_borrowing_or_denied_acquisition(text):
 assert not any(r.get('policy_cause') for r in extract_economic_changes(text))


def test_approval_acquisition_and_other_permits_keep_distinct_ids(tmp_path):
 store=ThemeStore(tmp_path/'themes');events=[]
 for i,(actor,verb) in enumerate([('가상전자','취득'),('새빛소재','취득'),('가상전자','승인')]):
  text=f'{actor}, 미국 ‘첨단칩통제법’ HBM 수출 허가 {verb}으로 생산 시작'
  row,=extract_economic_changes(text)
  event=economic_observation(row,origin_reference=f'https://gov.example.org/{i}',source_url=f'https://gov.example.org/{i}',source_id='synthetic',source_available_at=NOW.isoformat())
  events.append(event)
 themes=store.ingest(events,now=datetime.now(timezone.utc))
 assert len(themes)==3 and len({e['event_id'] for e in events})==3
 assert sum('취득' in theme_presentation(t)['name'] for t in themes)==2
 assert len(store.search(query='수출허가 취득'))==2
 assert len(store.search(query='수출허가 승인'))==1


def test_separate_company_clauses_and_parallel_actions():
 rows=extract_economic_changes(TITLE+' 및 생산능력 확대')
 assert [r['action'] for r in rows]==['PRODUCTION_START','CAPACITY_ADDITION']
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 일본 HBM 수입 허가 승인으로 생산능력 확대')
 assert [(r['entity_ids'],r['policy_cause']['change']) for r in rows]==[(['가상전자'],'취득'),(['새빛소재'],'승인')]
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 HBM 생산능력 확대')
 assert len(rows)==2 and 'policy_cause' not in rows[1]


def test_saved_acquisition_period_search_company_evidence(tmp_path,monkeypatch):
 import test_permit_company_actions as previous
 monkeypatch.setattr(previous,'CAUSE',CAUSE);monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_saved_permit_through_period_search_and_company_evidence(tmp_path,monkeypatch)


def test_legacy_acquisition_record_preserved(tmp_path,monkeypatch):
 import test_policy_company_actions as previous
 monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_legacy_policy_record_keeps_id_and_source_readable(tmp_path)


def test_licensed_body_acquisition_source_link(tmp_path,monkeypatch):
 import test_policy_company_actions as previous
 monkeypatch.setattr(previous,'TITLE',TITLE)
 previous.test_licensed_body_and_standalone_policy_preserve_scopes(tmp_path)
