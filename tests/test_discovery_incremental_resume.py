"""New-only processing preserves existing reading bindings and resumes partial commits."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import pytest
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.recent_theme_followups import publish_followups,metadata_resolver
from newscatalystos.source_share import SourceShareError
from newscatalystos.feed_analysis import analyze_completed_feed
from scripts.run_economic_discovery import execute
from test_execution_evidence import fixture
from test_discovery_pagination import setup
from test_federated_news_search import fingerprint,collect

def test_repeated_tick_preserves_reports_baseline_readings_and_export(tmp_path,monkeypatch):
    root,_,_,ws,bases,_,doc,opener=fixture(tmp_path,monkeypatch)
    publish_followups(root,doc,bases,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    at=datetime.now(timezone.utc)
    original=export_discovery(root,as_of=at,now=at,include_common_causes=True,recent_workspaces=(ws,))
    before=fingerprint(root);sources=[(ws.scope,ws.registry_path,ws.poll_state,ws.inbox_root)]
    for step in (1,2):
        result=execute(root,sources,now=at+timedelta(seconds=step))
        assert result['status']=='READY' and result['analyzed_titles']==0
        assert all(r['analysis_batches']==0 for r in result['sources'])
    assert fingerprint(root)==before
    assert export_discovery(root,as_of=at,now=at+timedelta(seconds=3),
                            include_common_causes=True,recent_workspaces=(ws,))==original
    current=read_discovery(root,include_common_causes=True,recent_workspaces=(ws,))
    group=next(g for g in current['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
    assert len(group['public_page_demand_analysis']['notes'])==3
    assert len(group['recent_news_comparison']['notes'])==6
    assert opener.calls==1

def test_new_and_revised_versions_only_after_large_initial_batch(tmp_path):
    w,reg,provider,_=setup(tmp_path);at=datetime.now(timezone.utc);root=tmp_path/'watch'
    sources=[('core',w.registry_path,w.poll_state,w.inbox_root)]
    first=execute(root,sources,now=at)
    assert first['analyzed_titles']==105 and first['sources'][0]['analysis_batches']==2
    previous=fingerprint(root/'feed_analysis')
    fixed=export_discovery(root,as_of=at,now=at)
    collect(w,reg,provider,[
        ('old-0','미래소재는 광수송촉매 공급을 중단했다','https://gov.example.org/archive/0'),
        ('brand-new','다른전력은 주파수안정장치 공급계약을 체결했다','https://gov.example.org/current/brand-new')
    ],at=datetime.now(timezone.utc))
    later=datetime.now(timezone.utc)
    result=execute(root,sources,now=later)
    assert result['status']=='READY' and result['analyzed_titles']==2
    assert result['sources'][0]['analysis_batches']==1
    current=fingerprint(root/'feed_analysis')
    assert all(current[k]==v for k,v in previous.items() if '/reports/' in k)
    assert execute(root,sources,now=later+timedelta(seconds=1))['analyzed_titles']==0
    assert export_discovery(root,as_of=at,now=later+timedelta(seconds=1))==fixed
    assert result['source_fetch_calls']==0

def test_failed_later_batch_resumes_only_remaining_versions(tmp_path,monkeypatch):
    import scripts.run_economic_discovery as runner
    w,_,_,at=setup(tmp_path);root=tmp_path/'watch'
    sources=[('core',w.registry_path,w.poll_state,w.inbox_root)]
    normal=runner.evaluate;calls=0
    def fail_second(opts,now=None):
        nonlocal calls
        calls+=1
        if calls==2:return 4,{'status':'FEED_ANALYSIS_INPUT_UNAVAILABLE','results':[]}
        return normal(opts,now=now)
    monkeypatch.setattr(runner,'evaluate',fail_second)
    first=execute(root,sources,now=at)
    assert first['status']=='PARTIAL' and first['analyzed_titles']==100
    reports={k:v for k,v in fingerprint(root/'feed_analysis').items() if '/reports/' in k}
    monkeypatch.setattr(runner,'evaluate',normal)
    recovered=execute(root,sources,now=at+timedelta(seconds=1))
    assert recovered['status']=='READY' and recovered['analyzed_titles']==5
    current=fingerprint(root/'feed_analysis')
    assert all(current[k]==v for k,v in reports.items())
    assert read_discovery(root,as_of=at+timedelta(seconds=1),now=at+timedelta(seconds=1))['counts']['events']==1

def test_report_written_before_interrupted_theme_commit_is_not_skipped(tmp_path,monkeypatch):
    import scripts.run_feed_analysis as analysis
    w,_,_,at=setup(tmp_path);root=tmp_path/'watch'
    sources=[('core',w.registry_path,w.poll_state,w.inbox_root)]
    normal=analysis.ThemeStore.ingest
    def fail(*a,**kw):raise SourceShareError('synthetic interruption before theme commit')
    monkeypatch.setattr(analysis.ThemeStore,'ingest',fail)
    result=execute(root,sources,now=at)
    assert result['status']=='PARTIAL'
    assert list((root/'feed_analysis').rglob('feed_analysis_*.json'))
    assert read_discovery(root,as_of=at,now=at)['counts']['events']==0
    monkeypatch.setattr(analysis.ThemeStore,'ingest',normal)
    result=execute(root,sources,now=at+timedelta(seconds=1))
    assert result['status']=='READY' and result['analyzed_titles']==1
    assert read_discovery(root,as_of=at+timedelta(seconds=1),now=at+timedelta(seconds=1))['counts']['events']==1
    assert execute(root,sources,now=at+timedelta(seconds=2))['analyzed_titles']==0

@pytest.mark.parametrize('excluded,industry',[
    ([('provider','bad','a'*64)],'ECONOMIC_DISCOVERY'),
    ([('provider','a'*64)],'ECONOMIC_DISCOVERY'),
    ([('provider','a'*64,'b'*64)],'SEMICONDUCTOR')])
def test_exclusion_is_exact_event_first_selection(tmp_path,excluded,industry):
    from test_new_source_adapter import registry
    with pytest.raises(SourceShareError):
        analyze_completed_feed(registry(),tmp_path/'inbox',tmp_path/'state',tmp_path/'analysis',
                               industry=industry,excluded_versions=excluded)
    assert not (tmp_path/'analysis').exists()


def test_nonadvancing_replay_stops_instead_of_repeating_the_same_batch(tmp_path,monkeypatch):
    import scripts.run_feed_analysis as analysis
    w,_,_,at=setup(tmp_path);root=tmp_path/'watch'
    monkeypatch.setattr(analysis,'known_discovery_versions',lambda *a,**kw:set())
    result=execute(root,[('core',w.registry_path,w.poll_state,w.inbox_root)],now=at)
    assert result['status']=='PARTIAL' and result['analyzed_titles']==100
    assert result['sources'][0]['status']=='DISCOVERY_REPLAY_INCOMPLETE'
    assert result['sources'][0]['has_more_older_titles']
