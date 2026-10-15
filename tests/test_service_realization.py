"""Synthetic service plans and starts; no independent realization certification."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256

import pytest

from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.standard_delivery import build_theme_bundle, read_theme_bundle
from test_theme_emergence import T


def claim(title, n, *, at=None):
    change=extract_economic_changes(title)[0]
    change['evidence_level']='REPORTED'
    return economic_observation(change,origin_reference=f'https://example.org/{n}',
        source_url=f'https://example.org/{n}',source_id='synthetic',
        source_available_at=(at or T+timedelta(hours=n)).isoformat(),
        content_scope='RSS_TITLE_METADATA')


def pair():
    return [claim('가상전자, ‘별빛검사’ 서비스 개시 예정',0),
            claim('가상전자, ‘별빛검사’ 서비스 정식 개시',1)]


def test_plan_start_preserves_identity_sources_pit_and_readonly_delivery(tmp_path):
    plan,start=pair(); store=ThemeStore(tmp_path/'themes')
    first=store.ingest([plan],now=T)[0]
    at=T+timedelta(hours=2)
    latest=store.ingest([start],now=at)[0]
    assert latest['theme_id']==first['theme_id']
    assert latest['first_detected_at']==first['first_detected_at']
    assert latest['event_ids']==sorted([plan['event_id'],start['event_id']])
    assert latest['scores']['distinct_economic_events']==1
    assert len(latest['source_refs'])==2 and latest['history'][-1]['event_count']==1
    link=latest['event_followups'][0]
    assert link['planned_event_id']==plan['event_id']
    assert link['realization_event_id']==start['event_id']
    assert link['status']=='SOURCE_REPORTED_REALIZATION' and link['is_realization_confirmed'] is False
    assert latest['verified_beneficiary_count']==0 and latest['status']=='CANDIDATE'
    assert store.search(as_of=T,now=at)==[first]
    assert store.search(query='별빛검사',now=at)==[latest]
    assert store.ingest([start,plan],now=at+timedelta(seconds=1))==[]
    raw=build_theme_bundle([latest],decision_at=at,now=at)
    assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)['ThemeCandidates']==[latest]


def test_pair_in_one_batch_is_order_independent(tmp_path):
    observations=pair(); at=T+timedelta(hours=2)
    forward=ThemeStore(tmp_path/'forward').ingest(observations,now=at)
    reverse=ThemeStore(tmp_path/'reverse').ingest(list(reversed(observations)),now=at)
    assert forward==reverse and len(forward)==1
    assert forward[0]['scores']['distinct_economic_events']==1


@pytest.mark.parametrize('title',[
    '새빛전자, ‘별빛검사’ 서비스 정식 개시',
    '가상전자, ‘달빛검사’ 서비스 정식 개시',
    '‘별빛검사’ 서비스 정식 개시',
    '가상전자와 새빛소재, ‘별빛검사’ 서비스 정식 개시',
])
def test_no_name_or_different_company_service_cannot_link(tmp_path,title):
    plan,_=pair(); start=claim(title,1)
    rows=ThemeStore(tmp_path/'themes').ingest([plan,start],now=T+timedelta(hours=2))
    assert len(rows)==2 and not any(r.get('event_followups') for r in rows)


def test_unnamed_same_function_is_not_identity_evidence(tmp_path):
    rows=[claim('가상전자, 정부지원사업 맞춤 추천 서비스 개시 예정',0),
          claim('가상전자, 정부지원사업 맞춤 추천 서비스 정식 개시',1)]
    result=ThemeStore(tmp_path/'themes').ingest(rows,now=T+timedelta(hours=2))
    assert len(result)==2


@pytest.mark.parametrize('offset',[0,-1])
def test_execution_must_be_available_after_the_plan(tmp_path,offset):
    plan,start=pair();start['source_available_at']=(T+timedelta(hours=offset)).isoformat()
    result=ThemeStore(tmp_path/'themes').ingest([plan,start],now=T+timedelta(hours=2))
    assert len(result)==2 and not any(r.get('event_followups') for r in result)


def test_ambiguous_regional_plans_are_not_merged(tmp_path):
    plan,start=pair()
    other=claim('가상전자, ‘별빛검사’ 서비스 전국 개시 예정',0)
    result=ThemeStore(tmp_path/'themes').ingest([plan,other,start],now=T+timedelta(hours=2))
    assert len(result)==3 and not any(r.get('event_followups') for r in result)


def test_same_demand_distinct_companies_still_form_emerging_theme(tmp_path):
    observations=[]
    for i,company in enumerate(['가상전자','새빛소재','미래장비']):
        prefix=f'{company}는 광자냉각 수요 증가에 대응해 ‘별빛검사’ 서비스 '
        observations.extend([claim(prefix+'개시 예정',i),claim(prefix+'정식 개시',i+3)])
    result=ThemeStore(tmp_path/'themes').ingest(observations,now=T+timedelta(hours=7))
    assert len(result)==1 and result[0]['status']=='EMERGING'
    assert result[0]['scores']['distinct_economic_events']==3
    assert len(result[0]['event_ids'])==6 and len(result[0]['event_followups'])==3


def test_legacy_observation_enrichment_does_not_change_event_or_theme(tmp_path):
    plan,start=pair();legacy=deepcopy(plan);del legacy['change']['service_name']
    store=ThemeStore(tmp_path/'themes');first=store.ingest([legacy],now=T)[0]
    result=store.ingest([plan,start],now=T+timedelta(hours=2))
    assert len(result)==1 and result[0]['theme_id']==first['theme_id']
    assert result[0]['scores']['distinct_economic_events']==1
    assert len(result[0]['source_refs'])==3


def test_preexisting_separate_themes_are_not_rewritten(tmp_path):
    plan,start=pair(); legacy=deepcopy(start);del legacy['change']['service_name']
    store=ThemeStore(tmp_path/'themes')
    original=store.ingest([plan,legacy],now=T+timedelta(hours=2))
    assert len(original)==2
    store.ingest([start],now=T+timedelta(hours=3))
    assert {r['theme_id'] for r in store.search(now=T+timedelta(hours=3))}=={r['theme_id'] for r in original}
    assert store.search(as_of=T+timedelta(hours=2),now=T+timedelta(hours=3))==sorted(original,key=lambda r:r['theme_id'],reverse=True)


def test_followup_export_cannot_certify_realization_or_lose_plan_source(tmp_path):
    from newscatalystos.source_share import SourceShareError
    at=T+timedelta(hours=2)
    theme=ThemeStore(tmp_path/'themes').ingest(pair(),now=at)[0]
    for change in ('confirmation','source','future'):
        modified=deepcopy(theme)
        if change=='confirmation': modified['event_followups'][0]['is_realization_confirmed']=True
        if change=='source': modified['event_followups'][0]['planned_event_id']='f'*64
        if change=='future': modified['event_followups'][0]['decision_at']=(at+timedelta(hours=1)).isoformat()
        with pytest.raises(SourceShareError):
            build_theme_bundle([modified],decision_at=at,now=at)


def test_saved_titles_to_dashboard_followup_without_paid_ai(tmp_path):
    import json
    import threading
    from datetime import datetime, timezone
    from urllib.request import urlopen
    from scripts import run_feed_analysis
    from scripts.open_research_dashboard import DashboardServer
    from test_federated_news_search import setup_workspace,collect,fingerprint,GOV
    from test_new_source_adapter import registry,NOW
    source=setup_workspace(tmp_path,'source',registry())
    work=tmp_path/'analyses'/'core';docs=tmp_path/'documents'
    opts=run_feed_analysis.parser().parse_args([
        '--registry',str(source.registry_path),'--inbox-root',str(source.inbox_root),
        '--state',str(source.poll_state),'--analysis-root',str(work),
        '--theme-root',str(docs/'theme_history')])
    collect(source,registry(),GOV,[('plan','가상전자, ‘별빛검사’ 서비스 개시 예정','https://gov.example.org/plan')],at=NOW)
    at=datetime.now(timezone.utc)
    code,first=run_feed_analysis.evaluate(opts,now=at)
    assert code==0 and first['theme_versions_created']==1
    collect(source,registry(),GOV,[('start','가상전자, ‘별빛검사’ 서비스 정식 개시','https://gov.example.org/start')],at=NOW+timedelta(hours=2))
    before=fingerprint(source.inbox_root.parent)
    code,second=run_feed_analysis.evaluate(opts,now=datetime.now(timezone.utc))
    assert code==0 and second['theme_versions_created']==1 and second['new_ai_results']==0
    assert fingerprint(source.inbox_root.parent)==before
    server=DashboardServer(0,work.parent,tmp_path/'notes',docs)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/themes') as response:
            shown=json.loads(response.read())['ThemeCandidates']
        assert len(shown)==1 and len(shown[0]['event_followups'])==1
        assert shown[0]['scores']['distinct_economic_events']==1
        assert {r['phase'] for r in shown[0]['source_refs']}=={'PLANNED','SOURCE_REPORTED'}
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_late_plan_republication_cannot_undo_realization_link(tmp_path):
    plan,start=pair()
    store=ThemeStore(tmp_path/'themes')
    first=store.ingest([plan,start],now=T+timedelta(hours=2))[0]
    repeated=economic_observation(plan['change'],origin_reference='https://another.example.org/plan',
        source_url='https://another.example.org/plan',source_id='syndicated',
        source_available_at=(T+timedelta(hours=3)).isoformat(),content_scope='RSS_TITLE_METADATA')
    latest=store.ingest([repeated],now=T+timedelta(hours=4))[0]
    assert latest['event_ids']==first['event_ids']
    assert latest['scores']['distinct_economic_events']==1
    assert len(latest['event_followups'])==1 and len(latest['source_refs'])==3
    assert latest['event_followups'][0]['planned_event_id']==plan['event_id']
