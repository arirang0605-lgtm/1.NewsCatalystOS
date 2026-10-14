"""Stored RSS reports -> independent reader. Sources/model replies here are synthetic."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from newscatalystos import feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis, SCHEMA
from newscatalystos.source_share import SourceShareError
from scripts import consume_feed_analysis as cli, run_feed_analysis as producer
from test_federated_news_search import setup_workspace, collect, fingerprint, GOV
from test_new_source_adapter import registry
from test_ai_openai_transport import LocalOpener, packet
from test_ai_provider import config


def produce(tmp_path, *, model=False, paid=False, empty=False, opener=None):
    source = setup_workspace(tmp_path, 'source', registry())
    if not empty:
        collect(source, registry(), GOV, [
            ('a', '글로벌 HBM 반도체 3년간 공급 계약 2000억원 체결', 'https://gov.example.org/a'),
            ('b', 'HBM 반도체 설비 투자 발표', 'https://gov.example.org/b'),
            ('c', '광고: 반도체 무료 리딩 안내', 'https://gov.example.org/c'),
        ], at=datetime.now(timezone.utc))
    args = ['--registry', str(source.registry_path), '--state', str(source.poll_state),
            '--inbox-root', str(source.inbox_root), '--analysis-root', str(tmp_path / 'derived'),
            '--limit', '100']
    if model:
        path = source.registry_path.parent / 'model.json'
        path.write_text(json.dumps(asdict(config()))); path.chmod(0o600)
        args.extend(['--model-config', str(path)])
    if paid:
        args.append('--allow-paid')
    opts = producer.parser().parse_args(args)
    code, report = producer.evaluate(opts, opener=opener)
    assert 'private_report_file' in report, (code, report)
    return opts, code, report


def read(report, **kwargs):
    path = Path(report['private_report_file'])
    return consume_feed_analysis(path, path.parent, report['report_sha256'], **kwargs)


def args(report):
    path = Path(report['private_report_file'])
    return ['--report-file', str(path), '--reports-root', str(path.parent),
            '--expected-sha256', report['report_sha256']]


def republish(report, transform):
    path = Path(report['private_report_file'])
    data = json.loads(path.read_bytes()); transform(data)
    file, digest = feed_analysis.publish_feed_analysis(data, path.parent)
    return {'private_report_file': str(file), 'report_sha256': digest}


def fail(*args, **kwargs):
    raise AssertionError('reader tried to use collection, AI or database')


def test_rules_report_fields_preserved_without_db_network_or_reanalysis(tmp_path, monkeypatch):
    _, code, stored = produce(tmp_path)
    assert code == 0
    before = fingerprint(tmp_path)
    import socket
    monkeypatch.setattr(socket, 'create_connection', fail)
    monkeypatch.setattr(sqlite3, 'connect', fail)
    monkeypatch.setattr(feed_analysis, 'analyze_completed_feed', fail)
    monkeypatch.setattr(feed_analysis, 'run_budgeted_openai_analysis', fail)
    out = read(stored, limit=100)
    assert out['schema'] == SCHEMA and out['returned_result_count'] == 3
    assert out['results'] == stored['results']
    assert out['routing_assumptions_not_acceptance_criteria'] == stored['routing_assumptions_not_acceptance_criteria']
    assert out['consumer_available_at'] >= stored['checked_at']
    assert out['ai_calls'] == out['database_writes'] == out['source_fetch_calls'] == 0
    assert not out['historical_decision_certified'] and not out['source_freshness_certified']
    assert out['market_action'] is None and not out['report_modified']
    assert fingerprint(tmp_path) == before


def test_source_event_and_title_filter_never_substitutes_another_item(tmp_path):
    _, _, stored = produce(tmp_path)
    target = stored['results'][1]
    out = read(stored, provider_id=GOV, event_id=target['source_event_sha256'],
               title_sha256=target['source_title_sha256'])
    assert out['results'] == [target] and out['report_result_count'] == 3
    assert read(stored, event_id='f'*64)['returned_result_count'] == 0
    assert read(stored, provider_id='missing-provider')['returned_result_count'] == 0
    with pytest.raises(SourceShareError):
        read(stored, title_sha256=target['source_title_sha256'])


def test_pagination_retains_original_order_and_producer_coverage_counts(tmp_path):
    _, _, stored = produce(tmp_path)
    first = read(stored, limit=2)
    last = read(stored, limit=2, offset=2)
    assert first['has_more_matches'] and not last['has_more_matches']
    assert first['results'] + last['results'] == stored['results']
    assert first['producer_summary']['matched_versions'] == 3
    assert last['producer_summary'] == first['producer_summary']
    assert read(stored, offset=3)['results'] == []


def test_empty_saved_report_is_valid_but_not_a_successful_analysis(tmp_path):
    _, code, stored = produce(tmp_path, empty=True)
    out = read(stored)
    assert code == 0 and out['status'] == 'NO_COMPLETED_FEED_INPUT'
    assert out['results'] == [] and out['producer_checked_at'] is None
    assert out['returned_result_count'] == out['report_result_count'] == 0


def test_ai_and_cache_results_are_preserved_but_reader_makes_no_new_call(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-synthetic-key-01234567890123456789')
    stub = LocalOpener(packet())
    options, code, first = produce(tmp_path, model=True, paid=True, opener=stub)
    assert code == 0 and stub.calls == 1
    analyzed = read(first)
    assert analyzed['results'] == first['results']
    options.allow_paid = False
    code, cached = producer.evaluate(options)
    assert code == 0 and cached['cache_hits'] == 1
    monkeypatch.delenv('OPENAI_API_KEY')
    monkeypatch.setattr(feed_analysis, 'run_budgeted_openai_analysis', fail)
    out = read(cached)
    assert out['results'] == cached['results']
    assert out['producer_summary']['cache_hits'] == 1 and out['ai_calls'] == 0
    assert stub.calls == 1


def test_failed_ai_leaves_source_fields_and_requested_incomplete_status_visible(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-synthetic-key-01234567890123456789')
    _, code, stored = produce(tmp_path, model=True, paid=True, opener=LocalOpener(b'not-json'))
    assert code == 4
    out = read(stored)
    assert out['results'] == stored['results']
    assert out['producer_summary']['requested_ai_complete'] is False
    assert any(row['source_matched_fields'] for row in out['results'])
    assert all(row['ai_analysis'] is None for row in out['results'])


def test_old_report_uses_current_consumer_time_not_backdated_source_time(tmp_path):
    _, _, stored = produce(tmp_path)
    later = datetime.now(timezone.utc) + timedelta(days=1)
    out = read(stored, now=later)
    assert out['consumer_available_at'] == later.isoformat()
    assert out['results'] == stored['results']
    assert out['producer_checked_at'] == stored['checked_at']
    assert not out['historical_decision_certified']


@pytest.mark.parametrize('field,value', [
    ('schema', 'newscatalyst.beneficiary_graph.v2'),
    ('checked_at', '2099-01-01T00:00:00+00:00'),
    ('verified_economic_facts', 1), ('market_action', 'BUY'),
])
def test_wrong_schema_future_report_or_certification_not_accepted(tmp_path, field, value):
    _, _, stored = produce(tmp_path)
    if field == 'schema':
        # Bypass the producer only for a deliberately invalid reader fixture.
        original = Path(stored['private_report_file'])
        data = json.loads(original.read_bytes())
        data[field] = value
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode()
        digest = sha256(raw).hexdigest()
        path = original.parent / ('feed_analysis_' + digest + '.json')
        path.write_bytes(raw)
        path.chmod(0o600)
        altered = {'private_report_file': str(path), 'report_sha256': digest}
    else:
        altered = republish(stored, lambda data: data.update({field: value}))
    with pytest.raises(SourceShareError):
        read(altered)


@pytest.mark.parametrize('field,value', [
    ('analysis_event_sha256', 'f'*64), ('verified_beneficiary', True),
    ('source_available_at', '2099-01-01T00:00:00+00:00'),
])
def test_source_identity_and_pit_are_checked_before_returning_any_results(tmp_path, field, value):
    _, _, stored = produce(tmp_path)
    bad = republish(stored, lambda data: data['results'][-1].update({field: value}))
    with pytest.raises(SourceShareError):
        read(bad, limit=1)


def test_modified_report_or_wrong_expected_digest_fails_without_echoing_content(tmp_path):
    _, _, stored = produce(tmp_path)
    options = cli.parser().parse_args(args(stored))
    options.expected_sha256 = 'f'*64
    code, err = cli.evaluate(options)
    assert code == 4 and 'results' not in err
    options.expected_sha256 = stored['report_sha256']
    Path(stored['private_report_file']).write_bytes(b'private modified data')
    assert cli.evaluate(options)[0] == 4
    assert str(tmp_path) not in json.dumps(err)


def test_missing_root_and_symlink_never_create_or_modify_files(tmp_path):
    missing = tmp_path / 'missing'
    with pytest.raises(SourceShareError):
        consume_feed_analysis(missing / ('feed_analysis_'+'f'*64+'.json'), missing, 'f'*64)
    assert not missing.exists()
    _, _, stored = produce(tmp_path)
    path = Path(stored['private_report_file'])
    saved = path.read_bytes(); other = path.with_name('outside.json')
    other.write_bytes(saved); other.chmod(0o600)
    path.unlink(); path.symlink_to(other)
    with pytest.raises(SourceShareError):
        read(stored)
    assert other.read_bytes() == saved


def test_actual_separate_consumer_process_reads_report_after_input_sources_removed(tmp_path):
    _, _, stored = produce(tmp_path)
    # Consumer has no dependency on the original registry or state path.
    for path in (tmp_path / 'source').rglob('*.sqlite3'):
        path.unlink()
    project = Path(__file__).resolve().parent.parent
    original = fingerprint(tmp_path)
    child = subprocess.run([sys.executable, str(project / 'scripts/consume_feed_analysis.py'),
                            *args(stored), '--limit', '100'], cwd=tmp_path,
                           env=dict(os.environ, PYTHONPATH=str(project / 'src'),
                                    PYTHONDONTWRITEBYTECODE='1'),
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout)['results'] == stored['results']
    assert fingerprint(tmp_path) == original
