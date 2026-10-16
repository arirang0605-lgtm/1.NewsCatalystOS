"""Query-only company/action comparison from the selected immutable snapshot."""
import json
from copy import deepcopy
from hashlib import sha256
from .theme_emergence import (_bytes,topic_key,validate_demand_scope,
    validate_demand_recovery,validate_product_price,validate_policy_cause,validate_policy_capacity_action,validate_policy_contract_action,validate_policy_investment_action,validate_policy_parallel_action,validate_recovery_parallel_action,validate_growth_parallel_action,validate_price_parallel_action,validate_order_service_action,validate_price_service_action,validate_investment_event_key,validate_adjacent_demand)
from .theme_changes import _groups
from .source_share import SourceShareError


def _cause(ref):
    if not ref.get('economic_driver') or not ref.get('topic'):
        return {'status':'SOURCE_EXPRESSION_UNAVAILABLE','source_expression':None}
    driver=ref['economic_driver'];topic=ref['topic']
    proofs=[]
    try:
        if 'adjacent_demand_cause' in ref:
            proof=ref['adjacent_demand_cause']
            validate_adjacent_demand(proof,topic,driver,ref['action'],[proof['source_actor']],ref['evidence_sha256'],scope=ref.get('demand_scope'))
            proofs.append(('adjacent_demand_cause',proof))
        if 'demand_scope' in ref:
            validate_demand_scope(ref['demand_scope'],topic,driver)
            proofs.append(('demand_scope',ref['demand_scope']))
        if 'demand_recovery_cause' in ref:
            validate_demand_recovery(ref['demand_recovery_cause'],topic,driver,ref['action'])
            proofs.append(('demand_recovery_cause',ref['demand_recovery_cause']))
        if 'product_price_cause' in ref:
            validate_product_price(ref['product_price_cause'],topic,driver)
            proofs.append(('product_price_cause',ref['product_price_cause']))
        if 'policy_capacity_action' in ref:
            validate_policy_capacity_action(ref['policy_capacity_action'],topic,driver,ref['action'],ref['phase'],ref.get('policy_cause'))
        if 'policy_contract_action' in ref:
            validate_policy_contract_action(ref['policy_contract_action'],topic,driver,ref['action'],ref['phase'],ref.get('policy_cause'))
        if 'policy_investment_action' in ref:
            validate_policy_investment_action(ref['policy_investment_action'],topic,driver,ref['action'],ref['phase'],ref.get('policy_cause'))
        if 'price_service_action' in ref:
            validate_price_service_action(ref['price_service_action'],topic,driver,ref['action'],ref['phase'],ref.get('product_price_cause'),ref.get('demand_scope'),ref.get('service_name'))
        if 'order_service_action' in ref:
            proof=ref['order_service_action']
            validate_order_service_action(proof,topic,driver,ref['action'],ref['phase'],ref.get('demand_scope'),ref.get('service_name'))
            expression=proof['source_expression'][slice(*proof['cause_span'])]
            proofs.append(('order_service_action',{'source_expression':expression,'expression_sha256':sha256(expression.encode()).hexdigest()}))
        if 'growth_parallel_action' in ref:
            proof=ref['growth_parallel_action']
            validate_growth_parallel_action(proof,topic,driver,ref['action'],ref['phase'],ref.get('demand_scope'),ref.get('service_name'),ref.get('market_entry'),ref.get('investment_project'))
            validate_investment_event_key(ref)
            expression=proof['source_expression'][slice(*proof['cause_span'])]
            proofs.append(('growth_parallel_action',{'source_expression':expression,'expression_sha256':sha256(expression.encode()).hexdigest()}))
        if 'price_parallel_action' in ref:
            validate_price_parallel_action(ref['price_parallel_action'],topic,driver,ref['action'],ref['phase'],ref.get('product_price_cause'),ref.get('demand_scope'),ref.get('service_name'),ref.get('market_entry'),ref.get('investment_project'))
            validate_investment_event_key(ref)
        if 'recovery_parallel_action' in ref:
            validate_recovery_parallel_action(ref['recovery_parallel_action'],topic,driver,ref['action'],ref['phase'],ref.get('demand_recovery_cause'),ref.get('demand_scope'),ref.get('service_name'),ref.get('market_entry'),ref.get('investment_project'))
            validate_investment_event_key(ref)
        if 'policy_parallel_action' in ref:
            validate_policy_parallel_action(ref['policy_parallel_action'],topic,driver,ref['action'],ref['phase'],ref.get('policy_cause'),ref.get('service_name'),ref.get('market_entry'))
        if 'policy_cause' in ref:
            if driver!='POLICY_ENABLEMENT':raise SourceShareError('different cause')
            validate_policy_cause(ref['policy_cause'],topic)
            proofs.append(('policy_cause',ref['policy_cause']))
    except (SourceShareError,ValueError,TypeError,KeyError):
        return {'status':'INCOMPATIBLE_STORED_CAUSE','source_expression':None}
    if not proofs:return {'status':'SOURCE_EXPRESSION_UNAVAILABLE','source_expression':None}
    kind,proof=proofs[0]
    return {'status':'STORED_EXPRESSION','kind':kind,
            'source_expression':proof['source_expression'],'expression_sha256':proof['expression_sha256'],
            **({'cause_expression':proof['cause_expression'],'action_expression':proof['action_expression'],
                'cause_span':proof['cause_span'],'action_span':proof['action_span'],
                'cause_sha256':proof['cause_sha256'],'action_sha256':proof['action_sha256'],
                'paragraph_sha256':proof['paragraph_sha256'],
                **({'contract_amount':deepcopy(proof['contract_amount'])} if 'contract_amount' in proof else {}),
                **({'demand_scope':deepcopy(ref['demand_scope'])} if 'demand_scope' in ref else {})} if kind=='adjacent_demand_cause' else {})}



