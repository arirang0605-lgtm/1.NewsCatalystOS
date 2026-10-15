"""Explicit service function phrases; synthetic inputs except title regression."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from newscatalystos.economic_changes import business_start_functions, extract_economic_changes
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.standard_delivery import build_theme_bundle, read_theme_bundle
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from scripts import run_feed_analysis
from test_feed_analysis import setup, run
from test_federated_news_search import fingerprint


@pytest.mark.parametrize('title,topic', [
    ('가상회사, AI 기반 정부지원사업 맞춤 추천 서비스 출시', '정부지원사업 맞춤 추천'),
    ('가상회사, 인공지능 기반 문서 자동 번역 서비스를 시작했다', '문서 자동 번역'),
    ('가상회사, 지역 음식점 검색 서비스 정식 개시', '지역 음식점 검색'),
    ('문서 분석 서비스 출시', '문서 분석'),
])
def test_explicit_service_object_and_function_become_individual_topic(tmp_path,title,topic):
    row=run(setup(tmp_path,title))['results'][0]
    assert row['category_candidate']=='BUSINESS_START'
    assert row['economic_changes'][0]['topic']==topic
    assert row['economic_changes'][0]['economic_driver']=='UNKNOWN'
    assert row['economic_changes'][0]['evidence_level']=='REPORTED'
    assert topic in [f['value'] for f in row['source_matched_fields']]
    assert not row['ai_eligible'] and not row['verified_beneficiary']


@pytest.mark.parametrize('title', [
    '가상회사, 신규 서비스 출시', '가상회사, AI 서비스 출시',
    '가상회사, AI 기반 맞춤 추천 서비스 출시', '가상회사, 통합 분석 서비스 출시',
    '가상회사, 문서 분석 서비스 출시 기념 행사',
    '가상회사, 문서 분석 서비스 출시 취소',
    '가상회사, 문서 분석 서비스 출시를 위한 협약 체결',
    '지난해 문서 분석 서비스 출시', '문서 분석 서비스를 출시하지 않았다',
    '문서 분석 소개. 신규 서비스 출시',
    '문서 분석 소개, 신규 서비스 출시',
    '수요 증가를 가정한 문서 분석 서비스 출시',
    '수요가 늘어난다는 가정 하에 문서 분석 서비스 출시',
])
def test_generic_negative_historical_and_cross_sentence_context_do_not_make_topic(title):
    assert extract_economic_changes(title)==[]


def test_plan_and_existing_brand_priority_are_preserved():
    c=extract_economic_changes('가상회사, 문서 분석 서비스 출시 예정')[0]
    assert c['phase']=='PLANNED'
    assert extract_economic_changes('가상회사, 문서 분석 서비스 ‘종이길’ 출시')[0]['topic']=='종이길'
    assert extract_economic_changes('가상회사, HBM 검사 서비스 개시')[0]['topic']=='HBM'


def test_saved_title_regression_to_theme_dashboard_export_and_replay(tmp_path):
    # Public RSS headline only; no article body or new source request.
    title='NICE평가정보, AI 기반 정부지원사업 맞춤 추천 서비스 출시'
    info=setup(tmp_path,title); source=info[0]
    work=tmp_path/'analysis/core'; theme_root=tmp_path/'themes'
    options=run_feed_analysis.parser().parse_args([
        '--registry',str(source.registry_path),'--inbox-root',str(source.inbox_root),
        '--state',str(source.poll_state),'--analysis-root',str(work),'--theme-root',str(theme_root)])
    before=fingerprint(source.inbox_root.parent)
    at=datetime.now(timezone.utc)
    code,report=run_feed_analysis.evaluate(options,now=at)
    assert code==0 and report['theme_versions_created']==1
    row=report['results'][0]
    assert row['economic_changes'][0]['entity_ids']==[]  # no fabricated issuer ID
    path=Path(report['private_report_file'])
    assert consume_feed_analysis(path,path.parent,report['report_sha256'],now=at)['results']==report['results']
    cards,stats=scan_saved_analysis(work.parent,now=at)
    assert stats['saved_reports_skipped']==0
    assert cards[0]['source_products']==['정부지원사업 맞춤 추천']
    store=ThemeStore(theme_root); themes=store.search(query='정부지원사업',now=at)
    assert len(themes)==1 and themes[0]['status']=='CANDIDATE'
    assert themes[0]['verified_beneficiary_count']==0
    raw=build_theme_bundle(themes,decision_at=at,now=at)
    assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)['ThemeCandidates']==themes
    assert not store.search(as_of=at-timedelta(seconds=1),now=at)
    assert run_feed_analysis.evaluate(options,now=at+timedelta(seconds=1))[1]['theme_versions_created']==0
    assert fingerprint(source.inbox_root.parent)==before


def test_shared_ai_or_function_phrase_does_not_assert_shared_demand(tmp_path):
    at=datetime.now(timezone.utc)
    rows=[]
    for n,title in enumerate(['가상회사, AI 기반 문서 분석 서비스 출시',
                              '다른회사, AI 기반 문서 분석 서비스 출시',
                              '또다른회사, AI 기반 음식점 추천 서비스 출시']):
        change=extract_economic_changes(title)[0]
        change['evidence_level']='REPORTED'
        for copy in range(2):
            rows.append(economic_observation(change,origin_reference=f'https://example.org/{n}/{copy}',
                source_url=f'https://example.org/{n}/{copy}',source_id='synthetic',
                source_available_at=at.isoformat(),content_scope='RSS_TITLE_METADATA'))
    themes=ThemeStore(tmp_path/'themes').ingest(rows,now=at)
    assert len(themes)==3
    assert all(t['status']=='CANDIDATE' and t['scores']['distinct_economic_events']==1 for t in themes)
