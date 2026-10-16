"""Read-only economic-action timelines from one PIT query's validated results."""
from copy import deepcopy
from hashlib import sha256
from .theme_emergence import _bytes,theme_presentation
from .theme_changes import _groups
from .theme_company_identity import ID
from .source_share import SourceShareError,_when


def company_timelines(themes,candidates,context,comparisons,*,as_of,since=None):
    if since is not None and since>as_of:raise SourceShareError('invalid timeline period')
    by_theme={t['theme_id']:t for t in themes};companies={}
    source_fields=('event_id','source_url','evidence_sha256','recorded_at','source_available_at','action','phase','source_binding')
    for c in candidates:
        theme=by_theme.get(c['theme_id']);view=context.get(c['candidate_id'])
        if not theme or not view or view['status']!='READY':continue
        snapshot=sha256(_bytes(theme)).hexdigest()
        if (c['theme_snapshot_sha256']!=snapshot or c['decision_at']!=theme['decision_at']
                or any(view[k]!=c[k] for k in ('theme_id','entity_id','theme_snapshot_sha256','decision_at'))
                or _when(theme['decision_at'],'snapshot decision')>as_of):continue
        identity=c.get('identity_context',{})
        identified=c['entity_id'] if ID.fullmatch(c['entity_id']) else c.get('resolved_entity_id') if identity.get('status')=='MATCHED' and identity.get('decision_at') and _when(identity['decision_at'],'identity decision')<=as_of else None
        if identified and not ID.fullmatch(identified):identified=None
        # Unresolved names remain separate candidate contexts across themes.
        key=identified or 'UNRESOLVED:'+c['candidate_id']
        name=c.get('official_name_context',{})
        usable_name=(name.get('status')=='MATCHED' and name['proof']['entity_id']==c['entity_id']
            and _when(name['decision_at'],'name decision')<=as_of and _when(name['proof']['available_at'],'name available')<=as_of)
        display=name['proof']['issuer_name'] if usable_name else c['display_name']
        company=companies.setdefault(key,{'company_key':key,'entity_id':identified or c['entity_id'],
            'identity_status':'IDENTIFIED' if identified else 'SOURCE_NAME_ONLY','display_names':set(),
            'candidate_ids':set(),'entries':{}})
        company['display_names'].add(display);company['candidate_ids'].add(c['candidate_id'])
        find,_,_=_groups(None,theme)
        active=set(theme['event_ids'])-set(theme['invalidated_event_ids'])
        comparison=comparisons.get(theme['theme_id'],{})
        usable=comparison.get('theme_snapshot_sha256')==snapshot and comparison.get('decision_at')==theme['decision_at']
        own=[s for row in comparison.get('rows',[]) if usable and row['entity_id']==c['entity_id'] for s in row['sources']]
        for source in view['sources']:
            if source['event_id'] not in active or source['event_id'] not in c['event_ids']:continue
            observed=_when(source['recorded_at'],'source recorded')
            related=source['company_participation']=='SUPPLY_CHAIN_CONTEXT'
            if related:
                if not source['impact_paths']:continue
                observed=max(observed,min(_when(p['linked_at'],'relationship linked') for p in source['impact_paths']))
            if observed>as_of or _when(source['source_available_at'],'source available')>as_of:continue
            if any(_when(p['linked_at'],'relationship linked')>as_of or _when(p['source_available_at'],'relationship available')>as_of for p in source['impact_paths']):continue
            exact=[s for s in own if all(s.get(k)==source.get(k) for k in source_fields)]
            cause=deepcopy(exact[0]['cause']) if exact and all(s['cause']==exact[0]['cause'] for s in exact) else {'status':'SOURCE_EXPRESSION_UNAVAILABLE','source_expression':None}
            entry={**deepcopy(source),'observed_at':observed.isoformat(),'candidate_id':c['candidate_id'],
                'theme_id':theme['theme_id'],'theme_name':theme_presentation(theme)['name'],
                'theme_snapshot_sha256':snapshot,'decision_at':theme['decision_at'],
                'economic_driver':theme['economic_driver'],'cause':cause,'action_group_id':find(source['event_id']),
                'current_activity':'ACTIVE','counterevidence':[],
                'identity_available_at':identity['decision_at'] if identified and not ID.fullmatch(c['entity_id']) else None}
            company['entries'][sha256(_bytes(entry)).hexdigest()]=entry
    result=[]
    for key,company in sorted(companies.items()):
        entries=sorted(company.pop('entries').values(),key=lambda s:(_when(s['observed_at'],'observed'),_when(s['source_available_at'],'source'),s['event_id'],s['source_url']))
        seen={};actor_groups=set();new_groups=set();related_groups=set()
        for e in entries:
            group=e['action_group_id'];prior=seen.setdefault(group,[])
            related=e['company_participation']=='SUPPLY_CHAIN_CONTEXT'
            if related:
                kind=('RELATION_CONTEXT_ADDED' if not prior else 'SOURCE_REPORTED_FOLLOWUP' if e['event_id'] not in {p['event_id'] for p in prior}
                    else 'EVENT_STAGE_UPDATE' if (e['action'],e['phase']) not in {(p['action'],p['phase']) for p in prior} else 'ADDITIONAL_SOURCE')
            elif not any(p['company_participation']=='SOURCE_EVENT_ACTOR' for p in prior):
                kind='ECONOMIC_ACTION_FIRST_OBSERVED';actor_groups.add(group)
                if since is None or _when(e['observed_at'],'observed')>=since:new_groups.add(group)
            elif e['event_id'] not in {p['event_id'] for p in prior}:kind='SOURCE_REPORTED_FOLLOWUP'
            elif (e['action'],e['phase']) not in {(p['action'],p['phase']) for p in prior}:kind='EVENT_STAGE_UPDATE'
            else:kind='ADDITIONAL_SOURCE'
            if related:related_groups.add(group)
            e['change_kind']=kind;e['in_period']=since is None or _when(e['observed_at'],'observed')>=since
            prior.append(e)
        company.update(display_names=sorted(company['display_names']),candidate_ids=sorted(company['candidate_ids']),
            entries=entries,distinct_economic_actions=len(actor_groups),new_actions_in_period=len(new_groups),
            related_action_contexts=len(related_groups-actor_groups),verified_real_transaction=False,verified_real_benefit=False)
        if entries:result.append(company)
    return {'as_of':as_of.isoformat(),'since':since.isoformat() if since else None,'status':'READY','companies':result}


def select_timelines(timeline,matches,query):
    result=deepcopy(timeline)
    if not query.strip():return result
    direct={cid for cid,v in matches.items() if v['match_kind']=='DIRECT_COMPANY'}
    result['companies']=[c for c in result['companies'] if direct.intersection(c['candidate_ids'])]
    from .company_search import search_term
    entities={v['entity_id'] for cid,v in matches.items() if cid in direct}
    if 'counterevidence_unresolved' in result:
        result['counterevidence_unresolved']=[e for e in result['counterevidence_unresolved'] if entities.intersection(e['entity_ids']) or any(search_term(query)==search_term(x) for x in e['entity_ids'])]
    if not result['companies']:
        if result.get('counterevidence_unresolved'):result['status']='TARGET_UNRESOLVED';return result
        result['status']='AMBIGUOUS_NAME' if any(v['match_kind']=='AMBIGUOUS_NAME' for v in matches.values()) else 'NO_EXACT_COMPANY_MATCH'
    return result
