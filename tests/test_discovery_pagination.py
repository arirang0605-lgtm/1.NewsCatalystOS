"""Previously unprocessed source titles must not be hidden behind a sector gate
or a permanent latest-100 gate. Reuse bounded reports, ACKs and ThemeStore.
"""
from dataclasses import replace
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json

import pytest
from newscatalystos.feed_analysis import analyze_completed_feed
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from scripts.run_economic_discovery import execute
from scripts.run_feed_analysis import parser,evaluate
from test_federated_news_search import setup_workspace,collect,fingerprint
from test_new_source_adapter import registry


def setup(tmp_path):
    reg=registry();provider=reg.providers[0].provider_id
    w=setup_workspace(tmp_path,'core',reg)
    first=datetime.now(timezone.utc)-timedelta(hours=3)
    older=[('old-'+str(i),'산업 일반 공지 '+str(i),'https://gov.example.org/archive/'+str(i)) for i in range(5)]
    older[0]=('old-0','미래소재는 광수송촉매 생산을 시작했다','https://gov.example.org/archive/0')
    collect(w,reg,provider,older,at=first)
    newer=[('new-'+str(i),'일반 행사 안내 '+str(i),'https://gov.example.org/current/'+str(i)) for i in range(100)]
    collect(w,reg,provider,newer,at=first+timedelta(hours=1))
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    return w,reg,provider,at


def test_unknown_sector_event_after_latest_hundred_reaches_watch_and_export(tmp_path):
    w,reg,provider,at=setup(tmp_path)
    sources=[('core',w.registry_path,w.poll_state,w.inbox_root)]
    before=fingerprint(w.registry_path.parent.parent)
    initial=analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'single-page',
        provider_id=provider,limit=100,now=at,industry='ECONOMIC_DISCOVERY')
    assert len(initial['results'])==100 and initial['has_more_results']
    assert not any(row['economic_changes'] for row in initial['results'])
    root=tmp_path/'observations'
    result=execute(root,sources,now=at)
    one,=result['sources']
    assert result['status']=='READY' and one['analysis_batches']==2
    assert one['titles']==result['analyzed_titles']==105 and not one['has_more_older_titles']
    assert result['economic_events']==result['unclassified_events']==1
    assert result['source_fetch_calls']==result['paid_ai_calls']==0
    view=read_discovery(root,as_of=at,now=at)
    assert view['counts']['analysis_title_versions']==105
    candidate,=view['candidates']
    assert candidate['watch_topic']=='광수송촉매'
    assert candidate['industry_tags']==[] and candidate['source_companies']==['미래소재']
    assert candidate['source_evidence'][0]['headline']=='미래소재는 광수송촉매 생산을 시작했다'
    assert candidate['source_evidence'][0]['analysis_available_at']==at.isoformat()
    assert read_discovery(root,as_of=at-timedelta(seconds=1),now=at)['candidates']==[]
    data=json.loads(export_discovery(root,as_of=at,now=at))
    assert data['ThemeCandidates'][0]['industry_tags']==[]
    assert data['ThemeCandidates'][0]['catalyst_material']['new_market_catalyst_count'] is None
    repeat=execute(root,sources,now=at+timedelta(minutes=1))
    assert repeat['sources'][0]['theme_versions_created']==0
    assert read_discovery(root,as_of=at+timedelta(minutes=1),now=at+timedelta(minutes=1))['counts']['events']==1
    assert fingerprint(w.registry_path.parent.parent)==before


