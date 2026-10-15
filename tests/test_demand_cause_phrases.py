"""Synthetic wording -> evidence-bound actions -> persisted multi-company theme."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from test_theme_emergence import T


@pytest.mark.parametrize('phrase,action,phase',[
    ('수요 급증으로','공급계약 체결','SOURCE_REPORTED'),
    ('수요 증가로','생산 시작','SOURCE_REPORTED'),
    ('수요 확대로 인해','생산능력 확대','SOURCE_REPORTED'),
    ('수요 급증으로 인해','신규 투자 결정','SOURCE_REPORTED'),
    ('수요 확대에 대비해','신규 투자 결정','PLANNED'),
    ('수요 증가에 대비하여','생산 시작 예정','PLANNED'),
])
def test_explicit_product_cause_and_source_stage(phrase,action,phase):
    text=f'가상전자, 광자냉각 {phrase} {action}'
    result=extract_economic_changes(text)
    assert len(result)==1
    assert result[0]['topic']=='광자냉각' and result[0]['economic_driver']=='DEMAND_EXPANSION'
    assert result[0]['entity_ids']==['가상전자'] and result[0]['phase']==phase
    assert result[0]['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
    assert result[0]['verified_economic_effect'] is False


@pytest.mark.parametrize('text',[
    '가상전자, 광자냉각 수요 급증으로 공급계약 체결 취소',
    '가상전자, 광자냉각 수요 급증으로 공급계약을 체결하지 않았다',
    '가상전자, 광자냉각 수요 급증으로 공급계약 체결 보도를 부인했다',
    '가상전자, 광자냉각 수요 확대에 대비해 생산 시작 계획을 철회했다',
    '가상전자, 광자냉각 수요 급증으로 공급계약이 체결되지 않았다',
    '가상전자, 광자냉각 수요 급증으로 공급계약 체결을 검토 중이다',
    '가상전자, 광자냉각 수요 급증으로 지난해 공급계약을 체결했다',
    '가상전자, 광자냉각 수요 급증으로 관심 증가. 새빛소재는 공급계약을 체결했다.',
    '가상전자, 광자냉각 수요 급증으로 가격이 상승했다',
    '가상전자, 광자냉각 수요 급증으로 기술 소개 행사를 개최했다',
    '가상전자, 광자냉각 및 양자유체 수요 급증으로 공급계약 체결',
    '가상전자, 광자냉각 수요 급증으로 양자유체 수요 확대로 공급계약 체결',
    '가상전자, 시장 수요 급증으로 공급계약 체결',
    '가상전자 수요 급증으로 공급계약 체결',
    '가상전자, 광자냉각 수요 확대에 대비하지 않은 공급계약 체결',
])
def test_denied_past_ambiguous_or_non_action_does_not_form_demand_event(text):
    assert extract_economic_changes(text)==[]


def test_known_topic_negation_and_company_name_are_not_common_causes():
    assert extract_economic_changes('가상전자, HBM 수요 급증으로 공급계약 체결 취소')==[]
    assert extract_economic_changes('다온 수요 급증으로 공급계약 체결',company_names=['다온'])==[]
    row=extract_economic_changes('가상전자, 노광장비 수요 급증으로 공급계약 체결')[0]
    assert row['topic']=='노광장비' and row['entity_ids']==['가상전자']


def test_demand_binds_following_action_not_earlier_production_mention():
    text='가상전자, HBM 생산 시작에 이어 광자냉각 수요 급증으로 공급계약 체결'
    row=extract_economic_changes(text)[0]
    assert row['topic']=='광자냉각' and row['action']=='CONTRACT'
    assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()


def test_three_companies_store_search_and_plan_remain_source_reported(tmp_path,capsys):
    from scripts.search_themes import main
    texts=[
        '가상전자, 광자냉각 수요 급증으로 공급계약 체결',
        '새빛소재, 광자냉각 수요 확대로 생산 시작',
        '미래장비, 광자냉각 수요 확대에 대비해 신규 투자 결정',
    ]
    events=[]
    for i,text in enumerate(texts):
        change=extract_economic_changes(text)[0];change['evidence_level']='REPORTED'
        events.append(economic_observation(change,origin_reference=f'https://example.org/{i}',
            source_url=f'https://example.org/{i}',source_id='synthetic',source_available_at=T.isoformat(),
            content_scope='RSS_TITLE_METADATA'))
    store=ThemeStore(tmp_path/'themes');first=store.ingest(events[:1],now=T)[0]
    at=T+timedelta(seconds=1);last=store.ingest(events[1:],now=at)[0]
    assert last['theme_id']==first['theme_id'] and last['status']=='EMERGING'
    assert last['scores']['distinct_economic_events']==3 and last['scores']['company_breadth']==3
    assert last['verified_beneficiary_count']==0
    assert {r['phase'] for r in last['source_refs']}=={'PLANNED','SOURCE_REPORTED'}
    assert store.search(as_of=T,now=at)==[first]
    copy=deepcopy(events[0]);copy['source_url']='https://press.example.org/reprint'
    with_copy=store.ingest([copy],now=at+timedelta(seconds=1))[0]
    assert with_copy['scores']['distinct_economic_events']==3
    assert store.ingest(events,now=at+timedelta(seconds=2))==[]
    before=(store.root/'themes.sqlite3').read_bytes()
    assert main(['--root',str(store.root),'--query','광자냉각','--company-candidates'])==0
    result=json.loads(capsys.readouterr().out)
    assert len(result['ThemeCandidates'])==1 and len(result['CompanyCandidates'])==3
    assert (store.root/'themes.sqlite3').read_bytes()==before


def test_saved_rss_analysis_reuses_pipeline_without_network(tmp_path):
    from test_feed_analysis import setup,run
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    info=setup(tmp_path,'가상전자, 광자냉각 수요 급증으로 공급계약 체결')
    report=run(info)
    assert report['source_fetch_calls']==0
    change=report['results'][0]['economic_changes'][0]
    assert change['topic']=='광자냉각' and change['evidence_level']=='REPORTED'
    path,digest=publish_feed_analysis(report,tmp_path/'reports')
    assert consume_feed_analysis(path,path.parent,digest)['results'][0]['economic_changes']==[change]
