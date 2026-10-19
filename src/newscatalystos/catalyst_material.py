"""News-owned material assessment, not a stock-selection or trading engine.

Use existing immutable ThemeStore versions, event/followup grouping and change
comparison. A first local observation is NEVER proof of a new market catalyst.
Impacts are conditional, source-company-specific economic paths, not returns.
"""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from hashlib import sha256

from .economic_path import ImpactHypothesis, build_impact_analysis
from .standard_delivery import build_theme_bundle
from .theme_changes import _difference, _groups
from .theme_emergence import _bytes
from .source_share import SourceShareError, _when

SCHEMA = 'newscatalyst.catalyst_material.v1'
LABELS = {
    'FIRST_RECORDED_CLAIM': '로컬 첫 관측 · 시장 신규 재료 여부 미확인',
    'EXISTING_SOURCE_NEWLY_ANALYZED': '이전 확보 자료를 이번에 분석 · 새 발생으로 계산하지 않음',
    'REPEATED_CLAIM': '기존 사건 반복·추가 보도 · 새 경제 행동 아님',
    'SOURCE_TEXT_REVISION_UNRESOLVED': '같은 원문 판본 변경 · 실질 변화 여부 추가 근거 필요',
    'REPORTED_STAGE_PROGRESS': '같은 사건의 계획 이후 개시·집행 보도 추가',
    'SOURCE_WITHDRAWAL': '출처가 기존 사건을 명시적으로 철회·무효화',
    'SOURCE_CONFLICT': '같은 사건에 상충 근거 발생',
    'PREVIOUSLY_INVALIDATED': '기존 무효화 상태 유지',
    'IDENTITY_OR_CONTEXT_ONLY': '기업 식별·근거 설명만 갱신 · 새 경제 행동 아님',
    'NO_NEW_MATERIAL': '비교 기간에 새 경제 행동·중요 변경 없음',
}
HINTS = {
    'FIRST_RECORDED_CLAIM': 'CONTEXT_ONLY_MARKET_NOVELTY_UNKNOWN',
    'EXISTING_SOURCE_NEWLY_ANALYZED': 'CONTEXT_ONLY_MARKET_NOVELTY_UNKNOWN',
    'SOURCE_TEXT_REVISION_UNRESOLVED': 'REASSESS_UNRESOLVED_SOURCE_REVISION',
    'REPORTED_STAGE_PROGRESS': 'REASSESS_REPORTED_PROGRESS',
    'SOURCE_WITHDRAWAL': 'REASSESS_WITHDRAWAL',
    'SOURCE_CONFLICT': 'REASSESS_CONFLICT',
    'PREVIOUSLY_INVALIDATED': 'EXCLUDE_INVALIDATED_CATALYST',
    'REPEATED_CLAIM': 'NO_NEW_CATALYST',
    'IDENTITY_OR_CONTEXT_ONLY': 'NO_NEW_CATALYST',
    'NO_NEW_MATERIAL': 'NO_NEW_CATALYST',
}
PATHS = {
    'PRODUCT_PRESENTATION': [('EARNINGS','UNKNOWN','출처의 제품·솔루션 공개·시연은 후속 출시·고객 채택을 확인할 사업 관찰 단서',
         '공개·시연을 판매 개시나 출시 완료로 보지 않음. 제조사·제품 가용성·계약·매출·사용자 채택 미확인')],
    'PRODUCT_LAUNCH': [('EARNINGS','UNKNOWN','출처의 제품·솔루션 출시 발표는 고객 채택·유료 판매로 이어질 경우 사업 기회가 될 수 있음',
         '출시 주체와 제조사·유통사를 구분. 실제 판매량·매출·수익성·사용자 채택·인허가·반복수요 미확인')],
    'INVESTMENT': [
        ('CAPEX','INCREASE','투자 계획이 실행되면 해당 기업의 시설투자 지출·자금 소요가 증가할 수 있음',
         '집행 일정·실제 장비 발주·투자재원 미확인. 지연·취소·투자비 증가 시 재평가'),
        ('SUPPLY','INCREASE','투자시설이 가동되고 수요가 뒷받침되면 생산능력 확대 가능',
         '가동시점·수율·수요·가동률 미확인. 과잉공급과 감가상각 부담도 가능')],
    'INVESTMENT_EXECUTION': [
        ('CAPEX','INCREASE','출처의 투자 집행 보도는 계획의 진전 근거이나 실제 지출액 확정은 아님',
         '계획 대비 집행액·준공·가동·현금부담을 확인해야 함')],
    'PRODUCTION_START': [('SUPPLY','INCREASE','출처에 명시된 생산 개시가 지속되면 제품 공급 확대 가능',
         '양산수율·고객 인증·출하·판매수요·매출 인식이 별도로 필요')],
    'CAPACITY_ADDITION': [('SUPPLY','INCREASE','출처가 명시한 증설의 가동 이후 공급능력 확대 가능',
         '장비도입·가동률·수요·투자비·기존설비 대체 여부 미확인')],
    'SUPPLY_RESUMPTION': [('SUPPLY','INCREASE','중단됐던 공급의 재개 보도로 공급 정상화 가능',
         '재개물량·지속성·고객수요·실제 매출 회복 미확인')],
    'SUPPLY_REDUCTION': [('SUPPLY','DECREASE','출처에 명시된 공급 축소는 해당 기업 물량·가동에 부담 가능',
         '업계 가격 상승 효과나 재고조정 효과는 별도 근거 없이는 판단 불가')],
    'CONTRACT': [('EARNINGS','UNKNOWN','계약 당사자의 공급·구매 조건 이행에 따라 매출 기회 또는 원가·지출이 달라질 수 있음',
         '판매자/구매자 역할·납기·수익률·해지조건·실제 납품/매출 인식 미확인')],
    'POLICY_CHANGE': [('COMPETITION','UNKNOWN','출처에 명시된 지원·정책 변경이 해당 기업의 사업 여건에 영향을 줄 수 있음',
         '의향·협약·발효·현금 지급을 구분. 조건 미충족·지원 취소·경쟁사 지원을 함께 확인')],
    'BUSINESS_START': [('EARNINGS','UNKNOWN','서비스 개시는 고객 채택·유료 이용으로 이어질 때 매출 기회가 될 수 있음',
         '이용량·가격·비용·반복매출·경쟁력은 개시 보도만으로 확인되지 않음')],
    'CUSTOMER_ACQUISITION': [('DEMAND','INCREASE','명시된 신규 고객 확보가 지속적인 구매 수요로 이어질 가능성',
         '채택·계약·발주·출하를 구분. 고객명·규모·반복성·취소 가능성 확인 필요')],
    'DELIVERY_START': [('EARNINGS','UNKNOWN','출처의 납품 개시 보도는 계약 이행의 진전 단서',
         '납품물량·검수·대금 수취·매출 및 이익 기여는 미확인')],
    'MARKET_ENTRY': [('DEMAND','UNKNOWN','명시된 시장 진입은 사업 범위 확대의 단서',
         '고객 확보·경쟁력·실제 판매·수익성 없이 시장 규모를 기업 수혜로 환산하지 않음')],
}


