"""Read-only period expansion and retained context for shared-end-use hypotheses."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json,sqlite3
from .theme_emergence import _bytes
from .theme_changes import _groups
from .standard_delivery import build_theme_bundle
from .theme_company_identity import resolve_candidates
from .common_cause_comparison import common_cause_comparisons
from .cross_product_demand import cross_product_demand
from .company_search import company_search_context,match_company_search
from .economic_changes import normalized
from .source_share import SourceShareError,_when


def _candidates(themes,at,now,identity_root):
    cs=json.loads(build_theme_bundle(themes,decision_at=at,now=now,include_company_candidates=True))['CompanyCandidates']
    return resolve_candidates(cs,identity_root,as_of=at,now=now)[0] if identity_root else cs


def period_cross_product(store,selected,current,*,since,as_of,now,query='',identity_root=None):
    result=deepcopy(current)
    if since is None:result['period_status']='PERIOD_NOT_SPECIFIED';return result
    since=_when(since.isoformat(),'period start');as_of=_when(as_of.isoformat(),'period end')
    if since>as_of:result['period_status']='NOT_STARTED';return result
    try:
        versions=store.period_versions(since=since,as_of=as_of,now=now)
        # Validate the stored payloads, not an inferred/replayed observation stream.
        for rows in versions.values():
            for t in rows:build_theme_bundle([t],decision_at=as_of,now=now)
        after=[rows[-1] for rows in versions.values()]
        before=[rows[0] for rows in versions.values() if _when(rows[0]['decision_at'],'baseline')<since]
        by_after={t['theme_id']:t for t in after};by_before={t['theme_id']:t for t in before}
        if any(t['theme_id'] not in by_after or _bytes(t)!=_bytes(by_after[t['theme_id']]) for t in selected):
            raise SourceShareError('selected period snapshot mismatch')
        cutoff=since-timedelta(microseconds=1)
        cs=_candidates(after,as_of,now,identity_root);prior_cs=_candidates(before,cutoff,now,identity_root)
        end=cross_product_demand(after,cs,common_cause_comparisons(after,cs),as_of=as_of,since=since,_min_products=1)
        start=cross_product_demand(before,prior_cs,common_cause_comparisons(before,prior_cs),as_of=cutoff,_min_products=1)
        def direction_key(g):return (g['group_id'] if g.get('economic_driver')=='POLICY_ENABLEMENT' else g['destination_key'],g.get('economic_driver','DEMAND_EXPANSION'))
        ends={direction_key(g):g for g in end['groups']};starts={direction_key(g):g for g in start['groups']}
        selected_ids={t['theme_id'] for t in selected}
        direct=set();search_keys={}
        for ts,candidates in [(after,cs),(before,prior_cs)]:
            context=company_search_context(ts,candidates)
            for cid,entry in context.items():search_keys.setdefault(cid,set()).update(k['value'] for k in entry['keys'])
            if query.strip():direct.update(cid for cid,v in match_company_search(context,query).items() if v['match_kind']=='DIRECT_COMPANY')
        missing={t['theme_id'] for t in after if t['theme_id'] not in by_before and _when(t['first_detected_at'],'first observation')<since}
        unavailable=set(start['unavailable_theme_ids'])|set(end['unavailable_theme_ids'])
        output=[]
        def summarize(group):
            products=(group or {}).get('products',[]);actions=set()
            for product in products:
                find,_,_=_groups(by_before.get(product['theme_id']),by_after.get(product['theme_id'],by_before.get(product['theme_id'])))
                for a in product['actions']:
                    keys={find(s['event_id']) for s in a['sources']};actions.update(keys)
                    a['period_action_group_ids']=sorted(keys)
            return {'products':sorted({p['product'] for p in products}),'action_group_ids':sorted(actions),
                'theme_snapshots':[{'theme_id':p['theme_id'],'sha256':p['theme_snapshot_sha256'],'decision_at':p['decision_at']} for p in products]}
        for key in sorted(set(ends)|set(starts)):
            old=deepcopy(starts.get(key));fresh=deepcopy(ends.get(key))
            left=summarize(old);right=summarize(fresh)
            all_products=(fresh or {}).get('products',[])+(old or {}).get('products',[])
            tids={p['theme_id'] for p in all_products}
            if not tids.intersection(selected_ids) or max(len(left['products']),len(right['products']))<2:continue
            group=fresh or {**old,'products':[],'distinct_action_groups':0,'identified_company_count':0,'unresolved_company_contexts':0}
            if not fresh and group.get('economic_driver')=='POLICY_ENABLEMENT':group['source_actor_name_count']=0
            is_current=len(right['products'])>=2 and len(right['action_group_ids'])>=2
            group['status']='COMMON_CAUSE_HYPOTHESIS' if is_current else 'PERIOD_CONTEXT_ONLY'
            for product in group['products']:
                product['context_kind']='SELECTED_THEME' if product['theme_id'] in selected_ids else 'EXISTING_PRODUCT_CONTEXT'
            removed=[];removed_action_contexts=[]
            gone=set(left['action_group_ids'])-set(right['action_group_ids'])
            for product in (old or {}).get('products',[]):
                removed_product=product['product'] not in right['products']
                if not removed_product:
                    product['actions']=[a for a in product['actions'] if gone.intersection(a['period_action_group_ids'])]
                    if not product['actions']:continue
                product['context_kind']='HISTORICAL_REMOVED_PRODUCT' if removed_product else 'HISTORICAL_REMOVED_ACTION'
                latest=by_after.get(product['theme_id'])
                if latest:
                    product['current_theme_status']=latest['status']
                    product['current_snapshot']={'sha256':sha256(_bytes(latest)).hexdigest(),'decision_at':latest['decision_at']}
                    product['counterevidence']=[deepcopy(r) for r in latest['source_refs'] if r['polarity']!='SUPPORT']
                for a in product['actions']:
                    for source in a['sources']:source['in_period']=False
                (removed if removed_product else removed_action_contexts).append(product)
            group['removed_products']=removed
            group['removed_action_contexts']=removed_action_contexts
            # Existing named decisions remain one economic action when execution
            # becomes eligible here; reuse the stored stage links and _groups roots.
            stage_contexts=[]
            for product in ((fresh or {}).get('products',[]) if group.get('economic_driver') in {'DEMAND_RECOVERY','POLICY_ENABLEMENT'} else []):
                prior=by_before.get(product['theme_id']);latest=by_after[product['theme_id']]
                if prior is None:continue
                executions={s['event_id'] for a in product['actions'] for s in a['sources'] if s['action']=='INVESTMENT_EXECUTION'}
                find,known,_=_groups(prior,latest)
                for link in latest.get('investment_stage_links',[]):
                    if (link['execution_event_id'] not in executions or link['execution_event_id'] in prior['event_ids']
                        or link['decision_event_id'] not in prior['event_ids'] or find(link['execution_event_id']) not in known):continue
                    stage_contexts.append({'theme_id':product['theme_id'],'action_group_id':find(link['execution_event_id']),
                        'before_snapshot':{'sha256':sha256(_bytes(prior)).hexdigest(),'decision_at':prior['decision_at']},
                        'after_snapshot':{'sha256':sha256(_bytes(latest)).hexdigest(),'decision_at':latest['decision_at']},
                        'stored_stage_link':deepcopy(link)})
            service_contexts=[]
            for product in (fresh or {}).get('products',[]):
                growth_sources={s['event_id'] for a in product['actions'] for s in a['sources'] if 'growth_parallel_action' in s}
                if group.get('economic_driver') not in {'DEMAND_RECOVERY','POLICY_ENABLEMENT'} and not growth_sources:continue
                prior=by_before.get(product['theme_id']);latest=by_after[product['theme_id']]
                if prior is None:continue
                service_starts={s['event_id'] for a in product['actions'] for s in a['sources'] if s['action']=='BUSINESS_START' and (not growth_sources or s['event_id'] in growth_sources)}
                find,known,_=_groups(prior,latest)
                def service_context(kind,event,old_refs,new_refs,link=None):
                    return {'kind':kind,'theme_id':product['theme_id'],'action_group_id':find(event),
                        'before_snapshot':{'sha256':sha256(_bytes(prior)).hexdigest(),'decision_at':prior['decision_at']},
                        'after_snapshot':{'sha256':sha256(_bytes(latest)).hexdigest(),'decision_at':latest['decision_at']},
                        'sources':deepcopy(old_refs+new_refs),
                        **({'stored_followup':deepcopy(link)} if link else {})}
                for link in latest.get('event_followups',[]):
                    event=link['realization_event_id']
                    if (event not in service_starts or event in prior['event_ids'] or link['planned_event_id'] not in prior['event_ids']
                        or find(event) not in known):continue
                    old_refs=[r for r in prior['source_refs'] if r['polarity']=='SUPPORT' and r['event_id']==link['planned_event_id']
                        and r['phase']=='PLANNED' and r['evidence_sha256']==link['evidence_sha256'][0]]
                    new_refs=[r for r in latest['source_refs'] if r['polarity']=='SUPPORT' and r['event_id']==event
                        and r['phase']=='SOURCE_REPORTED' and r['evidence_sha256']==link['evidence_sha256'][1]]
                    if old_refs and new_refs:service_contexts.append(service_context('STORED_SERVICE_FOLLOWUP',event,old_refs,new_refs,link))
                # An already-known event becoming eligible is a metadata/stage
                # update, never an invented two-event realization link.
                for event in sorted(service_starts.intersection(prior['event_ids'])):
                    if find(event) in left['action_group_ids']:continue
                    old_refs=[r for r in prior['source_refs'] if r['polarity']=='SUPPORT' and r['event_id']==event]
                    new_refs=[r for r in latest['source_refs'] if r['polarity']=='SUPPORT' and r['event_id']==event and r['phase']=='SOURCE_REPORTED']
                    if old_refs and new_refs:service_contexts.append(service_context('EXISTING_EVENT_UPDATE',event,old_refs,new_refs))
            policy_contexts=[]
            for product in ((fresh or {}).get('products',[]) if group.get('economic_driver')=='POLICY_ENABLEMENT' else []):
                prior=by_before.get(product['theme_id']);latest=by_after[product['theme_id']]
                if prior is None:continue
                find,known,_=_groups(prior,latest)
                for event in sorted({s['event_id'] for a in product['actions'] for s in a['sources']}):
                    if find(event) not in known or find(event) in left['action_group_ids'] or find(event) in {c['action_group_id'] for c in service_contexts}:continue
                    old_refs=[r for r in prior['source_refs'] if r['polarity']=='SUPPORT' and r['event_id']==event]
                    new_refs=[r for r in latest['source_refs'] if r['polarity']=='SUPPORT' and r['event_id']==event and r['phase']=='SOURCE_REPORTED']
                    if old_refs and new_refs:policy_contexts.append({'theme_id':product['theme_id'],'action_group_id':find(event),
                        'before_snapshot':{'sha256':sha256(_bytes(prior)).hexdigest(),'decision_at':prior['decision_at']},
                        'after_snapshot':{'sha256':sha256(_bytes(latest)).hexdigest(),'decision_at':latest['decision_at']},
                        'sources':deepcopy(old_refs+new_refs)})
            known_stage_groups={c['action_group_id'] for c in stage_contexts+service_contexts+policy_contexts}
            change={'status':'READY','baseline':'LATEST_STRICTLY_BEFORE_SINCE','since':since.isoformat(),'as_of':as_of.isoformat(),
                'before':left,'after':right,'is_current_candidate':is_current,
                'formed_in_period':len(left['products'])<2 and is_current,
                'new_products':sorted(set(right['products'])-set(left['products'])),
                'removed_product_codes':sorted(set(left['products'])-set(right['products'])),
                'new_action_group_ids':sorted(set(right['action_group_ids'])-set(left['action_group_ids'])-known_stage_groups),
                'removed_action_group_ids':sorted(set(left['action_group_ids'])-set(right['action_group_ids']))}
            if tids.intersection(missing|unavailable):
                change={'status':'UNAVAILABLE','reason':'BASELINE_OR_PRODUCT_EVIDENCE_UNAVAILABLE','is_current_candidate':is_current}
            elif not left['products']:change['baseline']='NO_PRIOR_RECORDED_SCOPE'
            if stage_contexts and change['status']=='READY':
                change['investment_stage_contexts']=sorted(stage_contexts,key=lambda c:(c['theme_id'],c['action_group_id']))
                if not left['products']:change['baseline']='RECORDED_INVESTMENT_DECISION_CONTEXT'
            if service_contexts and change['status']=='READY':
                change['service_stage_contexts']=sorted(service_contexts,key=lambda c:(c['theme_id'],c['action_group_id']))
                if not left['products']:
                    change['baseline']=('RECORDED_ACTION_STAGE_CONTEXT' if stage_contexts else
                        'RECORDED_SERVICE_EVENT_CONTEXT' if any(c['kind']=='EXISTING_EVENT_UPDATE' for c in service_contexts) else 'RECORDED_SERVICE_PLAN_CONTEXT')
            if policy_contexts and change['status']=='READY':
                change['existing_policy_action_contexts']=sorted(policy_contexts,key=lambda c:(c['theme_id'],c['action_group_id']))
                if not left['products']:change['baseline']='RECORDED_POLICY_EVENT_CONTEXT'
            group['period_change']=change
            group['search_keys']=sorted({k for p in group['products']+removed+removed_action_contexts for a in p['actions'] for k in search_keys.get(a['candidate_id'],set())})
            exact=any(a['candidate_id'] in direct for p in group['products']+removed+removed_action_contexts for a in p['actions'])
            if query.strip() and not exact and normalized(query) not in normalized(_bytes(group).decode()):continue
            group['search_match']='DIRECT_COMPANY_CONTEXT' if exact else 'TEXT_CONTEXT' if query.strip() else 'UNFILTERED'
            output.append(group)
        result.update(groups=output,period_status='PARTIAL' if any(g['period_change']['status']!='READY' for g in output) else 'READY',
            unavailable_theme_ids=sorted(unavailable))
        return result
    except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
        result['period_status']='UNAVAILABLE'
        for g in result['groups']:g['period_change']={'status':'UNAVAILABLE','reason':'STORED_PERIOD_UNAVAILABLE'}
        return result
