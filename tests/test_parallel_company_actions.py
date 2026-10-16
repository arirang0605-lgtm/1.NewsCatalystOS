"""Explicit nominal action lists, synthetic sources and immutable past results."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json

import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.company_evidence import company_evidence
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle
from test_feed_analysis import setup,run
from test_order_growth import observation
from test_federated_news_search import fingerprint

TITLE='가상전자, HBM 수요 증가로 공급계약 체결 및 신규 투자 결정'


@pytest.mark.parametrize(('tail','actions'),[
    ('공급계약 체결 및 신규 투자 결정',['CONTRACT','INVESTMENT']),
    ('신규 투자 결정 및 공급계약 체결',['INVESTMENT','CONTRACT']),
    ('생산 시작 및 생산능력 확대',['PRODUCTION_START','CAPACITY_ADDITION']),
    ('생산능력 확대 및 공급계약 체결',['CAPACITY_ADDITION','CONTRACT']),
    ('공급계약을 체결 및 생산을 시작했다',['CONTRACT','PRODUCTION_START']),
    ('공급계약 체결 및 신규 투자 결정 및 생산 시작',['CONTRACT','INVESTMENT','PRODUCTION_START']),
    ('공급계약 체결 및 공급계약 체결',['CONTRACT']),
])
def test_distinct_nominal_actions_and_same_action_dedup(tail,actions):
    text='가상전자, HBM 수요 증가로 '+tail
    rows=extract_economic_changes(text)
    assert [r['action'] for r in rows]==actions
    assert all(r['entity_ids']==['가상전자'] and r['economic_driver']=='DEMAND_EXPANSION' for r in rows)
    assert all(r['phase']=='SOURCE_REPORTED' and r['verified_economic_effect'] is False for r in rows)
    assert {r['source_paragraph_sha256'] for r in rows}=={sha256(text.encode()).hexdigest()}


@pytest.mark.parametrize('text',[
    TITLE+' 예정',TITLE+' 계획',TITLE+' 전망',TITLE+' 취소',TITLE+' 보도를 부인했다',
    '가상전자, HBM 수요 증가로 공급계약 체결 및 지난해 신규 투자 결정',
    '가상전자, HBM 수요 증가로 공급계약 체결 및 신규 투자 결정을 검토 중이다',
    '가상전자, HBM 수요 증가로 공급계약 체결 및 새빛소재는 신규 투자 결정',
    '가상전자, HBM 수요 증가로 공급계약 체결 및 그 회사는 신규 투자 결정',
    '가상전자, HBM 수요 증가로 공급계약 체결 및 DRAM 수요 확대로 신규 투자 결정',
    '가상전자, HBM 수요 증가로 공급계약 체결 및 DRAM 생산 시작',
    '가상전자, HBM 수요 증가로 공급계약 체결 및 신규 투자 결정에 관한 설명회 개최',
    'HBM 수요 증가로 공급계약 체결 및 신규 투자 결정',
    '가상전자, HBM 수요 증가로 공급계약 체결했고 신규 투자 결정',
])
def test_ambiguous_scope_does_not_invent_parallel_events(text):
    assert extract_economic_changes(text)==[]


def test_clause_boundaries_joint_subject_and_alias():
    text=TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 DRAM 주문 증가로 생산 시작 및 생산능력 확대'
    rows=extract_economic_changes(text)
    assert [(r['entity_ids'],r['topic'],r['action']) for r in rows]==[
        (['가상전자'],'HBM','CONTRACT'),(['가상전자'],'HBM','INVESTMENT'),
        (['새빛소재'],'DRAM','PRODUCTION_START'),(['새빛소재'],'DRAM','CAPACITY_ADDITION')]
    rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자와 새빛소재는'))
    assert len(rows)==2 and all(r['entity_ids']==['가상전자','새빛소재'] for r in rows)
    rows=extract_economic_changes(TITLE.replace('HBM 수요','광자냉각(PCX) 주문'))
    assert len(rows)==2 and all(r['topic_alias_evidence']['canonical_topic']=='광자냉각' for r in rows)


def test_existing_single_action_identity_and_shared_planning_cause():
    for text in [TITLE,'가상전자, HBM 수요 증가로 공급계약 체결',
                 '가상전자, HBM 수요 증가로 공급계약 체결 및 생산능력 확대',
                 '가상전자, HBM 수요 확대에 대비해 공급계약 체결 및 신규 투자 결정']:
        old=extract_economic_changes(text,include_parallel_actions=False)[0]
        rows=extract_economic_changes(text)
        assert old in rows
    assert all(r['phase']=='PLANNED' for r in rows)


def case(tmp_path):
    info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at);row=report['results'][0]
    root=tmp_path/'reports';docs=tmp_path/'documents'
    path,pin=publish_feed_analysis(report,root/'core/reports')
    assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==row['economic_changes']
    old=extract_economic_changes(TITLE,include_parallel_actions=False)[0];old['evidence_level']='REPORTED'
    old_event=observation(row,old)
    store=ThemeStore(docs/'theme_history');first=store.ingest([old_event],now=at)[0]
    events=[observation(row,c) for c in row['economic_changes']]
    later=at+timedelta(seconds=1);theme=store.ingest(events,now=later)[0]
    args=dict(reports_root=root,document_root=docs,feeds=[dict(registry=info[0].registry_path,
        inbox=info[0].inbox_root,state=info[0].poll_state)],as_of=later,now=later+timedelta(seconds=1))
    return theme,args,store,events,first,at,old_event


def test_saved_analysis_search_company_evidence_and_counts(tmp_path):
    theme,args,store,events,first,at,old=case(tmp_path)
    assert old['event_id'] in theme['event_ids'] and old['event_id'] in {e['event_id'] for e in events}
    assert theme['theme_id']==first['theme_id'] and theme['status']=='CANDIDATE'
    assert theme['scores']['distinct_economic_events']==2
    assert theme['scores']['company_breadth']==theme['scores']['distinct_claim_origins']==1
    assert store.search(as_of=at,now=args['now'])==[first]
    assert store.ingest(events,now=args['now'])==[]
    assert len(store.search(query='가상전자',as_of=args['as_of'],now=args['now']))==1
    before=fingerprint(tmp_path)
    items=company_evidence(theme,'가상전자',**args)['items']
    assert {i['action'] for i in items}=={'CONTRACT','INVESTMENT'}
    assert all(i['status']=='READY' and i['excerpt']==TITLE for i in items)
    assert len({i['evidence_sha256'] for i in items})==1
    data=json.loads(build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
    assert len(data['CompanyCandidates'])==1 and data['CompanyCandidates'][0]['verified_real_benefit'] is False
    assert fingerprint(tmp_path)==before


def test_old_planned_snapshot_evidence_stays_readable(tmp_path):
    text=TITLE+' 예정';info=setup(tmp_path,text);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at);row=report['results'][0]
    old=extract_economic_changes(text,include_parallel_actions=False)[0];old['evidence_level']='REPORTED'
    row['economic_changes']=[old]
    reports=tmp_path/'reports';docs=tmp_path/'documents'
    publish_feed_analysis(report,reports/'core/reports')
    store=ThemeStore(docs/'theme_history');theme=store.ingest([observation(row,old)],now=at)[0]
    before=fingerprint(tmp_path)
    result=company_evidence(theme,'가상전자',reports_root=reports,document_root=docs,as_of=at,now=at,
        feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])
    assert result['items'][0]['status']=='READY' and result['items'][0]['phase']=='PLANNED'
    assert fingerprint(tmp_path)==before


def test_permitted_body_uses_same_actions(tmp_path):
    from test_motir_document_analysis import case as body_case
    from newscatalystos.motir_document_analysis import analyze_motir_document
    source,opts=body_case(tmp_path,body=(TITLE+'. 추가 근거는 미확인이다. ')*3)
    report=analyze_motir_document(**opts)
    assert {c['action'] for c in report['economic_changes']}=={'CONTRACT','INVESTMENT'}