def default_since(at):
    return at.astimezone(timezone(timedelta(hours=9))).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)


def _source_key(ref):
    binding=ref.get('source_binding') or {}
    return (ref['source_id'], binding.get('source_event_sha256'), ref['source_url'])


def _relation_effects(theme,group_ids):
    rows=[]
    for company in theme['company_links']:
        for link in company.get('supply_chain_links',[]):
            if not set(link['event_ids']).intersection(group_ids):continue
            # Existing source graph validation has already bound this event,
            # same document/company, role and provenance. Never fill suppliers
            # from a shared industry name or a generic stage of production.
            rows.append({'entity_id':company['entity_id'],'source_entity_id':company['entity_id'],
                'role':'DOCUMENT_BOUND_'+link['role'].upper(),
                'relation_graph_sha256':link['graph_sha256'],
                'relation_sha256':link['relation_sha256'],
                'event_ids':sorted(set(link['event_ids']).intersection(group_ids)),
                'hypothesis':'기존 공급관계는 영향 가능성의 근거이며 새 발주·납품·매출을 확정하지 않음',
                'countercondition':'현재 사건에 대한 실제 발주·규모·시점 및 거래 지속 여부 미확인',
                'evidence_level':'HYPOTHESIS','verified_real_benefit':False})
    return rows


