"""Licensed publisher text -> economic events -> source-scoped company IDs."""
from copy import deepcopy
from hashlib import sha256
import re

from .economic_changes import extract_economic_changes, normalized
from .theme_emergence import economic_observation
from .official_relation_intake import read_publisher_relation_context


def mentions_name(text,name):
    # Whole names only; Korean particles may follow a name. No fuzzy/acronym map.
    return bool(re.search(r'(?<!\w)'+re.escape(normalized(name))+
        r'(?=$|[^\w]|(?:은|는|이|가|을|를|와|과|의|에|에게|에서|으로|로)(?=$|[^\w]))',normalized(text)))


def observations_from_context(context):
    if context.source_url is None:return []  # RSS feed URL is not an article URL.
    body=context.document.decode('utf-8')
    lines={sha256(line.strip().encode()).hexdigest():line.strip() for line in body.splitlines() if line.strip()}
    names={}
    for role in ('supplier','customer'):
        name=getattr(context.review,role+'_name')
        binding=getattr(context,role)
        names.setdefault(normalized(name),[]).append((name,binding))
    result=[]
    for original in extract_economic_changes(body):
        change=deepcopy(original);line=lines[change['source_paragraph_sha256']]
        mappings=[]
        for entries in names.values():
            # Keep ambiguous names unresolved instead of choosing a company.
            if len({(b.id_namespace,b.company_id) for _,b in entries})!=1:continue
            name,binding=entries[0]
            if len(name)>120 or not mentions_name(line,name):continue
            matched=[n for n in change['entity_ids'] if normalized(n)==normalized(name)]
            source_name=matched[0] if len(matched)==1 else name
            if source_name not in change['entity_ids']:change['entity_ids'].append(source_name)
            mappings.append({'source_name':source_name,
                'entity_id':binding.id_namespace+':'+binding.company_id,
                'evidence_sha256':binding.evidence_sha256})
        change['entity_ids']=sorted(set(change['entity_ids']))
        if change['action']=='CONTRACT' and context.edge.relation_kind=='ANNOUNCED_SUPPLY_PLAN':
            change['phase']='PLANNED'
        result.append(economic_observation(change,origin_reference=context.source_url,
            source_url=context.source_url,source_id=context.edge.source_id,
            source_available_at=context.edge.available_at.isoformat(),source_binding={
                'source_event_sha256':context.edge.source_event_sha256,
                'document_sha256':context.edge.document_sha256},company_mappings=mappings))
    return result


def read_publisher_theme_events(*args,**kwargs):
    return observations_from_context(read_publisher_relation_context(*args,**kwargs))
