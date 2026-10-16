"""Synthetic order cause -> existing source analysis, themes and company evidence."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.company_evidence import company_evidence
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.standard_delivery import build_theme_bundle
from test_feed_analysis import setup,run
from test_federated_news_search import collect,GOV,fingerprint
from test_new_source_adapter import NOW


@pytest.mark.parametrize(('phrase','action'),[
    ('주문 증가로','공급계약 체결'),('주문 급증으로 인해','생산 시작'),
    ('주문 확대에 따라','생산능력 확대'),('주문 증가에 대응해','신규 투자 결정'),
    ('주문 급증에 힘입어','생산 개시'),('주문 증가에 대응하여','생산능력 증설'),
    ('주문이 증가해','생산 시작'),('주문이 급증하여','공급계약 체결'),
])
def test_explicit_order_cause(phrase,action):
    text=f'가상전자, HBM {phrase} {action}'
    row=extract_economic_changes(text)[0]
    assert row['economic_driver']=='DEMAND_EXPANSION' and row['entity_ids']==['가상전자']
    assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
    assert row['phase']=='SOURCE_REPORTED' and row['verified_economic_effect'] is False


@pytest.mark.parametrize('text',[
    '가상전자, HBM 주문 증가',
    '가상전자, HBM 주문 증가로 가격 상승',
    '가상전자, HBM 주문 증가 전망으로 생산 시작',
    '가상전자, HBM 주문 증가 예상으로 공급계약 체결',
    '가상전자, HBM 주문 급증으로 공급계약 체결 취소',
    '가상전자, HBM 주문 급증으로 생산을 시작하지 않았다',
    '가상전자, HBM 주문 급증으로 생산능력 확대 보도를 부인했다',
    '가상전자, 지난해 HBM 주문 증가로 생산 시작',
    '가상전자, HBM 주문 증가로 지난달 생산 시작',
    '가상전자, HBM 주문 증가로 생산능력 확대를 검토 중이다',
    '가상전자, HBM 주문 증가로 DRAM 수요 확대로 생산 시작',
    '가상전자, HBM 주문 증가로 DRAM 주문 증가로 생산 시작',
    '가상전자, HBM 및 DRAM 주문 증가로 생산 시작',
    '가상전자, 시장 주문 증가로 HBM 생산 시작',
    '가상전자 주문 증가로 HBM 공급계약 체결',
    '가상전자는 HBM 주문 증가로 새빛소재는 생산 시작',
    '가상전자, HBM 주문 증가로 생산 시작했고 그 회사는 DRAM 주문 증가로 공급계약 체결',
])
def test_no_invented_action_or_cause(text):
    assert extract_economic_changes(text)==[]


@pytest.mark.parametrize('text',[
    '가상전자, HBM 주문 확대에 대비해 생산 시작',
    '가상전자, HBM 주문 증가로 생산 시작 계획',
    '가상전자, HBM 주문 증가로 생산능력 확대 추진',
])
def test_plans_are_kept_separate(text):
    row=extract_economic_changes(text)[0]
    assert row['economic_driver']=='DEMAND_EXPANSION' and row['phase']=='PLANNED'


def test_clause_scope_joint_subject_and_local_alias():
    rows=extract_economic_changes('가상전자는 HBM 주문 증가로 공급계약을 체결했고 새빛소재는 DRAM 주문 증가로 생산을 시작했다')
    assert [(r['entity_ids'],r['topic']) for r in rows]==[(['가상전자'],'HBM'),(['새빛소재'],'DRAM')]
    row=extract_economic_changes('가상전자와 새빛소재는 HBM 주문 증가로 공급계약 체결')[0]
    assert row['entity_ids']==['가상전자','새빛소재']
    row=extract_economic_changes('가상전자, 광자냉각(PCX) 주문 증가로 공급계약 체결')[0]
    assert row['topic_alias_evidence']['canonical_topic']=='광자냉각'
    row=extract_economic_changes('가상전자, HBM 생산 시작에 이어 광자냉각 주문 증가로 공급계약 체결')[0]
    assert row['topic']=='광자냉각' and row['action']=='CONTRACT'


def observation(row,change):
    return economic_observation(change,origin_reference=row['source_url'],source_url=row['source_url'],
        source_id=row['provider_id'],source_available_at=row['source_available_at'],content_scope='RSS_TITLE_METADATA',
        source_binding={'source_event_sha256':row['source_event_sha256'],'document_sha256':row['source_title_sha256']})


def case(tmp_path):
    titles=['가상전자, HBM 주문 증가로 공급계약 체결',
            '새빛소재, HBM 주문 확대에 따라 생산 시작',
            '미래장비, HBM 주문 급증으로 생산능력 확대']
    info=setup(tmp_path,titles[0])
    collect(info[0],info[1],GOV,[(f'order-{i}',t,f'https://gov.example.org/order-{i}') for i,t in enumerate(titles[1:],1)],at=NOW+timedelta(hours=1))
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at)
    root=tmp_path/'reports';docs=tmp_path/'documents'
    publish_feed_analysis(report,root/'core/reports')
    events=[observation(r,c) for r in report['results'] for c in r['economic_changes']]
    store=ThemeStore(docs/'theme_history');first=store.ingest(events[:1],now=at)[0]
    later=at+timedelta(seconds=1);theme=store.ingest(events[1:],now=later)[0]
    args=dict(reports_root=root,document_root=docs,feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)],as_of=later,now=later+timedelta(seconds=1))
    return theme,args,store,report,events,first,at


def test_saved_analysis_three_companies_search_evidence_and_pit(tmp_path):
    theme,args,store,report,events,first,at=case(tmp_path)
    assert report['source_fetch_calls']==report['new_ai_results']==report['semantic_ai_attempts']==0
    assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==3
    assert theme['scores']['company_breadth']==3 and theme['verified_beneficiary_count']==0
    assert store.search(as_of=at,now=args['now'])==[first]
    assert store.ingest(events,now=args['now'])==[]
    assert len(store.search(query='HBM',as_of=args['as_of'],now=args['now']))==1
    before=fingerprint(tmp_path)
    for name in ['가상전자','새빛소재','미래장비']:
        items=company_evidence(theme,name,**args)['items']
        assert len(items)==1 and items[0]['status']=='READY'
        assert name in items[0]['excerpt'] and '주문' in items[0]['excerpt']
    data=json.loads(build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
    assert len(data['CompanyCandidates'])==3
    assert all(c['verified_real_benefit'] is False for c in data['CompanyCandidates'])
    assert fingerprint(tmp_path)==before


def test_old_saved_event_and_evidence_are_not_reclassified(tmp_path):
    text='가상전자, HBM 주문 증가로 공급계약 체결'
    info=setup(tmp_path,text);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at);row=report['results'][0]
    old=extract_economic_changes(text,include_order_growth=False)[0];old['evidence_level']='REPORTED'
    row['economic_changes']=[old]
    reports=tmp_path/'reports';docs=tmp_path/'documents'
    publish_feed_analysis(report,reports/'core/reports')
    store=ThemeStore(docs/'theme_history');theme=store.ingest([observation(row,old)],now=at)[0]
    before=fingerprint(tmp_path)
    args=dict(reports_root=reports,document_root=docs,as_of=at,now=at+timedelta(seconds=1),
        feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])
    item=company_evidence(theme,'가상전자',**args)['items'][0]
    assert item['status']=='READY' and item['economic_driver']=='UNKNOWN'
    assert store.search(as_of=at,now=args['now'])==[theme]
    assert fingerprint(tmp_path)==before


def test_permitted_body_uses_same_order_rule(tmp_path):
    from test_motir_document_analysis import case as body_case
    from newscatalystos.motir_document_analysis import analyze_motir_document
    source,opts=body_case(tmp_path,body='가상전자, HBM 주문 증가로 공급계약 체결. 추가 근거는 미확인이다. '*3)
    report=analyze_motir_document(**opts)
    assert report['economic_changes'][0]['economic_driver']=='DEMAND_EXPANSION'