def assess_theme(before,after,*,since,scope,now):
    """Stable, source-bound summary; clocks/reanalysis do not mint new claims."""
    at=_when(after['decision_at'],'theme decision')
    build_theme_bundle([after]+([before] if before else []),decision_at=at,now=now)
    diff=_difference(before,after);find,old_groups,new_groups=_groups(before,after)
    old_refs=(before or {}).get('source_refs',[])
    supports=[r for r in after['source_refs'] if r['polarity']=='SUPPORT']
    added=diff['sources']['added']
    known_ever={r['event_id'] for r in supports}
    groups={}
    for e in known_ever:groups.setdefault(find(e),set()).add(e)
    rows=[]
    for key,ids in sorted(groups.items()):
        sources=[r for r in supports if r['event_id'] in ids]
        valid=[r for r in sources if r['event_id'] in after['event_ids']]
        latest=max(valid or sources,key=lambda r:(r['recorded_at'],r['source_available_at'],_bytes(r)))
        targeted=[r for r in added if r['polarity']!='SUPPORT' and
                  (r.get('supersedes_event_id') in ids or r['event_id'] in ids)]
        additions=[r for r in added if r['event_id'] in ids and r['polarity']=='SUPPORT']
        linked=[l for l in diff['followups_added'] if l['planned_event_id'] in ids or l['realization_event_id'] in ids]
        linked += [l for l in diff.get('investment_stage_links_added',[]) if l['decision_event_id'] in ids or l['execution_event_id'] in ids]
        previous_same_doc=[r for r in old_refs if r['polarity']=='SUPPORT' and r['event_id'] not in ids
            and _source_key(r)==_source_key(latest) and _source_key(r)[1] is not None
            and set(r.get('original_entity_ids',r['entity_ids']))==set(latest.get('original_entity_ids',latest['entity_ids']))]
        if any(r['polarity']=='RETRACT' for r in targeted):kind='SOURCE_WITHDRAWAL'
        elif not valid and set(after['invalidated_event_ids']).intersection(ids):kind='PREVIOUSLY_INVALIDATED'
        elif any(r['polarity']=='CONTRADICT' for r in targeted):kind='SOURCE_CONFLICT'
        elif linked:kind='REPORTED_STAGE_PROGRESS'
        elif previous_same_doc and key not in old_groups:kind='SOURCE_TEXT_REVISION_UNRESOLVED'
        elif key not in old_groups:
            kind=('EXISTING_SOURCE_NEWLY_ANALYZED' if min(_when(r['source_available_at'],'source') for r in sources)<since
                  else 'FIRST_RECORDED_CLAIM')
        elif additions:
            old_binding={(_source_key(r),(r.get('source_binding') or {}).get('document_sha256')) for r in old_refs if r['event_id'] in ids}
            kind=('IDENTITY_OR_CONTEXT_ONLY' if all((_source_key(r),(r.get('source_binding') or {}).get('document_sha256')) in old_binding for r in additions)
                  else 'REPEATED_CLAIM')
        else:kind='NO_NEW_MATERIAL'
        inactive=bool(set(after['invalidated_event_ids']).intersection(ids) and not valid)
        conflicting=bool(set(after['conflicting_event_ids']).intersection(ids))
        impacts=[]
        # Early valid publications may omit an action/topic. They remain
        # readable as source history, without guessing a business effect from
        # a theme name or upgrading a legacy observation to a new fact.
        topic=latest.get('topic');action=latest.get('action');phase=latest.get('phase')
        complete=bool(topic and action and phase)
        if not inactive and not conflicting:
            spec=PATHS.get(action,[]) if complete else []
            for entity in latest['entity_ids']:
                hypotheses=[ImpactHypothesis(path,direction,topic,latest['evidence_sha256'],premise,
                    'MISSING_INFORMATION',counter) for path,direction,premise,counter in spec]
                analysis=(build_impact_analysis(latest['event_id'],hypotheses,
                    available_at=_when(latest['source_available_at'],'source'),decision_at=at,now=now) if hypotheses else None)
                impacts.append({'entity_id':entity,'source_entity_id':entity,'role':'DIRECT_SOURCE_ACTION_PARTY',
                    'action':action,'phase':phase,'event_ids':sorted(ids),
                    'hypotheses':[asdict(h) for h in analysis.impact_hypotheses] if analysis else [],
                    'impact_status':'CONDITIONAL_PATH' if analysis else 'N/A',
                    'company_inclusion_basis':'EXACT_COMPANY_IN_THIS_SOURCE_EVENT',
                    'verified_real_benefit':False})
            impacts+=_relation_effects(after,ids)
        rows.append({'action_group_id':key,'event_ids':sorted(ids),'material_status':kind,'reason':LABELS[kind],
            'news_input_for_era':HINTS[kind],
            'source_action':action,'source_phase':phase,'topic':topic,
            'source_detail_status':'COMPLETE' if complete else 'LEGACY_DETAILS_UNAVAILABLE',
            'active':bool(valid) and not inactive,'conflicting':conflicting,
            'first_source_observed_at':min(r['source_available_at'] for r in sources),
            'first_event_recorded_at':min(r['recorded_at'] for r in sources),
            'source_published_at':None,'market_novelty':'UNCONFIRMED',
            'is_new_market_catalyst':None,'source_event_date_verified':False,
            'source_document_count':len({_source_key(r) for r in sources}),
            'locally_added_action_count':int(key in new_groups-old_groups and not previous_same_doc),
            'evidence':[{'event_id':r['event_id'],'evidence_sha256':r['evidence_sha256'],
                'source_id':r['source_id'],'source_url':r['source_url'],
                'source_available_at':r['source_available_at'],'recorded_at':r['recorded_at'],
                'polarity':r['polarity'],'supersedes_event_id':r.get('supersedes_event_id')}
                for r in sources+targeted],
            'previous_document_event_ids':sorted({r['event_id'] for r in previous_same_doc}),
            'company_impacts':impacts,'source_reported_progress':deepcopy(linked),
            'verified_economic_effect':False,'investment_rank':None,'orders_enabled':False})
    return {'schema':SCHEMA,'scope':scope,'theme_id':after['theme_id'],
        'source_theme_sha256':sha256(_bytes(after)).hexdigest(),
        'comparison_since':since.isoformat(),'basis_available_at':after['decision_at'],
        'baseline_sha256':sha256(_bytes(before)).hexdigest() if before else None,
        'novelty_coverage':'STORED_SAME_EVENT_OR_EXPLICIT_FOLLOWUP_NOT_ALL_MARKET_NEWS',
        'status':'READY','materials':rows,
        'summary':{k:sum(r['material_status']==k for r in rows) for k in LABELS},
        'selection_owner':'EraLeader','trading_decision_owner':'INDEPENDENT_STRATEGY',
        'market_expectation':'UNKNOWN','new_market_catalyst_count':None,
        'leader_score':None,'investment_rank':None,'orders_enabled':False}


