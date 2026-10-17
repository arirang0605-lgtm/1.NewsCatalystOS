"""Exact licensed-body evidence from an already-approved RSS version, no network."""
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from newscatalystos.federated_news_search import search_completed_workspaces
from newscatalystos.motir_article_binding import publish_motir_article_binding
from newscatalystos.motir_saved_document_evidence import bound_motir_document_evidence
from newscatalystos.source_share import _when
from scripts.open_research_dashboard import DashboardServer
from scripts.run_feed_triage import _registry
from scripts import run_motir_document_analysis
from test_federated_news_search import fingerprint, write_registry
from test_motir_article_binding import prepare, setup

BODY = "산업부는 반도체 수출 규제를 완화하기로 결정했다. " * 4


@pytest.fixture
def published(tmp_path):
    input_root = tmp_path / 'input'
    input_root.mkdir(mode=0o700)
    data = setup(input_root, body=BODY)
    feed, article_registry, workspace, item, archive_root, archived = data
    collection = tmp_path / 'document_collection'
    folder = collection / ('e' * 64)
    folder.mkdir(parents=True, mode=0o700)
    shutil.copytree(archive_root, folder / 'archive')
    registry_path = folder / 'registry.json'
    write_registry(registry_path, article_registry)
    binding_path, pin = publish_motir_article_binding(prepare(data), folder / 'bindings')
    analysis_root = tmp_path / 'document_analysis'
    opts = Namespace(binding_path=binding_path, binding_sha256=pin,
                     archive_root=folder / 'archive', article_registry=registry_path,
                     analysis_root=analysis_root / pin, company_identity_config=None,
                     model_config=None, ai_ledger=None, allow_paid=False,
                     analyze_existing=False, semantic_ai=False)
    code, report = run_motir_document_analysis.evaluate(opts)
    assert code == 0 and report['economic_changes'] >= 1
    assert report['theme_versions_created'] == 1 and report['source_fetch_calls'] == 0
    source, = search_completed_workspaces((workspace,), '반도체',
        registry_reader=_registry)['results']
    assert source['event_id'] == item['event_id']
    return dict(root=tmp_path, registry_path=registry_path, source=source, pin=pin,
                collection=collection, documents=analysis_root, binding=binding_path,
                report=report, workspace=workspace)


def lookup(published, source=None, *, as_of=None):
    x = published
    return bound_motir_document_evidence(
        source or x['source'], x['collection'], x['documents'],
        x['documents'] / 'theme_history', registry_reader=_registry, as_of=as_of)


def test_licensed_body_policy_theme_from_pinned_completed_rss_and_http(published):
    x = published
    before = fingerprint(x['root'])
    result = lookup(x)
    assert result['status'] == 'READY' and result['reason_code'] is None
    assert result['content_scope'] == 'LICENSED_ARTICLE_TEXT'
    assert result['binding_sha256'] == x['pin']
    assert result['document_sha256'] != x['source']['title_sha256']
    assert result['themes'][0]['events'][0]['action'] == 'POLICY_CHANGE'
    event = result['themes'][0]['events'][0]
    assert event['topic'] == '반도체'
    assert event['active_in_theme']
    assert event['content_scope'] == 'LICENSED_ARTICLE_TEXT'
    assert event['source_url'] == x['source']['source_url']
    assert event['companies'] == []  # No invented beneficiary.
    assert not result['independent_fact_verified']
    assert not result['verified_real_benefit']

    server = DashboardServer(0, x['root'] / 'reports', x['root'] / 'notes',
        x['documents'], evidence_base=x['root'],
        news_search_workspaces=(x['workspace'],))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        params = dict(q='반도체', provider_id=x['source']['provider_id'],
                      event_id=x['source']['event_id'],
                      title_sha256=x['source']['title_sha256'])
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/news-evidence?'
                     + urlencode(params), timeout=20) as response:
            detail = json.load(response)
            assert response.status == 200
        assert detail['status'] == 'N/A'  # No separate RSS-title event.
        body = detail['official_document_evidence']
        assert body['status'] == 'READY' and body['themes'][0]['events'][0]['action'] == 'POLICY_CHANGE'
        assert body['document_sha256'] != detail['source']['title_sha256']
        assert 'article_text' not in json.dumps(detail)
        assert '산업부는 반도체 수출 규제를 완화하기로' not in json.dumps(detail)
    finally:
        server.shutdown(); server.server_close();thread.join(3)
    assert fingerprint(x['root']) == before


def test_tampered_rss_identity_and_pit_fail_locally(published):
    x = published
    src = x['source']
    for changes in ({'event_id': 'f' * 64}, {'title_sha256':'f' * 64},
                    {'source_url':'https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172296/view'}):
        result = lookup(x, {**src, **changes})
        assert result['status'] == 'N/A' and result['themes'] == []
    from newscatalystos.motir_article_binding import consume_motir_article_binding
    binding = consume_motir_article_binding(x['binding'], x['pin'])
    earlier = _when(binding['binding_at'],'binding') - timedelta(microseconds=1)
    assert earlier > _when(src['source_available_at'],'RSS available')
    old = lookup(x, as_of=earlier)
    assert old['status'] == 'N/A' and old['reason_code'] == 'DOCUMENT_NOT_AVAILABLE_AS_OF'


def test_license_revocation_disables_document_without_affecting_rss(published):
    x = published
    registry = json.loads(x['registry_path'].read_text())
    assert len(registry['providers']) == 1
    registry['providers'][0]['approved'] = False
    x['registry_path'].write_text(json.dumps(registry))
    x['registry_path'].chmod(0o600)
    result = lookup(x)
    assert result['status'] == 'N/A'
    assert result['reason_code'] == 'DOCUMENT_RIGHTS_OR_ARCHIVE_UNAVAILABLE'
    assert result['themes'] == []


def test_bound_document_without_economic_change_stays_na(tmp_path):
    no_change = "산업부는 반도체 산업 교육 행사를 진행했다. " * 4
    data = setup(tmp_path / 'fixture', body=no_change)
    feed, article, workspace, item, original_archive, _ = data
    folder = tmp_path / 'document_collection' / ('a' * 64)
    folder.mkdir(mode=0o700,parents=True)
    shutil.copytree(original_archive,folder/'archive')
    reg = folder/'registry.json'
    write_registry(reg,article)
    bp,pin=publish_motir_article_binding(prepare(data),folder/'bindings')
    docroot=tmp_path/'document_analysis'
    opts=Namespace(binding_path=bp,binding_sha256=pin,archive_root=folder/'archive',
        article_registry=reg,analysis_root=docroot/pin,company_identity_config=None,
        model_config=None,ai_ledger=None,allow_paid=False,analyze_existing=False,
        semantic_ai=False)
    code,report=run_motir_document_analysis.evaluate(opts)
    assert code==0 and report['economic_changes']==0
    source,=search_completed_workspaces((workspace,),'반도체',registry_reader=_registry)['results']
    result=bound_motir_document_evidence(source,folder.parent,docroot,docroot/'theme_history',
                                          registry_reader=_registry)
    assert result['status']=='N/A'
    assert result['reason_code']=='NO_REPORTED_DOCUMENT_ECONOMIC_CHANGE'
