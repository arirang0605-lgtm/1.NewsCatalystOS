"""Attach explicit counterevidence to historical observations; no state writes."""
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3
from .source_share import _when,SourceShareError
from .theme_emergence import _bytes
from .standard_delivery import build_theme_bundle
from .theme_company_identity import resolve_candidates,ID
from .company_search import company_search_context
from .common_cause_comparison import common_cause_comparisons
from .company_timeline import company_timelines

BINDING=('event_id','source_url','evidence_sha256','recorded_at','source_binding')



def _unresolved(selected,report,target,reason):
    return {**{k:deepcopy(report.get(k)) for k in ('event_id','source_url','source_available_at','recorded_at','evidence_sha256','evidence_level','entity_ids','source_binding','polarity')},
        'theme_id':selected['theme_id'],'target_event_id':target,'reason':reason,'status':'TARGET_UNRESOLVED'}



def _relation_paths(prior,entry,report,*,as_of=None):
    if entry['company_participation']!='SUPPLY_CHAIN_CONTEXT' or not entry.get('source_binding'):return []
    cutoff=as_of or _when(report['recorded_at'],'counter recorded')
    actors=set(entry['event_entity_ids'])&set(report['entity_ids'])
    graphs={item['payload_sha256']:(json.loads(item['graph_payload']),item['available_at']) for item in prior.get('supply_chain_evidence',[])
        if sha256(item['graph_payload'].encode()).hexdigest()==item['payload_sha256']}
    matches=[]
    for path in entry['impact_paths']:
        pinned=graphs.get(path['graph_sha256'])
        if not pinned:continue
        graph,available=pinned
        edge=graph['edges'][0]
        role=path['role'];other='customer' if role=='supplier' else 'supplier'
        party=lambda r:edge[r+'_namespace']+':'+edge[r+'_id']
        if (role not in {'supplier','customer'} or path['entity_id']!=entry['entity_id']
                or path['event_id']!=report['supersedes_event_id']
                or path['counterparty_id'] not in actors or not ID.fullmatch(path['counterparty_id'])
                or party(role)!=entry['entity_id'] or party(other)!=path['counterparty_id']
                or path['relation_sha256']!=edge['relation_sha256']
                or path['product_stage']!=edge['product_stage'] or path['relation_kind']!=edge['relation_kind']
                or path['source_available_at']!=edge['source_available_at']
                or _when(available,'graph available')>cutoff
                or _when(path['linked_at'],'relationship linked')<_when(available,'graph available')
                or entry['source_binding']!={'source_event_sha256':graph['event_sha256'],'document_sha256':edge['document_sha256']}
                or entry['source_url'] not in path['source_urls']
                or _when(path['linked_at'],'relationship linked')>cutoff
                or _when(path['source_available_at'],'relationship source')>cutoff):continue
        match=deepcopy(path);match['source_urls']=[entry['source_url']];matches.append(match)
    return matches


