"""Company reasons derived from a persisted, as-of theme; no new collection.

Call through build_theme_bundle, which validates the source snapshot first.
Reported participation and supply links never certify revenue or investment merit.
"""
from hashlib import sha256

from .theme_emergence import _bytes

SCHEMA = 'newscatalyst.theme_company_candidate.v1'
ACTION_LABELS = {'SUPPLY_RESUMPTION':'생산·공급 재개', 'MARKET_ENTRY':'시장 진출', 'DELIVERY_START':'납품·공급 개시', 'CUSTOMER_ACQUISITION':'신규 고객 확보', 'CONTRACT':'계약', 'INVESTMENT':'투자', 'INVESTMENT_EXECUTION':'투자 집행', 'CAPACITY_ADDITION':'설비 확대',
                 'PRODUCTION_START':'생산 시작', 'SUPPLY_REDUCTION':'공급 축소',
                 'POLICY_CHANGE':'정책 변화', 'BUSINESS_START':'사업·서비스 시작'}
RELATION_LABELS = {'REPORTED_DIRECT_TRANSACTION':'출처에 보고된 거래 관계',
                   'ANNOUNCED_SUPPLY_PLAN':'발표된 공급 계획',
                   'THEMATIC_ASSOCIATION':'추론한 테마 연관'}


