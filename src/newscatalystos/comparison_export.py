"""Pinned local query delivery; SHA integrity does not certify source claims."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import os
from .theme_emergence import _bytes
from .source_share import SourceShareError,_when,_must_sha,_json
from .evidence_archive import _private_root,_write_new,_read_once
from .cross_product_period import _candidates,period_cross_product
from .cross_product_demand import cross_product_demand
from .common_cause_comparison import common_cause_comparisons

SCHEMA='newscatalyst.comparison_export.v1'
MAX_BYTES=20_000_000


def pack_comparison_export(themes,comparison,*,as_of,since=None,activity='all',query='',now=None):
    at=_when(as_of.isoformat(),'as of');start=_when(since.isoformat(),'since') if since else None
    value={'schema':SCHEMA,'query':{'as_of':at.isoformat(),'since':start.isoformat() if start else None,
        'activity':activity,'q':query},'selected_snapshots':sorted([
        {'theme_id':t['theme_id'],'sha256':sha256(_bytes(t)).hexdigest(),'decision_at':t['decision_at']} for t in themes],key=lambda p:p['theme_id']),
        'comparison':comparison,'original_content_included':False,'orders_enabled':False}
    raw=_bytes(value)
    read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=at,now=now)
    return raw


def query_comparison_export(store,*,as_of,since=None,activity='all',query='',now=None,identity_root=None):
    present=now or datetime.now(timezone.utc);at=_when(as_of.isoformat(),'as of')
    if at>present or (since is not None and since>at):raise SourceShareError('future or reversed comparison query')
    themes=store.search(as_of=at,since=since,activity=activity,now=present)
    cs=_candidates(themes,at,present,identity_root)
    comparison=cross_product_demand(themes,cs,common_cause_comparisons(themes,cs),as_of=at,since=since,query=query)
    comparison=period_cross_product(store,themes,comparison,since=since,as_of=at,now=present,query=query,identity_root=identity_root)
    return pack_comparison_export(themes,comparison,as_of=at,since=since,activity=activity,query=query,now=present)


def read_comparison_export(raw,expected_sha256,*,decision_at,now=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise SourceShareError('bounded comparison export required')
    if sha256(raw).hexdigest()!=_must_sha(expected_sha256,'comparison export SHA'):raise SourceShareError('comparison export SHA mismatch')
    value=_json(raw,'comparison export')
    try:
        if set(value)!={'schema','query','selected_snapshots','comparison','original_content_included','orders_enabled'} or value['schema']!=SCHEMA:
            raise SourceShareError('comparison export schema mismatch')
        if value['original_content_included'] is not False or value['orders_enabled'] is not False:raise SourceShareError('read-only comparison required')
        q=value['query']
        if set(q)!={'as_of','since','activity','q'} or q['activity'] not in {'all','new','updated','changed'} or not isinstance(q['q'],str) or len(q['q'])>200:
            raise SourceShareError('invalid comparison export query')
        at=_when(q['as_of'],'as of');consumer=_when(decision_at.isoformat(),'consumer decision')
        if at>consumer or consumer>_when((now or datetime.now(timezone.utc)).isoformat(),'now'):raise SourceShareError('future comparison export')
        if q['since'] is not None and _when(q['since'],'since')>at:raise SourceShareError('reversed comparison period')
        if q['activity']!='all' and q['since'] is None:raise SourceShareError('comparison activity requires period')
        comparison=value['comparison']
        if comparison['as_of']!=q['as_of'] or comparison['since']!=q['since'] or not isinstance(comparison['groups'],list):raise SourceShareError('comparison query binding mismatch')
        ids=[]
        for pin in value['selected_snapshots']:
            if set(pin)!={'theme_id','sha256','decision_at'}:raise SourceShareError('invalid selected snapshot pin')
            _must_sha(pin['theme_id'],'theme');_must_sha(pin['sha256'],'snapshot');ids.append(pin['theme_id'])
        if ids!=sorted(set(ids)):raise SourceShareError('noncanonical selected snapshot pins')
        def check_times(item):
            if isinstance(item,dict):
                for k,v in item.items():
                    if k in {'decision_at','recorded_at','source_available_at','as_of'} and v is not None and _when(v,k)>at:
                        raise SourceShareError('future pinned evidence')
                    check_times(v)
            elif isinstance(item,list):
                for v in item:check_times(v)
        check_times(value)
        if _bytes(value)!=raw:raise SourceShareError('noncanonical comparison export')
    except (KeyError,TypeError,ValueError) as exc:raise SourceShareError('invalid comparison export') from exc
    return value


def publish_comparison_export(raw,root,*,now=None):
    digest=sha256(raw).hexdigest();at=now or datetime.now(timezone.utc)
    read_comparison_export(raw,digest,decision_at=at,now=at)
    root=_private_root(root);final=root/('comparison_export_'+digest+'.json')
    temporary=root/('.comparison-'+uuid4().hex+'.tmp')
    try:
        _write_new(temporary,raw)
        try:os.link(temporary,final) # Exclusive publication: never expose partial bytes or overwrite a receipt.
        except FileExistsError:
            if _read_once(final,MAX_BYTES)!=raw:raise SourceShareError('comparison export publication conflict')
    finally:
        if temporary.exists():temporary.unlink()
    return {'path':str(final),'sha256':digest,'schema':SCHEMA}


def read_comparison_file(path,root,expected_sha256,*,decision_at,now=None):
    root=Path(root);path=Path(path)
    if not root.is_dir() or path.parent!=root or path.name!='comparison_export_'+_must_sha(expected_sha256,'comparison export SHA')+'.json':
        raise SourceShareError('comparison file outside pinned root')
    _private_root(root)
    return read_comparison_export(_read_once(path,MAX_BYTES),expected_sha256,decision_at=decision_at,now=now)
