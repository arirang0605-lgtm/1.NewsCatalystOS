"""Read-only company search attribution for one validated theme query version."""
import json
import unicodedata
from hashlib import sha256
from copy import deepcopy
from .theme_emergence import _bytes
from .source_share import SourceShareError
from .theme_company_identity import ID


def search_term(value):
    # Whole values only. This normalizes typography, never aliases or identities.
    return ' '.join(unicodedata.normalize('NFKC',value).lower().split())


def company_search_context(themes,candidates):
    by_theme={t['theme_id']:t for t in themes};output={};owners={}
    from .common_cause_comparison import common_cause_comparisons
    linked=[t for t in themes if any(c.get('supply_chain_links') for c in t['company_links'])]
    comparisons=common_cause_comparisons(linked,candidates)
    documents={}
    for theme in linked:
        for item in theme['supply_chain_evidence']:
            edge=json.loads(item['graph_payload'])['edges'][0]
            documents[(theme['theme_id'],item['payload_sha256'])]=edge.get('source_document_id')
    for c in candidates:
        t=by_theme.get(c['theme_id'])
        entry={k:c[k] for k in ('theme_id','entity_id','theme_snapshot_sha256','decision_at')}
        entry.update(status='SNAPSHOT_MISMATCH',keys=[],sources=[])
        output[c['candidate_id']]=entry
        if not t or c['theme_snapshot_sha256']!=sha256(_bytes(t)).hexdigest() or c['decision_at']!=t['decision_at']:continue
        entry['status']='READY'
        active=set(t['event_ids'])-set(t['invalidated_event_ids'])
        refs=[r for r in t['source_refs'] if r['event_id'] in active and r['polarity']=='SUPPORT' and c['entity_id'] in r['entity_ids']]
        names={c['display_name'],c['entity_id']}
        for r in refs:
            names.update(m['source_name'] for m in r.get('company_mappings',[]) if m['entity_id']==c['entity_id'])
        identity=c.get('identity_context',{})
        official=c.get('resolved_entity_id') if identity.get('status')=='MATCHED' else None
        # Candidate IDs already resolved in the snapshot need no later receipt.
        if ID.fullmatch(c['entity_id']):official=c['entity_id']
        if official:
            names.add(official)
            for m in identity.get('matches',[]):
                if m['entity_id']==official:names.update((m['source_name'],m['issuer_name']))
        directory=c.get('official_name_context',{})
        directory_name=None
        if directory.get('status')=='MATCHED' and directory['proof']['entity_id']==c['entity_id']:
            directory_name=directory['proof']['issuer_name'];names.add(directory_name)
        owner=official or 'SOURCE_NAME:'+search_term(c['entity_id'])
        for name in sorted(names):
            key=search_term(name)
            if not key:continue
            is_id=bool(ID.fullmatch(name)) and name==official
            entry['keys'].append({'value':key,'kind':'OFFICIAL_ID' if is_id else 'OFFICIAL_DIRECTORY_NAME' if name==directory_name else 'EXACT_NAME',
                                  'ambiguous':not is_id and (identity.get('status')=='AMBIGUOUS' or (name==directory_name and directory.get('name_ambiguous',False)))})
            owners.setdefault(key,set()).add(owner)
        entry['identity_status']='OFFICIAL_ID_AVAILABLE' if official else 'SOURCE_NAME_ONLY'
        fields=('event_id','action','phase','source_url','evidence_sha256','source_available_at','recorded_at')
        if t['theme_id'] in comparisons:
            sources=[s for row in comparisons[t['theme_id']]['rows'] if row['entity_id']==c['entity_id'] for s in row['sources']]
        else:
            sources=[{**r,'company_participation':'SOURCE_EVENT_ACTOR','event_entity_ids':r['entity_ids'],'impact_paths':[]} for r in refs]
        entry['sources']=[]
        for source in sources:
            record={k:source[k] for k in fields}
            if 'policy_capacity_action' in source:record['policy_capacity_action']=deepcopy(source['policy_capacity_action'])
            if 'policy_contract_action' in source:record['policy_contract_action']=deepcopy(source['policy_contract_action'])
            if 'policy_investment_action' in source:record['policy_investment_action']=deepcopy(source['policy_investment_action'])
            if 'policy_parallel_action' in source:record['policy_parallel_action']=deepcopy(source['policy_parallel_action'])
            if 'recovery_parallel_action' in source:
                record['recovery_parallel_action']=deepcopy(source['recovery_parallel_action'])
                record.update({k:deepcopy(source[k]) for k in ('investment_project','investment_event_key') if k in source})
            if source.get('economic_driver')=='POLICY_ENABLEMENT' and source['action']=='BUSINESS_START':
                record.update({k:deepcopy(source[k]) for k in ('service_name','service_event_key') if k in source})
            record.update(entity_id=c['entity_id'],company_participation=source['company_participation'],
                event_entity_ids=list(source['event_entity_ids']),evidence_level=source['evidence_level'],
                extraction_method=source.get('extraction_method'),source_binding=deepcopy(source.get('source_binding')),
                impact_paths=[])
            for path in source['impact_paths']:
                binding=source['source_binding']
                record['impact_paths'].append({**deepcopy(path),'document_id':documents.get((t['theme_id'],path['graph_sha256'])),
                    'document_sha256':binding['document_sha256'],'source_event_sha256':binding['source_event_sha256']})
            entry['sources'].append(record)
        entry['sources']=[json.loads(raw) for raw in sorted({_bytes(r) for r in entry['sources']})]
        entry['source_status']='AVAILABLE' if entry['sources'] else 'NOT_AVAILABLE_AS_OF'
    for entry in output.values():
        for key in entry['keys']:
            key['ambiguous']=key['ambiguous'] or (key['kind']!='OFFICIAL_ID' and len(owners[key['value']])>1)
    return output


def match_company_search(context,query):
    if not isinstance(query,str) or len(query)>200:raise SourceShareError('invalid company search query')
    term=search_term(query);direct=set();ambiguous=set()
    for cid,entry in context.items():
        keys=[k for k in entry['keys'] if k['value']==term] if term else []
        if any(not k['ambiguous'] for k in keys):direct.add(cid)
        elif keys:ambiguous.add(cid)
    themes={context[cid]['theme_id'] for cid in direct|ambiguous}
    return {cid:{**entry,'match_kind':('UNFILTERED' if not term else 'DIRECT_COMPANY' if cid in direct
            else 'AMBIGUOUS_NAME' if cid in ambiguous else 'RELATED_THEME' if entry['theme_id'] in themes
            else 'TEXT_CONTEXT')} for cid,entry in context.items()}
