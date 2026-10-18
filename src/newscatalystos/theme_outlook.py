"""Source-object synthesis for research themes, without an industry taxonomy.

Read validated, time-available discoveries. Shared literal business objects are
evidence for a research hypothesis, not proof of a shared demand shock. Original
events stay intact. Article counts, generic AI/program names and company aliases
are never used as investment scores or independent-event certification.
"""
from collections import defaultdict
from hashlib import sha256
import re

from .catalyst_material import PATHS
from .economic_changes import normalized
from .source_share import SourceShareError, _when
from .theme_emergence import _bytes

SCHEMA = 'newscatalyst.theme_outlook.v1'
RULE = 'literal-business-object-v1'
# Grammatical/program boilerplate, NOT industry names. New business vocabulary
# remains admissible without adding a sector to a dictionary.
GENERIC = set('''a an the to of for in on at with and or by its their this that
    more than up million billion percent first new novel next generation key
    domestic international global vertically integrated strategy company companies
    program programme award awards funding incentives agreement definitive direct
    finalization announces announcement production capacity investment investments
    expansion launch launches service services system platform support develop
    development expand enhance increase accelerate r d ai
    신규 새로운 최초 차세대 국내 해외 글로벌 기반 위한 관련 통한 지원 확대
    투자 생산 공장 시설 설비 서비스 출시 플랫폼 시스템 사업 계획 예정 공급 계약
    인공지능 개정안 법률 법 시행령 관리 활용 체계적 통합 공정한 문화'''.split())
TOKEN = re.compile(r'[^\W_]+', re.UNICODE)
ROLES = {
    'POLICY_CHANGE': ('POLICY', '정책·사업 지원'),
    'INVESTMENT': ('FACILITY', '시설·사업 투자 계획'),
    'INVESTMENT_EXECUTION': ('FACILITY', '투자 집행'),
    'CAPACITY_ADDITION': ('PRODUCTION', '생산능력 확대'),
    'PRODUCTION_START': ('PRODUCTION', '생산 개시'),
    'SUPPLY_RESUMPTION': ('PRODUCTION', '공급 재개'),
    'SUPPLY_REDUCTION': ('CONTRACTION', '공급 축소'),
    'CONTRACT': ('CONTRACT', '공급·구매 계약'),
    'DELIVERY_START': ('DELIVERY', '납품 개시'),
    'PRODUCT_LAUNCH': ('OFFERING', '제품·솔루션 출시'),
    'BUSINESS_START': ('OFFERING', '서비스·사업 개시'),
    'CUSTOMER_ACQUISITION': ('CUSTOMER', '고객 확보'),
    'MARKET_ENTRY': ('MARKET', '시장 진입'),
}


def _literal(text, expression, *, start=0):
    match = re.search(re.escape(expression), text[start:], re.I)
    if match is None:
        return None
    offset=start
    start, end = (p+offset for p in match.span())
    return {'text': text[start:end], 'start': start, 'end': end,
            'sha256': sha256(text[start:end].encode()).hexdigest()}


def _objects(expression, *, exact_product=False):
    """Bounded contiguous source phrases. No translation or inferred taxonomy.

    Product names are indivisible, preserving versions/digits. Other objects
    can share a substantive phrase (e.g. silicon-carbide / silicon carbide).
    Generic connecting words can occur inside, never define the subject alone.
    """
    tokens = list(TOKEN.finditer(expression))
    def generic(token):
        value = normalized(token)
        stem = re.sub(r'(?:으로|하는|위한|을|를|의|에|은|는|이|가|로)$', '', value)
        return value in GENERIC or stem in GENERIC
    useful = [m for m in tokens if not generic(m.group())
              and not m.group().isdigit() and len(m.group()) >= 2]
    if not useful:
        return {}
    exact = ('EXACT_OBJECT', normalized(expression))
    if exact_product:
        return {exact: expression}
    result = {}
    for i, left in enumerate(tokens):
        if left not in useful:
            continue
        for j in range(i, min(i + 5, len(tokens))):
            right = tokens[j]
            if right not in useful:
                continue
            window = tokens[i:j + 1]
            meaningful = sum(m in useful for m in window)
            # A solitary short acronym/program label cannot manufacture a
            # sector. A Korean business noun can be a complete source object.
            if meaningful < 2 and not (len(window) == 1 and
                    re.fullmatch(r'[가-힣]{3,}', left.group())):
                continue
            phrase = expression[left.start():right.end()]
            if len(phrase) > 100 or re.search(r'[,;!?。\n]', phrase):
                continue
            key = ('OBJECT', ' '.join(normalized(m.group()) for m in window))
            result[key] = phrase
    # A single named object can still be a watch item, but it cannot loosely
    # match a partial English brand/model across other observations.
    if (len(expression) <= 120 and (result or len(useful) == len(tokens))):
        result[exact] = expression
    return result


