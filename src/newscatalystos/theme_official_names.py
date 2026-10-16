"""PIT directory names for known IDs; never a name quoted in an article."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from .article_company_identity import encoded,resolve_names,validate_name_results
from .economic_changes import normalized
from .evidence_archive import _private_root,_read_once,_write_new
from .source_share import SourceShareError,_json,_must_sha,_when

SCHEMA='newscatalyst.theme_official_name.v1'
VERSION='exact-known-issuer-id-v1'
MAX_BYTES=128000
KEYS=('candidate_id','theme_snapshot_sha256','entity_id','directory_sha256','resolver_version')


def _read(path,now):
    saved=_json(_read_once(path,MAX_BYTES),'official name');r=saved['report']
    key={k:r[k] for k in KEYS}
    if (r['schema']!=SCHEMA or r['resolver_version']!=VERSION
            or saved['sha256']!=sha256(encoded(r)).hexdigest()
            or path.name!='theme_official_name_'+sha256(encoded(key)).hexdigest()+'.json'):
        raise SourceShareError('official name receipt mismatch')
    from .theme_company_identity import ID
    if not ID.fullmatch(r['entity_id']):raise SourceShareError('official ID required')
    for k in ('candidate_id','theme_snapshot_sha256','directory_sha256'):_must_sha(r[k],k)
    at=_when(r['decision_at'],'name decision')
    if at>now:raise SourceShareError('future name receipt')
    if r['status'] not in {'MATCHED','NOT_IN_SNAPSHOT','AMBIGUOUS_NAMES'}:raise SourceShareError('invalid name status')
    if r['status']=='MATCHED':
        proof=r['proof'];validate_name_results([proof],[],at)
        if proof['entity_id']!=r['entity_id'] or not isinstance(r['name_ambiguous'],bool):raise SourceShareError('name ID mismatch')
    elif r.get('proof') is not None:raise SourceShareError('unresolved name has proof')
    return r


def ensure_official_names(candidates,contexts,root,*,at,directory_sha256):
    from .theme_company_identity import ID
    # Existing reader supplies pinned FilingContext objects, with local availability.
    from .official_filing_context import FilingContext
    if any(not isinstance(r,FilingContext) or r.local_context_verified_at>at for r in contexts.values()):
        raise SourceShareError('unavailable official name directory')
    created=hits=0
    for c in candidates:
        if not ID.fullmatch(c['entity_id']):continue
        if _when(c['decision_at'],'candidate decision')>at:raise SourceShareError('future name candidate')
        key={k:c[k] for k in ('candidate_id','theme_snapshot_sha256','entity_id')}
        key.update(directory_sha256=directory_sha256,resolver_version=VERSION)
        path=_private_root(root)/('theme_official_name_'+sha256(encoded(key)).hexdigest()+'.json')
        if path.exists():_read(path,at);hits+=1;continue
        exact={k:r for k,r in contexts.items() if r.issuer_namespace_observed+':'+r.issuer_code_observed==c['entity_id']}
        names={normalized(r.issuer_name_observed) for r in exact.values()}
        status='MATCHED' if len(names)==1 else 'NOT_IN_SNAPSHOT' if not names else 'AMBIGUOUS_NAMES'
        proof=None;ambiguous=False
        if status=='MATCHED':
            name=min(exact.values(),key=lambda r:(r.local_context_verified_at,r.source_id,r.document_id)).issuer_name_observed
            matches,_=resolve_names([name],exact,at=at);proof=matches[0]
            ambiguous=len({r.issuer_namespace_observed+':'+r.issuer_code_observed for r in contexts.values() if normalized(r.issuer_name_observed)==normalized(name)})>1
        report={**key,'schema':SCHEMA,'decision_at':at.isoformat(),'status':status,'proof':proof,'name_ambiguous':ambiguous}
        raw=encoded({'report':report,'sha256':sha256(encoded(report)).hexdigest()})
        try:_write_new(path,raw);created+=1
        except FileExistsError:_read(path,at);hits+=1
    return {'created':created,'cache_hits':hits}


def resolve_official_names(candidates,root,*,as_of,now):
    root=Path(root);reports={};skipped=0
    if root.exists():
        if not root.is_absolute() or root.resolve()!=root:raise SourceShareError('unsafe name cache')
        paths=sorted(root.glob('theme_official_name_*.json'))
        if len(paths)>10000:raise SourceShareError('too many name receipts')
        for path in paths:
            try:r=_read(path,now)
            except (SourceShareError,KeyError,TypeError,ValueError,OSError):skipped+=1;continue
            if _when(r['decision_at'],'name decision')>as_of:continue
            key=tuple(r[k] for k in ('candidate_id','theme_snapshot_sha256','entity_id'))
            old=reports.get(key)
            if old is None or (_when(r['decision_at'],'name decision'),r['directory_sha256'])>(_when(old['decision_at'],'name decision'),old['directory_sha256']):reports[key]=r
    from .theme_company_identity import ID
    result=deepcopy(candidates)
    for c in result:
        c.pop('official_name_context',None)
        if not ID.fullmatch(c['entity_id']):continue
        c['official_name_context']={'status':'NOT_AVAILABLE_AS_OF'}
        r=reports.get(tuple(c[k] for k in ('candidate_id','theme_snapshot_sha256','entity_id')))
        if r:c['official_name_context']={k:deepcopy(r[k]) for k in ('status','decision_at','directory_sha256','proof','name_ambiguous')}
    return result,skipped
