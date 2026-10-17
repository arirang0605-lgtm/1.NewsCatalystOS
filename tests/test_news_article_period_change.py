"""An exact saved article opens existing PIT theme changes, not another search or event."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
from copy import deepcopy
import json
import sqlite3
import threading

import pytest

from newscatalystos.theme_emergence import ThemeStore, economic_observation
from scripts.open_research_dashboard import DashboardServer
from test_saved_article_evidence import connected, request
from test_federated_news_search import fingerprint, sample


def _case(connected, tmp_path):
    workspaces, row, theme_root, first_at = connected
    theme, = ThemeStore(theme_root).search(now=datetime.now(timezone.utc))
    params = {'q':'가상전자','provider_id':row['provider_id'],
              'event_id':row['event_id'],'title_sha256':row['title_sha256'],
              'theme_id':theme['theme_id']}
    server = DashboardServer(0, tmp_path/'reports', tmp_path/'notes',
                             theme_root.parent, news_search_workspaces=workspaces)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, params, theme_root, first_at


def test_article_theme_period_initial_no_change_and_pit(connected, tmp_path):
    before = fingerprint(tmp_path)
    server, thread, query, _, first = _case(connected, tmp_path)
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        # First discovery is one event group for each actual action.
        params={**query,'since':first.isoformat(),
                'as_of':datetime.now(timezone.utc).isoformat()}
        code, data=request(base, params)
        assert code==200 and data['theme_change_status']=='READY'
        change=data['theme_change']
        assert change['before'] is None
        assert change['events']['independent_actions_added']==2
        assert {r['code'] for r in change['reasons']} >= {'FIRST_OBSERVED','NEW_ECONOMIC_EVENTS'}
        assert len(change['sources']['added'])==2
        assert not data['verified_real_benefit']

        # Later empty period means no new event, not a weakened theme.
        params['since']=(first+timedelta(microseconds=1)).isoformat()
        _, data=request(base, params)
        assert data['theme_change_status']=='NO_CHANGE'
        change=data['theme_change']
        assert change['activity']=='unchanged' and change['reasons'][0]['code']=='NO_CHANGE'
        assert change['events']['added']==[] and change['sources']['added']==[]
        assert change['events']['independent_actions_added']==0
        assert change['status_transitions']==[]

        # No retrospectively available evidence from a future article version.
        params['since']=(first-timedelta(seconds=1)).isoformat()
        params['as_of']=(first-timedelta(microseconds=1)).isoformat()
        with pytest.raises(HTTPError) as err:request(base,params)
        assert err.value.code==404
        # Article cannot read another theme ID, irrespective of keyword overlap.
        params['as_of']=datetime.now(timezone.utc).isoformat()
        params['theme_id']='f'*64
        with pytest.raises(HTTPError) as err:request(base,params)
        assert err.value.code==404
        params['theme_id']='invalid'
        with pytest.raises(HTTPError) as err:request(base,params)
        assert err.value.code==400
        for bad in ({'since':datetime.now(timezone.utc).isoformat(),'as_of':first.isoformat()},
                    {'since':first.isoformat(),'as_of':(first+timedelta(days=3)).isoformat()}):
            with pytest.raises(HTTPError) as err:
                request(base,{**query,**bad})
            assert err.value.code==400
        for field in ['since','theme_id','as_of']:
            with pytest.raises(HTTPError) as err:
                request(base,{k:v for k,v in params.items() if k!=field})
            assert err.value.code==400
    finally:
        server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path)==before


def test_same_event_second_source_is_additional_evidence_not_new_action(connected,tmp_path):
    workspaces,row,theme_root,first=connected
    with sqlite3.connect('file:'+str(theme_root/'themes.sqlite3')+'?mode=ro',uri=True) as db:
        original=json.loads(db.execute('SELECT payload FROM observations LIMIT 1').fetchone()[0])
    now=datetime.now(timezone.utc)
    # One independent publisher reports the SAME bounded title claim; it
    # contains no newer economic event or separate customer/company.
    replay=economic_observation(original['change'],
        origin_reference='https://other-press.example/reprint',
        source_url='https://other-press.example/reprint',source_id='independent-press',
        source_available_at=original['source_available_at'],content_scope='RSS_TITLE_METADATA')
    assert replay['event_id']==original['event_id']
    store=ThemeStore(theme_root)
    assert store.ingest([replay],now=now)
    s,t,params,_,_= _case(connected,tmp_path)
    base=f'http://127.0.0.1:{s.server_port}'
    try:
        params.update(since=(first+timedelta(microseconds=1)).isoformat(),
                      as_of=datetime.now(timezone.utc).isoformat())
        code,data=request(base,params)
        assert code==200 and data['theme_change_status']=='READY'
        delta=data['theme_change']
        assert delta['activity']=='updated'
        assert delta['events']['independent_actions_added']==0
        assert delta['events']['added']==[]
        assert delta['companies']['new_event_participant_count']==0
        assert len(delta['sources']['added'])==1
        assert delta['sources']['added'][0]['source_id']=='independent-press'
        assert [r['code'] for r in delta['reasons']]==['ADDITIONAL_SOURCE']
        assert not delta['status_transitions']
    finally:
        s.shutdown();s.server_close();t.join(2)


def test_exact_article_theme_exposes_official_retraction_without_new_event(connected,tmp_path):
    _,row,theme_root,first=connected
    with sqlite3.connect('file:'+str(theme_root/'themes.sqlite3')+'?mode=ro',uri=True) as db:
        original=json.loads(db.execute('SELECT payload FROM observations LIMIT 1').fetchone()[0])
    from test_theme_emergence import event
    correction=event(99,topic=original['change']['topic'],company='가상전자',
                     polarity='RETRACT',target=original['event_id'])
    changed=deepcopy(correction['change'])
    if original['change'].get('demand_scope'):
        changed['demand_scope']=deepcopy(original['change']['demand_scope'])
    row2=economic_observation(changed,
        origin_reference='https://official.example.org/source-correction',
        source_url='https://official.example.org/source-correction',
        source_id='synthetic-official-correction',
        source_available_at=first.isoformat(),polarity='RETRACT',
        supersedes_event_id=original['event_id'])
    ThemeStore(theme_root).ingest([row2],now=datetime.now(timezone.utc))
    server,thread,params,_,_=_case(connected,tmp_path)
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        params.update(since=(first+timedelta(microseconds=1)).isoformat(),
                      as_of=datetime.now(timezone.utc).isoformat())
        code,data=request(base,params)
        assert code==200 and data['theme_change_status']=='READY'
        delta=data['theme_change']
        assert delta['events']['independent_actions_added']==0
        assert delta['events']['independent_actions_removed']==1
        assert delta['events']['removed'][0]['event_id']==original['event_id']
        assert delta['sources']['added'][0]['polarity']=='RETRACT'
        assert delta['sources']['added'][0]['supersedes_event_id']==original['event_id']
        assert {'RETRACTION','ACTIVE_EVENTS_REMOVED'} <= {r['code'] for r in delta['reasons']}
        assert delta['after']['status']=='WEAKENING'
    finally:
        server.shutdown();server.server_close();thread.join(2)
