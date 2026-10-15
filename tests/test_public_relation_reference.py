"""Synthetic references only; real counterparties and citations stay private."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

import pytest

from newscatalystos import public_relation_reference as ref
from newscatalystos.beneficiary_graph_contract import BeneficiaryGraph
from newscatalystos.official_relation_intake import read_official_relation_intake
from newscatalystos.reviewed_beneficiary_delivery import (
    ReviewedDelivery, publish_reviewed_beneficiary_graph,
)
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)


def example():
    return {
        'schema': ref.SCHEMA, 'annotation_kind': ref.ANNOTATION,
        'rights_status': ref.RIGHTS, 'source_url': 'https://company.example.org/press/packaging',
        'source_role': 'COMPANY_IR', 'source_reported_date': '2023-11-30',
        'recorded_at': (NOW - timedelta(minutes=1)).isoformat(),
        'source_excerpt': 'Alpha supplies semiconductor packaging services to Beta under a reported business relationship.',
        'supplier': {
            'legal_name': 'Alpha Incorporated', 'source_name': 'Alpha',
            'company_id': '0000111111',
            'identity_url': 'https://www.sec.gov/Archives/edgar/data/111111/000011111126000001/0000111111-26-000001-index.htm',
            'identity_excerpt': 'Alpha Incorporated (Filer) CIK: 0000111111',
        },
        'customer': {
            'legal_name': 'Beta Incorporated', 'source_name': 'Beta',
            'company_id': '0000222222',
            'identity_url': 'https://www.sec.gov/Archives/edgar/data/222222/000022222226000002/0000222222-26-000002-index.htm',
            'identity_excerpt': 'Beta Incorporated (Filer) CIK: 0000222222',
        },
        'product_stage': 'ADVANCED_PACKAGING', 'hypothesis_trigger': 'PACKAGING_CAPACITY',
        'hypothesis_note': 'Historical relationship reference; current capacity and earnings are not verified.',
        'collection_enabled': False, 'human_review_completed': False,
        'historical_reference_only': True,
    }


def save(tmp_path, monkeypatch, data=None, pin_at=NOW):
    monkeypatch.setattr(ref, '_different_disk', lambda *_: True)
    out, pins = tmp_path / 'refs', tmp_path / 'pins'
    out.mkdir(mode=0o700, exist_ok=True); pins.mkdir(mode=0o700, exist_ok=True)
    raw = ref._encoded(data if data is not None else example())
    digest = sha256(raw).hexdigest()
    source = out / ('relation_reference_' + digest + '.json')
    pin = pins / ('relation_reference_' + digest + '.pin.json')
    source.write_bytes(raw); source.chmod(0o600)
    pin.write_bytes(ref._encoded({
        'schema': ref.PIN_SCHEMA, 'reference_sha256': digest,
        'recorded_at': pin_at.isoformat(),
        'trust_level': 'LOCAL_INTEGRITY_ONLY_NOT_SOURCE_AUTHENTICATION',
    })); pin.chmod(0o600)
    return source, pin


def fingerprint(root):
    return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_reference_reuses_graph_but_never_enables_runtime_or_labels(tmp_path, monkeypatch):
    source, pin = save(tmp_path, monkeypatch)
    before = fingerprint(tmp_path)
    report = ref.inspect_public_relation_reference(source, pin, now=NOW)
    assert fingerprint(tmp_path) == before
    assert report['status'] == ref.STATUS
    assert report['candidate_category'] == 'EFFECT_DIRECTION_UNKNOWN'
    assert report['available_at'] == NOW.isoformat()
    assert report['published_at'] is None and report['original_document_sha256'] is None
    assert report['supplier']['company_id'] == '0000111111'
    assert report['customer']['company_id'] == '0000222222'
    assert report['annotation_kind'] == ref.ANNOTATION
    assert report['historical_reference_only']
    for flag in ('eligible_for_delivery', 'collection_enabled', 'source_authenticity_certified',
                 'verified_real_transaction', 'verified_real_benefit', 'new_economic_event_verified',
                 'source_evidence_complete', 'release_gate_verified', 'runtime_databases_modified'):
        assert report[flag] is False
    assert report['network_calls'] == report['ai_calls'] == 0
    graph = report['graph_preview']
    assert len(graph['edges']) == 1
    assert graph['edges'][0]['evidence_sha256'] == report['reference_sha256']
    assert graph['edges'][0]['revenue_contribution_krw'] is None
    assert 'document_sha256' not in graph['edges'][0]
    assert sha256(ref._encoded(graph)).hexdigest() == report['graph_sha256']
    assert example()['source_excerpt'] not in json.dumps(report)


def test_preview_is_not_accepted_by_official_outbox_even_when_wrapped(tmp_path, monkeypatch):
    source, pin = save(tmp_path, monkeypatch)
    report = ref.inspect_public_relation_reference(source, pin, now=NOW)
    data = report['graph_preview']; body = ref._encoded(data)
    graph = BeneficiaryGraph(data['schema'], data['event_sha256'], data['profile_sha256'],
                              NOW, 1, body, report['graph_sha256'])
    wrong = ReviewedDelivery(graph, graph.payload_sha256, NOW, data['event_sha256'])
    with pytest.raises(SourceShareError, match='official relation fields'):
        publish_reviewed_beneficiary_graph(wrong, tmp_path / 'must-not-publish', now=NOW)
    assert not (tmp_path / 'must-not-publish').exists()
    with pytest.raises(SourceShareError, match='intake schema'):
        read_official_relation_intake(tmp_path / 'no-publication', tmp_path,
                                      'a'*64, source, source, 'b'*64, now=NOW)


@pytest.mark.parametrize(('field', 'value'), [
    ('collection_enabled', True), ('human_review_completed', True),
    ('historical_reference_only', False), ('annotation_kind', 'HUMAN_REVIEWED'),
    ('rights_status', 'WRITTEN_LICENSE'), ('source_role', 'INDEPENDENT_NEWS'),
    ('article_body', 'This extra field is prohibited.'),
])
def test_reference_cannot_become_permission_human_review_or_article_storage(tmp_path, monkeypatch, field, value):
    data = example(); data[field] = value
    source, pin = save(tmp_path, monkeypatch, data)
    with pytest.raises(SourceShareError, match='authorize collection'):
        ref.inspect_public_relation_reference(source, pin, now=NOW)


@pytest.mark.parametrize('case', ['url_cik', 'name', 'id_text', 'missing_party', 'same_entity', 'stage', 'route', 'quote_length'])
def test_bad_company_stage_and_reference_fail_before_graph(tmp_path, monkeypatch, case):
    data = example()
    if case == 'url_cik': data['supplier']['company_id'] = '0000333333'
    elif case == 'name': data['supplier']['legal_name'] = 'Unrelated Corporation'
    elif case == 'id_text': data['supplier']['identity_excerpt'] = 'Alpha Incorporated CIK: 999'
    elif case == 'missing_party': data['source_excerpt'] = 'Alpha supplies packaging services for an unidentified customer in Asia.'
    elif case == 'same_entity': data['customer'] = deepcopy(data['supplier'])
    elif case == 'stage': data['product_stage'] = 'AUTOMOTIVE'
    elif case == 'route': data['hypothesis_trigger'] = 'MEMORY_PRICE'
    else: data['source_excerpt'] = 'Alpha Beta ' + 'word '*30
    source, pin = save(tmp_path, monkeypatch, data)
    with pytest.raises(SourceShareError): ref.inspect_public_relation_reference(source, pin, now=NOW)


@pytest.mark.parametrize('case', ['pin_future', 'record_future', 'source_date_future', 'backdate'])
def test_pit_does_not_backdate_historical_article_into_trading_data(tmp_path, monkeypatch, case):
    data = example(); pin_at = NOW
    if case == 'pin_future': pin_at = NOW + timedelta(seconds=1)
    elif case == 'record_future': data['recorded_at'] = (NOW + timedelta(seconds=1)).isoformat()
    elif case == 'source_date_future': data['source_reported_date'] = '2027-01-01'
    source, pin = save(tmp_path, monkeypatch, data, pin_at)
    when = NOW - timedelta(days=1000) if case == 'backdate' else NOW
    with pytest.raises(SourceShareError): ref.inspect_public_relation_reference(source, pin, now=when)


def test_tampering_and_same_disk_are_rejected(tmp_path, monkeypatch):
    source, pin = save(tmp_path, monkeypatch)
    source.write_bytes(source.read_bytes() + b' ')
    with pytest.raises(SourceShareError, match='SHA pin'):
        ref.inspect_public_relation_reference(source, pin, now=NOW)
    monkeypatch.setattr(ref, '_different_disk', lambda *_: False)
    with pytest.raises(SourceShareError, match='separate local disks'):
        ref.inspect_public_relation_reference(source, pin, now=NOW)


def test_missing_paths_do_not_get_created(tmp_path):
    with pytest.raises(SourceShareError):
        ref.inspect_public_relation_reference(tmp_path / 'absent/source.json', tmp_path / 'other/pin.json')
    assert not (tmp_path / 'absent').exists() and not (tmp_path / 'other').exists()


def test_read_only_entry_does_not_fetch_or_call_ai(tmp_path, monkeypatch):
    source, pin = save(tmp_path, monkeypatch)
    import socket
    monkeypatch.setattr(socket, 'create_connection', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network forbidden')))
    from scripts.inspect_public_relation_reference import main
    assert main(['--reference-file', str(source), '--pin-file', str(pin)]) == 0


def test_cli_errors_are_nonzero_and_do_not_print_private_paths(tmp_path, capsys):
    from scripts.inspect_public_relation_reference import main
    code = main(['--reference-file', str(tmp_path / 'no/file'), '--pin-file', str(tmp_path / 'no/pin')])
    out = capsys.readouterr().out
    assert code == 4 and str(tmp_path) not in out
    assert json.loads(out)['eligible_for_delivery'] is False
