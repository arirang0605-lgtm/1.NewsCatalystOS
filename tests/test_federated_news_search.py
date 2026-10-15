"""Synthetic completed pipelines: isolated title search, not human gold evidence."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from newscatalystos.federated_news_search import (
    TitleSearchWorkspace, search_completed_workspaces,
)
from newscatalystos.feed_recovery import save_retry_checkpoint, acknowledge_retry_checkpoint
from newscatalystos.feed_triage import triage_committed_feed, publish_feed_triage
from newscatalystos.incremental_ingest import incremental_poll
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.news_search import read_completed_title_snapshots
from newscatalystos.provider_registry import ProviderRegistry, SCHEMA
from newscatalystos.source_share import SourceShareError
from scripts import search_news
from scripts.run_feed_triage import _registry
from test_new_source_adapter import NOW, registry

GOV = 'synthetic-government-feed'
WIRE = 'synthetic-wire-feed'
MINISTRY = 'synthetic-ministry-feed'
SAME = '반도체 설비 투자 10억원 발표'
REVISION = '반도체 설비 투자 20억원 정정'
SHARED = 'https://gov.example.org/semiconductor/1'


def write_registry(path, reg):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    rows = []
    for provider in reg.providers:
        row = asdict(provider)
        for name in ('reviewed_at', 'expires_at'):
            if row[name] is not None:
                row[name] = row[name].isoformat()
        rows.append(row)
    path.write_text(json.dumps({'schema': SCHEMA, 'providers': rows}))
    path.chmod(0o600)


def collect(workspace, reg, provider_id, items, *, at=NOW):
    """Exercise original checkpoint -> SQLite commit -> triage -> ACK stack."""
    payload = '<rss version="2.0"><channel>'
    for key, title, url in items:
        payload += ('<item><guid>' + escape(key) + '</guid><title>' + escape(title)
                    + '</title><link>' + escape(url) + '</link>'
                    + '<description>FULL ARTICLE BODY NOT FOR STORAGE</description></item>')
    payload += '</channel></rss>'
    received = []
    def fetch(source_registry, name, *, at):
        return parse_authorized_feed(source_registry, name, payload.encode(), observed_at=at)
    poll = incremental_poll(reg, provider_id, workspace.poll_state, now=at, fetcher=fetch,
        before_commit=lambda p: received.append(save_retry_checkpoint(workspace.inbox_root, p)))
    current = datetime.now(timezone.utc)
    triage = triage_committed_feed(reg, poll, workspace.poll_state.parent / 'dedup.sqlite3',
                                  decision_at=current, now=current)
    out = publish_feed_triage(triage, workspace.inbox_root.parent / 'results')
    ack = acknowledge_retry_checkpoint(workspace.inbox_root, received[0], out, triage.payload_sha256)
    return out, ack


def setup_workspace(root, scope, reg):
    base = root / scope
    workspace = TitleSearchWorkspace(scope, base / 'providers/approved.json',
                                    base / 'state/poll.sqlite3', base / 'inbox')
    write_registry(workspace.registry_path, reg)
    return workspace


@pytest.fixture
def sample(tmp_path):
    base = registry().providers[0]
    core_reg = ProviderRegistry((base, replace(base, provider_id=WIRE,
                               kind='LICENSED_NEWS', endpoint='https://wire.example.org/rss')))
    ministry_reg = ProviderRegistry((replace(base, provider_id=MINISTRY,
                                      endpoint='https://ministry.example.org/rss'),))
    core = setup_workspace(tmp_path, 'core', core_reg)
    ministry = setup_workspace(tmp_path, 'motir', ministry_reg)
    core_items = [('a', SAME, SHARED), ('b', REVISION, SHARED),
                  ('c', '중소기업 정책 설명', 'https://gov.example.org/policy/1')]
    core_out, _ = collect(core, core_reg, GOV, core_items)
    collect(core, core_reg, WIRE, [('d', SAME, 'https://wire.example.org/press/1')],
            at=NOW + timedelta(minutes=15))
    ministry_items = [('e', SAME, SHARED),
                      ('f', '반도체 지원 30억원', 'https://ministry.example.org/policy/2')]
    ministry_out, _ = collect(ministry, ministry_reg, MINISTRY, ministry_items,
                              at=NOW + timedelta(hours=1))
    return (core, ministry), (core_reg, ministry_reg), (core_out, ministry_out), core_items


def search(workspaces, **kwargs):
    return search_completed_workspaces(tuple(workspaces), '반도체', registry_reader=_registry, **kwargs)


def fingerprint(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_three_sources_one_readonly_search_preserves_versions(sample, tmp_path, monkeypatch):
    scopes, _, _, _ = sample
    import newscatalystos.feed_transport as transport
    def forbidden(*args, **kwargs):
        raise AssertionError('search attempted a network call')
    monkeypatch.setattr(transport, 'fetch_authorized_once', forbidden)
    import newscatalystos.feed_recovery as recovery
    monkeypatch.setattr(recovery, '_connect', forbidden)
    before = fingerprint(tmp_path)
    result = search(scopes)
    assert fingerprint(tmp_path) == before
    assert result['coverage_complete']
    assert result['verified_provider_count'] == 3
    assert result['searched_document_versions'] == 6
    assert result['keyword_hits'] == result['matched_document_versions'] == 5
    assert {x['headline'] for x in result['results']} == {SAME, REVISION, '반도체 지원 30억원'}
    assert result['independent_economic_event_count'] is None
    assert not result['fact_verified_by_search']
    assert result['network_calls'] == result['ai_calls'] == 0
    assert not result['source_databases_modified']
    assert all(not x['verified_supply_transaction'] and not x['confirmed_beneficiary']
               and not x['verified_economic_fact'] and not x['article_body_included']
               for x in result['results'])
    assert 'FULL ARTICLE BODY' not in json.dumps(result)
    assert not list(tmp_path.rglob('news_search.sqlite3'))


def test_exact_overlaps_do_not_merge_or_certify_independence(sample):
    result = search(sample[0])
    assert result['metadata_overlap_scope'] == 'RETURNED_RESULTS_ONLY'
    by_reason = {x['reason']: x for x in result['metadata_overlap_hints']}
    assert set(by_reason) == {'EXACT_NORMALIZED_TITLE', 'SHARED_CANONICAL_URL'}
    assert len(by_reason['EXACT_NORMALIZED_TITLE']['member_versions']) == 3
    assert not by_reason['EXACT_NORMALIZED_TITLE']['different_title_versions']
    assert len(by_reason['SHARED_CANONICAL_URL']['member_versions']) == 3
    assert by_reason['SHARED_CANONICAL_URL']['different_title_versions']
    assert all(x['review_required'] and not x['same_economic_event_verified']
               and not x['source_independence_verified'] for x in by_reason.values())
    again = search(sample[0])
    assert again['metadata_overlap_hints'] == result['metadata_overlap_hints']


def test_global_limit_and_source_filter_applied_after_combining(sample):
    result = search(sample[0], limit=1)
    assert result['keyword_hits'] == 1 and result['matched_document_versions'] == 5
    assert result['has_more_matches']
    assert result['results'][0]['provider_id'] == MINISTRY
    only = search(sample[0], source_id=WIRE)
    assert len(only['results']) == 1 and only['results'][0]['provider_id'] == WIRE
    assert only['results'][0]['source_kind'] == 'PRESS_RELEASE'
    assert only['metadata_overlap_hints'] == []


def test_repeated_collection_retains_earliest_version_time(sample):
    scopes, regs, _, core_items = sample
    collect(scopes[0], regs[0], GOV, core_items, at=NOW + timedelta(hours=2))
    result = search(scopes)
    assert result['searched_document_versions'] == 6
    assert result['scopes'][0]['acknowledged_triage_receipts_checked'] == 3
    assert all(x['source_available_at'] == NOW.isoformat()
               for x in result['results'] if x['provider_id'] == GOV)


def test_title_change_same_document_retained_as_new_version(sample):
    scopes, regs, _, _ = sample
    changed = '반도체 설비 투자 99억원 정정'
    collect(scopes[0], regs[0], GOV, [('a', changed, SHARED)], at=NOW + timedelta(hours=2))
    result = search(scopes)
    rows = [x for x in result['results'] if x['provider_id'] == GOV]
    assert {r['headline'] for r in rows} == {SAME, REVISION, changed}
    assert result['searched_document_versions'] == 7


def test_semiconductor_filter_excludes_advertising_not_source_facts(sample):
    scopes, regs, _, _ = sample
    collect(scopes[1], regs[1], MINISTRY,
            [('advert', '광고: 반도체 투자 100% 수익 보장', 'https://ministry.example.org/ad')],
            at=NOW + timedelta(hours=2))
    assert search(scopes)['keyword_hits'] == 6
    filtered = search(scopes, semiconductor_only=True)
    assert filtered['keyword_hits'] == 5
    assert all(r['analysis_candidate'] for r in filtered['results'])


def test_corrupt_scope_is_partial_and_never_uses_stale_cache(sample):
    scopes, _, outputs, _ = sample
    prior = search(scopes)
    assert prior['coverage_complete']
    target = outputs[1] / 'triage.json'
    target.write_bytes(target.read_bytes() + b'corrupt')
    result = search(scopes)
    assert not result['coverage_complete']
    assert result['status'] == 'FEDERATED_SEARCH_PARTIAL_DATA_UNAVAILABLE'
    assert result['verified_provider_count'] == 2
    assert result['searched_document_versions'] == 4
    assert result['scopes'][1]['status'] == 'SEARCH_DATA_UNAVAILABLE'
    assert all(x['search_scope'] == 'core' for x in result['results'])
    assert 'error_type' in result['scopes'][1]
    assert str(target) not in json.dumps(result)


def test_revoked_provider_not_visible_in_prior_metadata(sample):
    scopes, regs, _, _ = sample
    revoked = ProviderRegistry((regs[0].providers[0], replace(regs[0].providers[1], approved=False)))
    write_registry(scopes[0].registry_path, revoked)
    result = search(scopes)
    assert result['coverage_complete']
    assert result['verified_provider_count'] == 2
    assert all(x['provider_id'] != WIRE for x in result['results'])
    with pytest.raises(SourceShareError, match='unapproved'):
        search(scopes, source_id=WIRE)


def test_missing_one_approved_provider_is_not_complete(sample):
    scopes, regs, _, _ = sample
    extra = replace(regs[1].providers[0], provider_id='synthetic-not-yet-collected')
    write_registry(scopes[1].registry_path, ProviderRegistry(regs[1].providers + (extra,)))
    result = search(scopes)
    assert result['keyword_hits'] == 5 and not result['coverage_complete']
    assert result['scopes'][1]['status'] == 'INCOMPLETE_SOURCE_COVERAGE'
    assert result['scopes'][1]['missing_approved_provider_ids'] == [extra.provider_id]


def test_missing_workspace_not_created_or_hidden(sample, tmp_path):
    scopes, _, _, _ = sample
    absent = replace(scopes[1], inbox_root=tmp_path / 'absent/inbox')
    before = fingerprint(tmp_path)
    result = search((scopes[0], absent))
    assert fingerprint(tmp_path) == before
    assert not absent.inbox_root.exists()
    assert result['keyword_hits'] == 3 and not result['coverage_complete']


def test_new_shared_reader_does_not_create_missing_inbox(tmp_path):
    assert read_completed_title_snapshots(tmp_path / 'missing', tmp_path / 'poll.sqlite3', registry()) == ()
    assert list(tmp_path.iterdir()) == []


def test_duplicate_provider_across_workspaces_rejected_before_data(sample):
    scopes, regs, _, _ = sample
    write_registry(scopes[1].registry_path, regs[0])
    with pytest.raises(SourceShareError, match='multiple'):
        search(scopes)


def test_pit_search_before_ack_not_available(sample):
    result = search(sample[0], now=NOW)
    assert not result['coverage_complete']
    assert result['keyword_hits'] == 0
    assert result['searched_document_versions'] == 0


def test_unknown_source_rejected(sample):
    with pytest.raises(SourceShareError, match='unapproved'):
        search(sample[0], source_id='sec-submissions')


@pytest.mark.parametrize('phrase,limit', [('', 20), ('a', 20), ('a\x00b', 20),
                                         ('반도체', 0), ('반도체', True), ('반도체', 101)])
def test_bad_query_fails_before_read(tmp_path, phrase, limit):
    def no_read(path):
        raise AssertionError('bad query must fail before file read')
    workspace = TitleSearchWorkspace('core', tmp_path / 'reg.json', tmp_path / 'poll.sqlite3', tmp_path / 'inbox')
    with pytest.raises(SourceShareError, match='invalid'):
        search_completed_workspaces((workspace,), phrase, registry_reader=no_read, limit=limit)


def test_aliased_and_eraleader_paths_forbidden_before_read(sample, tmp_path):
    scopes, _, _, _ = sample
    for changed in (replace(scopes[1], poll_state=scopes[0].poll_state),
                    replace(scopes[1], poll_state=tmp_path / 'eraleader/poll.sqlite3')):
        with pytest.raises(SourceShareError, match='isolated'):
            search((scopes[0], changed))
    link = tmp_path / 'aliased'
    link.symlink_to(scopes[1].inbox_root, target_is_directory=True)
    with pytest.raises(SourceShareError, match='isolated'):
        search((scopes[0], replace(scopes[1], inbox_root=link)))


def cli_opts(scopes, *, scope='all'):
    core, ministry = scopes
    return search_news.parser().parse_args([
        '--query', '반도체', '--scope', scope,
        '--registry', str(core.registry_path), '--state', str(core.poll_state),
        '--inbox-root', str(core.inbox_root), '--motir-registry', str(ministry.registry_path),
        '--motir-state', str(ministry.poll_state), '--motir-inbox-root', str(ministry.inbox_root),
    ])


def test_cli_all_and_motir_keep_cache_unused(sample, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('federated mode must not open or modify a title cache')
    monkeypatch.setattr(search_news, 'sync_completed_titles', denied)
    code, all_sources = search_news.evaluate(cli_opts(sample[0]))
    assert code == 0 and all_sources['keyword_hits'] == 5
    code, ministry = search_news.evaluate(cli_opts(sample[0], scope='motir'))
    assert code == 0 and ministry['keyword_hits'] == 2
    assert {r['provider_id'] for r in ministry['results']} == {MINISTRY}
    assert search_news.parser().parse_args(['--query', '반도체']).scope == 'core'


def test_cli_partial_exit_four_keeps_healthy_scope_results(sample):
    scopes, _, _, _ = sample
    scopes[1].registry_path.unlink()
    code, result = search_news.evaluate(cli_opts(scopes))
    assert code == 4 and not result['coverage_complete']
    assert result['keyword_hits'] == 3
    assert result['scopes'][1]['status'] == 'SEARCH_DATA_UNAVAILABLE'
