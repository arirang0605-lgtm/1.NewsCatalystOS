"""Synthetic saved report histories; no collection or real AI calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import threading
from urllib.request import urlopen

import pytest

from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.motir_document_analysis import analyze_motir_document, publish_motir_document_analysis
from newscatalystos.research_dashboard import KST, build_period, period_as_of, scan_saved_analysis, scan_saved_documents
from scripts import open_research_dashboard as dashboard
from test_feed_analysis import setup, run
from test_ai_provider import config
from test_ai_openai_transport import LocalOpener, packet
from test_ai_gemini_transport import LocalOpener as GeminiOpener, packet as gemini_packet
from test_motir_document_analysis import case
from test_federated_news_search import fingerprint


def history(tmp_path, monkeypatch, kind):
    (tmp_path/'source').mkdir(mode=0o700)
    first = datetime.now(timezone.utc) + timedelta(days=1)
    later = first + timedelta(days=1)
    reports = tmp_path/'reports'
    documents = tmp_path/'documents'
    if kind == 'rss':
        monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key-only-for-offline-tests')
        info = setup(tmp_path/'source')
        old = run(info, now=first)
        new = run(info, model=config(), allow_paid=True, opener=LocalOpener(packet()), now=later)
        # A legacy report before the extractor added economic actions.
        old['results'][0].pop('economic_changes', None)
        folder = reports/'core/reports'
        publish = publish_feed_analysis
    else:
        monkeypatch.setenv('GEMINI_API_KEY', 'synthetic-key-only-for-offline-tests')
        _, args = case(tmp_path/'source')
        old = analyze_motir_document(**args, now=first)
        new = analyze_motir_document(**args, allow_paid=True, opener=GeminiOpener(gemini_packet()))
        new['analysis_available_at'] = later.isoformat()
        folder = documents/args['binding_sha256']/'reports'
        publish = publish_motir_document_analysis
    _, old_sha = publish(old, folder)
    _, new_sha = publish(new, folder)
    return reports, documents, first, later, old, new, old_sha, new_sha, publish, folder


@pytest.mark.parametrize('kind', ['rss', 'body'])
def test_asof_selects_earlier_report_before_merging_and_keeps_first_day(tmp_path, monkeypatch, kind):
    reports, docs, first, later, old, new, old_sha, new_sha, publish, folder = history(tmp_path, monkeypatch, kind)
    before = fingerprint(tmp_path)
    day = first.astimezone(KST).date().isoformat()
    at = period_as_of('day', day, now=later)
    past, status = scan_saved_analysis(reports, document_root=docs, now=later, as_of=at)
    latest, _ = scan_saved_analysis(reports, document_root=docs, now=later)
    assert status['saved_reports_skipped'] == 0
    assert len(past) == len(latest) == 1
    assert past[0]['report_sha256'] == old_sha
    assert latest[0]['report_sha256'] == new_sha
    assert past[0]['ai_summary'] is None and latest[0]['ai_summary']
    assert past[0]['event_id'] == latest[0]['event_id']
    assert past[0]['day'] == latest[0]['day'] == day
    if kind == 'rss':
        assert not past[0]['economic_changes'] and latest[0]['economic_changes']
    result = build_period(past, [], 'day', day, now=later)
    assert result['counts']['items'] == 1 and result['counts']['ai_analyzed'] == 0
    # Defense in depth cannot reconstruct history from an already merged latest row.
    assert build_period(latest, [], 'day', day, now=later)['counts']['items'] == 0
    assert scan_saved_analysis(reports, document_root=docs, now=later, as_of=first-timedelta(seconds=1))[0] == []
    assert fingerprint(tmp_path) == before
    # Reanalysis adds a report, never a second event or a new discovery day.
    replay = deepcopy(new)
    if kind == 'rss':
        replay['checked_at'] = (later+timedelta(seconds=1)).isoformat()
    else:
        replay['analysis_available_at'] = (later+timedelta(seconds=1)).isoformat()
    publish(replay, folder)
    rows, _ = scan_saved_analysis(reports, document_root=docs, now=later+timedelta(seconds=2))
    assert len(rows) == 1 and rows[0]['day'] == day


@pytest.mark.parametrize('kind', ['rss', 'body'])
def test_future_and_tampered_reports_never_replace_eligible_version(tmp_path, monkeypatch, kind):
    reports, docs, first, later, old, new, old_sha, new_sha, publish, folder = history(tmp_path, monkeypatch, kind)
    rows, status = scan_saved_analysis(reports, document_root=docs, now=first, as_of=later)
    assert rows[0]['report_sha256'] == old_sha and status['saved_reports_skipped'] == 1
    path = next(folder.glob('*'+new_sha+'.json'))
    path.write_bytes(path.read_bytes()+b' ')
    rows, status = scan_saved_analysis(reports, document_root=docs, now=later)
    assert rows[0]['report_sha256'] == old_sha and status['saved_reports_skipped'] == 1


def test_producer_check_time_not_earlier_row_time_controls_rss_visibility(tmp_path, monkeypatch):
    reports, docs, first, later, old, _, _, _, publish, folder = history(tmp_path, monkeypatch, 'rss')
    for path in folder.iterdir(): path.unlink()
    old['checked_at'] = later.isoformat()
    publish(old, folder)
    assert scan_saved_analysis(reports, now=later, as_of=first)[0] == []
    assert len(scan_saved_analysis(reports, now=later)[0]) == 1


def test_body_does_not_borrow_a_future_or_untimed_rss_headline(tmp_path, monkeypatch):
    _, docs, first, later, old, *_ = history(tmp_path, monkeypatch, 'body')
    headline = {'source_event_sha256':old['source_event_sha256'], 'headline':'나중에 관측한 제목', 'available_at':later.isoformat()}
    rows, _ = scan_saved_documents(docs, [headline], now=later, as_of=first)
    assert rows[0]['bound_title'] is None
    headline.pop('available_at')
    assert scan_saved_documents(docs, [headline], now=later, as_of=first)[0][0]['bound_title'] is None
    headline['available_at'] = first.isoformat()
    assert scan_saved_documents(docs, [headline], now=later, as_of=first)[0][0]['bound_title'] == headline['headline']


@pytest.mark.parametrize('view,date,expected', [
    ('day','2026-10-15','2026-10-15T14:59:59.999999+00:00'),
    ('week','2026-10-07','2026-10-11T14:59:59.999999+00:00'),
    ('month','2026-09-10','2026-09-30T14:59:59.999999+00:00'),
    ('day','2026-10-16','2026-10-16T02:00:00+00:00'),
    ('month','2026-11-01','2026-10-16T02:00:00+00:00'),
])
def test_kst_period_end_capped_at_actual_now(view, date, expected):
    assert period_as_of(view,date,now=datetime(2026,10,16,2,tzinfo=timezone.utc)).isoformat() == expected


def test_api_passes_same_period_cutoff_to_report_selection(tmp_path, monkeypatch):
    reports, docs, first, later, _, _, old_sha, *_ = history(tmp_path, monkeypatch, 'rss')
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return later.astimezone(tz)
    monkeypatch.setattr(dashboard, 'datetime', Clock)
    server = dashboard.DashboardServer(0, reports, tmp_path/'notes', docs)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    day = first.astimezone(KST).date().isoformat()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/period?view=day&date={day}') as response:
            data = json.load(response)
        assert data['counts']['items'] == 1
        assert data['items'][0]['report_sha256'] == old_sha
        assert data['items'][0]['ai_summary'] is None
        assert data['as_of'] == period_as_of('day',day,now=later).isoformat()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


@pytest.mark.parametrize('field', ['ai_summary_available_at', 'company_identity_analysis_available_at'])
def test_period_rejects_future_enrichment_provenance(field):
    from test_research_dashboard import record
    row = record('2026-10-15', 'one')
    row[field] = '2026-10-16T00:00:00+00:00'
    now = datetime(2026,10,16,2,tzinfo=timezone.utc)
    assert build_period([row], [], 'day', '2026-10-15', now=now)['items'] == []
    assert build_period([row], [], 'month', '2026-10-15', now=now)['counts']['items'] == 1
