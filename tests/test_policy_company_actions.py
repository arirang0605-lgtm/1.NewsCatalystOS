"""Synthetic reported policy causes; no real collection, AI, or barrier certification."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json

import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.company_evidence import company_evidence
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.source_share import SourceShareError
from test_feed_analysis import setup,run
from test_order_growth import observation
from test_federated_news_search import collect,GOV,fingerprint
from test_new_source_adapter import NOW

CAUSE='미국 ‘첨단칩통제법’ HBM 수출 규제 완화로'
TITLE='가상전자, '+CAUSE+' 생산 시작'


@pytest.mark.parametrize('tail,action,phase',[
    ('생산 시작','PRODUCTION_START','SOURCE_REPORTED'),
    ('생산능력 확대','CAPACITY_ADDITION','SOURCE_REPORTED'),
    ('공급계약 체결','CONTRACT','SOURCE_REPORTED'),
    ('신규 공장 투자 결정','INVESTMENT','SOURCE_REPORTED'),
    ('생산 시작 계획','PRODUCTION_START','PLANNED'),
    ('생산능력 확대 예정','CAPACITY_ADDITION','PLANNED'),
])
def test_reported_cause_keeps_company_action_and_stage(tail,action,phase):
    text='가상전자, '+CAUSE+' '+tail
    rows=extract_economic_changes(text)
    assert len(rows)==1
    row=rows[0]
    assert (row['action'],row['phase'],row['entity_ids'])==(action,phase,['가상전자'])
    assert row['economic_driver']=='POLICY_ENABLEMENT' and not row['verified_economic_effect']
    assert row['policy_cause']['policy_name']=='첨단칩통제법'
    assert row['policy_cause']['source_expression']==CAUSE
    assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
    economic_observation(row,origin_reference='https://gov.example.org/1',source_url='https://gov.example.org/1',
        source_id='synthetic',source_available_at=NOW.isoformat())


@pytest.mark.parametrize('text',[
    TITLE+' 보도를 부인했다',TITLE+' 취소',TITLE+'를 검토 중이다',
    '가상전자, 지난해 '+CAUSE+' 생산 시작',
    '가상전자, '+CAUSE+' 새빛소재는 생산 시작',
    '가상전자, '+CAUSE+' 생산 시작했고 그 회사는 생산능력 확대',
    '가상전자, '+CAUSE+' DRAM 수요 증가로 생산 시작',
    '가상전자, '+CAUSE+' 일본 ‘다른통제법’ HBM 수출 규제 완화로 생산 시작',
    CAUSE+' 생산 시작',
    '가상전자, '+CAUSE+' 가격 상승',
    '가상전자, '+CAUSE+' DRAM 생산 시작',
    '가상전자, '+CAUSE+' 그 회사는 생산 시작',
    '가상전자, HBM 및 DRAM 수출 규제 완화로 생산 시작',
])
def test_ambiguous_or_denied_cause_does_not_invent_response(text):
    assert extract_economic_changes(text)==[]


def test_anticipation_parallel_and_separate_company_clauses():
    rows=extract_economic_changes(TITLE.replace('완화로 생산 시작','완화에 대비해 생산 시작'))
    assert rows[0]['phase']=='PLANNED'
    rows=extract_economic_changes(TITLE+' 및 생산능력 확대')
    assert [r['action'] for r in rows]==['PRODUCTION_START','CAPACITY_ADDITION']
    text=TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 일본 ‘별도통제법’ HBM 수출 규제 폐지로 생산능력 확대'
    rows=extract_economic_changes(text)
    assert [r['entity_ids'] for r in rows]==[['가상전자'],['새빛소재']]
    assert [r['policy_cause']['policy_name'] for r in rows]==['첨단칩통제법','별도통제법']


def case(tmp_path, *, titles=None):
    titles=titles or [TITLE,'새빛소재, '+CAUSE+' 생산능력 확대','미래장비, '+CAUSE+' 신규 공장 투자 결정']
    info=setup(tmp_path,titles[0])
    collect(info[0],info[1],GOV,[(f'policy-{i}',t,f'https://gov.example.org/policy-{i}') for i,t in enumerate(titles[1:],1)],at=NOW+timedelta(hours=1))
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at);root=tmp_path/'reports';docs=tmp_path/'documents'
    path,pin=publish_feed_analysis(report,root/'core/reports')
    assert consume_feed_analysis(path,path.parent,pin,now=at)['results']==report['results']
    events=[observation(r,c) for r in report['results'] for c in r['economic_changes']]
    store=ThemeStore(docs/'theme_history');first=store.ingest(events[:1],now=at)[0]
    later=at+timedelta(seconds=1);theme=store.ingest(events[1:],now=later)[0]
    args=dict(reports_root=root,document_root=docs,feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)],as_of=later,now=later+timedelta(seconds=1))
    return theme,args,store,report,events,first,at


def test_saved_sources_common_policy_theme_company_reasons_and_pit(tmp_path):
    theme,args,store,report,events,first,at=case(tmp_path)
    assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3
    assert theme['scores']['distinct_economic_events']==3 and theme['verified_beneficiary_count']==0
    assert '첨단칩통제법' in theme['provisional_name']
    assert store.search(as_of=at,now=args['now'])==[first]
    assert store.ingest(events,now=args['now'])==[]
    assert len(store.search(query='첨단칩통제법',as_of=args['as_of'],now=args['now']))==1
    before=fingerprint(tmp_path)
    for name in ['가상전자','새빛소재','미래장비']:
        items=company_evidence(theme,name,**args)['items']
        assert len(items)==1 and items[0]['status']=='READY'
        assert name in items[0]['excerpt'] and CAUSE in items[0]['excerpt']
    raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
    data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
    assert len(data['CompanyCandidates'])==3
    assert all(CAUSE in c['inclusion_basis'][0]['reason'] and not c['verified_real_benefit'] for c in data['CompanyCandidates'])
    assert report['source_fetch_calls']==report['new_ai_results']==report['semantic_ai_attempts']==0
    assert fingerprint(tmp_path)==before


@pytest.mark.parametrize('other',[
    CAUSE.replace('첨단칩통제법','다른통제법'),CAUSE.replace('미국','일본'),
    CAUSE.replace('수출','수입'),CAUSE.replace('완화','폐지'),
    'HBM 수출 규제 완화로',
])
def test_same_product_different_or_unnamed_policy_is_not_merged(tmp_path,other):
    store=ThemeStore(tmp_path/'themes');events=[]
    for i,(actor,cause) in enumerate([('가상전자',CAUSE),('새빛소재',other)]):
        change=extract_economic_changes(f'{actor}, {cause} 생산 시작')[0]
        events.append(economic_observation(change,origin_reference=f'https://gov.example.org/{i}',
            source_url=f'https://gov.example.org/{i}',source_id='synthetic',source_available_at=NOW.isoformat()))
    assert len(store.ingest(events,now=datetime.now(timezone.utc)))==2


@pytest.mark.parametrize('cause',['HBM 수출 규제 완화로','‘첨단칩통제법’ HBM 수출 규제 완화로'])
def test_incompletely_identified_policy_articles_stay_individual(tmp_path,cause):
    store=ThemeStore(tmp_path/'themes');events=[]
    for i,actor in enumerate(['가상전자','새빛소재']):
        change=extract_economic_changes(f'{actor}, {cause} 생산 시작')[0]
        assert change['action']=='PRODUCTION_START' and change['policy_cause']['jurisdiction'] is None
        events.append(economic_observation(change,origin_reference=f'https://gov.example.org/{i}',
            source_url=f'https://gov.example.org/{i}',source_id='synthetic',source_available_at=NOW.isoformat()))
    assert len(store.ingest(events,now=datetime.now(timezone.utc)))==2


def test_legacy_policy_record_keeps_id_and_source_readable(tmp_path):
    info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at);row=report['results'][0]
    old=extract_economic_changes(TITLE,include_policy_causes=False)[0];old['evidence_level']='REPORTED'
    assert old['action']=='POLICY_CHANGE'
    row['economic_changes']=[old]
    root=tmp_path/'reports';docs=tmp_path/'documents'
    path,pin=publish_feed_analysis(report,root/'core/reports')
    assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
    event=observation(row,old);theme=ThemeStore(docs/'theme_history').ingest([event],now=at)[0]
    before=fingerprint(tmp_path)
    result=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
        feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])
    assert result['items'][0]['status']=='READY' and result['items'][0]['event_id']==event['event_id']
    assert fingerprint(tmp_path)==before


@pytest.mark.parametrize('tamper',['name','source','action'])
def test_saved_policy_proof_must_match_the_source_title(tmp_path,tamper):
    info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at);change=report['results'][0]['economic_changes'][0]
    if tamper=='name':change['policy_cause']['policy_name']='다른법'
    if tamper=='source':change['policy_cause']=extract_economic_changes(TITLE.replace('미국','일본'))[0]['policy_cause']
    if tamper=='action':change['action']='CONTRACT'
    path,pin=publish_feed_analysis(report,tmp_path/'reports')
    with pytest.raises(SourceShareError):consume_feed_analysis(path,path.parent,pin,now=at)


def test_licensed_body_and_standalone_policy_preserve_scopes(tmp_path):
    from test_motir_document_analysis import case as body_case
    from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
    _,args=body_case(tmp_path,(TITLE+'. 집행 결과는 독립 확인되지 않았다. ')*3)
    report=analyze_motir_document(**args)
    assert [c['action'] for c in report['economic_changes']]==['PRODUCTION_START']
    path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
    assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']
    text='반도체 관련 개정령안이 의결되었으며 다음 달 시행될 예정이다.'
    assert extract_economic_changes(text)==extract_economic_changes(text,include_policy_causes=False)
    assert extract_economic_changes(text)[0]['phase']=='ADOPTED_NOT_YET_EFFECTIVE'
