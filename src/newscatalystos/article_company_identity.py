"""Licensed article names joined to previously pinned filing issuer metadata.

Names/IDs are source-reported identity context, never contract or benefit proof.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from .economic_changes import COMPANIES, normalized
from .evidence_archive import read_archived_evidence, _private_root, _read_once, _write_new
from .official_filing_context import FilingContext
from .publisher_theme_events import mentions_name
from .provider_registry import permits_document_storage
from .source_share import SourceShareError, _must_sha, _when, _json

SCHEMA='newscatalyst.article_company_identity.v1'
CACHE_SCHEMA='newscatalyst.article_company_identity.v2'
RESOLVER_VERSION='exact-filing-name-v1'
MAX_BYTES=128000
NON_COMPANY_TERMS={'노광장비','첨단장비','반도체소재','첨단반도체','대한민국반도체','한국반도체','산업소재'}


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def resolve_names(names,contexts,*,at):
    directory={}
    for row in contexts.values():
        if not isinstance(row,FilingContext) or row.local_context_verified_at>at:
            raise SourceShareError('unavailable filing identity metadata')
        directory.setdefault(normalized(row.issuer_name_observed),[]).append(row)
    matches=[];unresolved=[]
    for name in sorted(set(names)):
        rows=directory.get(normalized(name),[])
        ids={(r.issuer_namespace_observed,r.issuer_code_observed) for r in rows}
        if len(ids)!=1:
            unresolved.append({'source_name':name,'status':'AMBIGUOUS' if ids else 'NOT_IN_SNAPSHOT'})
            continue
        row=min(rows,key=lambda r:(r.source_id,r.document_id))
        proof={'source_name':name,'issuer_name':row.issuer_name_observed,
               'entity_id':row.issuer_namespace_observed+':'+row.issuer_code_observed,
               'source_id':row.source_id,'filing_document_id':row.document_id,
               'source_receipt_sha256':row.source_receipt_sha256,'original_sha256':row.original_sha256,
               'available_at':row.local_context_verified_at.isoformat()}
        matches.append({**proof,'evidence_sha256':sha256(encoded(proof)).hexdigest()})
    return matches,unresolved


def prepare_article_identity(archive_root,archive_version,receipt_sha256,document_sha256,registry,contexts,*,now=None):
    at=_when((now or datetime.now(timezone.utc)).isoformat(),'identity decision')
    body,archive=read_archived_evidence(archive_root,archive_version,now=at)
    if (archive.receipt_sha256!=_must_sha(receipt_sha256,'receipt pin')
            or archive.payload_sha256!=_must_sha(document_sha256,'document pin')
            or archive.content_scope!='LICENSED_SOURCE_BYTES'):
        raise SourceShareError('identity article pins mismatch')
    provider=registry.active(archive.provider_id,at=at)
    if (not permits_document_storage(provider) or provider.method!='DOCUMENT'
            or not provider.enabled_at(archive.first_verified_at)):
        raise SourceShareError('licensed article URL required')
    text=body.decode('utf-8')
    names={x.issuer_name_observed for x in contexts.values() if mentions_name(text,x.issuer_name_observed)}
    names.update(x for x in COMPANIES.findall(text) if x not in NON_COMPANY_TERMS and mentions_name(text,x))
    if len(names)>100:raise SourceShareError('too many article company candidates')
    matches,unresolved=resolve_names(names,contexts,at=at)
    at=_when((now or datetime.now(timezone.utc)).isoformat(),'identity completed')
    registry.active(archive.provider_id,at=at)
    report={'schema':SCHEMA,'archive_version':archive.version_id,'document_sha256':document_sha256,
            'archive_receipt_sha256':receipt_sha256,'source_url':provider.endpoint,
            'source_available_at':archive.archived_at.isoformat(),'decision_at':at.isoformat(),
            'matches':matches,'unresolved':unresolved,'evidence_level':'SOURCE_REPORTED_IDENTITY',
            'verified_real_transaction':False,'verified_real_benefit':False,'original_content_included':False}
    validate_report(report,at)
    return report


def validate_report(report,at):
    from .theme_emergence import _url, _text
    if (not isinstance(report,dict) or set(report)!={'schema','archive_version','document_sha256',
            'archive_receipt_sha256','source_url','source_available_at','decision_at','matches','unresolved',
            'evidence_level','verified_real_transaction','verified_real_benefit','original_content_included'} | (
                {'directory_sha256','resolver_version'} if report.get('schema')==CACHE_SCHEMA else set())
            or report.get('schema') not in (SCHEMA,CACHE_SCHEMA) or report.get('evidence_level')!='SOURCE_REPORTED_IDENTITY'
            or any(report.get(k) is not False for k in ('verified_real_transaction','verified_real_benefit','original_content_included'))
            or not _url(report.get('source_url'))
            or not _when(report['source_available_at'],'article available')<=_when(report['decision_at'],'identity decision')<=at):
        raise SourceShareError('invalid article identity report')
    if report['schema']==CACHE_SCHEMA:
        _must_sha(report['directory_sha256'],'filing directory')
        if report['resolver_version']!=RESOLVER_VERSION:raise SourceShareError('unsupported identity resolver')
    for key in ('archive_version','document_sha256','archive_receipt_sha256'):_must_sha(report[key],key)
    validate_name_results(report['matches'],report['unresolved'],_when(report['decision_at'],'decision'))


def validate_name_results(matches,unresolved,at):
    from .theme_emergence import _text
    if not isinstance(matches,list) or not isinstance(unresolved,list) or len(matches)+len(unresolved)>100:
        raise SourceShareError('bounded company results required')
    seen=set()
    for row in matches:
        if (set(row)!={'source_name','issuer_name','entity_id','source_id','filing_document_id','source_receipt_sha256','original_sha256','available_at','evidence_sha256'}
                or not _text(row['source_name'],200) or not _text(row['issuer_name'],200)
                or normalized(row['source_name'])!=normalized(row['issuer_name'])
                or not re.fullmatch(r'(?:DART_CORP:[0-9]{8}|SEC_CIK:[0-9]{1,10})',row['entity_id'])
                or not _text(row['filing_document_id'])
                or row['source_id'] not in {'dart-disclosures','sec-submissions'}
                or not row['entity_id'].startswith('DART_CORP:' if row['source_id']=='dart-disclosures' else 'SEC_CIK:')
                or not _when(row['available_at'],'identity available')<=at):
            raise SourceShareError('invalid source company identity')
        for key in ('source_receipt_sha256','original_sha256','evidence_sha256'):_must_sha(row[key],key)
        if sha256(encoded({k:v for k,v in row.items() if k!='evidence_sha256'})).hexdigest()!=row['evidence_sha256']:
            raise SourceShareError('identity evidence mismatch')
        if normalized(row['source_name']) in seen:raise SourceShareError('duplicate identity name')
        seen.add(normalized(row['source_name']))
    for row in unresolved:
        if set(row)!={'source_name','status'} or not _text(row['source_name'],200) or row['status'] not in {'AMBIGUOUS','NOT_IN_SNAPSHOT'}:
            raise SourceShareError('invalid unresolved identity')
        if normalized(row['source_name']) in seen:raise SourceShareError('ambiguous identity claim')
        seen.add(normalized(row['source_name']))


def publish_article_identity(report,root):
    validate_report(report,datetime.now(timezone.utc))
    raw=encoded(report)
    if len(raw)>MAX_BYTES:raise SourceShareError('oversized identity report')
    digest=sha256(raw).hexdigest();path=_private_root(root)/('article_company_identity_'+digest+'.json')
    try:_write_new(path,raw)
    except FileExistsError:
        if _read_once(path,MAX_BYTES)!=raw:raise SourceShareError('identity publication collision')
    return path,digest


def search_article_identities(root,*,query='',as_of=None):
    at=as_of or datetime.now(timezone.utc);root=Path(root);latest={}
    if at>datetime.now(timezone.utc) or not isinstance(query,str) or len(query)>200:
        raise SourceShareError('invalid company identity query')
    if not root.exists():return []
    if root.is_symlink() or root.resolve()!=root:raise SourceShareError('unsafe identity root')
    paths=sorted(root.glob('article_company_identity_*.json'))
    if len(paths)>1000:raise SourceShareError('too many identity reports')
    for path in paths:
        raw=_read_once(path,MAX_BYTES)
        if path.name!='article_company_identity_'+sha256(raw).hexdigest()+'.json':raise SourceShareError('identity report SHA mismatch')
        row=_json(raw,'article identity')
        validate_report(row,datetime.now(timezone.utc))
        if _when(row['decision_at'],'identity decision')>at:continue
        old=latest.get(row['archive_version'])
        if old is None or _when(row['decision_at'],'decision')>_when(old['decision_at'],'decision'):latest[row['archive_version']]=row
    return [r for _,r in sorted(latest.items()) if normalized(query) in normalized(json.dumps(r,ensure_ascii=False))]


def ensure_article_identity(archive_root, binding, registry, output_root,
                            era_root, era_report, independent_anchor, *, now=None):
    """Reuse an exact article/directory version, rechecking current pins and rights.

    Directory verification times change on each read and are excluded from the
    fingerprint. Raw/receipt SHAs and every issuer identity remain in the key.
    """
    from dataclasses import asdict
    from .official_filing_context import read_pinned_filing_context
    contexts=read_pinned_filing_context(era_root,era_report,independent_anchor,now=now)
    directory=[]
    for row in contexts.values():
        item=asdict(row);item.pop('local_context_verified_at')
        directory.append(item)
    fingerprint=sha256(encoded(sorted(directory,key=lambda r:(r['source_id'],r['document_id'])))).hexdigest()
    at=_when((now or datetime.now(timezone.utc)).isoformat(),'identity cache check')
    _,archive=read_archived_evidence(archive_root,binding['archive_version'],now=at)
    provider=registry.active(archive.provider_id,at=at)
    if (archive.receipt_sha256!=binding['archive_receipt_sha256']
            or archive.payload_sha256!=binding['document_sha256']
            or archive.content_scope!='LICENSED_SOURCE_BYTES'
            or provider.endpoint!=binding['source_url']
            or not permits_document_storage(provider) or provider.method!='DOCUMENT'
            or not provider.enabled_at(archive.first_verified_at)):
        raise SourceShareError('current article identity authorization/pins required')
    for row in search_article_identities(output_root,as_of=at):
        if (row['archive_version']==binding['archive_version']
                and row['archive_receipt_sha256']==binding['archive_receipt_sha256']
                and row['document_sha256']==binding['document_sha256']
                and row['source_url']==binding['source_url']
                and row.get('directory_sha256')==fingerprint
                and row.get('resolver_version')==RESOLVER_VERSION):
            return row,'CACHE_HIT'
    report=prepare_article_identity(archive_root,binding['archive_version'],
        binding['archive_receipt_sha256'],binding['document_sha256'],registry,contexts,now=now)
    report.update(schema=CACHE_SCHEMA,directory_sha256=fingerprint,resolver_version=RESOLVER_VERSION)
    publish_article_identity(report,output_root)
    return report,'CREATED'
