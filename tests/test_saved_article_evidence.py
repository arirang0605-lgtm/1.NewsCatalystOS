"""Exact stored RSS title -> existing event/theme/company evidence, with PIT and N/A."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.federated_news_search import search_completed_workspaces
from newscatalystos.news_search_evidence import saved_article_evidence
from newscatalystos.source_share import SourceShareError, _when
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from scripts.open_research_dashboard import DashboardServer
from scripts.run_feed_triage import _registry
from test_federated_news_search import sample, collect, GOV, NOW, fingerprint
from test_market_commercial_parallel import article, PARTNERS, MARKETS


def request(base, params):
    with urlopen(base + '/api/news-evidence?' + urlencode(params), timeout=20) as response:
        return response.status, json.load(response)


@pytest.fixture
def connected(sample, tmp_path):
    workspaces, registries, *_ = sample
    title = article('수요 증가로', [PARTNERS[0][1], MARKETS[0]])
    assert len(extract_economic_changes(title)) == 2
    collect(workspaces[0], registries[0], GOV,
            [('new-claim-v1', title, 'https://gov.example.org/semiconductor/actual-claim')],
            at=NOW + timedelta(hours=2))
    current = datetime.now(timezone.utc)
    saved = search_completed_workspaces(workspaces, '가상전자', registry_reader=_registry, now=current)
    row, = [r for r in saved['results'] if r['headline'] == title]
    # An actually extracted, complete claim and exact original title SHA:
    # no copied or fabricated event ID is used to build the observation.
    changes = extract_economic_changes(title)
    assert all(c['source_paragraph_sha256'] == row['title_sha256'] for c in changes)
    store = ThemeStore(tmp_path / 'saved_document_analysis/theme_history')
    for change in changes:
        change['evidence_level'] = 'REPORTED'
    publications = store.ingest([economic_observation(
        change, origin_reference=row['source_url'], source_url=row['source_url'],
        source_id=row['provider_id'], source_available_at=row['source_available_at'],
        source_binding={'source_event_sha256': row['event_id'],
                        'document_sha256': row['title_sha256']},
        content_scope='RSS_TITLE_METADATA',
    ) for change in changes], now=current)
    assert publications
    return workspaces, row, store.root, current


def test_same_exact_article_links_both_actions_and_only_reported_firm(connected, tmp_path):
    workspaces, row, theme_root, created = connected
    before = fingerprint(tmp_path)
    s = DashboardServer(0, tmp_path / 'reports', tmp_path / 'notes',
                        theme_root.parent, news_search_workspaces=workspaces)
    t = threading.Thread(target=s.serve_forever, daemon=True); t.start()
    base = f'http://127.0.0.1:{s.server_port}'
    params = {'q':'가상전자', 'provider_id':row['provider_id'],
              'event_id':row['event_id'], 'title_sha256':row['title_sha256']}
    try:
        code, detail = request(base, params)
        assert code == 200 and detail['status'] == 'READY'
        assert detail['source']['source_url'] == row['source_url']
        assert detail['source']['title_sha256'] == row['title_sha256']
        assert detail['source_coverage_complete']
        ev = [event for theme in detail['themes'] for event in theme['events']]
        assert {e['action'] for e in ev} == {'MARKET_ENTRY', 'DELIVERY_START'}
        assert all(e['companies'] == [{'entity_id':'가상전자'}] for e in ev)
        assert all(e['source_url'] == row['source_url']
                   and e['content_scope'] == 'RSS_TITLE_METADATA'
                   and e['evidence_level'] == 'REPORTED'
                   and e['active_in_theme'] for e in ev)
        assert not detail['verified_real_transaction']
        assert not detail['verified_real_benefit']
        assert not detail['independent_fact_verified']
        companies = detail['article_company_context']
        assert companies['status'] == 'READY' and not companies['verified_real_benefit']
        assert len(companies['themes']) == 1
        assert len(companies['themes'][0]['direct_parties']) == 2
        assert all(x['source_name'] == '가상전자' and x['official_entity_id'] is None
                   and x['inclusion_status'] == 'READY'
                   and len(x['inclusion_reasons']) == 1
                   for x in companies['themes'][0]['direct_parties'])
        assert companies['themes'][0]['related_supply_context'] == []
        again = request(base, params)[1]
        assert again['status'] == 'READY' and again['source'] == detail['source']

        # The title existed earlier but the economic theme was not yet saved:
        # never backfill a future observation into an earlier decision.
        early = (created - timedelta(microseconds=1)).isoformat()
        code, old = request(base, {**params, 'as_of': early})
        assert code == 200 and old['status'] == 'N/A'
        assert old['reason_code'] == 'NO_SAVED_EXACT_THEME_EVIDENCE'
        assert old['themes'] == []
        earlier_than_source = (_when(row['source_available_at'],'source')-timedelta(seconds=1)).isoformat()
        code, old = request(base, {**params, 'as_of': earlier_than_source})
        assert code == 200 and old['reason_code'] == 'SOURCE_NOT_AVAILABLE_AS_OF'

        for tampered in ({**params,'title_sha256':'f'*64},
                         {**params,'event_id':'f'*64},
                         {**params,'provider_id':'synthetic-wrong-provider'}):
            with pytest.raises(HTTPError) as exc: request(base, tampered)
            assert exc.value.code == 404
        with pytest.raises(HTTPError) as exc:
            request(base, {**params,'title_sha256':'invalid'})
        assert exc.value.code == 400
        with pytest.raises(HTTPError) as exc:
            request(base, {**params,'as_of':(created+timedelta(days=5)).isoformat()})
        assert exc.value.code == 400
    finally:
        s.shutdown(); s.server_close(); t.join(3)
    assert fingerprint(tmp_path) == before


def test_same_headline_other_source_does_not_inherit_theme_and_lookup_not_truncated(connected):
    workspaces, row, theme_root, created = connected
    selected = search_completed_workspaces(workspaces, '가상전자', registry_reader=_registry,
        exact_identity=(row['provider_id'],row['event_id'],row['title_sha256']), limit=1)
    assert len(selected['results']) == 1 and selected['results'][0]['event_id'] == row['event_id']
    unrelated = search_completed_workspaces(workspaces, '반도체', registry_reader=_registry,
                                              limit=100)['results']
    no_theme = next(r for r in unrelated if r['event_id'] != row['event_id'])
    missing = saved_article_evidence(no_theme, theme_root, now=datetime.now(timezone.utc))
    assert missing['status'] == 'N/A'
    assert missing['reason_code'] == 'NO_SAVED_EXACT_THEME_EVIDENCE'
    assert missing['themes'] == []
    with pytest.raises(SourceShareError):
        search_completed_workspaces(workspaces, '반도체', registry_reader=_registry,
                                     exact_identity=(row['provider_id'],'bad',row['title_sha256']))


def test_exact_pinned_theme_rejects_wrong_document_version_and_source_url(connected):
    _, row, theme_root, _ = connected
    present = datetime.now(timezone.utc)
    assert saved_article_evidence(row, theme_root, now=present)['status'] == 'READY'
    for key, value in [('title_sha256','f'*64),
                       ('event_id','f'*64),
                       ('source_url','https://evil.example.test/other')]:
        forged = {**row, key:value}
        assert saved_article_evidence(forged, theme_root, now=present)['status'] == 'N/A'
