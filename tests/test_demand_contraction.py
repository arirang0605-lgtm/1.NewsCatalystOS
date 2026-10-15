"""Synthetic demand contraction -> existing reduction action -> theme output."""
from datetime import timedelta
from hashlib import sha256
import json
import threading
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from test_theme_emergence import T

@pytest.mark.parametrize('phrase',[
    'HBM 수요 감소로 생산을 축소했다',
    'HBM 수요 급감으로 인해 공급을 중단했다',
    'HBM 주문 축소에 따라 감산을 결정했다',
    'HBM 주문이 감소해 생산을 축소했다',
    'HBM 수요 감소에 대응해 감산을 실시했다',
])
def test_explicit_cause_is_not_supply_contraction(phrase):
    text='가상전자, '+phrase
    row=extract_economic_changes(text)[0]
    assert (row['topic'],row['economic_driver'],row['action'])==('HBM','DEMAND_CONTRACTION','SUPPLY_REDUCTION')
    assert row['entity_ids']==['가상전자'] and row['phase']=='SOURCE_REPORTED'
    assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
    assert row['verified_economic_effect'] is False

@pytest.mark.parametrize('text',[
    '가상전자, HBM 수요 감소로 주가 하락',
    '가상전자, HBM 주문 축소로 가격 하락',
    '가상전자, HBM 수요 감소 전망으로 감산을 결정했다',
    '가상전자, HBM 수요 감소로 감산 가능성',
    '가상전자, HBM 수요 감소로 지난해 생산을 축소했다',
    '가상전자, HBM 주문 축소로 작년 감산을 결정했다',
    '가상전자, HBM 수요 감소로 생산을 축소하지 않았다',
    '가상전자, HBM 주문 축소로 감산 결정을 철회했다',
    '가상전자, HBM 수요 감소로 감산 결정 보도를 부인했다',
    '가상전자, HBM 수요 감소로 생산 축소를 검토 중이다',
    '가상전자, HBM 수요 감소로 DRAM 수요 급감으로 생산을 축소했다',
    '가상전자, HBM 수요 감소로 감산을 결정했고 그 회사는 DRAM 수요 감소로 공급을 중단했다',
    '가상전자, 자동차 수요 감소로 생산을 축소했다',
])
def test_non_actions_ambiguous_or_unrealized_claims_are_not_events(text):
    assert extract_economic_changes(text)==[]

@pytest.mark.parametrize('text',[
    '가상전자, HBM 수요 감소에 대비해 생산 축소 예정',
    '가상전자, HBM 주문 축소로 감산을 추진했다',
])
def test_plan_is_not_observed_reduction(text):
    row=extract_economic_changes(text)[0]
    assert row['economic_driver']=='DEMAND_CONTRACTION' and row['phase']=='PLANNED'


def test_unconnected_supply_cause_and_expansion_keep_their_keys():
    for text,driver in [
        ('가상전자, HBM 공급을 중단했다','SUPPLY_CONTRACTION'),
        ('가상전자, HBM 수요 감소. HBM 생산을 축소했다','SUPPLY_CONTRACTION'),
        ('가상전자, HBM 수요 감소와 공급 축소를 발표했다','SUPPLY_CONTRACTION'),
        ('가상전자, HBM 수요 증가로 공급계약 체결','DEMAND_EXPANSION'),
    ]:
        row=extract_economic_changes(text)[0]
        assert row['economic_driver']==driver


def test_joint_and_separate_company_causes():
    joint=extract_economic_changes('가상전자와 새빛소재는 HBM 수요 감소로 감산을 결정했다')
    assert len(joint)==1 and joint[0]['entity_ids']==['가상전자','새빛소재']
    rows=extract_economic_changes('가상전자는 HBM 수요 감소로 감산을 결정했고 새빛소재는 DRAM 수요 증가로 공급계약을 체결했다')
    assert [(r['entity_ids'],r['economic_driver'],r['topic']) for r in rows]==[
        (['가상전자'],'DEMAND_CONTRACTION','HBM'),(['새빛소재'],'DEMAND_EXPANSION','DRAM')]


