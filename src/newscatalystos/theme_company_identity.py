"""Versioned name resolution for existing theme candidates, without theme writes."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from .article_company_identity import encoded, resolve_names, validate_name_results, RESOLVER_VERSION
from .evidence_archive import _private_root, _read_once, _write_new
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA='newscatalyst.theme_company_identity.v1'
ID=re.compile(r'(?:DART_CORP:[0-9]{8}|SEC_CIK:[0-9]{1,10}|KRX_STOCK:[0-9]{6})\Z')
MAX_BYTES=128000


def ensure_identities(candidates, contexts, root, *, at):
    directory=[]
    for row in contexts.values():
        fields=asdict(row);fields.pop('local_context_verified_at');directory.append(fields)
    fingerprint=sha256(encoded(sorted(directory,key=lambda r:(r['source_id'],r['document_id'])))).hexdigest()
    output=[]
    for candidate in candidates:
        if ID.fullmatch(candidate['entity_id']):continue
        if _when(candidate['decision_at'],'candidate decision')>at:raise SourceShareError('future candidate')
        name=candidate['entity_id']
        key={'candidate_id':candidate['candidate_id'],'theme_snapshot_sha256':candidate['theme_snapshot_sha256'],
             'source_name':name,'directory_sha256':fingerprint,'resolver_version':RESOLVER_VERSION}
        path=_private_root(root)/('theme_identity_'+sha256(encoded(key)).hexdigest()+'.json')
        if path.exists():
            report=_read_report(path,at)
            if any(report[k]!=v for k,v in key.items()):raise SourceShareError('identity cache key mismatch')
            output.append('CACHE_HIT');continue
        matches,unresolved=resolve_names([name],contexts,at=at)
        report={**key,'schema':SCHEMA,'decision_at':at.isoformat(),'matches':matches,'unresolved':unresolved}
        raw=encoded({'report':report,'sha256':sha256(encoded(report)).hexdigest()})
        try:_write_new(path,raw);output.append('CREATED')
        except FileExistsError:
            saved=_read_report(path,at)
            if any(saved[k]!=v for k,v in key.items()):raise SourceShareError('identity publication collision')
            output.append('CACHE_HIT')
    return {'created':output.count('CREATED'),'cache_hits':output.count('CACHE_HIT')}


def _read_report(path, now):
    saved=_json(_read_once(path,MAX_BYTES),'theme identity');r=saved['report']
    key={k:r[k] for k in ('candidate_id','theme_snapshot_sha256','source_name','directory_sha256','resolver_version')}
    if (r['schema']!=SCHEMA or r['resolver_version']!=RESOLVER_VERSION
            or saved['sha256']!=sha256(encoded(r)).hexdigest()
            or path.name!='theme_identity_'+sha256(encoded(key)).hexdigest()+'.json'):
        raise SourceShareError('theme identity receipt mismatch')
    for k in ('candidate_id','theme_snapshot_sha256','directory_sha256'):_must_sha(r[k],k)
    decision=_when(r['decision_at'],'identity decision')
    if decision>now:raise SourceShareError('future identity')
    validate_name_results(r['matches'],r['unresolved'],decision)
    if len(r['matches'])+len(r['unresolved'])!=1 or any(
            row['source_name']!=r['source_name'] for row in r['matches']+r['unresolved']):
        raise SourceShareError('candidate name mismatch')
    return r


def resolve_candidates(candidates, root, *, as_of, now=None):
    present=now or datetime.now(timezone.utc)
    if as_of>present:raise SourceShareError('future identity query')
    reports={};skipped=0;root=Path(root)
    if root.exists():
        if not root.is_absolute() or root.resolve()!=root:raise SourceShareError('unsafe identity cache')
        paths=sorted(root.glob('theme_identity_*.json'))
        if len(paths)>10000:raise SourceShareError('too many theme identity receipts')
        for path in paths:
            try:r=_read_report(path,present)
            except (SourceShareError,KeyError,TypeError,ValueError,OSError):skipped+=1;continue
            if _when(r['decision_at'],'identity decision')>as_of:continue
            key=(r['candidate_id'],r['theme_snapshot_sha256'],r['source_name'])
            previous=reports.get(key)
            if previous is None or _when(r['decision_at'],'decision')>_when(previous['decision_at'],'decision'):
                reports[key]=r
    result=deepcopy(candidates)
    for candidate in result:
        candidate.pop('resolved_entity_id',None)
        if ID.fullmatch(candidate['entity_id']):
            candidate['identity_context']={'status':'ALREADY_IDENTIFIED'};continue
        r=reports.get((candidate['candidate_id'],candidate['theme_snapshot_sha256'],candidate['entity_id']))
        candidate['identity_context']={'status':'NOT_RESOLVED_AS_OF'}
        if r:
            candidate['identity_context']={'status':'MATCHED' if r['matches'] else r['unresolved'][0]['status'],
                'decision_at':r['decision_at'],'directory_sha256':r['directory_sha256'],
                'source_name':r['source_name'],'matches':r['matches'],
                'receipt_sha256':sha256(encoded(r)).hexdigest()}
            if r['matches']:candidate['resolved_entity_id']=r['matches'][0]['entity_id']
    return result,skipped


def resolve_stored_candidates(theme_root, config, output_root, *, now=None):
    from .feed_company_identity import load_directory
    from .theme_emergence import ThemeStore
    from .standard_delivery import build_theme_bundle
    import json
    at=now or datetime.now(timezone.utc)
    themes=ThemeStore(theme_root).search(now=at)
    candidates=json.loads(build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True))['CompanyCandidates']
    if not any(not ID.fullmatch(c['entity_id']) for c in candidates):return {'created':0,'cache_hits':0}
    contexts=load_directory(config,now=at)
    return ensure_identities(candidates,contexts,output_root,at=at)


def filter_research(research, themes, query):
    from .economic_changes import normalized
    if not isinstance(query,str) or len(query)>200:raise SourceShareError('invalid company research query')
    term=normalized(query)
    from .theme_emergence import theme_presentation
    matching_themes={t['theme_id'] for t in themes
                     if term in normalized(encoded(t).decode()+' '+theme_presentation(t)['name'])}
    research['CompanyCandidates']=[c for c in research['CompanyCandidates']
        if c['theme_id'] in matching_themes or term in normalized(encoded(c).decode())]
    return research
