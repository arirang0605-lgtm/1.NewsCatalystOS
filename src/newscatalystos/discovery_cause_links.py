"""Optional, source-bound common causes for the existing discovery watch.

No event reclassification or persistence. Reuse the semiconductor cause parser
and validators, then bind each interpretation to the exact stored actor/action.
Literal end-use equality is a research hypothesis, never a transaction.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256

from .common_cause_comparison import _cause
from .economic_changes import extract_economic_changes, normalized
from .source_share import _when, SourceShareError
from .theme_emergence import _bytes
from .theme_outlook import _observations, _literal
from .catalyst_material import PATHS

SCHEMA = 'newscatalyst.discovery_common_causes.v1'
PRODUCTS = {'HBM', 'DRAM', 'NAND'}


def _bound_cause(row):
    # The old discovery source, actor and verb must all agree with the existing
    # cause parser. Ambiguous multi-action titles cannot lend their cause here.
    changes = [c for c in extract_economic_changes(row['headline'],
                company_names=row['source_companies'])
               if c['topic'] in PRODUCTS and c['action'] == row['action']
               and set(c['entity_ids']) == set(row['source_companies'])]
    if len(changes) != 1 or not row['source_companies']:
        return None
    change = changes[0]
    driver = change['economic_driver']
    if driver not in {'DEMAND_EXPANSION', 'DEMAND_RECOVERY'}:
        return None
    proof = _cause(change)
    if proof['status'] != 'STORED_EXPRESSION':
        return None
    evidence = _literal(row['headline'], proof['source_expression'])
    if evidence is None or evidence['sha256'] != proof['expression_sha256']:
        return None
    scope = change.get('demand_scope') or {}
    if scope.get('status') != 'EXPLICIT':
        return None
    basis = (change.get('demand_recovery_cause') or {}).get('basis')
    if basis is None:
        basis = 'ORDER' if '주문' in scope['source_expression'] else 'DEMAND'
    key = (driver, basis, normalized(scope['destination']))
    subject = scope['destination']
    # Parser phase is deliberately allowed to be more conservative than the
    # old watch. Future-tense execution cannot become a reported physical act.
    phase = 'PLANNED' if 'PLANNED' in {row['phase'], change['phase']} else 'SOURCE_REPORTED'
    return key, subject, change, phase, evidence


def build_discovery_causes(themes, titles, candidates, *, as_of, since, now):
    at = _when(as_of.isoformat(), 'cause as of')
    start = _when(since.isoformat(), 'cause since')
    if start > at or at > _when(now.isoformat(), 'now'):
        raise SourceShareError('invalid common-cause interval')
    grouped = defaultdict(list)
    snapshots = {t['theme_id']: {'sha256': sha256(_bytes(t)).hexdigest(),
                 'decision_at': t['decision_at']} for t in themes}
    for row in _observations(themes, titles, candidates, at):
        bound = _bound_cause(row)
        if bound is None:
            continue
        key, subject, change, phase, cause = bound
        source = {k: deepcopy(v) for k, v in row.items() if k != 'objects'}
        source.update(in_period=_when(row['basis_available_at'], 'basis') >= start, product=change['topic'], phase=phase, cause_evidence=cause,
                      source_theme_snapshots={tid: snapshots[tid] for tid in row['theme_ids']})
        grouped[key].append((subject, source))
    groups = []
    for key, values in sorted(grouped.items()):
        rows = [v[1] for v in values]
        products = sorted({r['product'] for r in rows})
        # One product/one repeated source cannot certify cross-product breadth.
        if len(products) < 2:
            continue
        names = sorted({n for r in rows for n in r['source_companies']})
        actions = sorted({r['action'] for r in rows})
        paths = [dict(action=action, dimension=d, direction=direction,
                      opportunity=premise, countercondition=counter)
                 for action in actions for d, direction, premise, counter in PATHS.get(action, [])]
        groups.append({'group_id': sha256(_bytes([SCHEMA, key])).hexdigest(),
            'subject': values[0][0], 'economic_driver': key[0],
            'cause_basis': key[1], 'status': 'SOURCE_REPORTED_COMMON_CAUSE_HYPOTHESIS',
            'products': products, 'economic_actions': actions, 'source_company_names': names,
            'theme_ids': sorted({t for r in rows for t in r['theme_ids']}),
            'event_ids': sorted({r['event_id'] for r in rows}),
            'source_evidence': rows, 'conditional_paths': paths,
            'first_observed_at': min(r['basis_available_at'] for r in rows),
            'basis_available_at': max(r['basis_available_at'] for r in rows),
            'reported_action_count': sum(r['phase'] == 'SOURCE_REPORTED' for r in rows),
            'planned_action_count': sum(r['phase'] == 'PLANNED' for r in rows),
            'source_cause_link_explicit': True, 'common_market_shock_verified': False,
            'independent_company_count': None, 'supply_chain_transaction_verified': False,
            'verified_real_benefit': False, 'orders_enabled': False})
    return {'schema': SCHEMA, 'groups': groups, 'as_of': at.isoformat(),
            'since': since.isoformat(), 'interpretation_at': now.isoformat(),
            'interpretation_is_historical_record': False,
            'source_writes': False, 'original_events_unchanged': True,
            'scope': 'EXPLICIT_SEMICONDUCTOR_END_USE_DEMAND',
            'note': '조회 시 기존 원문을 해석한 연결 가설 · 당시 저장된 사건·점수·수혜 판정은 변경하지 않음'}
