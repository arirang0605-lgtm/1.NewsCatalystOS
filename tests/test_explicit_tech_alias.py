"""Explicit source-local technology definitions, no global acronym guessing."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import pytest
from newscatalystos.economic_changes import extract_economic_changes,explicit_topic_aliases
from newscatalystos.theme_emergence import ThemeStore,economic_observation,validate_change
from newscatalystos.source_share import SourceShareError
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from test_theme_emergence import T

PAIR='광자냉각(PCX)'
FIRST='가상전자, 광자냉각 수요 증가로 공급계약 체결'
SECOND='새빛소재, 광자냉각(PCX) 수요 증가로 생산 시작'
THIRD='미래장비, 광자냉각(PCX) 기술의 PCX 수요 증가로 투자 결정'


def event(text,n=1):
    change=extract_economic_changes(text)[0];change['evidence_level']='REPORTED'
    return economic_observation(change,origin_reference=f'https://example.org/{n}',
        source_url=f'https://example.org/{n}',source_id='synthetic',source_available_at=T.isoformat(),
        content_scope='RSS_TITLE_METADATA')


def test_literal_definition_and_existing_event_identity():
    direct=extract_economic_changes(SECOND)[0]
    assert direct['topic']=='광자냉각'
    assert direct['source_paragraph_sha256']==sha256(SECOND.encode()).hexdigest()
    proof=direct['topic_alias_evidence']
    assert proof['expression_sha256']==sha256(PAIR.encode()).hexdigest()
    assert proof['source_expression']==PAIR
    later=event(THIRD)
    assert later['change']['topic']=='PCX'
    original=deepcopy(later['change']);del original['topic_alias_evidence']
    baseline=economic_observation(original,**{k:v for k,v in later.items() if k not in {'change','event_id'}})
    assert later['event_id']==baseline['event_id']


def test_multi_company_theme_search_pit_and_duplicate_count(tmp_path,capsys):
    from scripts.search_themes import main
    store=ThemeStore(tmp_path/'themes')
    first=store.ingest([event(FIRST)],now=T)[0]
    at=T+timedelta(seconds=1)
    after=store.ingest([event(SECOND,2),event(THIRD,3)],now=at)[0]
    assert after['theme_id']==first['theme_id'] and after['status']=='EMERGING'
    assert after['scores']['distinct_economic_events']==3 and after['scores']['company_breadth']==3
    assert after['topic_aliases']==['광자냉각','PCX']
    assert store.search(query='PCX',as_of=T,now=at)==[]
    assert store.search(as_of=T,now=at)==[first]
    assert store.search(query='PCX',now=at)==[after]
    copy=dict(event(SECOND,2),source_url='https://example.org/reprint')
    assert store.ingest([copy],now=at+timedelta(seconds=1))[0]['scores']['distinct_economic_events']==3
    assert store.ingest([event(SECOND,2)],now=at+timedelta(seconds=2))==[]
    before=(store.root/'themes.sqlite3').read_bytes()
    assert main(['--root',str(store.root),'--query','PCX','--company-candidates'])==0
    bundle=json.loads(capsys.readouterr().out)
    assert len(bundle['ThemeCandidates'])==1 and len(bundle['CompanyCandidates'])==3
    assert (store.root/'themes.sqlite3').read_bytes()==before
    raw=build_theme_bundle([after],decision_at=at,now=at,include_company_candidates=True)
    assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)['ThemeCandidates']==[after]


def test_other_document_bare_acronym_and_conflicting_meaning_stay_separate(tmp_path):
    store=ThemeStore(tmp_path/'themes')
    rows=store.ingest([event(SECOND),event('다온전자, PCX 수요 증가로 공급계약 체결',2),
        event('가온장비, 양자유체(PCX) 수요 증가로 생산 시작',3)],now=T)
    assert len(rows)==3
    assert {r['scores']['distinct_economic_events'] for r in rows}=={1}


@pytest.mark.parametrize('text',[
    '가상전자, 광자냉각(PCX)과 양자유체(PCX) 기술의 PCX 수요 증가로 공급계약 체결',
    '가상전자, 광자냉각(PCX)과 광자냉각(QCX) 기술의 PCX 수요 증가로 공급계약 체결',
    '가상전자, 광자냉각(HBM) 기술의 HBM 수요 증가로 공급계약 체결',
    '가상전자, 새빛전자(PCX) 수요 증가로 공급계약 체결',
    '가상전자, 광자냉각(PCX) 수요 증가로 공급계약 체결 취소',
    '가상전자, 광자냉각(PCX) 수요 증가로 지난해 공급계약 체결',
])
def test_ambiguous_issuer_denied_and_past_definitions_not_joined(text):
    assert extract_economic_changes(text)==[]


def test_definition_not_borrowed_across_sentence_or_company_clause():
    text='가상전자는 광자냉각(PCX) 수요 증가로 공급계약을 체결했고 새빛소재는 PCX 수요 증가로 생산을 시작했다'
    rows=extract_economic_changes(text)
    assert 'topic_alias_evidence' in rows[0] and 'topic_alias_evidence' not in rows[1]
    rows=extract_economic_changes('광자냉각(PCX)은 새 기술이다. 새빛소재, PCX 수요 증가로 생산 시작')
    assert len(rows)==1 and 'topic_alias_evidence' not in rows[0]


def test_duplicate_full_name_and_acronym_statement_not_two_events():
    text='가상전자, 광자냉각(PCX) 수요 증가로 공급계약 체결\n가상전자, 광자냉각(PCX) 기술의 PCX 수요 증가로 공급계약 체결'
    assert len(extract_economic_changes(text))==1


def test_existing_known_aliases_do_not_get_redefined():
    for text,topic in [('가상전자, 고대역폭메모리(HBM) 수요 증가로 공급계약 체결','HBM'),
                       ('가상전자, 극자외선(EUV) 공급계약 체결','EUV')]:
        row=extract_economic_changes(text)[0]
        assert row['topic']==topic and 'topic_alias_evidence' not in row
    assert explicit_topic_aliases('다온(PCX)',company_names=['다온'])==[]


@pytest.mark.parametrize('field,value',[
    ('canonical_topic','다른기술'),('abbreviation','OTHER'),('expression_sha256','e'*64),('source_expression','허위 병기'),
])
def test_tampered_definition_rejected(field,value):
    row=extract_economic_changes(SECOND)[0];row['topic_alias_evidence'][field]=value
    with pytest.raises(SourceShareError):validate_change(row)


def test_rss_publication_rejects_alias_from_another_title(tmp_path):
    from test_feed_analysis import setup,run
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    report=run(setup(tmp_path,SECOND));path,pin=publish_feed_analysis(report,tmp_path/'reports')
    assert consume_feed_analysis(path,path.parent,pin)['results']==report['results']
    row=report['results'][0];row['headline']=row['headline'].replace(PAIR,'광자냉각')
    path,pin=publish_feed_analysis(report,tmp_path/'reports')
    with pytest.raises(SourceShareError,match='alias'):consume_feed_analysis(path,path.parent,pin)


def test_old_stored_acronym_event_is_not_moved_by_reanalysis(tmp_path):
    store=ThemeStore(tmp_path/'themes');new=event(THIRD)
    old=deepcopy(new);del old['change']['topic_alias_evidence']
    first=store.ingest([old],now=T)[0]
    after=store.ingest([new],now=T+timedelta(seconds=1))[0]
    assert after['theme_id']==first['theme_id'] and after['event_ids']==first['event_ids']
    assert store.search(as_of=T,now=T+timedelta(seconds=1))==[first]


def test_distinct_company_clauses_can_define_conflicting_acronym_without_merging(tmp_path):
    from test_feed_analysis import setup,run
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    text='가상전자는 광자냉각(PCX) 수요 증가로 공급계약을 체결했고 새빛소재는 양자유체(PCX) 수요 증가로 생산을 시작했다'
    report=run(setup(tmp_path,text));path,pin=publish_feed_analysis(report,tmp_path/'reports')
    rows=consume_feed_analysis(path,path.parent,pin)['results'][0]['economic_changes']
    assert {r['topic_alias_evidence']['canonical_topic'] for r in rows}=={'광자냉각','양자유체'}