def _event_impact_paths(theme,company,ref,candidate,snapshot_sha,graph_bindings):
    if (not candidate or candidate['entity_id']!=company['entity_id']
            or candidate['theme_id']!=theme['theme_id']
            or candidate['theme_snapshot_sha256']!=snapshot_sha
            or candidate['decision_at']!=theme['decision_at']
            or ref['event_id'] not in candidate['event_ids']):return []
    paths=[]
    for link in company.get('supply_chain_links',[]):
        if (ref['event_id'] not in link['event_ids'] or ref['source_url'] not in link['source_urls']
                or not ref.get('source_binding') or ref['source_binding']!=graph_bindings.get(link['graph_sha256'])):continue
        basis=any(b.get('kind') in {'SOURCE_REPORTED_SUPPLY_RELATION','INFERRED_ASSOCIATION'}
            and all(b.get(k)==v for k,v in link.items()) for b in candidate['inclusion_basis'])
        projection={'role':link['role'],'counterparty_id':link['counterparty_id'],
            'product_stage':link['product_stage'],'category':link['impact_category'],
            'evidence_level':link['impact_evidence_level'],
            'graph_sha256':link['graph_sha256'],'relation_sha256':link['relation_sha256']}
        if not basis or projection not in candidate['benefit_paths']:continue
        fields=('role','counterparty_id','product_stage','relation_kind','impact_category',
                'impact_evidence_level','graph_sha256','relation_sha256','source_available_at','linked_at','link_scope')
        paths.append({**{k:link[k] for k in fields},'event_id':ref['event_id'],
            'entity_id':company['entity_id'],'source_urls':[ref['source_url']],
            'conflicting':ref['event_id'] in link['conflicting_event_ids'],
            'verified_real_transaction':False,'verified_real_benefit':False,'revenue_contribution':None})
    return paths