def test_page_selection_is_exact_and_default_v1_stays_unchanged(tmp_path):
    w,reg,provider,at=setup(tmp_path)
    options=dict(provider_id=provider,limit=100,now=at)
    first=analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'original',**options)
    explicit=analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'zero',**options,discovery_offset=0)
    assert first==explicit and 'discovery_offset' not in first
    second=analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'discovery',**options,
        industry='ECONOMIC_DISCOVERY',discovery_offset=100)
    assert len(second['results'])==5 and second['matched_versions']==105 and not second['has_more_results']
    assert second['discovery_offset']==100
    from newscatalystos.feed_analysis_delivery import _validate_report
    assert _validate_report(second,at)==at
    broken=deepcopy(second);broken['discovery_offset']=105
    with pytest.raises(SourceShareError):_validate_report(broken,at)
    broken=deepcopy(second);broken['discovery_offset']=True
    with pytest.raises(SourceShareError):_validate_report(broken,at)
    assert sum(bool(r['economic_changes']) for r in second['results'])==1
    with pytest.raises(SourceShareError,match='outside available'):
        analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'past',**options,
            industry='ECONOMIC_DISCOVERY',discovery_offset=105)
    assert not (tmp_path/'past').exists()


@pytest.mark.parametrize('offset,industry',[(True,'ECONOMIC_DISCOVERY'),(-1,'ECONOMIC_DISCOVERY'),
    (1,'SEMICONDUCTOR'),(1,'POWER_EQUIPMENT')])
def test_discovery_page_cannot_change_other_profiles_or_use_invalid_offset(tmp_path,offset,industry):
    with pytest.raises(SourceShareError,match='discovery offset'):
        analyze_completed_feed(registry(),tmp_path/'inbox',tmp_path/'state',tmp_path/'out',
            industry=industry,discovery_offset=offset)
    assert not (tmp_path/'out').exists()


def test_later_batch_failure_is_visible_and_does_not_skip_other_source(tmp_path,monkeypatch):
    import scripts.run_economic_discovery as module
    reg=registry();base=reg.providers[0]
    reg=ProviderRegistry((base,replace(base,provider_id='second-source',endpoint='https://other.example.org/feed')))
    w=setup_workspace(tmp_path,'core',reg);calls=[]
    def mock(opts,now=None):
        calls.append((opts.provider_id,opts.discovery_offset))
        if opts.provider_id==base.provider_id and opts.discovery_offset==100:
            return 4,{'status':'FEED_ANALYSIS_UNAVAILABLE','results':[]}
        if opts.provider_id==base.provider_id:
            return 0,{'status':'FEED_ECONOMIC_ANALYSIS_READY','results':[{'economic_changes':[]}]*100,
                     'matched_versions':102,'has_more_results':True,'economic_changes_count':0}
        return 0,{'status':'FEED_ECONOMIC_ANALYSIS_READY','results':[{'economic_changes':[]}],
                  'matched_versions':1,'has_more_results':False}
    monkeypatch.setattr(module,'evaluate',mock)
    result=execute(tmp_path/'watch',[('core',w.registry_path,w.poll_state,w.inbox_root)])
    assert result['status']=='PARTIAL' and result['sources_failed']==1
    failed=next(r for r in result['sources'] if r['provider_id']==base.provider_id)
    healthy=next(r for r in result['sources'] if r['provider_id']=='second-source')
    assert failed['titles']==100 and failed['has_more_older_titles'] and failed['exit_code']==4
    assert healthy['exit_code']==0 and healthy['titles']==1
    assert (base.provider_id,100) in calls and ('second-source',0) in calls


def test_unchanged_snapshot_count_required_between_pages(tmp_path,monkeypatch):
    import scripts.run_economic_discovery as module
    reg=registry();w=setup_workspace(tmp_path,'core',reg)
    def mock(opts,now=None):
        return 0,{'status':'FEED_ECONOMIC_ANALYSIS_READY','results':[{'economic_changes':[]}]*100,
                  'matched_versions':201 if opts.discovery_offset else 200,'has_more_results':True}
    monkeypatch.setattr(module,'evaluate',mock)
    result=execute(tmp_path/'watch',[('core',w.registry_path,w.poll_state,w.inbox_root)])
    assert result['status']=='PARTIAL' and result['sources'][0]['status']=='SOURCE_SNAPSHOT_CHANGED'
    assert result['sources'][0]['titles']==100 and result['sources'][0]['has_more_older_titles']