def _observations(themes, titles, candidates, at):
    contexts = {c['theme_id']: c for c in candidates}
    seen = {}
    for theme in themes:
        context = contexts.get(theme['theme_id'], {})
        for ref in theme['source_refs']:
            if (ref['polarity'] != 'SUPPORT' or ref['event_id'] not in theme['event_ids']
                    or ref['event_id'] in theme['conflicting_event_ids']
                    or ref['event_id'] in theme['invalidated_event_ids']):
                continue
            key = (ref['source_id'], (ref.get('source_binding') or {}).get('source_event_sha256'),
                   ref['evidence_sha256'])
            row = titles.get(key)
            if row is None:
                continue
            records = [r for r in row.get('economic_discovery', []) if
                       (r['change']['topic'], r['change']['action'], r['change']['phase']) ==
                       (ref.get('topic'), ref.get('action'), ref.get('phase'))]
            if len(records) != 1:
                continue
            change, discovery = records[0]['change'], records[0]['discovery']
            if discovery.get('source_reports_historical_context'):
                continue
            text = row['headline']
            description = discovery['object_expression']
            expression = change['topic'] if change['action'] == 'PRODUCT_LAUNCH' else description
            evidence = _literal(text, expression)
            if evidence is None or discovery.get('topic_label_truncated'):
                continue
            available = max(_when(row['available_at'], 'analysis available'),
                            _when(ref['source_available_at'], 'source available'),
                            _when(ref['recorded_at'], 'event recorded'))
            if available > at:
                continue
            companies = list(change['entity_ids'])
            # Use ONLY the recipient context attached to this exact event.
            for connection in context.get('source_context_connections', []):
                if (connection['event_id'], connection['source_id'], connection['source_title_sha256']) == (
                        ref['event_id'], key[0], key[2]) and connection['company_links']:
                    companies = [c['source_name'] for c in connection['company_links']]
                    available = max(available, _when(connection['available_at'], 'context available'))
            if available > at:
                continue
            identity = sha256(_bytes([*key, ref['event_id']])).hexdigest()
            existing = seen.get(identity)
            value = {'observation_id': identity, 'theme_ids': sorted(set(
                         (existing or {}).get('theme_ids', []) + [theme['theme_id']])),
                     'event_id': ref['event_id'], 'provider_id': key[0],
                     'source_event_sha256': key[1], 'source_title_sha256': key[2],
                     'report_sha256': row['report_sha256'], 'headline': text,
                     'source_url': row['source_url'], 'source_companies': sorted(companies),
                     'action': change['action'], 'phase': change['phase'],
                     'object_evidence': evidence, 'business_description_evidence': _literal(text, description),
                     'action_evidence': discovery['action_evidence'],
                     'source_available_at': ref['source_available_at'],
                     'basis_available_at': available.isoformat(),
                     'reported_published_at': None,
                     'objects': _objects(expression, exact_product=change['action'] == 'PRODUCT_LAUNCH')}
            seen[identity] = value
    # A revised title of the same provider document is still one research input.
    # Different economic actions in that document remain visible separately.
    latest = {}
    for row in seen.values():
        key = (row['provider_id'], row['source_event_sha256'], row['action'])
        if key not in latest or (row['source_available_at'], row['basis_available_at'], row['observation_id']) > (
                latest[key]['source_available_at'], latest[key]['basis_available_at'], latest[key]['observation_id']):
            latest[key] = row
    return sorted(latest.values(), key=lambda r: r['observation_id'])


