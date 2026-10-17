"""Stored news -> stable scheduled publication -> unmodified Era input contract.

Old state is not discarded on failure; repeated reads do not mint new catalysts.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from copy import deepcopy
import json
import threading
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

import pytest
from newscatalystos.material_publication import publish_material,read_published
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.standard_delivery import read_theme_bundle
from test_theme_emergence import T,event
from test_federated_news_search import fingerprint
from test_service_realization import pair

AT=T+timedelta(minutes=5)


def setup(tmp_path,scope='company'):
    store=ThemeStore(tmp_path/'source-themes');store.ingest([event()],now=T)
    return store,tmp_path/'outbox',{scope:store.root}


def latest(root,at=AT):
    record,payload,pin=read_published(root,as_of=at,now=at)
    return record,json.loads(payload),payload,pin


def test_same_sources_same_bytes_even_after_midnight_and_many_reads(tmp_path):
    store,root,sources=setup(tmp_path)
    source=fingerprint(store.root)
    dry=publish_material(root,sources,now=AT,dry_run=True)
    assert dry['status']=='WOULD_PUBLISH' and not root.exists()
    first=publish_material(root,sources,now=AT)
    assert first['status']=='PUBLISHED' and first['new_publication']
    record,bundle,raw,pin=latest(root)
    row=bundle['ThemeCandidates'][0]
    assert row['catalyst_material']['materials'][0]['is_new_market_catalyst'] is None
    before=fingerprint(root)
    for when in (AT,AT+timedelta(hours=2),AT+timedelta(days=1)):
        second=publish_material(root,sources,now=when)
        assert second['status']=='ALREADY_PUBLISHED' and second['sha256']==first['sha256']
        assert second['published_at']==first['published_at']
        assert read_published(root,now=when)[1]==raw
    assert fingerprint(root)==before
    assert fingerprint(store.root)==source
    assert read_published(root,as_of=AT-timedelta(microseconds=1),now=AT) is None
    assert read_theme_bundle(raw,first['sha256'],decision_at=AT,now=AT)['decision_at']==AT.isoformat()


def test_automatic_previous_cutoff_reprint_no_addition_then_withdrawal(tmp_path):
    store,root,sources=setup(tmp_path);first=publish_material(root,sources,now=AT)
    old=fingerprint(root);original=event();copied=deepcopy(original)
    copied['source_id']='same-story-other-feed';copied['source_url']='https://example.org/other'
    t2=AT+timedelta(minutes=10);store.ingest([copied],now=t2)
    second=publish_material(root,sources,now=t2)
    record,bundle,raw,pin=latest(root,t2)
    m=bundle['ThemeCandidates'][0]['catalyst_material']
    assert second['sha256']!=first['sha256']
    assert m['comparison_since']==(AT+timedelta(microseconds=1)).isoformat()
    assert m['materials'][0]['material_status']=='REPEATED_CLAIM'
    assert m['materials'][0]['news_input_for_era']=='NO_NEW_CATALYST'
    assert m['materials'][0]['locally_added_action_count']==0
    t3=t2+timedelta(minutes=5)
    store.ingest([event(3,polarity='RETRACT',target=original['event_id'])],now=t3)
    third=publish_material(root,sources,now=t3)
    after=latest(root,t3)[1]['ThemeCandidates'][0]['catalyst_material']['materials'][0]
    assert after['material_status']=='SOURCE_WITHDRAWAL' and after['company_impacts']==[]
    historical=read_published(root,as_of=t2,now=t3)
    assert sha256(historical[1]).hexdigest()==second['sha256']
    assert historical[1]==raw
    assert all(fingerprint(root)[p]==h for p,h in old.items() if not p.endswith('latest.json'))


def test_saved_plan_progress_is_reassessment_not_two_independent_actions(tmp_path):
    plan,start=pair();plan['change']['industry_tags']=start['change']['industry_tags']=['SEMICONDUCTOR']
    store=ThemeStore(tmp_path/'source');store.ingest([plan],now=T)
    root=tmp_path/'out';sources={'base':store.root}
    publish_material(root,sources,now=AT)
    t2=T+timedelta(hours=2);store.ingest([start],now=t2)
    publish_material(root,sources,now=t2)
    m=latest(root,t2)[1]['ThemeCandidates'][0]['catalyst_material']['materials'][0]
    assert m['material_status']=='REPORTED_STAGE_PROGRESS'
    assert m['news_input_for_era']=='REASSESS_REPORTED_PROGRESS'
    assert m['locally_added_action_count']==0 and not m['verified_economic_effect']
    assert len(m['event_ids'])==2


def test_one_corrupt_scope_keeps_last_good_and_others_continue_then_recovers(tmp_path,monkeypatch):
    a=ThemeStore(tmp_path/'a');b=ThemeStore(tmp_path/'b')
    a.ingest([event()],now=T);b.ingest([event(2)],now=T)
    root=tmp_path/'out';sources={'company':a.root,'nist':b.root}
    publish_material(root,sources,now=AT)
    initial=latest(root)[0];read=ThemeStore.search
    def broken(self,*args,**kw):
        if self.root==a.root:raise SourceShareError('injected source failure')
        return read(self,*args,**kw)
    t2=AT+timedelta(minutes=10);b.ingest([event(3)],now=t2)
    monkeypatch.setattr(ThemeStore,'search',broken)
    result=publish_material(root,sources,now=t2)
    record,bundle,raw,pin=latest(root,t2)
    assert result['status']=='PUBLISHED_PARTIAL' and result['unavailable_scopes']==1
    assert record['scopes']['company']['last_successful_input_at']==AT.isoformat()
    assert record['scopes']['nist']['last_successful_input_at']==t2.isoformat()
    company=next(t for t in bundle['ThemeCandidates'] if t['material_publication_source']['scope']=='company')
    assert company['material_publication_source']['status']=='LAST_GOOD_SOURCE_UNAVAILABLE'
    assert len(company['event_ids'])==1
    again=publish_material(root,sources,now=t2+timedelta(seconds=5))
    assert again['status']=='ALREADY_PUBLISHED' and again['sha256']==result['sha256']
    monkeypatch.setattr(ThemeStore,'search',read)
    t3=t2+timedelta(minutes=10);a.ingest([event(4)],now=t3)
    recovered=publish_material(root,sources,now=t3)
    record,bundle,_,_=latest(root,t3)
    assert recovered['status']=='PUBLISHED' and recovered['unavailable_scopes']==0
    company=next(t for t in bundle['ThemeCandidates'] if t['material_publication_source']['scope']=='company')
    assert company['catalyst_material']['comparison_since']==(AT+timedelta(microseconds=1)).isoformat()
    assert len(company['event_ids'])==2
    assert record['scopes']['nist']['last_successful_input_at']==t2.isoformat()


def test_interrupted_publish_does_not_advance_checkpoint_and_retry_no_duplicate(tmp_path,monkeypatch):
    from newscatalystos import material_publication as module
    store,root,sources=setup(tmp_path);first=publish_material(root,sources,now=AT)
    t2=AT+timedelta(minutes=10);store.ingest([event(2)],now=t2)
    commit=module._commit_pointer
    monkeypatch.setattr(module,'_commit_pointer',lambda *a:(_ for _ in ()).throw(OSError('interrupted before pointer')))
    with pytest.raises(OSError):publish_material(root,sources,now=t2)
    assert sha256(read_published(root,now=t2)[1]).hexdigest()==first['sha256']
    monkeypatch.setattr(module,'_commit_pointer',commit)
    complete=publish_material(root,sources,now=t2)
    assert complete['status']=='PUBLISHED'
    assert len(list(root.glob('theme_delivery_*.json')))==2
    assert len(list(root.glob('material_checkpoint_*.json')))==2
    assert publish_material(root,sources,now=t2+timedelta(minutes=5))['status']=='ALREADY_PUBLISHED'


def test_checksum_future_paths_lock_and_removed_source_fail_closed(tmp_path):
    import fcntl,os
    store,root,sources=setup(tmp_path);publish_material(root,sources,now=AT)
    with pytest.raises(SourceShareError):publish_material(Path('relative-outbox'),sources,now=AT,dry_run=True)
    with pytest.raises(SourceShareError):publish_material(store.root/'nested',sources,now=AT)
    with pytest.raises(SourceShareError):publish_material(tmp_path/'EraLeader/data',sources,now=AT)
    with pytest.raises(SourceShareError):read_published(root,as_of=AT+timedelta(seconds=1),now=AT)
    with pytest.raises(SourceShareError):publish_material(root,{'other':store.root},now=AT)
    fd=os.open(root/'.publish.lock',os.O_WRONLY)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(SourceShareError,match='already running'):publish_material(root,sources,now=AT)
    finally:os.close(fd)
    _,_,raw,pin=latest(root)
    file=root/('material_checkpoint_'+pin+'.json')
    file.write_bytes(file.read_bytes().replace(b'CURRENT_SNAPSHOT',b'BROKEN__SNAPSHOT'))
    with pytest.raises(SourceShareError):read_published(root,now=AT)


def test_recovery_cannot_erase_previously_known_theme(tmp_path,monkeypatch):
    store,root,sources=setup(tmp_path);first=publish_material(root,sources,now=AT)
    monkeypatch.setattr(ThemeStore,'search',lambda *a,**k:[])
    result=publish_material(root,sources,now=AT+timedelta(minutes=1))
    assert result['status']=='PUBLISHED_PARTIAL'
    record,bundle,*_=latest(root,AT+timedelta(minutes=1))
    assert len(bundle['ThemeCandidates'])==1
    assert bundle['ThemeCandidates'][0]['material_publication_source']['status']=='LAST_GOOD_SOURCE_UNAVAILABLE'


def test_optional_identity_financial_revision_does_not_mint_new_news(tmp_path,monkeypatch):
    from newscatalystos import material_publication as module
    from test_era_daily_assessment import source as producer
    from newscatalystos.era_daily_assessment import import_daily
    from test_era_daily_assessment import T as ERA_T
    begin=max(T,ERA_T);after=begin+timedelta(minutes=5)
    root,path,pin,doc=producer(tmp_path/'era',at=begin)
    identity=tmp_path/'identity'
    import_daily(root,path,pin,identity,now=after)
    store=ThemeStore(tmp_path/'themes');store.ingest([event(company='가상전자')],now=begin)
    out=tmp_path/'out'
    first=publish_material(out,{'company':store.root},identity_root=identity,now=after)
    raw=latest(out,after)[2]
    assert b'DART_CORP:00164779' in raw
    original=module.read_identity
    def later(*a,**k):
        snap,skipped=original(*a,**k);r,d=deepcopy(snap)
        r['source_sha256']='e'*64;r['imported_at']=(after+timedelta(minutes=1)).isoformat()
        d['candidates'][0]['krx_completed_close']['close_krw']=999
        return (r,d),skipped
    monkeypatch.setattr(module,'read_identity',later)
    second=publish_material(out,{'company':store.root},identity_root=identity,now=after+timedelta(minutes=2))
    assert second['sha256']==first['sha256'] and second['status']=='ALREADY_PUBLISHED'


def test_http_exact_published_edition_does_not_recompute_on_each_request(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    store,root,sources=setup(tmp_path)
    documents=tmp_path/'documents';documents.mkdir(mode=0o700)
    out=documents/'material_outbox'
    first=publish_material(out,sources,now=AT)
    expected=latest(out)[2]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return AT+timedelta(days=1)
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,news_search_workspaces=())
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    before=fingerprint(tmp_path)
    url=f'http://127.0.0.1:{server.server_port}/api/themes?'
    try:
        with urlopen(url.rstrip('?'),timeout=10) as r:
            assert r.status==200 and r.read()==expected  # unchanged receiver URL
        for _ in range(2):
            with urlopen(url+urlencode({'publication':'latest'}),timeout=10) as r:
                assert r.status==200 and r.read()==expected
        with pytest.raises(HTTPError) as e:urlopen(url+urlencode({'publication':'latest','as_of':(AT-timedelta(seconds=1)).isoformat()}))
        assert e.value.code==404
        with pytest.raises(HTTPError) as e:urlopen(url+'publication=latest&since='+T.isoformat())
        assert e.value.code==400
        assert fingerprint(tmp_path)==before
    finally:server.shutdown();server.server_close();thread.join(3)


def test_existing_scheduler_publishes_real_synthetic_source_outputs_once(tmp_path,monkeypatch):
    from scripts.run_approved_research_feeds_once import parser,execute
    from test_approved_research_feeds_once import _setup,_sample
    from newscatalystos import incremental_ingest
    from newscatalystos.new_source_adapter import parse_authorized_feed
    work=_setup(tmp_path);calls=[]
    def read(registry,provider,*,at=None):
        calls.append(provider)
        return parse_authorized_feed(registry,provider,_sample(provider),observed_at=at or datetime.now(timezone.utc))
    monkeypatch.setattr(incremental_ingest,'fetch_authorized_once',read)
    out=tmp_path/'outbox';base=tmp_path/'unused-base'
    args=['--workspaces-root',str(work),'--material-outbox',str(out),'--material-base-root',str(base)]
    code,dry=execute(parser().parse_args(args+['--dry-run']))
    assert code==0 and dry['material_delivery']['status']=='WOULD_PUBLISH' and not out.exists() and not calls
    code,first=execute(parser().parse_args(args+['--once']))
    assert code==0 and first['sources_checked']==5 and len(calls)==5
    assert first['material_delivery']['status']=='PUBLISHED'
    prior=first['material_delivery']['sha256']
    code,repeat=execute(parser().parse_args(args+['--once']))
    assert code==0 and len(calls)==5
    assert repeat['material_delivery']['status']=='ALREADY_PUBLISHED'
    assert repeat['material_delivery']['sha256']==prior
    assert repeat['ai_calls']==0 and repeat['era_api_calls']==0


def test_older_restored_source_does_not_silently_replace_newer_economic_evidence(tmp_path,monkeypatch):
    store,root,sources=setup(tmp_path)
    old=store.search(as_of=T,now=AT)
    store.ingest([event(2)],now=AT)
    publish_material(root,sources,now=AT)
    monkeypatch.setattr(ThemeStore,'search',lambda *a,**k:deepcopy(old))
    after=AT+timedelta(minutes=1)
    outcome=publish_material(root,sources,now=after)
    assert outcome['status']=='PUBLISHED_PARTIAL'
    theme=latest(root,after)[1]['ThemeCandidates'][0]
    assert len(theme['event_ids'])==2
    assert theme['material_publication_source']['status']=='LAST_GOOD_SOURCE_UNAVAILABLE'
