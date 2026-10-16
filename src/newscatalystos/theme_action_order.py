"""Read-only discovery ordering over one validated PIT period comparison."""
from copy import deepcopy
from hashlib import sha256
from .theme_emergence import _bytes
from .source_share import _when,SourceShareError


def order_theme_actions(themes,changes,comparisons,*,since,as_of,mode='latest'):
    if mode not in {'latest','actions'}:raise ValueError('invalid theme sort')
    since=_when(since.isoformat(),'period start');as_of=_when(as_of.isoformat(),'period end')
    entries={}
    bounded=(changes is not None and changes.get('since')==since.isoformat()
             and changes.get('as_of')==as_of.isoformat())
    by_theme={r['theme_id']:r for r in changes['ThemeChanges']} if bounded else {}
    for theme in themes:
        tid=theme['theme_id'];digest=sha256(_bytes(theme)).hexdigest()
        entry={'status':'UNAVAILABLE','reason':'PERIOD_COMPARISON_UNAVAILABLE',
               'theme_snapshot_sha256':digest,'decision_at':theme['decision_at'],
               'independent_actions_added':None,'independent_actions_removed':None,
               'new_event_participant_count':None,'action_group_ids':[],'new_participant_entity_ids':[]}
        try:
            change=by_theme.get(tid);comparison=comparisons.get(tid)
            if change is not None:
                entry['reason']='SELECTED_SNAPSHOT_MISMATCH'
                if (change['after']['snapshot_sha256']==digest and change['after']['decision_at']==theme['decision_at']
                    and comparison is not None and comparison['theme_snapshot_sha256']==digest
                    and comparison['decision_at']==theme['decision_at'] and comparison['theme_id']==tid
                    and _when(theme['decision_at'],'decision')<=as_of):
                    counts={k:change['events'][k] for k in ('independent_actions_added','independent_actions_removed')}
                    counts['new_event_participant_count']=change['companies']['new_event_participant_count']
                    if any(type(v) is not int or v<0 for v in counts.values()):raise ValueError('invalid period count')
                    groups=sorted({r['action_group_id'] for r in change['events']['added'] if r['kind']=='NEW_ECONOMIC_EVENT'})
                    entities=sorted({r['entity_id'] for r in change['companies']['added'] if r['kind']=='NEW_EVENT_PARTICIPANT'})
                    if len(groups)!=counts['independent_actions_added'] or len(entities)!=counts['new_event_participant_count']:
                        raise ValueError('inconsistent period evidence')
                    entry.update(status='READY',reason=None,**counts,action_group_ids=groups,new_participant_entity_ids=entities)
        except (SourceShareError,ValueError,KeyError,TypeError):
            entry['reason']='PERIOD_EVIDENCE_UNAVAILABLE'
        entries[tid]=entry
    # Keep the established newest-first order for the default mode and ties.
    ordered=sorted(themes,key=lambda t:(_when(t['decision_at'],'decision'),t['theme_id']),reverse=True)
    if mode=='actions':
        ordered.sort(key=lambda t:(entries[t['theme_id']]['status']=='READY',
            entries[t['theme_id']]['independent_actions_added'] or 0,
            entries[t['theme_id']]['new_event_participant_count'] or 0),reverse=True)
    ready=sum(e['status']=='READY' for e in entries.values())
    return deepcopy(ordered),{'mode':mode,'status':('READY' if ready==len(entries) else 'PARTIAL' if ready else 'UNAVAILABLE'),
        'since':since.isoformat(),'as_of':as_of.isoformat(),
        'criteria':(['PERIOD_EVIDENCE_AVAILABLE_DESC','INDEPENDENT_ACTIONS_ADDED_DESC','NEW_EVENT_PARTICIPANTS_DESC'] if mode=='actions' else [])
                   +['DECISION_AT_DESC','THEME_ID_DESC'],
        'entries':entries,'verified_real_benefit':False,'verified_market_leader':False}