def company_candidates(theme):
    candidates=[]
    active=set(theme['event_ids'])-set(theme['invalidated_event_ids'])
    snapshot_sha=sha256(_bytes(theme)).hexdigest()
    for company in theme['company_links']:
        entity=company['entity_id']
        events=set(company['event_ids']) & active
        refs=[r for r in theme['source_refs'] if r['event_id'] in events
              and r['polarity']=='SUPPORT' and entity in r.get('entity_ids',[])]
        links=[link for link in company.get('supply_chain_links',[])
               if events.intersection(link['event_ids'])]
        if not refs and not links:
            continue  # No fabricated companies from a bare display label.
        names=sorted({m['source_name'] for ref in refs for m in ref.get('company_mappings',[])
                      if m['entity_id']==entity})
        basis=[]
        for ref in refs:
            reported=ref['evidence_level'] in {'OFFICIAL_SOURCE','REPORTED'}
            policy=ref.get('policy_cause')
            reason=f"{ref['topic']} 관련 {ACTION_LABELS.get(ref['action'],ref['action'])} 근거에 기업이 포함됨"
            if policy:
                reason+=f" · 보도된 원인: {policy['source_expression']}"
            if ref.get('demand_recovery_cause'):reason+=' · 보도된 회복 원인: '+ref['demand_recovery_cause']['source_expression']
            if ref.get('product_price_cause'):reason+=' · 보도된 제품 가격 원인: '+ref['product_price_cause']['source_expression']
            if ref.get('market_entry'):reason+=' · 명시 진출 대상: '+ref['market_entry']['source_expression']
            if ref.get('demand_scope'):
                reason+=' · 보도된 수요처 범위: '+ref['demand_scope']['source_expression']
                if ref['demand_scope']['status']=='UNRESOLVED':reason+=' (복수·불명확, 공통 수요처 미확인)'
            if ref.get('investment_project'):reason+=' · 명시 프로젝트: '+ref['investment_project']['project_name']
            basis.append({'kind':'SOURCE_REPORTED_PARTICIPANT' if reported else 'INFERRED_ASSOCIATION',
                'reason':reason,
                **({'investment_project':ref['investment_project']} if 'investment_project' in ref else {}),
                **({'policy_cause':policy} if policy else {}),
                **({'demand_scope':ref['demand_scope']} if 'demand_scope' in ref else {}),
                **({'market_entry':ref['market_entry']} if 'market_entry' in ref else {}),
                **({'demand_recovery_cause':ref['demand_recovery_cause']} if 'demand_recovery_cause' in ref else {}),
                **({'product_price_cause':ref['product_price_cause']} if 'product_price_cause' in ref else {}),
                'event_id':ref['event_id'], 'topic':ref['topic'], 'action':ref['action'],
                'phase':ref['phase'], 'evidence_level':ref['evidence_level'],
                'content_scope':ref.get('content_scope','UNSPECIFIED'),
                'source_url':ref['source_url'], 'evidence_sha256':ref['evidence_sha256'],
                'source_binding':ref.get('source_binding'),
                'source_available_at':ref['source_available_at'], 'recorded_at':ref['recorded_at'],
                'identity_evidence': [m for m in ref.get('company_mappings',[]) if m['entity_id']==entity]})
        for link in theme.get('investment_stage_links',[]):
            if entity not in link['entity_ids']:continue
            basis.append({'kind':'SOURCE_REPORTED_INVESTMENT_STAGES',
                'reason':link['project_name']+' · 투자 결정 → 집행 보도 연결 · 실제 지출·거래·수혜는 독립 확인되지 않음',
                'source_urls':[s['source_url'] for s in link['sources']],**link})
        for link in links:
            basis.append({'kind':'INFERRED_ASSOCIATION' if link['relation_kind']=='THEMATIC_ASSOCIATION'
                          else 'SOURCE_REPORTED_SUPPLY_RELATION',
                'reason':f"{RELATION_LABELS.get(link['relation_kind'],link['relation_kind'])}의 "
                         +('공급자' if link['role']=='supplier' else '고객'),
                **link})
        # A headline's topic is not the company's independently verified business.
        topics=sorted({r['topic'] for r in refs})
        stages=sorted({link['product_stage'] for link in links})
        uncertainties=['출처에 등장하거나 관계가 보도됐다는 사실만으로 실제 수혜·투자 매력을 확정할 수 없음',
                       '매출 기여·재무·현재 가격 평가는 연결되지 않아 미확인']
        if any(r.get('demand_recovery_cause') for r in refs):
            uncertainties.append('수요·주문 회복은 출처 표현이며 기준 수요량·이전 중단·실제 판매·손익·수혜는 독립 확인되지 않음')
        if any(r.get('product_price_cause') for r in refs):
            uncertainties.append('제품 가격 원인은 출처 보도이며 판매량·이익·실제 수혜는 독립 확인되지 않음')
        if any(r.get('product_price_cause',{}).get('change')=='DECREASE' for r in refs):
            uncertainties.append('가격 하락 대응의 감산 결정·계획은 실제 감산 이행이나 매출·이익 감소 확인이 아님')
        if any(r['action']=='MARKET_ENTRY' for r in refs):
            uncertainties.append('시장 진출은 출처 보도이며 고객·계약·실제 판매·매출·수혜는 독립 확인되지 않음')
        if any(r['action']=='SUPPLY_RESUMPTION' for r in refs):
            uncertainties.append('생산·공급 재개는 출처 보도이며 이전 중단 이력·실제 판매·매출·수혜는 독립 확인되지 않음')
        if any(r['action']=='DELIVERY_START' for r in refs):
            uncertainties.append('납품·공급 개시는 출처 보도이며 실제 납품·계약 이행·매출·수혜는 독립 확인되지 않음')
        if any(r['action']=='CUSTOMER_ACQUISITION' for r in refs):
            uncertainties.append('신규 고객 확보는 출처 보도이며 계약 체결·매출·거래 실현은 독립 확인되지 않음')
        if not names: uncertainties.append('공시 명부와 연결된 기업명 근거가 이 결과에 없음')
        if any(r.get('content_scope')=='RSS_TITLE_METADATA' for r in refs):
            uncertainties.append('제목 근거 포함: 본문상의 역할·계약 조건은 확인되지 않음')
        if any(r.get('policy_cause') for r in refs):
            uncertainties.append('정책과 기업 행동의 인과는 출처 보도이며 장벽 해소·수혜를 독립 확인하지 않음')
        if any(r.get('policy_cause') and not r['policy_cause']['policy_name'] for r in refs):
            uncertainties.append('정책명 미확인: 다른 기업 기사와 동일 정책으로 연결하지 않음')
        if any(r.get('policy_cause') and not r['policy_cause']['jurisdiction'] for r in refs):
            uncertainties.append('정책 관할 미확인: 다른 기업 기사와 동일 정책으로 연결하지 않음')
        if any(r['phase']!='SOURCE_REPORTED' for r in refs) or any(
                x['relation_kind']=='ANNOUNCED_SUPPLY_PLAN' for x in links):
            uncertainties.append('계획 또는 시행 전 근거 포함: 집행·공급 실현 미확인')
        conflicts=sorted(events & set(theme['conflicting_event_ids']))
        if conflicts: uncertainties.append('연결된 사건에 상충 근거가 있음')
        paths=[{'role':link['role'],'counterparty_id':link['counterparty_id'],
                'product_stage':link['product_stage'],'category':link['impact_category'],
                'evidence_level':link['impact_evidence_level'],
                'graph_sha256':link['graph_sha256'],'relation_sha256':link['relation_sha256']}
               for link in links]
        candidates.append({'schema_version':SCHEMA,
            'candidate_id':sha256(_bytes([theme['theme_id'],entity])).hexdigest(),
            'theme_id':theme['theme_id'],'theme_snapshot_sha256':snapshot_sha,
            'entity_id':entity,'display_name':' / '.join(names) if names else entity,
            'decision_at':theme['decision_at'],'theme_status':theme['status'],
            'event_ids':sorted(events),'conflicting_event_ids':conflicts,
            'inclusion_basis':basis,
            'business_context':{'source_topics':topics,'reported_supply_stages':stages,
                                'verified_company_business':None},
            'benefit_paths':paths,'benefit_path_status':'HYPOTHESIS' if paths else 'UNKNOWN',
            'uncertainties':uncertainties,
            'financial_assessment':{'status':'NOT_CONNECTED','value':None},
            'price_assessment':{'status':'NOT_CONNECTED','value':None},
            'investment_merit':'NOT_ASSESSED','revenue_contribution':None,
            'verified_real_transaction':False,'verified_real_benefit':False})
    return candidates
