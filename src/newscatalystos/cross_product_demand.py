"""Query-only shared demand or policy hypotheses across pinned semiconductor themes."""
from copy import deepcopy
from hashlib import sha256
from .theme_emergence import _bytes,validate_demand_scope,validate_demand_recovery,validate_market_entry,validate_service_event_key,validate_policy_cause,validate_policy_capacity_action,validate_policy_contract_action,validate_policy_investment_action,validate_policy_parallel_action,validate_recovery_parallel_action,validate_growth_parallel_action,validate_order_service_action,validate_investment_project,validate_investment_event_key,_text,topic_key
from .economic_changes import normalized,policy_cause_key
from .common_cause_comparison import common_cause_comparisons
from .company_search import company_search_context,match_company_search
from .theme_company_identity import ID
from .source_share import _when,SourceShareError

PRODUCTS={'HBM','DRAM','NAND'}
BINDING=('event_id','source_url','evidence_sha256','recorded_at','source_binding','action','phase','source_available_at')


def cross_product_demand(themes,candidates,comparisons,*,as_of,since=None,query='',_min_products=2):
    as_of=_when(as_of.isoformat(),'comparison end')
    since=_when(since.isoformat(),'comparison start') if since else None
    result={'as_of':as_of.isoformat(),'since':since.isoformat() if since else None,
        'status':'READY','groups':[],'unavailable_theme_ids':[],
        'verified_real_transaction':False,'verified_real_benefit':False,'orders_enabled':False}
    if since and since>as_of:result['status']='NOT_STARTED';return result
    grouped={}
    for theme in themes:
        tid=theme['theme_id']
        driver=theme['economic_driver']
        if driver not in {'DEMAND_EXPANSION','DEMAND_CONTRACTION','DEMAND_RECOVERY','POLICY_ENABLEMENT'} or theme['industry_tags']!=['SEMICONDUCTOR']:continue
        products={p for p in PRODUCTS if topic_key(p) in {topic_key(x) for x in theme.get('topic_aliases',[])}}
        if len(products)!=1:continue
        product=next(iter(products));digest=sha256(_bytes(theme)).hexdigest()
        cs=[c for c in candidates if c['theme_id']==tid]
        try:
            if (_when(theme['decision_at'],'decision')>as_of or not cs
                or any(c['theme_snapshot_sha256']!=digest or c['decision_at']!=theme['decision_at'] for c in cs)
                or comparisons.get(tid)!=common_cause_comparisons([theme],cs).get(tid)):
                raise SourceShareError('unpinned product comparison')
            by_entity={c['entity_id']:c for c in cs};items={}
            for row in comparisons[tid]['rows']:
                candidate=by_entity.get(row['entity_id'])
                if not candidate:continue
                identity=candidate.get('identity_context',{})
                resolved=(candidate['entity_id'] if ID.fullmatch(candidate['entity_id']) else
                    candidate.get('resolved_entity_id') if identity.get('status')=='MATCHED' and identity.get('decision_at')
                    and _when(identity['decision_at'],'identity available')<=as_of else None)
                if resolved and not ID.fullmatch(resolved):resolved=None
                for source in row['sources']:
                    if source['company_participation']!='SOURCE_EVENT_ACTOR':continue
                    if driver=='POLICY_ENABLEMENT' and (source['action'] not in {'PRODUCTION_START','CAPACITY_ADDITION','CONTRACT','DELIVERY_START','CUSTOMER_ACQUISITION','MARKET_ENTRY','INVESTMENT_EXECUTION','BUSINESS_START'} or source['phase']!='SOURCE_REPORTED'):continue
                    if driver=='DEMAND_CONTRACTION' and (source['action']!='SUPPLY_REDUCTION' or source['phase']!='SOURCE_REPORTED'):continue
                    if driver=='DEMAND_RECOVERY' and (source['action'] not in {'SUPPLY_RESUMPTION','CONTRACT','DELIVERY_START','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT_EXECUTION','CUSTOMER_ACQUISITION','MARKET_ENTRY','BUSINESS_START'} or source['phase']!='SOURCE_REPORTED'):continue
                    if (source['event_id'] not in set(theme['event_ids'])-set(theme['invalidated_event_ids'])
                        or _when(source['recorded_at'],'recorded')>as_of
                        or _when(source['source_available_at'],'source available')>as_of):continue
                    refs=[r for r in theme['source_refs'] if r['polarity']=='SUPPORT'
                        and all(r.get(k)==source.get(k) for k in BINDING)
                        and row['entity_id'] in r['entity_ids'] and r.get('industry_tags')==['SEMICONDUCTOR']
                        and topic_key(r.get('topic',''))==topic_key(product) and r.get('economic_driver')==driver]
                    for ref in refs:
                        scope=ref.get('demand_scope')
                        if driver=='POLICY_ENABLEMENT':
                            policy=ref.get('policy_cause')
                            validate_policy_cause(policy,ref['topic'])
                            if not policy['policy_name'] or not policy['jurisdiction']:continue
                            if 'policy_parallel_action' in ref:
                                validate_policy_parallel_action(ref['policy_parallel_action'],ref['topic'],driver,ref['action'],ref['phase'],policy,ref.get('service_name'),ref.get('market_entry'),ref.get('investment_project'))
                                actors={m['source_name']:m['entity_id'] for m in ref.get('company_mappings',[])}
                                if not all(actors.get(a,a) in ref['entity_ids'] for a in ref['policy_parallel_action']['actors']):raise SourceShareError('shared action actor mismatch')
                            if ref['action']=='BUSINESS_START':
                                # A validated parallel proof also carries a concrete
                                # function without asserting a source-named identity.
                                if not ref.get('service_name') and 'policy_parallel_action' not in ref:continue
                                if ref.get('service_name') is not None and not _text(ref['service_name'],80):raise SourceShareError('invalid explicit service name')
                                validate_service_event_key(ref)
                            if ref['action']=='MARKET_ENTRY':validate_market_entry(ref.get('market_entry'),ref['action'])
                            if ref['action']=='CAPACITY_ADDITION':
                                if 'policy_capacity_action' not in ref:continue
                                validate_policy_capacity_action(ref['policy_capacity_action'],ref['topic'],driver,ref['action'],ref['phase'],policy)
                                actors={m['source_name']:m['entity_id'] for m in ref.get('company_mappings',[])}
                                if not all(actors.get(a,a) in ref['entity_ids'] for a in ref['policy_capacity_action']['actors']):raise SourceShareError('policy capacity actor mismatch')
                            if ref['action']=='CONTRACT':
                                if 'policy_contract_action' not in ref:continue
                                validate_policy_contract_action(ref['policy_contract_action'],ref['topic'],driver,ref['action'],ref['phase'],policy)
                                actors={m['source_name']:m['entity_id'] for m in ref.get('company_mappings',[])}
                                if not all(actors.get(a,a) in ref['entity_ids'] for a in ref['policy_contract_action']['actors']):raise SourceShareError('policy contract actor mismatch')
                            if ref['action']=='INVESTMENT_EXECUTION':
                                if 'policy_investment_action' not in ref:continue
                                validate_policy_investment_action(ref['policy_investment_action'],ref['topic'],driver,ref['action'],ref['phase'],policy)
                                actors={m['source_name']:m['entity_id'] for m in ref.get('company_mappings',[])}
                                if not all(actors.get(a,a) in ref['entity_ids'] for a in ref['policy_investment_action']['actors']):raise SourceShareError('policy investment actor mismatch')
                                if ref['policy_investment_action'].get('investment_project')!=ref.get('investment_project'):raise SourceShareError('policy investment project mismatch')
                                if 'investment_project' in ref:validate_investment_project(ref['investment_project'],ref['action'])
                                validate_investment_event_key(ref)
                            key=sha256(_bytes(policy_cause_key(policy))).hexdigest()
                        else:
                            if not scope or scope['status']!='EXPLICIT':continue
                            validate_demand_scope(scope,ref['topic'],driver)
                            key=normalized(scope['destination'])
                        if 'order_service_action' in ref:
                            validate_order_service_action(ref['order_service_action'],ref['topic'],driver,ref['action'],ref['phase'],scope,ref.get('service_name'))
                            validate_service_event_key(ref)
                            actors=dict(zip(ref.get('original_entity_ids',ref['entity_ids']),ref['entity_ids']))
                            if not all(actors.get(a,a) in ref['entity_ids'] for a in ref['order_service_action']['actors']):raise SourceShareError('order service actor mismatch')
                            if ref['phase']!='SOURCE_REPORTED':continue
                        if 'growth_parallel_action' in ref:
                            validate_growth_parallel_action(ref['growth_parallel_action'],ref['topic'],driver,ref['action'],ref['phase'],scope,ref.get('service_name'),ref.get('market_entry'),ref.get('investment_project'))
                            validate_service_event_key(ref)
                            validate_investment_event_key(ref)
                            actors=dict(zip(ref.get('original_entity_ids',ref['entity_ids']),ref['entity_ids']))
                            if not all(actors.get(a,a) in ref['entity_ids'] for a in ref['growth_parallel_action']['actors']):raise SourceShareError('shared growth actor mismatch')
                        if driver=='DEMAND_RECOVERY':
                            if 'recovery_parallel_action' in ref:
                                validate_recovery_parallel_action(ref['recovery_parallel_action'],ref['topic'],driver,ref['action'],ref['phase'],ref.get('demand_recovery_cause'),scope,ref.get('service_name'),ref.get('market_entry'),ref.get('investment_project'))
                                validate_investment_event_key(ref)
                                actors=dict(zip(ref.get('original_entity_ids',ref['entity_ids']),ref['entity_ids']))
                                if not all(actors.get(a,a) in ref['entity_ids'] for a in ref['recovery_parallel_action']['actors']):raise SourceShareError('shared recovery actor mismatch')
                            proof=ref.get('demand_recovery_cause')
                            validate_demand_recovery(proof,ref['topic'],driver,ref['action'])
                            if not scope['source_expression'].endswith(proof['source_expression']):continue
                            if ref['action']=='MARKET_ENTRY':validate_market_entry(ref.get('market_entry'),ref['action'])
                            if ref['action']=='BUSINESS_START':
                                # A validated parallel proof also carries a concrete
                                # function without asserting a source-named identity.
                                if not ref.get('service_name') and 'recovery_parallel_action' not in ref:continue
                                if ref.get('service_name') is not None and not _text(ref['service_name'],80):raise SourceShareError('invalid explicit service name')
                                validate_service_event_key(ref)
                        if source['cause']['status']!='STORED_EXPRESSION':continue
                        item=items.setdefault(key,{'product':product,'theme_id':tid,'theme_snapshot_sha256':digest,
                            'decision_at':theme['decision_at'],'theme_status':theme['status'],
                            'conflicting_event_ids':list(theme['conflicting_event_ids']),
                            'invalidated_event_ids':list(theme['invalidated_event_ids']),
                            'counterevidence':[deepcopy(r) for r in theme['source_refs'] if r['polarity']!='SUPPORT'
                                and _when(r['recorded_at'],'counter recorded')<=as_of
                                and _when(r['source_available_at'],'counter available')<=as_of],'actions':{}})
                        action=item['actions'].setdefault((candidate['candidate_id'],row['action_group_id']),{
                            'candidate_id':candidate['candidate_id'],'entity_id':candidate['entity_id'],
                            'company_key':resolved or 'UNRESOLVED:'+candidate['candidate_id'],
                            'identity_status':'IDENTIFIED' if resolved else 'SOURCE_NAME_ONLY',
                            'display_name':row['display_name'],'action_group_id':row['action_group_id'],'sources':{}})
                        observation={**deepcopy(source),
                            **({'policy_cause':deepcopy(policy),**({'policy_capacity_action':deepcopy(ref['policy_capacity_action'])} if ref['action']=='CAPACITY_ADDITION' else {}),**({'policy_contract_action':deepcopy(ref['policy_contract_action'])} if ref['action']=='CONTRACT' else {})} if driver=='POLICY_ENABLEMENT' else {'demand_scope':deepcopy(scope)}),
                            **({k:deepcopy(ref[k]) for k in ('policy_investment_action','investment_project','investment_event_key') if k in ref} if driver=='POLICY_ENABLEMENT' and ref['action']=='INVESTMENT_EXECUTION' else {}),
                            'in_period':since is None or _when(source['recorded_at'],'recorded')>=since,
                            **({'demand_recovery_cause':deepcopy(proof)} if driver=='DEMAND_RECOVERY' else {}),
                            **({'market_entry':deepcopy(ref['market_entry'])} if driver in {'DEMAND_RECOVERY','POLICY_ENABLEMENT'} and ref['action']=='MARKET_ENTRY' else {}),
                            **({k:deepcopy(ref[k]) for k in ('service_name','service_event_key') if k in ref} if driver in {'DEMAND_RECOVERY','POLICY_ENABLEMENT'} and ref['action']=='BUSINESS_START' else {})}
                        action['sources'][sha256(_bytes(observation)).hexdigest()]=observation
            for key,item in items.items():
                first=next(iter(next(iter(item['actions'].values()))['sources'].values()))
                if driver=='POLICY_ENABLEMENT':
                    policy=first['policy_cause']
                    group=grouped.setdefault((key,driver),{'policy_cause_key':policy_cause_key(policy),
                        'group_id':sha256(_bytes(['CROSS_PRODUCT_POLICY',policy_cause_key(policy)])).hexdigest(),
                        'economic_driver':driver,'products':[]})
                else:
                    scope=first['demand_scope']
                    identity=['CROSS_PRODUCT_DEMAND',key]+([driver] if driver!='DEMAND_EXPANSION' else [])
                    group=grouped.setdefault((key,driver),{'destination_key':key,'destination_expressions':set(),
                        'group_id':sha256(_bytes(identity)).hexdigest(),'products':[],
                        **({'economic_driver':driver} if driver!='DEMAND_EXPANSION' else {})})
                    group['destination_expressions'].add(scope['destination'])
                for a in item['actions'].values():a['sources']=sorted(a['sources'].values(),key=lambda s:(s['recorded_at'],s['event_id'],s['source_url']))
                item['actions']=list(item['actions'].values());group['products'].append(item)
        except (SourceShareError,ValueError,TypeError,KeyError):result['unavailable_theme_ids'].append(tid)
    context=company_search_context(themes,candidates)
    direct={cid for cid,v in match_company_search(context,query).items() if v['match_kind']=='DIRECT_COMPANY'} if query.strip() else set()
    for key,group in sorted(grouped.items()):
        actions=[a for p in group['products'] for a in p['actions']]
        groups={a['action_group_id'] for a in actions}
        if len({p['product'] for p in group['products']})<_min_products or len(groups)<_min_products:continue
        if group.get('economic_driver')=='POLICY_ENABLEMENT':
            # Literal names are contexts, not independently resolved companies.
            group['source_actor_name_count']=len({normalized(a['display_name']) for a in actions})
        else:group['destination_expressions']=sorted(group['destination_expressions'])
        group.update(
            products=sorted(group['products'],key=lambda p:(p['product'],p['theme_id'])),
            distinct_action_groups=len(groups),identified_company_count=len({a['company_key'] for a in actions if a['identity_status']=='IDENTIFIED'}),
            unresolved_company_contexts=len({a['company_key'] for a in actions if a['identity_status']=='SOURCE_NAME_ONLY'}),
            status='COMMON_CAUSE_HYPOTHESIS',verified_real_transaction=False,verified_real_benefit=False)
        exact=any(a['candidate_id'] in direct for a in actions)
        if query.strip() and not exact and normalized(query) not in normalized(_bytes(group).decode()):continue
        group['search_match']='DIRECT_COMPANY_CONTEXT' if exact else 'TEXT_CONTEXT' if query.strip() else 'UNFILTERED'
        result['groups'].append(group)
    if result['unavailable_theme_ids']:result['status']='PARTIAL'
    return result