def targeted_counterevidence(store,themes,timeline,context,*,as_of,now,since=None,identity_root=None):
    reports=[(t,r) for t in themes for r in t['source_refs'] if r['polarity'] in {'CONTRADICT','RETRACT'}
        and _when(r['recorded_at'],'counter recorded')<=as_of and _when(r['source_available_at'],'counter available')<=as_of]
    if not reports:return timeline,context
    result=deepcopy(timeline);search=deepcopy(context);unresolved=[]
    companies={c['company_key']:c for c in result['companies']}
    earliest=min(_when(t['first_detected_at'],'first theme') for t,_ in reports)
    history_failure=False
    try:history=store.period_versions(since=earliest,as_of=as_of,now=now)
    except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):history={};history_failure=True
    cache={}
    for selected,report in sorted(reports,key=lambda pair:(_when(pair[1]['recorded_at'],'counter recorded'),pair[1]['event_id'])):
        target=report.get('supersedes_event_id')
        reason='TARGET_NOT_SPECIFIED' if not target else 'TARGET_NOT_FOUND'
        supports=[r for r in selected['source_refs'] if r['polarity']=='SUPPORT' and r['event_id']==target
            and _when(r['recorded_at'],'target recorded')<=_when(report['recorded_at'],'counter recorded')]
        prior=None
        if target and supports:
            reason='HISTORICAL_VERSION_UNAVAILABLE' if history_failure else 'TARGET_NOT_AVAILABLE_BEFORE_REPORT'
            prior=next((v for v in reversed(history.get(selected['theme_id'],[]))
                if _when(v['decision_at'],'historical decision')<_when(report['recorded_at'],'counter recorded')
                and target in set(v['event_ids'])-set(v['invalidated_event_ids'])),None)
        linked=False
        if prior:
            pin=sha256(_bytes(prior)).hexdigest()
            if pin not in cache:
                try:
                    cs=json.loads(build_theme_bundle([prior],decision_at=as_of,now=now,include_company_candidates=True))['CompanyCandidates']
                    if identity_root is not None:cs,_=resolve_candidates(cs,identity_root,as_of=as_of,now=now)
                    ctx=company_search_context([prior],cs)
                    past=company_timelines([prior],cs,ctx,common_cause_comparisons([prior],cs),as_of=as_of,since=since)
                    cache[pin]=(past,ctx)
                except (SourceShareError,OSError,ValueError,KeyError,TypeError,sqlite3.Error):
                    unresolved.append(_unresolved(selected,report,target,'HISTORICAL_VERSION_UNAVAILABLE'));continue
            past,ctx=cache[pin]
            reason='COMPANY_BINDING_MISMATCH'
            entries={}
            def add_entry(company,entry,relationship_snapshot,search_context):
                key=sha256(_bytes({k:entry.get(k) for k in ('entity_id','company_participation',*BINDING)})).hexdigest()
                entries[key]=(company,entry,relationship_snapshot,search_context)
            for company in past['companies']:
                for entry in company['entries']:add_entry(company,entry,prior,ctx)
            # A later-known relation is usable only at/after its own PIT availability.
            for company in timeline['companies']:
                for entry in company['entries']:
                    if entry['theme_id']==selected['theme_id'] and entry['company_participation']=='SUPPLY_CHAIN_CONTEXT' and entry['theme_snapshot_sha256']==sha256(_bytes(selected)).hexdigest() and entry['decision_at']==selected['decision_at'] and _when(entry['decision_at'],'relation snapshot')<=as_of:
                        add_entry(company,entry,selected,context)
            for old_company,old_entry,relationship_snapshot,entry_context in entries.values():
                if old_entry['event_id']!=target:continue
                matching=[s for s in supports if all(s.get(k)==old_entry.get(k) for k in BINDING)]
                if not matching:reason='TARGET_SOURCE_VERSION_MISMATCH';continue
                related=old_entry['company_participation']=='SUPPLY_CHAIN_CONTEXT'
                relation_paths=_relation_paths(relationship_snapshot,old_entry,report,as_of=as_of) if related else []
                # Direct actor matching remains separate from relationship context.
                if related:
                    if not relation_paths:continue
                else:
                    if old_entry['entity_id'] not in report['entity_ids']:continue
                    if not ID.fullmatch(old_entry['entity_id']) and (not old_entry.get('source_binding') or old_entry['source_binding']!=report.get('source_binding')):
                        reason='COMPANY_ID_UNRESOLVED';continue
                proof={k:deepcopy(report.get(k)) for k in ('event_id','source_url','source_id','source_available_at','recorded_at',
                    'evidence_sha256','evidence_level','source_binding','extraction_method','polarity','entity_ids')}
                proof.update(target_event_id=target,target_entity_id=old_entry['entity_id'],
                    target_evidence_sha256=old_entry['evidence_sha256'],target_source_binding=deepcopy(old_entry.get('source_binding')),
                    target_snapshot_sha256=pin,selected_snapshot_sha256=sha256(_bytes(selected)).hexdigest(),
                    status='EXPLICIT_EVENT_COMPANY_AND_SOURCE',
                    document_binding_status='PINNED_SEPARATE_SOURCE_DOCUMENTS' if old_entry.get('source_binding') and report.get('source_binding') else 'SOURCE_HASH_ONLY',
                    reason=None if old_entry.get('source_binding') and report.get('source_binding') else 'DOCUMENT_ID_UNAVAILABLE',
                    in_period=since is None or _when(report['recorded_at'],'counter recorded')>=since,
                    verified_transaction_cancellation=False)
                company=companies.get(old_company['company_key'])
                if company is None:
                    company={**deepcopy(old_company),'entries':[],'distinct_economic_actions':0,'new_actions_in_period':0,'related_action_contexts':0}
                    companies[company['company_key']]=company
                company['candidate_ids']=sorted(set(company['candidate_ids'])|set(old_company['candidate_ids']))
                existing=next((e for e in company['entries'] if e['entity_id']==old_entry['entity_id']
                    and e['company_participation']==old_entry['company_participation']
                    and all(e.get(k)==old_entry.get(k) for k in BINDING)),None)
                if existing is None:
                    existing=deepcopy(old_entry);company['entries'].append(existing)
                if related:
                    existing.setdefault('relation_counterevidence',[])
                    for path in relation_paths:
                        relation_proof={**deepcopy(proof),'status':'RELATION_EVENT_CONTEXT',
                            'target_entity_id':path['counterparty_id'],'target_actor_ids':[path['counterparty_id']],
                            'relation_entity_id':old_entry['entity_id'],'relationship':path,
                            'affects_own_action':False,'verified_benefit_loss':False,
                            'relationship_snapshot_sha256':sha256(_bytes(relationship_snapshot)).hexdigest(),
                            'context_observed_at':max(_when(path['linked_at'],'relation linked'),_when(report['recorded_at'],'counter recorded')).isoformat(),
                            'context_in_period':since is None or max(_when(path['linked_at'],'relation linked'),_when(report['recorded_at'],'counter recorded'))>=since}
                        if relation_proof not in existing['relation_counterevidence']:existing['relation_counterevidence'].append(relation_proof)
                    existing['relation_counterevidence_status']='LINKED_CONTEXT'
                    existing['current_activity']='RELATION_EVENT_CONTEXT_EXCLUDED' if target in selected['invalidated_event_ids'] else 'RELATION_EVENT_CONTEXT_CONFLICTING'
                else:
                    existing.setdefault('counterevidence',[])
                    if proof not in existing['counterevidence']:existing['counterevidence'].append(proof)
                    existing['current_activity']='EXCLUDED_BY_STORED_RETRACTION' if target in selected['invalidated_event_ids'] else 'CONFLICTING_ACTIVE'
                for cid in old_company['candidate_ids']:
                    if cid not in entry_context:continue
                    historical=entry_context[cid]
                    if cid not in search:search[cid]=deepcopy(historical)
                    elif search[cid]['entity_id']==historical['entity_id']:
                        search[cid]['keys']=[json.loads(raw) for raw in sorted({_bytes(k) for k in search[cid]['keys']+historical['keys']})]
                linked=True
        if not linked:
            unresolved.append(_unresolved(selected,report,target,reason))
    for company in companies.values():
        company['entries'].sort(key=lambda e:(_when(e['observed_at'],'observed'),_when(e['source_available_at'],'source'),e['event_id'],e['source_url']))
        company['historical_relation_contexts']=len({e['action_group_id'] for e in company['entries'] if e.get('current_activity')=='RELATION_EVENT_CONTEXT_EXCLUDED'})
        company['historical_target_actions']=len({e['action_group_id'] for e in company['entries'] if e.get('current_activity')=='EXCLUDED_BY_STORED_RETRACTION'})
    result['companies']=[companies[k] for k in sorted(companies)]
    result['counterevidence_unresolved']=unresolved
    return result,search