def build_theme_outlook(themes, titles, candidates, *, as_of, since, now, include_demand_context=False):
    """Explain research attention and source-described areas; never rank stocks.

    Multi-company is a literal source-name breadth, NOT independent legal entity
    verification. Shared object is a hypothesis, not a certified common cause.
    Every read uses the requested historical snapshot and performs zero writes.
    """
    at = _when(as_of.isoformat(), 'outlook as of')
    start = _when(since.isoformat(), 'outlook since')
    if start > at or at > _when(now.isoformat(), 'now'):
        raise SourceShareError('invalid theme outlook interval')
    observations = _observations(themes, titles, candidates, at)
    if include_demand_context:
        from .business_demand_context import enrich_source_objects
        enrich_source_objects(observations)
    grouped = defaultdict(list)
    for row in observations:
        for key in row['objects']:
            grouped[key].append(row)
    # Prefer the longest common expression for the SAME members. This avoids
    # emitting silicon carbide and silicon carbide semiconductors as two themes.
    by_members = {}
    for key, rows in grouped.items():
        members = tuple(r['observation_id'] for r in rows)
        previous = by_members.get(members)
        if previous is None or (len(key[1]), key) > (len(previous[0][1]), previous[0]):
            by_members[members] = (key, rows)
    groups = sorted(by_members.values(), key=lambda pair: (-len(pair[1]), -len(pair[0][1]), pair[0]))
    used = set()
    output = []
    for key, rows in groups:
        ids = {r['observation_id'] for r in rows}
        if ids <= used:
            continue
        # A single article repeated on several URLs contributes one signature.
        signatures = {(normalized(r['headline']), r['action']) for r in rows}
        names = sorted({name for r in rows for name in r['source_companies']})
        name_count = len({normalized(name) for name in names})
        actions = sorted({r['action'] for r in rows})
        reported = any(r['phase'] == 'SOURCE_REPORTED' for r in rows)
        shrinking = 'SUPPLY_REDUCTION' in actions
        multi = name_count >= 2 and len(signatures) >= 2
        tier = ('CAUTION' if shrinking else 'MULTI_ACTIVITY' if multi and len(actions) >= 2 and reported
                else 'MULTI_COMPANY' if multi and reported else 'EARLY_WATCH')
        label = {'CAUTION': '축소 신호 함께 확인', 'MULTI_ACTIVITY': '우선 조사 후보',
                 'MULTI_COMPANY': '복수 기업의 움직임', 'EARLY_WATCH': '초기 관찰'}[tier]
        representative = min(rows, key=lambda r: (r['basis_available_at'], r['observation_id']))
        subject = representative['objects'][key]
        reasons = []
        if multi:
            reasons.append(f'같은 사업 대상에 원문 회사명 {name_count}개의 행동이 관측됨')
        else:
            reasons.append('단일 회사 또는 회사 미확보 자료 중심으로 후속 관찰 필요')
        if len(actions) >= 2:
            reasons.append('서로 다른 경제 행동이 연결돼 사업 변화의 여러 단계를 살펴볼 수 있음')
        if not reported:
            reasons.append('현재 근거는 계획 단계이며 실행 보도는 아직 없음')
        reasons.append('공통 사업 대상에 대한 연결 가설이며 공통 수요 증가의 인과관계는 미확인')
        paths = []
        for action in actions:
            for dimension, direction, premise, counter in PATHS.get(action, []):
                paths.append({'action': action, 'dimension': dimension, 'direction': direction,
                              'opportunity': premise, 'countercondition': counter})
        sources = []
        areas = {}
        for row in rows:
            source = {k: v for k, v in row.items() if k != 'objects'}
            source['shared_object_evidence'] = _literal(row['headline'], row['objects'][key],
                start=row['object_evidence']['start'] if include_demand_context else 0)
            sources.append(source)
            role, role_label = ROLES.get(row['action'], ('UNKNOWN', '역할 미확인'))
            area_key = ((row['business_description_evidence'] or row['object_evidence'])['text'], row['action'])
            area = areas.setdefault(area_key, {'source_described_area': area_key[0],
                'role': role, 'role_label': role_label, 'action': row['action'],
                'source_companies': [], 'observation_ids': [],
                'classification_basis': 'SOURCE_BUSINESS_OBJECT_AND_ACTION',
                'official_industry_code': None, 'supply_chain_link_verified': False})
            area['source_companies'] = sorted(set(area['source_companies']) | set(row['source_companies']))
            area['observation_ids'].append(row['observation_id'])
        old = [r for r in rows if _when(r['basis_available_at'], 'basis') <= start]
        recent = [r for r in rows if r not in old]
        old_signatures = {(normalized(r['headline']), r['action']) for r in old}
        additions = [r for r in recent if (normalized(r['headline']), r['action']) not in old_signatures]
        activity = 'FIRST_OBSERVED' if not old else 'ADDITIONAL_OBSERVATION' if additions else 'NO_NEW_OBSERVATION'
        output.append({'outlook_id': sha256(_bytes([SCHEMA, RULE, *key])).hexdigest(),
            'subject': subject, 'title': subject + ' 관련 경제 변화', 'status': 'RESEARCH_HYPOTHESIS',
            'attention_tier': tier, 'attention_label': label, 'attention_reasons': reasons,
            'grouping_basis': 'LITERAL_SHARED_BUSINESS_OBJECT_NOT_PROVEN_COMMON_CAUSE',
            'common_demand_cause_verified': False, 'source_company_names': names,
            'source_company_name_count': name_count, 'independent_company_count': None,
            'economic_actions': actions, 'source_observation_count': len(rows),
            'unique_title_action_count': len(signatures), 'independent_market_event_count': None,
            'theme_ids': sorted({t for r in rows for t in r['theme_ids']}),
            'event_ids': sorted({r['event_id'] for r in rows}), 'source_evidence': sources,
            'related_business_areas': list(areas.values()), 'conditional_paths': paths,
            'first_observed_at': min(r['basis_available_at'] for r in rows),
            'basis_available_at': max(r['basis_available_at'] for r in rows),
            'period_activity': activity, 'market_newness': 'UNKNOWN',
            'growth_or_profitability_verified': False, 'investment_score': None,
            'orders_enabled': False})
        if include_demand_context:
            from .business_demand_context import demand_coverage,stated_demand
            if any(r.get('source_product_word_hint') or stated_demand(r) for r in rows):
                output[-1]['source_demand_context']=demand_coverage(rows)
        used.update(ids)
    order = {'MULTI_ACTIVITY': 0, 'MULTI_COMPANY': 1, 'CAUTION': 2, 'EARLY_WATCH': 3}
    output.sort(key=lambda r: (order[r['attention_tier']], r['outlook_id']))
    return {**({'context_interpretation_rule':'source-business-demand-v1',
                'context_is_historical_record':False,'interpretation_at':now.isoformat()}
               if any("source_demand_context" in r for r in output) else {}),
            'schema': SCHEMA, 'rule_version': RULE, 'candidates': output,
            'industry_taxonomy_required': False, 'source_writes': False,
            'counts': {'theme_hypotheses': len(output),
                       'priority_research_candidates': sum(r['attention_tier'] == 'MULTI_ACTIVITY' for r in output),
                       'multi_company_candidates': sum(r['attention_tier'] == 'MULTI_COMPANY' for r in output),
                       'early_watch_candidates': sum(r['attention_tier'] == 'EARLY_WATCH' for r in output),
                       'caution_candidates': sum(r['attention_tier'] == 'CAUTION' for r in output),
                       'generic_or_unavailable_object_observations': sum(not r['objects'] for r in observations)},
            'scope_note': '허용된 저장 뉴스의 사업 대상에 근거한 조사 후보 · 수익성·주가 전망은 미확인'}


