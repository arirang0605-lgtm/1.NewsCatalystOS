"""5_2 reference-only bridge to the existing semiconductor relation pipeline.

A short citation located during research is NOT an authorized feed capture,
a human review, a complete SEC filing, or permission for automated collection.
This reader produces an in-memory preview only. It does not write an outbox,
register a provider, assign human labels, or invoke an external service.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
import json
import re

from .beneficiary_classification import classify_semiconductor_beneficiary
from .beneficiary_graph_contract import build_beneficiary_graph
from .event_identity import CompanyBinding
from .private_paths import _existing_private_dir
from .new_source_adapter import FeedObservation
from .official_relation_intake import _private_input
from .physical_recovery import _different_disk
from .provider_registry import _safe_https_endpoint
from .semiconductor_impact import propagate_semiconductor_claim
from .semiconductor_profile import build_semiconductor_profile
from .source_share import SourceShareError, _json, _must_sha, _when
from .supply_chain_graph import observed_supply_edge

SCHEMA = 'newscatalyst.public_relation_reference.v1'
PIN_SCHEMA = 'newscatalyst.public_relation_reference_pin.v1'
ANNOTATION = 'ASSISTANT_SOURCE_RESEARCH_NOT_HUMAN_REVIEW'
RIGHTS = 'SHORT_CITATION_ONLY_NOT_COLLECTION_PERMISSION'
STATUS = 'PUBLIC_REFERENCE_CANDIDATE_NOT_OFFICIAL_REVIEW'
MAX_BYTES = 16384
FIELDS = frozenset({
    'schema', 'annotation_kind', 'rights_status', 'source_url', 'source_role',
    'source_reported_date', 'recorded_at', 'source_excerpt', 'supplier',
    'customer', 'product_stage', 'hypothesis_trigger', 'hypothesis_note',
    'collection_enabled', 'human_review_completed', 'historical_reference_only',
})
COMPANY_FIELDS = frozenset({
    'legal_name', 'source_name', 'company_id', 'identity_url', 'identity_excerpt',
})


def _encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


def _text(value: object, label: str, limit: int) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 for c in value)):
        raise SourceShareError('invalid bounded ' + label)
    return value


def _company(value: object, source: FeedObservation, at: datetime) -> CompanyBinding:
    if not isinstance(value, dict) or set(value) != COMPANY_FIELDS:
        raise SourceShareError('explicit company identity reference required')
    legal = _text(value['legal_name'], 'company name', 140)
    alias = _text(value['source_name'], 'source company name', 80)
    code = value['company_id']
    if (not isinstance(code, str) or not re.fullmatch(r'[0-9]{10}', code)
            or int(code) == 0 or alias.casefold() not in legal.casefold()):
        raise SourceShareError('SEC identity reference and company name disagree')
    url = _safe_https_endpoint(value['identity_url'])
    uri = urlsplit(url)
    if (uri.netloc != 'www.sec.gov' or uri.query
            or not re.fullmatch(r'/Archives/edgar/data/' + str(int(code))
                               + r'/[0-9]{18}/[0-9]{10}-[0-9]{2}-[0-9]{6}-index\.htm', uri.path)):
        raise SourceShareError('SEC identity reference URL does not match CIK')
    excerpt = _text(value['identity_excerpt'], 'identity citation', 220)
    if (len(excerpt.split()) > 25 or code not in excerpt
            or legal.casefold() not in excerpt.casefold() or 'CIK:' not in excerpt):
        raise SourceShareError('explicit name and CIK citation required')
    binding = CompanyBinding(source.provider_id, source.document_id, 'SEC_CIK',
                             code, None, sha256(_encoded(value)).hexdigest(), at)
    binding.validate()
    return binding


def inspect_public_relation_reference(
    reference_file: Path, pin_file: Path, *, now: datetime | None = None,
) -> dict:
    """Verify a separately retained local pin, then preview existing 5_2~5_5.

    SHA only establishes local integrity. The referenced URLs and excerpts are
    research annotations, not cryptographic proof of what a publisher said.
    recorded_at is conservative local recording time; source date is date-only.
    No historical reference can become an important NEW economic event here.
    """
    reference_file, pin_file = Path(reference_file), Path(pin_file)
    _existing_private_dir(reference_file.parent)
    _existing_private_dir(pin_file.parent)
    if not _different_disk(reference_file.parent, pin_file.parent):
        raise SourceShareError('reference and pin must remain on separate local disks')
    pin = _json(_private_input(pin_file, 4096), 'public reference local pin')
    if (set(pin) != {'schema', 'reference_sha256', 'recorded_at', 'trust_level'}
            or pin['schema'] != PIN_SCHEMA
            or pin['trust_level'] != 'LOCAL_INTEGRITY_ONLY_NOT_SOURCE_AUTHENTICATION'):
        raise SourceShareError('unsupported reference pin')
    digest = _must_sha(pin['reference_sha256'], 'reference SHA')
    if (reference_file.name != 'relation_reference_' + digest + '.json'
            or pin_file.name != 'relation_reference_' + digest + '.pin.json'):
        raise SourceShareError('reference file and retained pin identity mismatch')
    raw = _private_input(reference_file, MAX_BYTES)
    if sha256(raw).hexdigest() != digest:
        raise SourceShareError('reference bytes differ from retained SHA pin')
    data = _json(raw, 'short public source reference')
    if (set(data) != FIELDS or data['schema'] != SCHEMA
            or data['annotation_kind'] != ANNOTATION or data['rights_status'] != RIGHTS
            or data['collection_enabled'] is not False
            or data['human_review_completed'] is not False
            or data['historical_reference_only'] is not True
            or data['source_role'] not in ('COMPANY_IR', 'GOVERNMENT_POLICY')):
        raise SourceShareError('reference cannot authorize collection or impersonate human review')
    checked = _when((now or datetime.now(timezone.utc)).isoformat(), 'reference checked')
    recorded = _when(data['recorded_at'], 'reference recorded')
    pinned = _when(pin['recorded_at'], 'reference pinned')
    if not recorded <= pinned <= checked:
        raise SourceShareError('reference or pin unavailable at decision')
    reported_date = date.fromisoformat(data['source_reported_date'])
    if reported_date.isoformat() != data['source_reported_date'] or reported_date > recorded.date():
        raise SourceShareError('invalid source-reported date')
    url = _safe_https_endpoint(data['source_url'])
    excerpt = _text(data['source_excerpt'], 'short source citation', 600)
    if not 5 <= len(excerpt.split()) <= 25:
        raise SourceShareError('only a short reference citation is supported')
    note = _text(data['hypothesis_note'], 'hypothesis limitation', 500)
    # Reuse the lightweight source-claim input only in memory. This is NOT a
    # fabricated RSS receipt and is never inserted in feed/Gold databases.
    source_id = 'public-reference-' + urlsplit(url).hostname
    event = sha256((source_id + '\0' + url).encode()).hexdigest()
    source = FeedObservation(source_id, event, url, 'Public relation reference',
                             url, recorded, None,
                             verification_status='PUBLIC_REFERENCE_NOT_FEED_CAPTURE')
    supplier = _company(data['supplier'], source, recorded)
    customer = _company(data['customer'], source, recorded)
    if any(data[role]['source_name'].casefold() not in excerpt.casefold()
           for role in ('supplier', 'customer')):
        raise SourceShareError('both counterparties must appear in the cited reference')
    edge = observed_supply_edge(
        source, supplier, customer, product_stage=data['product_stage'],
        relation_kind='REPORTED_DIRECT_TRANSACTION', reviewed_at=checked, now=checked,
    )
    edge = replace(edge, evidence_sha256=digest, evidence_status=STATUS,
                   edge_sha256=sha256((edge.edge_sha256 + ':' + digest).encode()).hexdigest())
    profile = build_semiconductor_profile()
    impact = propagate_semiconductor_claim(
        profile, edge.source_event_sha256, data['hypothesis_trigger'],
        direction='UNKNOWN', evidence_note=note, source_available_at=edge.available_at,
        reviewed_at=checked, now=checked,
    )
    if edge.product_stage not in impact.stages:
        raise SourceShareError('reference stage does not match proposed hypothesis route')
    candidate = classify_semiconductor_beneficiary(edge, impact, reviewed_at=checked, now=checked)
    graph = build_beneficiary_graph(profile, impact, (edge,), (candidate,), checked, now=checked)
    return {
        'schema': 'newscatalyst.public_relation_preview.v1', 'status': STATUS,
        'reference_sha256': digest, 'source_url': url,
        'source_reported_date': reported_date.isoformat(), 'published_at': None,
        'recorded_at': recorded.isoformat(), 'available_at': checked.isoformat(),
        'annotation_kind': ANNOTATION, 'rights_status': RIGHTS,
        'supplier': {'legal_name': data['supplier']['legal_name'], 'namespace': 'SEC_CIK',
                     'company_id': supplier.company_id, 'identity_url': data['supplier']['identity_url']},
        'customer': {'legal_name': data['customer']['legal_name'], 'namespace': 'SEC_CIK',
                     'company_id': customer.company_id, 'identity_url': data['customer']['identity_url']},
        'product_stage': edge.product_stage, 'candidate_category': candidate.category,
        'hypothesis_note': note, 'graph_sha256': graph.payload_sha256,
        'graph_preview': _json(graph.JSON_bytes, 'reference graph preview'),
        'source_excerpt_included': False, 'original_document_sha256': None,
        'historical_reference_only': True, 'new_economic_event_verified': False,
        'source_authenticity_certified': False, 'verified_real_transaction': False,
        'verified_real_benefit': False, 'collection_enabled': False,
        'source_evidence_complete': False, 'eligible_for_delivery': False,
        'network_calls': 0, 'ai_calls': 0,
        'runtime_databases_modified': False, 'release_gate_verified': False,
    }
