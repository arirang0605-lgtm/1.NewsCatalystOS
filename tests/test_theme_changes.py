"""Synthetic period changes, with immutable original snapshots and no live calls."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import sqlite3
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from newscatalystos.theme_changes import compare_themes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.source_share import SourceShareError
from test_theme_emergence import T,event
from test_service_realization import pair

LATER=T+timedelta(hours=1)


def compare(store,start=LATER,end=LATER,**kw):
    return compare_themes(store,since=start,as_of=end,now=end,**kw)['ThemeChanges']


def test_exact_start_and_end_with_new_events_companies_and_pit(tmp_path):
    store=ThemeStore(tmp_path/'themes');first=store.ingest([event()],now=T)[0]
    last=store.ingest([event(2),event(3)],now=LATER)[0]
    store.ingest([event(4,industry='DATA_CENTER')],now=LATER+timedelta(hours=1))
    before=(store.root/'themes.sqlite3').read_bytes()
    result=compare(store)[0]
    assert result['before']['decision_at']==T.isoformat() and result['after']['decision_at']==LATER.isoformat()
    assert result['activity']=='updated' and result['events']['independent_actions_added']==2
    assert len(result['events']['added'])==2 and result['companies']['new_event_participant_count']==2
    assert result['status_transitions'][0]['from_status']=='CANDIDATE'
    assert result['status_transitions'][0]['to_status']=='EMERGING'
    assert len(result['status_transitions'][0]['evidence'])==2
    assert all(r['source_available_at']==T.isoformat() and r['recorded_at']==LATER.isoformat() for r in result['sources']['added'])
    assert not compare(store,query='가상기업4')
    assert compare(store,query='가상기업3',activity='updated')==[result]
    assert compare(store,start=T,end=T)[0]['before'] is None
    assert store.search(as_of=T,now=LATER)==[first]
    assert store.search(as_of=LATER,now=LATER)==[last]
    assert (store.root/'themes.sqlite3').read_bytes()==before


def test_no_news_is_unchanged_not_invalidated_or_new(tmp_path):
    store=ThemeStore(tmp_path/'themes');store.ingest([event()],now=T)
    result=compare(store,end=LATER+timedelta(days=100))[0]
    assert result['activity']=='unchanged' and result['after']['status']=='CANDIDATE'
    assert result['status_transitions']==[] and result['events']['added']==[]
    assert result['reasons'][0]['code']=='NO_CHANGE'
    assert not compare(store,activity='changed')


def test_reprints_add_source_not_event_or_company(tmp_path):
    store=ThemeStore(tmp_path/'themes');original=event();store.ingest([original],now=T)
    copy=deepcopy(original);copy['source_url']='https://press.example.org/reprint';copy['source_id']='press'
    store.ingest([copy],now=LATER)
    result=compare(store)[0]
    assert len(result['sources']['added'])==1 and result['events']['added']==[]
    assert result['events']['independent_actions_added']==0 and result['companies']['added']==[]
    assert result['status_transitions']==[]


def test_identity_update_does_not_invent_company_expansion(tmp_path):
    store=ThemeStore(tmp_path/'themes');row=event(company='가상기업')
    binding={'source_event_sha256':'a'*64,'document_sha256':'b'*64}
    row=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'event_id','change'}},source_binding=binding)
    store.ingest([row],now=T)
    later=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'event_id','change'}},
        company_mappings=[{'source_name':'가상기업','entity_id':'DART_CORP:12345678','evidence_sha256':'c'*64}])
    store.ingest([later],now=LATER)
    result=compare(store)[0]
    assert result['events']['added']==result['companies']['added']==result['companies']['removed']==[]
    assert result['companies']['new_event_participant_count']==0
    assert result['companies']['identity_updates'][0]['from_entity_id']=='가상기업'
    assert result['companies']['identity_updates'][0]['to_entity_id']=='DART_CORP:12345678'
    assert any(r['code']=='IDENTITY_UPDATED' for r in result['reasons'])


def test_plan_start_is_followup_not_a_second_economic_action(tmp_path):
    store=ThemeStore(tmp_path/'themes');plan,start=pair()
    store.ingest([plan],now=T);store.ingest([start],now=LATER)
    result=compare(store)[0]
    assert result['events']['independent_actions_added']==0
    assert result['events']['added'][0]['kind']=='FOLLOWUP_OBSERVATION'
    assert result['followups_added'][0]['is_realization_confirmed'] is False
    assert compare(store,start=T)[0]['events']['independent_actions_added']==1


def test_contradiction_retraction_and_reactivation_keep_intermediate_causes(tmp_path):
    store=ThemeStore(tmp_path/'themes');original=event();store.ingest([original],now=T)
    store.ingest([event(2,polarity='RETRACT',target=original['event_id'])],now=LATER)
    removed=compare(store)[0]
    assert removed['events']['removed'][0]['event_id']==original['event_id']
    assert removed['events']['removed'][0]['supporting_source']['source_url']==original['source_url']
    assert removed['companies']['removed'][0]['entity_id']=='가상기업1'
    assert removed['sources']['added'][0]['polarity']=='RETRACT'
    assert compare(store,query='가상기업1')==[removed]
    end=LATER+timedelta(hours=1);store.ingest([event(3)],now=end)
    result=compare(store,end=end)[0]
    assert [r['to_status'] for r in result['status_transitions']]==['INVALIDATED','REACTIVATED']
    assert result['status_transitions'][0]['evidence'][0]['supersedes_event_id']==original['event_id']
    assert result['status_transitions'][1]['evidence'][0]['event_id']==event(3)['event_id']
    assert result['events']['independent_actions_added']==result['events']['independent_actions_removed']==1
    # A contradiction is visible but does not remove the supported event.
    other=ThemeStore(tmp_path/'conflict');other.ingest([original],now=T)
    other.ingest([event(2,polarity='CONTRADICT',target=original['event_id'])],now=LATER)
    conflict=compare(other)[0]
    assert conflict['events']['removed']==[] and conflict['after']['status']=='WEAKENING'
    assert any(r['code']=='CONTRADICTION' for r in conflict['reasons'])


def test_first_observed_then_retracted_in_period_keeps_first_transition(tmp_path):
    store=ThemeStore(tmp_path/'themes');original=event();store.ingest([original],now=T)
    store.ingest([event(2,polarity='RETRACT',target=original['event_id'])],now=LATER)
    result=compare(store,start=T)[0]
    assert result['before'] is None and result['after']['status']=='INVALIDATED'
    assert [r['to_status'] for r in result['status_transitions']]==['CANDIDATE','INVALIDATED']
    assert result['events']['independent_actions_added']==0
    assert len(result['sources']['added'])==2


def test_supply_context_is_not_new_company_economic_expansion(tmp_path):
    from test_theme_supply_chain import setup,attach
    info,out,pub,store,_,first=setup(tmp_path)
    at=info[-1]+timedelta(seconds=1);attach(store,out,pub,at)
    result=compare(store,start=at,end=at)[0]
    assert result['events']['independent_actions_added']==0
    assert result['companies']['new_event_participant_count']==0
    assert result['companies']['added'][0]['kind']=='SUPPLY_CONTEXT'
    assert result['companies']['added'][0]['supply_chain_links']


@pytest.mark.parametrize('fault',['reverse','future','query','activity','digest'])
def test_invalid_query_or_corrupt_snapshot_rejected(tmp_path,fault):
    store=ThemeStore(tmp_path/'themes');store.ingest([event()],now=T)
    args={'since':T,'as_of':LATER,'now':LATER}
    if fault=='reverse':args['since']=LATER+timedelta(seconds=1)
    if fault=='future':args['now']=T
    if fault=='query':args['query']='a'*201
    if fault=='activity':args['activity']='invented'
    if fault=='digest':
        with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute("UPDATE versions SET digest=?",('f'*64,))
    with pytest.raises(SourceShareError):compare_themes(store,**args)


def test_absent_store_is_read_only_empty_result(tmp_path):
    store=ThemeStore(tmp_path/'missing')
    assert compare(store)==[] and not store.root.exists()


def test_cli_export_http_period_and_legacy_contract(tmp_path,capsys):
    from scripts.search_themes import main
    from scripts.open_research_dashboard import DashboardServer
    from newscatalystos.standard_delivery import build_theme_bundle
    docs=tmp_path/'docs';store=ThemeStore(docs/'theme_history');original=event()
    store.ingest([original],now=T)
    store.ingest([event(2,polarity='RETRACT',target=original['event_id'])],now=LATER)
    before=(store.root/'themes.sqlite3').read_bytes()
    assert main(['--root',str(store.root),'--changes','--since',LATER.isoformat(),'--as-of',LATER.isoformat(),
                 '--query','가상기업1','--export-root',str(tmp_path/'exports')])==0
    meta=json.loads(capsys.readouterr().out)
    from pathlib import Path
    raw=Path(meta['path']).read_bytes();assert sha256(raw).hexdigest()==meta['sha256']
    expected=json.loads(raw);assert expected['ThemeChanges'][0]['events']['removed']
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        query=urlencode({'since':LATER.isoformat(),'as_of':LATER.isoformat(),'q':'가상기업1'})
        with urlopen(base+'/api/theme-changes?'+query) as r:assert json.load(r)==expected
        with urlopen(base+'/api/period?view=day&date=2026-10-15') as r:period=json.load(r)
        change=next(iter(period['theme_changes'].values()))
        assert change['before'] is None and change['after']['status']=='INVALIDATED'
        assert period['theme_changes_status']=='READY'
        with urlopen(base+'/api/period?view=day&date=2099-01-01') as r:future=json.load(r)
        assert future['theme_changes']=={} and future['theme_changes_status']=='NOT_STARTED'
        with urlopen(base+'/api/themes?as_of='+LATER.isoformat().replace('+','%2B')) as r:legacy=json.load(r)
        assert legacy==json.loads(build_theme_bundle(store.search(as_of=LATER),decision_at=LATER))
        assert (store.root/'themes.sqlite3').read_bytes()==before
        # Optional comparison failure must not hide valid existing theme cards.
        with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute('UPDATE versions SET digest=? WHERE decision_at=?',('f'*64,T.isoformat()))
        with urlopen(base+'/api/period?view=day&date=2026-10-15') as r:unavailable=json.load(r)
        assert unavailable['theme_changes_status']=='UNAVAILABLE' and unavailable['theme_status']=='READY'
        assert len(unavailable['themes'])==1
    finally:server.shutdown();server.server_close();thread.join(2)