def materials_for_store(store,*,since,as_of,scope='base',now=None,industry='SEMICONDUCTOR'):
    if industry not in {'SEMICONDUCTOR','POWER_EQUIPMENT','ALL_DISCOVERED'}:raise SourceShareError('unsupported material industry')
    present=now or datetime.now(timezone.utc)
    start=_when(since.isoformat(),'comparison since');at=_when(as_of.isoformat(),'as of')
    if start>at or at>present:raise SourceShareError('invalid material query time')
    versions=store.period_versions(since=start,as_of=at,now=present)
    result={}
    for theme_id,history in versions.items():
        before=history[0] if _when(history[0]['decision_at'],'baseline')<start else None
        after=history[-1]
        supported=industry=='ALL_DISCOVERED' or any(industry in h['industry_tags'] for h in history)
        if not supported and after['invalidated_event_ids']:
            # A fully retracted theme has no active industry tags. Its exact
            # first saved edition, not a keyword guess, retains its scope.
            initial=store.search(as_of=_when(after['first_detected_at'],'first theme'),now=present)
            supported=any(h['theme_id']==theme_id and industry in h['industry_tags'] for h in initial)
        if not supported:continue
        result[theme_id]=assess_theme(before,after,since=start,scope=scope,now=present)
    return result


def attach_material(exported,materials):
    """Receiver extension retains exact official mappings without producer edits."""
    result=deepcopy(exported)
    for t in result:
        origin=t.get('export_origin',{}).get('theme_id',t['theme_id'])
        value=materials.get(origin)
        if not value:continue
        value=deepcopy(value)
        # Identity is an independently received mapping, not a new news event.
        mappings={}
        for ref in t['source_refs']:
            for m in ref.get('company_mappings',[]):mappings.setdefault(m['source_name'],set()).add(m['entity_id'])
        for event in value['materials']:
            for c in event['company_impacts']:
                found=mappings.get(c['entity_id'],set())
                if len(found)==1:c['entity_id']=next(iter(found))
        t['catalyst_material']=value
    return result
