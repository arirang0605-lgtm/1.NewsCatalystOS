"""Query-only company/action comparison from the selected immutable snapshot."""
from copy import deepcopy
from hashlib import sha256
from .theme_emergence import (_bytes,topic_key,validate_demand_scope,
    validate_demand_recovery,validate_product_price,validate_policy_cause)
from .theme_changes import _groups
from .source_share import SourceShareError


def _cause(ref):
    if not ref.get('economic_driver') or not ref.get('topic'):
        return {'status':'SOURCE_EXPRESSION_UNAVAILABLE','source_expression':None}
    driver=ref['economic_driver'];topic=ref['topic']
    proofs=[]
    try:
        if 'demand_scope' in ref:
            validate_demand_scope(ref['demand_scope'],topic,driver)
            proofs.append(('demand_scope',ref['demand_scope']))
        if 'demand_recovery_cause' in ref:
            validate_demand_recovery(ref['demand_recovery_cause'],topic,driver,ref['action'])
            proofs.append(('demand_recovery_cause',ref['demand_recovery_cause']))
        if 'product_price_cause' in ref:
            validate_product_price(ref['product_price_cause'],topic,driver)
            proofs.append(('product_price_cause',ref['product_price_cause']))
        if 'policy_cause' in ref:
            if driver!='POLICY_ENABLEMENT':raise SourceShareError('different cause')
            validate_policy_cause(ref['policy_cause'],topic)
            proofs.append(('policy_cause',ref['policy_cause']))
    except (SourceShareError,ValueError,TypeError,KeyError):
        return {'status':'INCOMPATIBLE_STORED_CAUSE','source_expression':None}
    if not proofs:return {'status':'SOURCE_EXPRESSION_UNAVAILABLE','source_expression':None}
    kind,proof=proofs[0]
    return {'status':'STORED_EXPRESSION','kind':kind,
            'source_expression':proof['source_expression'],'expression_sha256':proof['expression_sha256']}


def common_cause_comparisons(themes):
    output={}
    for theme in themes:
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
            source.update(cause=_cause(ref),content_scope=ref.get('content_scope','UNSPECIFIED'),
                extraction_method=ref.get('extraction_method'),
                conflicting=ref['event_id'] in theme['conflicting_event_ids'])
            for company in theme['company_links']:
                if company['entity_id'] not in ref['entity_ids'] or ref['event_id'] not in company['event_ids']:continue
                key=(company['entity_id'],find(ref['event_id']))
                row=grouped.setdefault(key,{'entity_id':company['entity_id'],
                    'action_group_id':key[1],'sources':{},'source_names':set()})
                row['source_names'].update(m['source_name'] for m in ref.get('company_mappings',[]) if m['entity_id']==company['entity_id'])
                row['sources'][sha256(_bytes(source)).hexdigest()]=source
        rows=[]
        for key,row in sorted(grouped.items()):
            sources=sorted(row['sources'].values(),key=lambda s:(s['source_available_at'],s['recorded_at'],s['event_id'],s['source_url']))
            rows.append({'entity_id':row['entity_id'],'display_name':' / '.join(sorted(row['source_names'])) or row['entity_id'],
                'action_group_id':row['action_group_id'],'event_ids':sorted({s['event_id'] for s in sources}),
                'sources':sources,'distinct_event_count':len({s['event_id'] for s in sources})})
        output[theme['theme_id']]={'theme_id':theme['theme_id'],
            'theme_snapshot_sha256':sha256(_bytes(theme)).hexdigest(),'decision_at':theme['decision_at'],
            'economic_driver':theme['economic_driver'],'rows':rows,
            'distinct_action_groups':len({r['action_group_id'] for r in rows}),
            'excluded_incompatible_refs':excluded,'verified_real_transaction':False,'verified_real_benefit':False}
    return deepcopy(output)
