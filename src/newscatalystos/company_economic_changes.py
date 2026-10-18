"""Connect bound company reading analyses to the existing material publication.

These are attributed economic interpretations, not new title events. The source
theme, recent article, first available analysis and exact official company link
remain separate. No name aliases, financial evaluator, collector or score.
"""
from copy import deepcopy
from hashlib import sha256

from .catalyst_material import PATHS
from .era_daily_assessment import assessment_for
from .source_share import _when
from .theme_emergence import _bytes

SCHEMA = 'newscatalyst.company_economic_changes.v1'
ACTIONS = {
    'REPORTED_CONTRACT': 'CONTRACT', 'CONDITIONAL_FRAMEWORK': 'CONTRACT',
    'REPORTED_CAPACITY_OPERATION': 'PRODUCTION_START',
    'REPORTED_DELIVERY': 'DELIVERY_START', 'REPORTED_ORDER_PERFORMANCE': None,
    'PLAN_ONLY': None, 'DEMAND_REDUCTION': None, 'CANCELLATION': None,
    'REPORTED_DELAY': None, 'RISK_ONLY': None, 'CONTEXT_ONLY': None,
}


def _identity(name, snapshot, previous):
    matched = assessment_for(name, snapshot)
    if matched['status'] != 'AVAILABLE':
        return {'status': matched['status'], 'source_name': name}
    binding = {k: matched[k] for k in ('entity_id', 'security_id', 'identity_evidence_sha256')}
    # New quotes do not turn an unchanged official issuer mapping into news.
    old = (previous or {}).get('identity', {})
    if old.get('status') == 'AVAILABLE' and all(old.get(k) == v for k,v in binding.items()):
        return deepcopy(old)
    return {'status': 'AVAILABLE', 'source_name': name, **binding,
            'source_snapshot_sha256': matched['source_sha256'],
            'available_at': matched['imported_at'],
            'method': matched['identity_method']}


def build_changes(themes, view, snapshot, *, as_of, previous=None):
    """Use only source-bound notes already admitted by the discovery reader."""
    baselines = {}; recent = {}
    for group in view['theme_outlook']['candidates']:
        for note in group.get('public_page_demand_analysis', {}).get('notes', []):
            baselines[note['note_id']] = note
        for note in group.get('recent_news_comparison', {}).get('notes', []):
            recent[note['note_id']] = note
    old = {e['baseline']['note_id']: e for ext in (previous or {}).values()
           for e in ext['entries']}
    output = {}
    for theme in themes:
        entries = []
        for row in sorted(recent.values(), key=lambda r: r['note_id']):
            note = row['note']; baseline = baselines.get(note['baseline_note_id'])
            if baseline is None or note['evidence_kind'] not in ACTIONS:
                continue
            n = baseline['note']; name = n['source_company']
            refs = [r for r in theme['source_refs'] if r['polarity'] == 'SUPPORT'
                    and r['event_id'] in theme['event_ids']
                    and r['event_id'] not in theme['conflicting_event_ids']
                    and r['event_id'] not in theme['invalidated_event_ids']
                    and r['event_id'] == n['event_id'] and r['source_id'] == n['provider_id']
                    and r['evidence_sha256'] == n['source_title_sha256']
                    and r.get('source_binding', {}).get('source_event_sha256') == n['source_event_sha256']
                    and r['source_url'] == n['source_url'] and name in r['entity_ids']]
            if not refs:
                continue
            identity = _identity(name, snapshot, old.get(baseline['note_id']))
            known = max(_when(baseline['available_at'], 'baseline analysis'),
                        _when(row['available_at'], 'recent analysis'),
                        _when(row['recent_available_at'], 'recent source'))
            if identity['status'] == 'AVAILABLE':
                known = max(known, _when(identity['available_at'], 'official identity'))
            if known > as_of:
                continue
            action = ACTIONS[note['evidence_kind']]
            hypotheses = [{'path': path, 'direction': direction, 'premise': premise,
                           'counter_argument': counter}
                          for path,direction,premise,counter in PATHS.get(action, [])]
            if not hypotheses:
                hypotheses = [{'path': 'BUSINESS', 'direction': 'UNKNOWN',
                    'premise': note['analysis_text'], 'counter_argument': note['limitation']}]
            # Keep source-specific amount/conditions in the original paraphrase.
            hypotheses.append({'path': 'SOURCE_SPECIFIC', 'direction': 'UNKNOWN',
                'premise': note['analysis_text'], 'counter_argument': note['limitation']})
            entry = {'source_company': name, 'identity': identity,
                'baseline': {'note_id': baseline['note_id'], 'note': deepcopy(n),
                             'available_at': baseline['available_at']},
                'recent': {'note_id': row['note_id'], 'note': deepcopy(note),
                           'available_at': row['available_at'],
                           'source_available_at': row['recent_available_at']},
                'evidence_kind': note['evidence_kind'], 'source_action': action,
                'hypotheses': hypotheses, 'basis_available_at': known.isoformat(),
                'market_novelty': 'UNCONFIRMED', 'source_truth_verified': False,
                'verified_real_benefit': False, 'realized_revenue': None,
                'orders_enabled': False}
            # Optional stored execution interpretation remains attributed; it
            # must never be manufactured from two unrelated contracts here.
            if row.get('execution_context'):
                entry['execution_context'] = deepcopy(row['execution_context'])
            entry['change_id'] = sha256(_bytes([SCHEMA, name, baseline['note_id'], row['note_id']])).hexdigest()
            entry['content_sha256'] = sha256(_bytes(entry)).hexdigest()
            entries.append(entry)
        if entries:
            output[theme['theme_id']] = {'schema': SCHEMA, 'source_theme_id': theme['theme_id'],
                'source_theme_sha256': sha256(_bytes(theme)).hexdigest(),
                'original_theme_decision_at': theme['decision_at'], 'entries': entries,
                'new_economic_events_created': False, 'selection_owner': 'EraLeader'}
    return output
