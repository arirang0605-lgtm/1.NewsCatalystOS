"""Synthetic RSS titles and pinned directory metadata; no network or paid AI."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from newscatalystos import official_filing_context as filing
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.source_share import SourceShareError
from newscatalystos.standard_delivery import build_theme_bundle, read_theme_bundle
from newscatalystos.theme_emergence import ThemeStore
from scripts import run_feed_analysis, run_scheduled_triage
from test_article_company_identity import context
from test_feed_analysis import setup, run
from test_federated_news_search import fingerprint
from test_scheduled_feed_analysis import opts, no_call


def directory(tmp_path, monkeypatch, rows):
    config = tmp_path / 'identity.json'
    config.write_text(json.dumps({k: str(tmp_path/k) for k in ('era_root','era_report','independent_anchor')}))
    config.chmod(0o600)
    monkeypatch.setattr(filing, 'read_pinned_filing_context', lambda *a, **kw: rows)
    return config


def test_existing_event_enriched_without_duplicates_and_with_pit(tmp_path, monkeypatch):
    source, _, _, _, work = setup(tmp_path, '별빛공업, HBM 수요 증가에 대응해 공급계약 체결')
    work = tmp_path/'analysis/core'
    params = opts(source, work, operation='--replay-only')
    at = datetime.now(timezone.utc) + timedelta(minutes=1)
    def tick():
        return run_scheduled_triage.execute(params,
            feed_runner=lambda _: (0, {'status':'NO_PENDING_REPLAY'}),
            analysis_runner=lambda a: run_feed_analysis.evaluate(a, opener=no_call, now=at))
    before = fingerprint(source.inbox_root.parent)
    code, result = tick()
    assert code == 0
    store = ThemeStore(work/'theme_history')
    earliest = store.search(now=at)
    assert earliest[0]['entity_ids'] == []
    first_time = at
    at += timedelta(minutes=1)
    rows = {'one': context(at, '별빛공업')}
    params.company_identity_config = directory(tmp_path, monkeypatch, rows)
    code, result = tick()
    detail = result['providers'][0]['analysis']
    assert code == 0 and detail['theme_versions_created'] == 1
    path = Path(detail['private_report_file'])
    saved = consume_feed_analysis(path, path.parent, detail['report_sha256'], now=at)
    row = saved['results'][0]
    assert row['economic_changes'][0]['original_entity_ids'] == []
    identity = row['company_identity']
    assert identity['matches'][0]['entity_id'] == 'DART_CORP:00000001'
    current = store.search(now=at)
    assert current[0]['event_ids'] == earliest[0]['event_ids']
    assert current[0]['entity_ids'] == ['DART_CORP:00000001']
    assert current[0]['scores']['distinct_economic_events'] == 1
    assert current[0]['verified_beneficiary_count'] == 0
    assert store.search(as_of=first_time, now=at) == earliest
    raw = build_theme_bundle(current, decision_at=at, now=at)
    assert read_theme_bundle(raw, sha256(raw).hexdigest(), decision_at=at, now=at)['ThemeCandidates'] == current
    cards, info = scan_saved_analysis(work.parent, now=at)
    assert info['saved_reports_skipped'] == 0
    assert cards[0]['company_identity'] == identity
    assert scan_saved_analysis(work.parent, now=first_time)[0][0]['company_identity'] is None
    assert scan_saved_analysis(work.parent, now=at, as_of=first_time)[0][0]['company_identity'] is None
    rows['one'] = replace(rows['one'], local_context_verified_at=at+timedelta(seconds=1))
    at += timedelta(minutes=1)
    code, replay = tick()
    assert code == 0 and replay['providers'][0]['analysis']['theme_versions_created'] == 0
    assert store.search(now=at) == current
    assert fingerprint(source.inbox_root.parent) == before
    assert len(list((work/'company_identity').glob('*.json'))) == 1
    # New directory version becomes a new observation, never edits past history.
    enriched_at = at
    rows['one'] = replace(rows['one'], issuer_code_observed='00000002', original_sha256='c'*64)
    at += timedelta(minutes=1)
    assert tick()[0] == 0
    assert len(list((work/'company_identity').glob('*.json'))) == 2
    assert store.search(now=at)[0]['entity_ids'] == ['DART_CORP:00000002']
    assert store.search(as_of=enriched_at, now=at) == current


@pytest.mark.parametrize('title,expected', [
    ('별빛공업은 HBM 공급계약 체결', ['별빛공업']),
    ('별빛공업서비스, HBM 공급계약 체결', []),
    ('새빛공업, HBM 공급계약 체결', []),
    ('별빛공업, 서비스 ‘초록길’ 출시', ['별빛공업']),
])
def test_only_whole_directory_names_are_matched(tmp_path, monkeypatch, title, expected):
    info = setup(tmp_path, title)
    at = datetime.now(timezone.utc)
    config = directory(tmp_path, monkeypatch, {'a':context(at, '별빛공업')})
    row = run(info, company_identity_config=config)['results'][0]
    assert [r['source_name'] for r in row['company_identity']['matches']] == expected
    if expected:
        assert row['economic_changes'][0]['entity_ids'] == expected
    assert row['verified_beneficiary'] is False


def test_ambiguous_future_and_unavailable_directory_do_not_block_news(tmp_path, monkeypatch):
    info = setup(tmp_path, '별빛공업, HBM 공급계약 체결')
    at = datetime.now(timezone.utc)
    rows = {'a':context(at, '별빛공업'), 'b':context(at, '별빛공업','00000002')}
    config = directory(tmp_path, monkeypatch, rows)
    row = run(info, company_identity_config=config)['results'][0]
    assert row['company_identity']['matches'] == []
    assert row['company_identity']['unresolved'] == [{'source_name':'별빛공업','status':'AMBIGUOUS'}]
    rows['a'] = replace(rows['a'], local_context_verified_at=at+timedelta(days=1))
    row = run(info, company_identity_config=config)['results'][0]
    assert row['company_identity_status'] == 'UNAVAILABLE' and 'company_identity' not in row
    config.write_text('{}')
    row = run(info, company_identity_config=config)['results'][0]
    assert row['economic_changes'] and row['company_identity_status'] == 'UNAVAILABLE'
    # A custom analysis root never implicitly opens the installed directory.
    assert run(info)['results'][0]['company_identity_status'] == 'NOT_CONFIGURED'


@pytest.mark.parametrize('fault', ['title', 'source', 'future', 'benefit', 'evidence'])
def test_saved_identity_remains_bound_to_title_and_time(tmp_path, monkeypatch, fault):
    info = setup(tmp_path, '별빛공업, HBM 공급계약 체결')
    config = directory(tmp_path, monkeypatch, {'a':context(datetime.now(timezone.utc), '별빛공업')})
    report = run(info, company_identity_config=config)
    bad = deepcopy(report)
    identity = bad['results'][0]['company_identity']
    if fault == 'title': bad['results'][0]['headline'] = '다른 회사 HBM 공급계약 체결'
    if fault == 'source': identity['source_event_sha256'] = 'f'*64
    if fault == 'future': identity['decision_at'] = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    if fault == 'benefit': identity['verified_real_benefit'] = True
    if fault == 'evidence': identity['matches'][0]['original_sha256'] = 'c'*64
    path, digest = publish_feed_analysis(bad, tmp_path/'reports')
    with pytest.raises(SourceShareError): consume_feed_analysis(path, path.parent, digest)


def test_raw_title_hash_differs_from_normalized_display_title(tmp_path, monkeypatch):
    info = setup(tmp_path, '별빛공업,  HBM 공급계약 체결')
    config = directory(tmp_path, monkeypatch, {'a':context(datetime.now(timezone.utc), '별빛공업')})
    report = run(info, company_identity_config=config)
    row = report['results'][0]
    assert row['company_identity_status'] == 'READY'
    assert row['source_title_sha256'] != sha256(row['headline'].encode()).hexdigest()
    assert row['company_identity']['matches'][0]['source_name'] == '별빛공업'
    path, digest = publish_feed_analysis(report, tmp_path/'reports')
    assert consume_feed_analysis(path, path.parent, digest)['results'] == report['results']


def test_existing_ai_summary_does_not_hide_later_identity(tmp_path, monkeypatch):
    from test_ai_openai_transport import LocalOpener, packet
    from test_ai_provider import config as model_config
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-material-not-real-abcdef0123456789')
    info = setup(tmp_path, '별빛공업, 글로벌 반도체 업계 3년간 HBM 1조원 공급계약 체결')
    info = (*info[:4], tmp_path/'analysis/core')
    root = info[4]/'reports'
    first = run(info, model=model_config(), allow_paid=True, opener=LocalOpener(packet()))
    assert first['results'][0]['ai_analysis'] is not None
    publish_feed_analysis(first, root)
    identity_config = directory(tmp_path, monkeypatch, {'a':context(datetime.now(timezone.utc), '별빛공업')})
    second = run(info, company_identity_config=identity_config)
    publish_feed_analysis(second, root)
    cards, _ = scan_saved_analysis(info[4].parent, now=datetime.now(timezone.utc))
    assert cards[0]['ai_summary'] == first['results'][0]['ai_analysis']['summary']
    assert cards[0]['company_identity'] == second['results'][0]['company_identity']
    assert cards[0]['company_identity_analysis_available_at'] == second['results'][0]['analysis_available_at']
