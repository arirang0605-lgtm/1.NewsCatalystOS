"""Synthetic explicit company clauses through existing source-bound themes."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import pytest
from newscatalystos.economic_changes import company_clauses, extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from test_theme_emergence import T

MIXED='가상전자는 광자냉각 수요 급증으로 공급계약을 체결했고 새빛소재는 HBM 수요 확대로 생산을 시작했다.'

def test_distinct_company_cause_action_keeps_original_source():
    rows=extract_economic_changes(MIXED)
    assert [(r['entity_ids'],r['topic'],r['action']) for r in rows]==[
        (['가상전자'],'광자냉각','CONTRACT'),(['새빛소재'],'HBM','PRODUCTION_START')]
    assert {r['source_paragraph_sha256'] for r in rows}=={sha256(MIXED.encode()).hexdigest()}
    assert all(not r['verified_economic_effect'] for r in rows)


def test_joint_participants_are_one_event():
    text='가상전자와 새빛소재는 광자냉각 수요 급증으로 공급계약을 체결했다.'
    assert company_clauses(text)==[text]
    rows=extract_economic_changes(text)
    assert len(rows)==1 and rows[0]['entity_ids']==['가상전자','새빛소재']


@pytest.mark.parametrize('tail',[
    '그 회사는 광자냉각 수요 확대로 생산을 시작했다.',
    '광자냉각 수요 확대로 생산을 시작했다.',
    '그 회사는 HBM 수요 확대로 생산을 시작했다.',
    'HBM 생산을 시작했다.',
])
def test_unresolved_subject_does_not_borrow_actor(tail):
    assert extract_economic_changes('가상전자는 광자냉각 수요 급증으로 공급계약을 체결했고 '+tail)==[]


@pytest.mark.parametrize('first',[
    '지난해 광자냉각 수요 급증으로 공급계약을 체결했고',
    '광자냉각 수요 급증으로 공급계약 체결을 취소했고',
    '광자냉각 수요 급증으로 공급계약 체결을 부인했고',
    '광자냉각 수요 급증으로 공급계약 체결을 검토하고',
])
def test_local_past_denial_or_plan_does_not_poison_other_actor(first):
    rows=extract_economic_changes('가상전자는 '+first+' 새빛소재는 HBM 수요 확대로 생산을 시작했다.')
    second=next(r for r in rows if r['entity_ids']==['새빛소재'])
    assert second['phase']=='SOURCE_REPORTED'
    if '검토' in first:
        assert rows[0]['phase']=='PLANNED'
    else:assert len(rows)==1


def test_shared_denial_and_quoted_statement_are_not_split():
    denied=MIXED[:-1]+'는 해당 보도를 모두 부인했다.'
    assert company_clauses(denied)==[denied]
    assert extract_economic_changes(denied)==[]
    quoted='“'+MIXED+'”'
    assert company_clauses(quoted)==[quoted]
    assert extract_economic_changes(quoted)==[]


def test_directory_only_named_subjects_keep_separate_event_ids(tmp_path,capsys):
    from scripts.search_themes import main
    text='다온은 광자냉각 수요 급증으로 공급계약을 체결했고 라온은 광자냉각 수요 확대로 공급계약을 체결했다.'
    rows=extract_economic_changes(text,company_names=['다온','라온'])
    assert [r['entity_ids'] for r in rows]==[['다온'],['라온']]
    for row in rows:row['evidence_level']='REPORTED'
    events=[economic_observation(r,origin_reference='https://example.org/clauses',
        source_url='https://example.org/clauses',source_id='synthetic',source_available_at=T.isoformat(),
        content_scope='RSS_TITLE_METADATA') for r in rows]
    assert len({e['event_id'] for e in events})==2
    store=ThemeStore(tmp_path/'themes')
    first=store.ingest(events[:1],now=T)[0]
    at=T+timedelta(seconds=1)
    last=store.ingest(events[1:],now=at)[0]
    assert last['scores']['company_breadth']==2 and last['scores']['distinct_economic_events']==2
    assert store.search(as_of=T,now=at)==[first]
    assert store.ingest(events,now=at+timedelta(seconds=1))==[]
    copy=dict(events[0],source_url='https://example.org/reprint')
    assert store.ingest([copy],now=at+timedelta(seconds=2))[0]['scores']['distinct_economic_events']==2
    before=(store.root/'themes.sqlite3').read_bytes()
    assert main(['--root',str(store.root),'--query','광자냉각','--company-candidates'])==0
    result=json.loads(capsys.readouterr().out)
    assert len(result['CompanyCandidates'])==2
    assert (store.root/'themes.sqlite3').read_bytes()==before


def test_rss_identity_does_not_merge_clauses_and_saved_title_sha(tmp_path,monkeypatch):
    from test_feed_analysis import setup,run
    from test_feed_company_identity import directory
    from test_article_company_identity import context
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    title=MIXED.replace('새빛소재','별빛공업').replace(' HBM','  HBM')
    info=setup(tmp_path,title)
    config=directory(tmp_path,monkeypatch,{'a':context(datetime.now(timezone.utc),'별빛공업')})
    report=run(info,company_identity_config=config)
    row=report['results'][0]
    assert [(r['entity_ids'],r['topic']) for r in row['economic_changes']]==[
        (['가상전자'],'광자냉각'),(['별빛공업'],'HBM')]
    assert all(r['source_paragraph_sha256']==sha256(title.encode()).hexdigest() for r in row['economic_changes'])
    assert all(r['evidence_level']=='REPORTED' for r in row['economic_changes'])
    path,digest=publish_feed_analysis(report,tmp_path/'reports')
    assert consume_feed_analysis(path,path.parent,digest)['results']==report['results']


@pytest.mark.parametrize('first',[
    '광자냉각 수요 급증으로 공급계약 체결을 취소했고',
    '광자냉각 수요 급증으로 공급계약 체결을 추진하고',
])
def test_rss_clause_local_denial_and_plan(tmp_path,first):
    from test_feed_analysis import setup,run
    row=run(setup(tmp_path,'가상전자는 '+first+' 새빛소재는 HBM 수요 확대로 생산을 시작했다.'))['results'][0]
    rows=row['economic_changes']
    assert next(r for r in rows if r['entity_ids']==['새빛소재'])['phase']=='SOURCE_REPORTED'
    if '취소' in first:assert len(rows)==1
    else:assert rows[0]['phase']=='PLANNED'
