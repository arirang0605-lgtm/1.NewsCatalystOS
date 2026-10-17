"""An old reserved semantic call cannot stop a healthy scheduled RSS pipeline.

Synthetic approved source and model only; no network, paid call, or operating DB.
"""
from argparse import Namespace
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3

from newscatalystos.ai_cost_ledger import existing_invocation_state, reserve_ai_call
from newscatalystos.ai_provider import AIRequest
from newscatalystos.feed_analysis import analyze_completed_feed
from newscatalystos.news_semantics import PROMPT_VERSION, analyze_title, validate_saved
from scripts.run_scheduled_triage import _analyze_provider
from test_ai_provider import config
from test_feed_analysis import setup, run, TITLE, URL
from test_federated_news_search import setup_workspace, collect, GOV, fingerprint
from test_new_source_adapter import registry
from test_news_semantics import proposal, response
from test_ai_gemini_transport import LocalOpener


def _no_network(*args, **kwargs):
    raise AssertionError("no paid provider or network call allowed")


def test_reserved_semantic_event_is_reused_as_unsettled_without_another_api_call(tmp_path):
    info = setup(tmp_path)
    row = run(info)['results'][0]
    now = datetime.now(timezone.utc)
    model = replace(config("GEMINI"), prompt_version=PROMPT_VERSION)
    metadata = 'Unverified RSS title: ' + row['headline']
    request = AIRequest(row['analysis_event_sha256'], metadata, 'LICENSED_METADATA',
                        datetime.fromisoformat(row['source_available_at']), now, False, False,
                        analysis_purpose='EXISTING_ARTICLE')
    ledger = tmp_path / 'private/ledger.sqlite3'
    assert existing_invocation_state(ledger, model, request, now=now) is None
    assert not ledger.exists() and not ledger.parent.exists()
    pending = reserve_ai_call(ledger, model, request, now=now)
    assert pending.status == 'RESERVED'
    before = sha256(ledger.read_bytes()).hexdigest()
    assert existing_invocation_state(ledger, model, request, now=now) == 'UNSETTLED'
    status, called = analyze_title(
        row, config("GEMINI"), info[-1]/'missing_cache.sqlite3', ledger,
        allow_paid=True, now=now, opener=_no_network, clock=now)
    assert status == {'status':'AI_PREVIOUS_CALL_UNSETTLED'} and called is False
    assert not (info[-1]/'missing_cache.sqlite3').exists()
    assert sha256(ledger.read_bytes()).hexdigest() == before
    report = dict(row, semantic_analysis=status)
    validate_saved(report, now)


def test_scheduler_keeps_incomplete_optional_semantics_visible_without_failing_source():
    opts = Namespace(registry=None, state=None, inbox_root=None, output_root=None,
                     analysis_scope='motir', semantic_ai=True, allow_paid_ai=True,
                     analysis_root=__import__('pathlib').Path('/private/tmp/semantic-offline-test'),
                     analysis_limit=100, semantic_call_limit=1)
    example = {'semantic_analysis':{'status':'AI_PREVIOUS_CALL_UNSETTLED'},
               'ai_eligible':False, 'ai_status':'NOT_ELIGIBLE'}
    saved = {'status':'FEED_ECONOMIC_ANALYSIS_READY', 'requested_ai_complete':False,
             'semantic_ai_attempts':0, 'results':[example],
             'source_versions_checked':1, 'new_ai_results':0,
             'economic_changes_count':0, 'theme_versions_created':0}
    code, summary = _analyze_provider(opts, GOV, lambda _: (4, saved))
    assert code == 0 and summary['exit_code'] == 0
    assert summary['semantic_ai_incomplete'] == 1
    assert summary['semantic_ai_deferred'] == 1
    assert summary['requested_ai_complete'] is False
    assert summary['optional_semantic_incomplete'] is True
    assert summary['semantic_ai_attempts'] == 0
    # If this is an important eligible new event, its failed AI is NOT optional.
    necessary = {**example, 'ai_eligible':True}
    code, summary = _analyze_provider(opts, GOV, lambda _: (4,{**saved,'results':[necessary]}))
    assert code == 4 and not summary['optional_semantic_incomplete']
    # Failed ingestion/report publication remains a real scheduler failure.
    code, _ = _analyze_provider(opts, GOV, lambda _: (4,{'status':'FEED_ANALYSIS_INPUT_UNAVAILABLE'}))
    assert code == 4


def test_scheduled_old_context_does_not_pay_but_new_v1_semiconductor_can(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    model = config('GEMINI')
    # Prior completed metadata may still be searched, but must not mint a
    # new billed request on each hourly scheduler invocation.
    reg = registry()
    source = setup_workspace(tmp_path/'old','old',reg)
    collect(source, reg, GOV, [('old-claim',TITLE,URL)],
            at=now-timedelta(days=3))
    now = datetime.now(timezone.utc)  # ACK was committed after the earlier clock read.
    work = tmp_path/'old_analysis'
    old = analyze_completed_feed(reg, source.inbox_root, source.poll_state, work,
        model=model, allow_paid=True, semantic_ai=True,
        semantic_scheduled_only=True, now=now, opener=_no_network)
    assert old['semantic_ai_attempts'] == 0
    assert old['results'][0]['semantic_analysis']['status']=='NOT_ANALYZED_NO_CALL'
    assert not (work/'ai_costs.sqlite3').exists()

    # A fresh source-backed V1-sector headline still has a normal success path
    # through the already-budgeted synthetic Gemini adapter.
    workspace=setup_workspace(tmp_path/'fresh','fresh',registry())
    title,event=proposal(topic='HBM')
    collect(workspace,registry(),GOV,[('recent-event',title,'https://gov.example.org/hbm')],
            at=now-timedelta(minutes=3))
    monkeypatch.setenv("GEMINI_API_KEY","synthetic-offline-key-for-tests")
    opener=LocalOpener(response(event))
    now=datetime.now(timezone.utc)
    fresh=analyze_completed_feed(registry(),workspace.inbox_root,workspace.poll_state,
        tmp_path/'fresh_analysis',model=model,allow_paid=True,semantic_ai=True,
        semantic_scheduled_only=True,now=now,opener=opener)
    assert fresh['semantic_ai_attempts']==1 and opener.calls==1
    assert fresh['results'][0]['semantic_analysis']['status']=='ANALYZED'
    assert fresh['results'][0]['economic_changes'][0]['topic']=='HBM'
    assert fresh['verified_economic_facts']==0