def compare_outlooks(current, previous):
    """Compare source-backed breadth, without interpreting new articles as growth."""
    old = {r['outlook_id']: r for r in previous['candidates']}
    for row in current['candidates']:
        before = old.get(row['outlook_id'])
        def signatures(value):
            return {(normalized(s['headline']), s['action']) for s in value['source_evidence']}
        if before is None:
            status = 'FIRST_LOCAL_OBSERVATION'
        elif signatures(row) == signatures(before):
            status = 'NO_SUBSTANTIVE_OBSERVATION_CHANGE'
        elif row['source_company_name_count'] < before['source_company_name_count']:
            status = 'SUPPORT_NARROWED'
        elif (row['source_company_name_count'] > before['source_company_name_count'] or
              set(row['economic_actions']) > set(before['economic_actions'])):
            status = 'SUPPORT_BROADENED'
        else:
            status = 'EVIDENCE_CHANGED'
        row['period_change'] = {'status': status,
            'previous_attention_tier': before['attention_tier'] if before else None,
            'previous_company_name_count': before['source_company_name_count'] if before else 0,
            'current_company_name_count': row['source_company_name_count'],
            'market_newness_confirmed': False}
    live = {r['outlook_id'] for r in current['candidates']}
    current['previous_groups_not_currently_matched'] = [
        {'outlook_id': r['outlook_id'], 'subject': r['subject'],
         'status': 'GROUPING_OR_AVAILABLE_EVIDENCE_CHANGED_NOT_CERTIFIED_CANCELLATION'}
        for r in previous['candidates'] if r['outlook_id'] not in live]
