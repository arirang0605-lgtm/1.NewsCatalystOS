"""Pinned semiconductor relationship context for theme events.

Only an exact source event, document version and identified counterparty join.
A relationship reported in that document does not prove its economic effect.
No article text, company-name guessing, collection or external project writes.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from .evidence_archive import _read_once
from .reviewed_beneficiary_delivery import (
    consume_reviewed_beneficiary_graph, _validate_reviewed_graph, MAX_GRAPH_BYTES,
)
from .source_share import SourceShareError, _must_sha, _when


def read_evidence(folder, out_root, expected_sha256, *, graph_version, now):
    consumed=consume_reviewed_beneficiary_graph(folder,out_root,expected_sha256,
                                               graph_version=graph_version,now=now)
    raw=_read_once(Path(folder)/'beneficiary_graph.json',MAX_GRAPH_BYTES)
    evidence={'payload_sha256':consumed['payload_sha256'],'graph_version':graph_version,
              'graph_payload':raw.decode('utf-8'),'available_at':consumed['consumer_checked_at']}
    validate_evidence(evidence,now)
    return evidence


def validate_evidence(evidence, at):
    if (not isinstance(evidence,dict) or set(evidence)!=
            {'payload_sha256','graph_version','graph_payload','available_at'}
            or evidence['graph_version'] not in {'v1','v2'}
            or not isinstance(evidence['graph_payload'],str)):
        raise SourceShareError('invalid theme supply evidence')
    raw=evidence['graph_payload'].encode('utf-8')
    if len(raw)>MAX_GRAPH_BYTES or sha256(raw).hexdigest()!=_must_sha(evidence['payload_sha256'],'graph pin'):
        raise SourceShareError('theme supply graph SHA mismatch')
    available=_when(evidence['available_at'],'relationship available')
    if available>at:raise SourceShareError('future theme supply evidence')
    graph=json.loads(raw)
    _validate_reviewed_graph(graph,available,graph_version=evidence['graph_version'])
    return graph


def _party(edge,role):
    return edge[role+'_namespace']+':'+edge[role+'_id']


def _matching_refs(theme,graph):
    edge=graph['edges'][0]
    ids={_party(edge,'supplier'),_party(edge,'customer')}
    binding={'source_event_sha256':graph['event_sha256'],'document_sha256':edge['document_sha256']}
    return [r for r in theme['source_refs']
            if r['event_id'] in theme['event_ids'] and r['polarity']=='SUPPORT'
            and r.get('source_binding')==binding
            and 'SEMICONDUCTOR' in r.get('industry_tags',[])
            and ids.intersection(r.get('entity_ids',[]))]


def enrich_theme(theme,evidence):
    """Recompute links from active source events; never inflate event/breadth scores."""
    from .theme_emergence import RELATION_SCHEMA
    at=_when(theme['decision_at'],'theme decision')
    linked=[]
    by_entity={x['entity_id']:x for x in theme['company_links']}
    for item in evidence:
        graph=validate_evidence(item,at)
        refs=_matching_refs(theme,graph)
        if not refs:continue
        linked.append(item)
        edge=graph['edges'][0]
        event_ids=sorted({r['event_id'] for r in refs})
        for role in ('supplier','customer'):
            entity=_party(edge,role)
            company=by_entity.setdefault(entity,{'entity_id':entity,'relation_kind':'SOURCE_BACKED_CONTEXT',
                'evidence_level':'SOURCE_REPORTED','event_ids':[],'revenue_contribution':None})
            company['event_ids']=sorted(set(company['event_ids'])|set(event_ids))
            company.setdefault('supply_chain_links',[]).append({
                'graph_sha256':item['payload_sha256'],'relation_sha256':edge['relation_sha256'],
                'event_ids':event_ids,'role':role,'counterparty_id':_party(edge,'customer' if role=='supplier' else 'supplier'),
                'relation_kind':edge['relation_kind'],'product_stage':edge['product_stage'],
                'impact_category':edge['candidate_category'] if role=='supplier' else 'EFFECT_DIRECTION_UNKNOWN',
                'impact_evidence_level':'IMPACT_HYPOTHESIS_NOT_VERIFIED',
                'link_scope':'SAME_DOCUMENT_AND_COMPANY',
                'source_urls':sorted({r['source_url'] for r in refs}),
                'source_available_at':edge['source_available_at'],
                'linked_at':max(_when(item['available_at'],'graph available'),
                    min(_when(r['recorded_at'],'event recorded') for r in refs)).isoformat(),
                'conflicting_event_ids':sorted(set(event_ids)&set(theme['conflicting_event_ids'])),
                'verified_real_transaction':False,'verified_real_benefit':False,
                'revenue_contribution':None})
    if linked:
        theme['schema_version']=RELATION_SCHEMA
        theme['supply_chain_evidence']=linked
        theme['company_links']=[by_entity[k] for k in sorted(by_entity)]
    return theme


def validate_theme_relations(theme, at):
    """Rebuild the exported projection from its pinned metadata and source joins."""
    from .theme_emergence import SCHEMA, RELATION_SCHEMA
    if theme['schema_version']==SCHEMA:
        if theme.get('supply_chain_evidence') or any('supply_chain_links' in x for x in theme['company_links']):
            raise SourceShareError('relationship context requires theme v2')
        return
    evidence=theme.get('supply_chain_evidence')
    if (theme['schema_version']!=RELATION_SCHEMA or not isinstance(evidence,list)
            or not 1<=len(evidence)<=1000):
        raise SourceShareError('invalid theme relationship version')
    for item in evidence:validate_evidence(item,at)
    rebuilt=deepcopy(theme)
    rebuilt['schema_version']=SCHEMA
    rebuilt.pop('supply_chain_evidence')
    rebuilt['company_links']=[{'entity_id':e,'relation_kind':'THEMATIC_ONLY','evidence_level':'INFERRED',
        'event_ids':sorted({r['event_id'] for r in theme['source_refs'] if r['event_id'] in theme['event_ids']
                           and r['polarity']=='SUPPORT' and e in r.get('entity_ids',[])}),
        'revenue_contribution':None} for e in theme['entity_ids']]
    enrich_theme(rebuilt,evidence)
    if (rebuilt['company_links']!=theme['company_links']
            or rebuilt.get('supply_chain_evidence')!=evidence):
        raise SourceShareError('unsubstantiated theme supply relationship')
