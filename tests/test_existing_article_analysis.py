"""Existing source analysis never changes the event's novelty or bypasses cost limits."""
from dataclasses import replace, asdict
import json
import sqlite3
import pytest
from newscatalystos.ai_provider import run_ai_analysis
from newscatalystos.ai_cost_ledger import reserve_ai_call
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.source_share import SourceShareError
from scripts import run_feed_analysis
from test_ai_provider import config, request, stub
from test_feed_analysis import setup, run, fake_key
from test_ai_openai_transport import LocalOpener, packet
from test_new_source_adapter import NOW


def selection(info):
    row = run(info)['results'][0]
    return dict(provider_id=row['provider_id'], event_id=row['source_event_sha256'],
                title_sha256=row['source_title_sha256'], limit=1, analyze_existing=True)


def test_existing_article_result_is_saved_consumable_and_cached(tmp_path, fake_key):
    info = setup(tmp_path, title='반도체 산업 과거 투자계획 이행 점검')
    selected = selection(info)
    opener = LocalOpener(packet())
    first = run(info, **selected, model=config(), allow_paid=True, opener=opener)
    row = first['results'][0]
    assert not row['ai_eligible'] and row['analysis_purpose'] == 'EXISTING_ARTICLE'
    assert row['ai_status'] == 'ANALYZED_UNVERIFIED'
    assert first['ai_eligible_candidates'] == 0 and first['new_ai_results'] == 1
    file, digest = publish_feed_analysis(first, info[-1] / 'reports')
    saved = consume_feed_analysis(file, file.parent, digest)
    assert saved['results'][0]['ai_analysis']['summary']
    again = run(info, **selected, model=config(), allow_paid=True, opener=opener)
    assert again['cache_hits'] == 1 and opener.calls == 1
    regular = run(info, model=config(), allow_paid=True, opener=opener)
    assert regular['new_ai_results'] == 0 and regular['cache_hits'] == 0
    assert opener.calls == 1


def test_existing_analysis_cannot_select_whole_feed(tmp_path):
    info = setup(tmp_path)
    with pytest.raises(SourceShareError, match='one exact source'):
        run(info, analyze_existing=True, model=config())


def test_default_request_still_requires_novel_event():
    old = replace(request(), important=False, new_economic_event=False)
    with pytest.raises(SourceShareError, match='novel'):
        run_ai_analysis(config(), old, transport=stub, now=NOW)
    result = run_ai_analysis(config(), replace(old, analysis_purpose='EXISTING_ARTICLE'),
                             transport=stub, now=NOW)
    assert result.input_tokens == 40


def test_shared_budget_blocks_second_source_before_http(tmp_path, fake_key):
    first = setup(tmp_path / 'first')
    second = setup(tmp_path / 'second', title='반도체 연구 동향')
    ledger = tmp_path / 'shared' / 'ai.sqlite3'
    ledger.parent.mkdir(mode=0o700)
    costly = replace(config(), max_input_tokens=1000, max_output_tokens=1000,
                     input_krw_per_million=25_000_000, output_krw_per_million=25_000_000)
    reserve_ai_call(ledger, costly, request())
    opener = LocalOpener(packet())
    result = run(second, **selection(second), model=config(), allow_paid=True,
                 opener=opener, ai_ledger=ledger)
    assert opener.calls == 0
    assert result['results'][0]['ai_status'] == 'AI_BUDGET_UNAVAILABLE'


def test_cli_failed_selected_analysis_is_not_false_success(tmp_path, fake_key):
    info = setup(tmp_path, title='반도체 산업 동향')
    selected = selection(info)
    folder = tmp_path / 'models'; folder.mkdir(mode=0o700)
    model = folder / 'test.json'; model.write_text(json.dumps(asdict(config()))); model.chmod(0o600)
    source = info[0]
    args = run_feed_analysis.parser().parse_args([
        '--registry', str(source.registry_path), '--state', str(source.poll_state),
        '--inbox-root', str(source.inbox_root), '--analysis-root', str(info[-1]),
        '--model-config', str(model), '--analyze-existing', '--allow-paid', '--limit', '1',
        '--provider-id', selected['provider_id'], '--event-id', selected['event_id'],
        '--title-sha256', selected['title_sha256']])
    class Offline:
        def open(self, *a, **kw): raise OSError('offline')
    code, result = run_feed_analysis.evaluate(args, opener=Offline())
    assert code == 4 and result['requested_ai_complete'] is False


def test_dashboard_shows_later_ai_and_keeps_first_observation_day(tmp_path, fake_key):
    from newscatalystos.research_dashboard import scan_saved_analysis
    info = setup(tmp_path, title='반도체 산업 과거 투자계획 점검')
    reports = tmp_path / 'dashboard' / 'core' / 'reports'
    first = run(info)
    publish_feed_analysis(first, reports)
    analyzed = run(info, **selection(info), model=config(), allow_paid=True,
                   opener=LocalOpener(packet()))
    _, ai_digest = publish_feed_analysis(analyzed, reports)
    latest = run(info)
    _, latest_digest = publish_feed_analysis(latest, reports)
    rows, stats = scan_saved_analysis(tmp_path / 'dashboard')
    assert len(rows) == 1 and stats['saved_reports_skipped'] == 0
    assert rows[0]['ai_summary'] == analyzed['results'][0]['ai_analysis']['summary']
    assert rows[0]['analysis_purpose'] == 'EXISTING_ARTICLE'
    # Current rules and the preserved AI summary have separate provenance.
    # An old AI timestamp must not backdate a newer rule interpretation.
    assert rows[0]['analysis_available_at'] == latest['results'][0]['analysis_available_at']
    assert rows[0]['report_sha256'] == latest_digest
    assert rows[0]['ai_summary_available_at'] == max(
        analyzed['checked_at'], analyzed['results'][0]['analysis_available_at'])
    assert rows[0]['ai_summary_report_sha256'] == ai_digest
    from datetime import datetime
    past, _ = scan_saved_analysis(tmp_path / 'dashboard',
        as_of=datetime.fromisoformat(analyzed['checked_at']))
    assert past[0]['analysis_available_at'] == analyzed['results'][0]['analysis_available_at']
    assert past[0]['report_sha256'] == ai_digest