def common_cause_comparisons(themes,candidates=None):
    output={}
    for theme in themes:
        snapshot_sha=sha256(_bytes(theme)).hexdigest()
        linked=any(c.get('supply_chain_links') for c in theme['company_links'])
        if linked:
            from .theme_supply_chain import validate_theme_relations
            from .theme_company_candidates import company_candidates
            from .source_share import _when
            validate_theme_relations(theme,_when(theme['decision_at'],'comparison decision'))
            graph_bindings={}
            for item in theme['supply_chain_evidence']:
                graph=json.loads(item['graph_payload'])
                graph_bindings[item['payload_sha256']]={'source_event_sha256':graph['event_sha256'],
                    'document_sha256':graph['edges'][0]['document_sha256']}
            cs=company_candidates(theme) if candidates is None else candidates
            by_entity={c['entity_id']:c for c in cs if c['theme_id']==theme['theme_id']}
        else:by_entity={}
        active=set(theme['event_ids'])-set(theme['invalidated_event_ids'])
        find,_,_=_groups(None,theme)
        grouped={};excluded=0
        for ref in theme['source_refs']:
            if ref['polarity']!='SUPPORT' or ref['event_id'] not in active:continue
            # No cross-driver/topic joins, even if a caller hands us mixed refs.
            if (ref.get('economic_driver') not in (None,theme['economic_driver']) or
                    (ref.get('topic') and topic_key(ref.get('topic_alias_evidence',{}).get('canonical_topic',ref['topic'])) not in
                    {topic_key(x) for x in theme['topic_aliases']})):
                excluded+=1;continue
            fields=('event_id','action','phase','topic','economic_driver','source_url','source_id',
                    'source_available_at','recorded_at','evidence_sha256','evidence_level','origin_reference')
            source={k:ref.get(k) for k in fields}
            if ref.get('source_binding'):source['source_binding']=deepcopy(ref['source_binding'])
            if 'policy_capacity_action' in ref:source['policy_capacity_action']=deepcopy(ref['policy_capacity_action'])
            if 'policy_contract_action' in ref:source['policy_contract_action']=deepcopy(ref['policy_contract_action'])
            if 'policy_investment_action' in ref:source['policy_investment_action']=deepcopy(ref['policy_investment_action'])
            if 'policy_parallel_action' in ref:source['policy_parallel_action']=deepcopy(ref['policy_parallel_action'])
            if 'price_service_action' in ref:
                source.update({k:deepcopy(ref[k]) for k in ('price_service_action','service_name','service_event_key','product_price_cause') if k in ref})
            if 'order_service_action' in ref:
                source.update({k:deepcopy(ref[k]) for k in ('order_service_action','service_name','service_event_key') if k in ref})
            if 'price_parallel_action' in ref:
                source.update({k:deepcopy(ref[k]) for k in ('price_parallel_action','product_price_cause','service_name','service_event_key','market_entry','investment_project','investment_event_key') if k in ref})
            if 'growth_parallel_action' in ref:
                source.update({k:deepcopy(ref[k]) for k in ('growth_parallel_action','service_name','service_event_key','market_entry','investment_project','investment_event_key') if k in ref})
            if 'recovery_parallel_action' in ref:
                source['recovery_parallel_action']=deepcopy(ref['recovery_parallel_action'])
                source.update({k:deepcopy(ref[k]) for k in ('investment_project','investment_event_key') if k in ref})
            if ref.get('economic_driver')=='POLICY_ENABLEMENT' and ref['action']=='BUSINESS_START':
                source.update({k:deepcopy(ref[k]) for k in ('service_name','service_event_key') if k in ref})
            source.update(cause=_cause(ref),content_scope=ref.get('content_scope','UNSPECIFIED'),
                extraction_method=ref.get('extraction_method'),
                conflicting=ref['event_id'] in theme['conflicting_event_ids'])
            for company in theme['company_links']:
                if ref['event_id'] not in company['event_ids']:continue
                actor=company['entity_id'] in ref['entity_ids']
                paths=_event_impact_paths(theme,company,ref,by_entity.get(company['entity_id']),snapshot_sha,graph_bindings) if linked else []
                if not actor and not paths:continue
                company_source=deepcopy(source)
                company_source.update(impact_paths=paths,impact_path_status='LINKED' if paths else 'UNKNOWN',
                    company_participation='SOURCE_EVENT_ACTOR' if actor else 'SUPPLY_CHAIN_CONTEXT',
                    event_entity_ids=list(ref['entity_ids']))
                if not actor:company_source['cause']={'status':'COUNTERPARTY_CAUSE_NOT_ATTRIBUTED','source_expression':None}
                key=(company['entity_id'],find(ref['event_id']))
                row=grouped.setdefault(key,{'entity_id':company['entity_id'],
                    'action_group_id':key[1],'sources':{},'source_names':set()})
                row['source_names'].update(m['source_name'] for m in ref.get('company_mappings',[]) if m['entity_id']==company['entity_id'])
                row['sources'][sha256(_bytes(company_source)).hexdigest()]=company_source
        rows=[]
        for key,row in sorted(grouped.items()):
            sources=sorted(row['sources'].values(),key=lambda s:(s['source_available_at'],s['recorded_at'],s['event_id'],s['source_url']))
            rows.append({'entity_id':row['entity_id'],'display_name':' / '.join(sorted(row['source_names'])) or row['entity_id'],
                'action_group_id':row['action_group_id'],'event_ids':sorted({s['event_id'] for s in sources}),
                'sources':sources,'distinct_event_count':len({s['event_id'] for s in sources})})
        output[theme['theme_id']]={'theme_id':theme['theme_id'],
            'theme_snapshot_sha256':snapshot_sha,'decision_at':theme['decision_at'],
            'economic_driver':theme['economic_driver'],'rows':rows,
            'distinct_action_groups':len({r['action_group_id'] for r in rows}),
            'excluded_incompatible_refs':excluded,'verified_real_transaction':False,'verified_real_benefit':False}
    return deepcopy(output)