def observation(text,n):
    row=extract_economic_changes(text)[0];row['evidence_level']='REPORTED'
    return economic_observation(row,origin_reference=f'https://example.org/{n}',
        source_url=f'https://example.org/{n}',source_id='synthetic',source_available_at=T.isoformat(),
        content_scope='RSS_TITLE_METADATA')


def test_same_cause_persistence_search_dashboard_and_pit(tmp_path,capsys):
    from scripts.search_themes import main
    from scripts.open_research_dashboard import DashboardServer
    docs=tmp_path/'documents';store=ThemeStore(docs/'theme_history')
    old=observation('가상전자, HBM 공급을 중단했다',0)
    first=store.ingest([old],now=T)[0]
    events=[observation(text,i+1) for i,text in enumerate([
        '가상전자, HBM 수요 감소로 생산을 축소했다',
        '새빛소재, HBM 주문 축소에 따라 공급을 중단했다',
        '미래장비, HBM 수요 급감으로 감산을 결정했다'])]
    at=T+timedelta(seconds=1);new=store.ingest(events,now=at)[0]
    assert new['theme_id']!=first['theme_id'] and new['status']=='EMERGING'
    assert new['scores']['distinct_economic_events']==new['scores']['company_breadth']==3
    assert new['provisional_name']=='HBM · 수요·주문 축소'
    assert store.search(as_of=T,now=at)==[first]
    assert store.ingest(events,now=at+timedelta(seconds=1))==[]
    copy=dict(events[0],source_url='https://example.org/reprint')
    assert store.ingest([copy],now=at+timedelta(seconds=2))[0]['scores']['distinct_economic_events']==3
    before=(store.root/'themes.sqlite3').read_bytes()
    assert main(['--root',str(store.root),'--query','수요·주문 축소','--company-candidates'])==0
    bundle=json.loads(capsys.readouterr().out)
    assert len(bundle['ThemeCandidates'])==1 and len(bundle['CompanyCandidates'])==3
    assert all(c['verified_real_benefit'] is False and c['investment_merit']=='NOT_ASSESSED' for c in bundle['CompanyCandidates'])
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/themes?company_candidates=1') as response: data=json.load(response)
        candidate=next(r for r in data['ThemeCandidates'] if r['theme_id']==new['theme_id'])
        assert candidate['provisional_name']=='HBM · 수요·주문 축소'
        assert {r['economic_driver'] for r in candidate['source_refs']}=={'DEMAND_CONTRACTION'}
        assert {r['action'] for r in candidate['source_refs']}=={'SUPPLY_REDUCTION'}
    finally:server.shutdown();server.server_close();worker.join(2)
    assert (store.root/'themes.sqlite3').read_bytes()==before


def test_saved_rss_report_delivers_contraction_without_paid_calls(tmp_path):
    from test_feed_analysis import setup,run
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    report=run(setup(tmp_path,'가상전자, HBM 수요 감소로 감산을 결정했다'))
    assert report['source_fetch_calls']==0
    row=report['results'][0]['economic_changes'][0]
    assert row['economic_driver']=='DEMAND_CONTRACTION' and row['evidence_level']=='REPORTED'
    path,digest=publish_feed_analysis(report,tmp_path/'reports')
    assert consume_feed_analysis(path,path.parent,digest)['results']==report['results']

@pytest.mark.parametrize('text',[
    '가상전자, HBM 지난해 감산을 실시했다',
    '가상전자, HBM 감산 결정을 철회했다',
    '가상전자, HBM 감산 실시 전망',
])
def test_standalone_reduction_word_does_not_create_past_or_denied_event(text):
    assert extract_economic_changes(text)==[]


def test_standalone_plan_does_not_invent_a_demand_cause():
    row=extract_economic_changes('가상전자, HBM 감산을 추진했다')[0]
    assert row['phase']=='PLANNED' and row['economic_driver']=='SUPPLY_CONTRACTION'
