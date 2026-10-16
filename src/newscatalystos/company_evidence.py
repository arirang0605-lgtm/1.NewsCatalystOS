"""Read exact stored company-event evidence; no collection, analysis or DB writes.

Report filename hashes provide local integrity, not independent certification.
Original source bytes and current rights are checked separately before disclosure.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from .economic_changes import company_clauses, extract_economic_changes, mentions_name, explicit_topic_aliases
from .evidence_archive import _read_once, read_archived_evidence
from .feed_analysis_delivery import MAX_REPORT_BYTES, _validate_report
from .feed_recovery import read_retry_checkpoint
from .motir_article_binding import consume_motir_article_binding
from .motir_document_analysis import consume_motir_document_analysis
from .news_search import read_completed_title_snapshots
from .provider_registry import parse_provider_registry, permits_document_storage, MAX_BYTES
from .source_share import SourceShareError, _json, _when
from .text_normalization import normalize_text
from .theme_emergence import economic_observation
from .contract_amount_history import contract_amount_history

ERRORS=(SourceShareError,OSError,ValueError,TypeError,KeyError)
REASONS={
    'NOT_STORED':'일치하는 저장 근거가 없습니다.',
    'NOT_AVAILABLE_AS_OF':'조회 시점에는 이 근거 판본을 사용할 수 없습니다.',
    'SOURCE_MISMATCH':'사건·출처·시각 또는 원본 SHA가 일치하지 않습니다.',
    'RIGHTS_UNAVAILABLE':'현재 출처 사용권 또는 허가 설정을 확인할 수 없습니다.',
    'CLAUSE_UNRESOLVED':'이 기업의 원인·행동 구간을 명확하게 연결할 수 없습니다.',
    'UNSUPPORTED_SCOPE':'직접 사건 근거가 없는 공급 관계 또는 지원하지 않는 근거 범위입니다.',
}


def _exists(path):
    p=Path(path)
    return p.is_absolute() and p.exists() and not p.is_symlink() and p.resolve()==p


def _registry(path):
    if not _exists(path):raise SourceShareError('registry unavailable')
    return parse_provider_registry(_read_once(path,MAX_BYTES))


def installed_sources(base):
    """Use only existing NC paths. Never create missing directories/configs."""
    if base is None or not _exists(base):return [],[]
    base=Path(base);feeds=[];jobs=[]
    for prefix in ('','motir_'):
        feeds.append({'registry':base/'providers'/f'{prefix}authorized_sources.json',
            'inbox':base/'inbox'/f'{prefix}feed_triage',
            'state':base/'state'/f'{prefix}incremental_feeds.sqlite3'})
    path=base/'providers/motir_document_jobs.json'
    if _exists(path):
        try:jobs.extend(_json(_read_once(path,128000),'document jobs')['jobs'][:100])
        except ERRORS:pass
    root=base/'document_collection'
    if _exists(root):
        for folder in sorted(root.iterdir())[:100]:
            if not _exists(folder) or not re.fullmatch('[0-9a-f]{64}',folder.name):continue
            for binding in sorted((folder/'bindings').glob('motir_article_binding_*.json'))[:100]:
                if not _exists(binding):continue
                jobs.append({'binding_path':binding,'binding_sha256':binding.stem.rsplit('_',1)[1],
                    'archive_root':folder/'archive','article_registry':folder/'registry.json'})
    return feeds,jobs[:200]


def _reports(root,documents,now):
    """Preserve individual report versions instead of selecting latest analysis."""
    count=0
    folders=[]
    if root and _exists(root):folders.extend((Path(root)/s/'reports',False) for s in ('core','motir'))
    if documents and _exists(documents):
        folders.extend((f/'reports',True) for f in sorted(Path(documents).iterdir())
                       if re.fullmatch('[0-9a-f]{64}',f.name) and _exists(f))
    for folder,body in folders:
        if not _exists(folder):continue
        prefix='motir_document_analysis_' if body else 'feed_analysis_'
        for path in sorted(folder.glob(prefix+'*.json')):
            match=re.fullmatch(prefix+'([0-9a-f]{64})'+r'\.json',path.name)
            if not match or not _exists(path):continue
            count+=1
            if count>1000:raise SourceShareError('bounded evidence report scan required')
            try:
                if body:
                    data=consume_motir_document_analysis(path,match[1],now=now)
                    yield data,data['analysis_available_at'],match[1],True
                else:
                    raw=_read_once(path,MAX_REPORT_BYTES)
                    if sha256(raw).hexdigest()!=match[1]:continue
                    data=_json(raw,'saved feed analysis');checked=_validate_report(data,now)
                    if checked:
                        for row in data['results']:
                            yield row,max(checked,_when(row['analysis_available_at'],'analysis')).isoformat(),match[1],False
            except ERRORS:continue


def _change_matches(change,ref):
    if change.get('topic_alias_evidence')!=ref.get('topic_alias_evidence'):return False
    if change.get('policy_cause')!=ref.get('policy_cause'):return False
    if change.get('investment_project')!=ref.get('investment_project'):return False
    if change.get('demand_scope')!=ref.get('demand_scope'):return False
    if change.get('market_entry')!=ref.get('market_entry'):return False
    if change.get('product_price_cause')!=ref.get('product_price_cause'):return False
    if any(change.get(k)!=ref.get(k) for k in ('topic','action','phase','economic_driver')):return False
    if change['source_paragraph_sha256']!=ref['evidence_sha256']:return False
    event=economic_observation(change,origin_reference=ref['origin_reference'],source_url=ref['source_url'],
        source_id=ref['source_id'],source_available_at=ref['source_available_at'],content_scope=ref.get('content_scope'))
    return event['event_id']==ref['event_id']


def _rss_source(ref,row,feeds,at,now):
    status='NOT_STORED'
    for spec in feeds:
        try:
            status='RIGHTS_UNAVAILABLE'
            registry=_registry(Path(spec['registry']))
            if ref['source_id'] not in {p.provider_id for p in registry.providers}:continue
            registry.active(ref['source_id'],at=now)
            status='NOT_STORED'
            if not all(_exists(spec[k]) for k in ('inbox','state')):continue
            status='SOURCE_MISMATCH'
            for ack,doc,digest in read_completed_title_snapshots(Path(spec['inbox']),Path(spec['state']),registry,now=now):
                if doc['provider_id']!=ref['source_id']:continue
                for item in doc['items']:
                    if item['event_id']!=row['source_event_sha256']:continue
                    if (item['title_sha256']!=ref['evidence_sha256'] or item['canonical_url']!=ref['source_url']
                            or item['available_at']!=ref['source_available_at'] or item['headline']!=row['headline']):
                        status='SOURCE_MISMATCH';continue
                    if _when(ack['confirmed_at'],'ack')>at:return None,'NOT_AVAILABLE_AS_OF'
                    checkpoint=read_retry_checkpoint(Path(spec['inbox'])/('pending_'+ack['checkpoint_sha256']),
                                                     Path(spec['inbox']),ack['checkpoint_sha256'])
                    originals=[s.headline for s in checkpoint.poll.observations if s.event_id==item['event_id']]
                    if len(originals)!=1 or sha256(originals[0].encode()).hexdigest()!=ref['evidence_sha256']:
                        return None,'SOURCE_MISMATCH'
                    return normalize_text(originals[0])[0],'READY'
        except ERRORS:pass
    return None,status


def _body_source(ref,row,jobs,at,now):
    status='NOT_STORED'
    for job in jobs:
        if job.get('binding_sha256')!=row['binding_sha256']:continue
        try:
            status='SOURCE_MISMATCH'
            binding=consume_motir_article_binding(Path(job['binding_path']),job['binding_sha256'],now=now)
            status='RIGHTS_UNAVAILABLE'
            provider=_registry(Path(job['article_registry'])).active(binding['article_provider_id'],at=now)
            if not permits_document_storage(provider) or provider.method!='DOCUMENT' or provider.endpoint!=ref['source_url']:
                return None,'RIGHTS_UNAVAILABLE'
            status='SOURCE_MISMATCH'
            if (ref.get('source_binding')!={'source_event_sha256':binding['archive_version'],'document_sha256':binding['document_sha256']}
                    or binding['source_url']!=ref['source_url'] or binding['binding_at']!=ref['source_available_at']
                    or row['document_sha256']!=binding['document_sha256']
                    or row['source_event_sha256']!=binding['source_event_sha256']):return None,'SOURCE_MISMATCH'
            if _when(binding['binding_at'],'binding')>at:return None,'NOT_AVAILABLE_AS_OF'
            archive=Path(job['archive_root'])
            if not _exists(archive):return None,'NOT_STORED'
            raw,receipt=read_archived_evidence(archive,binding['archive_version'],decision_at=at,now=now)
            if (sha256(raw).hexdigest()!=binding['document_sha256'] or receipt.receipt_sha256!=binding['archive_receipt_sha256']
                    or receipt.receipt_sha256!=row['archive_receipt_sha256']
                    or receipt.content_scope!='LICENSED_SOURCE_BYTES'
                    or receipt.provider_id!=binding['article_provider_id']
                    or receipt.document_id!=binding['source_url'].split('/')[-2]
                    or receipt.archived_at.isoformat()!=binding['article_archived_at']):return None,'SOURCE_MISMATCH'
            paragraphs={p.strip() for p in raw.decode().splitlines() if p.strip()
                        and sha256(p.strip().encode()).hexdigest()==ref['evidence_sha256']}
            if len(paragraphs)!=1:return None,'SOURCE_MISMATCH'
            return paragraphs.pop(),'READY'
        except ERRORS:pass
    return None,status


def _clause(text,change,entity,ref,*,include_investment_execution=True,include_new_customers=True,include_delivery_start=True,include_market_entry=True):
    names=[m['source_name'] for m in ref.get('company_mappings',[]) if m['entity_id']==entity] or [entity]
    options=dict(company_names=change['entity_ids'],include_investment_execution=include_investment_execution,
                 include_resumption=change['action']=='SUPPLY_RESUMPTION',include_demand_scopes='demand_scope' in change,include_product_prices='product_price_cause' in change,
                 include_investment_projects='investment_project' in change,include_new_customers=include_new_customers,include_delivery_start=include_delivery_start,include_market_entry=include_market_entry)
    matches=[]
    for sentence in re.split(r'(?<=[.!?。])\s+',text):
        for clause in company_clauses(sentence,change['entity_ids'],include_resumption=change['action']=='SUPPLY_RESUMPTION',include_investment_execution=include_investment_execution,include_new_customers=include_new_customers,include_delivery_start=include_delivery_start,include_market_entry=include_market_entry):
            if ('topic_alias_evidence' in change
                    and change['topic_alias_evidence'] not in explicit_topic_aliases(clause)):
                continue
            if not any(mentions_name(clause,n) for n in names):continue
            # Pure matching only: never persist a reinterpreted event or infer a subject.
            candidates=extract_economic_changes(clause,**options)
            if 'policy_cause' in change and 'destination' not in change['policy_cause']:
                candidates+=extract_economic_changes(clause,**options,include_policy_destinations=False)
            if 'policy_cause' not in change:
                candidates+=extract_economic_changes(clause,**options,include_policy_causes=False)
            if ' 및 ' in clause:
                candidates+=extract_economic_changes(clause,**options,include_parallel_actions=False)
            # A saved pre-order-growth event retains its original driver/ID.
            # Match its old extraction without persisting or reclassifying it.
            if change['economic_driver']!='DEMAND_EXPANSION':
                candidates+=extract_economic_changes(clause,**options,include_order_growth=False,include_parallel_actions=False)
            for found in candidates:
                if (all(found[k]==change[k] for k in ('topic','economic_driver','action','phase'))
                        and found.get('policy_cause')==change.get('policy_cause')
                        and found.get('demand_scope')==change.get('demand_scope')
                        and found.get('market_entry')==change.get('market_entry')
                        and found.get('product_price_cause')==change.get('product_price_cause')
                        and ('investment_project' not in change or found.get('investment_project')==change['investment_project'])):
                    matches.append(clause);break
    matches=list(dict.fromkeys(matches))
    if len(matches)!=1 and include_market_entry and change['action']!='MARKET_ENTRY':
        return _clause(text,change,entity,ref,include_investment_execution=include_investment_execution,
                       include_new_customers=include_new_customers,include_delivery_start=include_delivery_start,include_market_entry=False)
    if len(matches)!=1 and include_delivery_start and change['action']!='DELIVERY_START':
        return _clause(text,change,entity,ref,include_investment_execution=include_investment_execution,
                       include_new_customers=include_new_customers,include_delivery_start=False,include_market_entry=include_market_entry)
    if len(matches)!=1 and include_new_customers and change['action']!='CUSTOMER_ACQUISITION':
        return _clause(text,change,entity,ref,include_investment_execution=include_investment_execution,include_new_customers=False,include_delivery_start=include_delivery_start,include_market_entry=include_market_entry)
    if len(matches)!=1 and include_investment_execution and change['action']=='INVESTMENT':
        return _clause(text,change,entity,ref,include_investment_execution=False,include_new_customers=include_new_customers,include_delivery_start=include_delivery_start,include_market_entry=include_market_entry)
    return matches[0] if len(matches)==1 else None


def company_evidence(theme,entity,*,reports_root,document_root=None,feeds=(),jobs=(),as_of=None,now=None):
    """Input is an as-of ThemeStore snapshot; output is private read-only context."""
    now=now or datetime.now(timezone.utc);at=as_of or now
    if at>now or _when(theme['decision_at'],'theme')>at:raise SourceShareError('future evidence query')
    active=set(theme['event_ids'])-set(theme['invalidated_event_ids'])
    refs=[r for r in theme['source_refs'] if r['event_id'] in active and r['polarity']=='SUPPORT'
          and entity in r['entity_ids']]
    result={'schema':'newscatalyst.company_evidence.v1','theme_id':theme['theme_id'],'entity_id':entity,
            'as_of':at.isoformat(),'items':[],'evidence_limit':'LOCAL_SOURCE_INTEGRITY_NOT_INDEPENDENT_VERIFICATION'}
    reports=list(_reports(reports_root,document_root,now)) if refs else []
    for ref in refs:
        item={k:ref[k] for k in ('event_id','source_url','source_available_at','evidence_sha256','topic','action','economic_driver','phase')}
        item.update(status='NOT_STORED',excerpt=None,content_scope=ref.get('content_scope','UNSPECIFIED'))
        if max(_when(ref[k],k) for k in ('source_available_at','recorded_at'))>at:
            item['status']='NOT_AVAILABLE_AS_OF'
        else:
            for row,available,pin,body in reports:
                if row['source_url']!=ref['source_url']:continue
                if row['source_available_at']!=ref['source_available_at']:
                    item['status']='SOURCE_MISMATCH';continue
                if not body and (row['provider_id']!=ref['source_id'] or ref.get('source_binding',{
                        'source_event_sha256':row['source_event_sha256'],'document_sha256':row['source_title_sha256']})!={
                        'source_event_sha256':row['source_event_sha256'],'document_sha256':row['source_title_sha256']}):
                    item['status']='SOURCE_MISMATCH';continue
                for change in row.get('economic_changes',[]):
                    if not _change_matches(change,ref):continue
                    if _when(available,'report')>at:
                        item['status']='NOT_AVAILABLE_AS_OF';continue
                    text,status=(_body_source(ref,row,jobs,at,now) if body else _rss_source(ref,row,feeds,at,now))
                    item['status']=status
                    if text is None:continue
                    excerpt=_clause(text,change,entity,ref)
                    if excerpt is None:item['status']='CLAUSE_UNRESOLVED';continue
                    item.update(status='READY',excerpt=excerpt,content_scope='LICENSED_ARTICLE_TEXT' if body else 'RSS_TITLE_METADATA',
                        excerpt_sha256=sha256(excerpt.encode()).hexdigest(),analysis_available_at=available,report_sha256=pin)
                    if not body and change['action']=='CONTRACT':
                        item['contract_amount_history']=contract_amount_history(row,ref,reports,at=at,
                            read_source=lambda r,v:_rss_source(r,v,feeds,at,now))
                        for revision in item['contract_amount_history']['changes']:
                            revision['before_source'].update(analysis_available_at=available,report_sha256=pin)
                    break
                if item['status']=='READY':break
        item['reason']=REASONS.get(item['status'],'원본 판본과 사건이 일치하는 근거입니다.')
        result['items'].append(item)
    if not refs:result['reason']=REASONS['UNSUPPORTED_SCOPE']
    return result
