"""Publish stable, successive news-material inputs for an independent selector.

Reuse ThemeStore, material comparison, exact identity projection and the existing
v1/v2 envelope. Reads never advance a cursor. Unchanged inputs reuse the same
bytes; failed scopes keep their last good edition with explicit stale status.
No receiver writes, market ranking, orders, new source fetch or paid analysis.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
import fcntl
import os
import re
import sqlite3
import stat
import tempfile

from .catalyst_material import materials_for_store, attach_material, default_since
from .era_daily_assessment import read_latest as read_identity, assessment_for, project_themes
from .evidence_archive import _private_root, _read_once
from .source_share import SourceShareError, _json, _when, _must_sha
from .standard_delivery import build_theme_bundle, read_theme_bundle
from .theme_emergence import ThemeStore, _bytes

SCHEMA='newscatalyst.material_publication.v1'
LIMIT=2_000_000
ERRORS=(SourceShareError,OSError,ValueError,TypeError,KeyError,sqlite3.Error)


def _read_checkpoint(root,pin,now):
    pin=_must_sha(pin,'publication receipt')
    raw=_read_once(root/('material_checkpoint_'+pin+'.json'),LIMIT)
    if sha256(raw).hexdigest()!=pin:raise SourceShareError('material checkpoint SHA mismatch')
    doc=_json(raw,'material checkpoint')
    if doc.get('schema')!=SCHEMA or _bytes(doc)!=raw:
        raise SourceShareError('invalid material checkpoint')
    at=_when(doc['published_at'],'material published')
    if at>now:raise SourceShareError('future material publication')
    payload_pin=_must_sha(doc['payload_sha256'],'material payload')
    payload=_read_once(root/('theme_delivery_'+payload_pin+'.json'),LIMIT)
    bundle=read_theme_bundle(payload,payload_pin,decision_at=at,now=now)
    if bundle['decision_at']!=doc['published_at']:
        raise SourceShareError('publication/payload time mismatch')
    return doc,payload


def read_published(root,*,as_of=None,now=None):
    """Read exact completed bytes, optionally from a prior PIT-safe edition."""
    now=now or datetime.now(timezone.utc);at=as_of or now
    now=_when(now.isoformat(),'now');at=_when(at.isoformat(),'as of')
    if at>now:raise SourceShareError('future publication query')
    root=Path(root)
    if not root.exists() or not (root/'latest.json').exists():return None
    if not root.is_absolute() or root.resolve()!=root:raise SourceShareError('unsafe publication root')
    pointer=_json(_read_once(root/'latest.json',8192),'latest publication')
    if set(pointer)!={'schema','checkpoint_sha256'} or pointer['schema']!=SCHEMA:
        raise SourceShareError('invalid publication pointer')
    pin=pointer['checkpoint_sha256'];seen=set()
    for _ in range(4096):
        if pin in seen:raise SourceShareError('cyclic publication history')
        seen.add(pin);doc,payload=_read_checkpoint(root,pin,now)
        if _when(doc['published_at'],'published')<=at:return doc,payload,pin
        pin=doc['previous_checkpoint_sha256']
        if pin is None:return None
    raise SourceShareError('publication history exceeds bounded query')


def _freeze(path,data):
    # No partially-written immutable file is visible after an interrupted tick.
    fd,tmp=tempfile.mkstemp(prefix='.material-',dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        try:os.link(tmp,path)
        except FileExistsError:
            if _read_once(path,LIMIT)!=data:raise SourceShareError('conflicting immutable publication')
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def _commit_pointer(root,pin):
    data=_bytes({'schema':SCHEMA,'checkpoint_sha256':pin})
    fd,tmp=tempfile.mkstemp(prefix='.material-current-',dir=root)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,root/'latest.json')
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def _paths(root,sources):
    if not sources or len(sources)>20:raise SourceShareError('bounded news scopes required')
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root or root.is_symlink():
        raise SourceShareError('absolute non-symlink publication root required')
    for scope,value in sources.items():
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}',scope):raise SourceShareError('invalid source scope')
        path=Path(value)
        if (not path.is_absolute() or path.resolve()!=path
                or any('eraleader' in s.casefold() for s in path.parts+root.parts)
                or root.resolve().is_relative_to(path) or path.is_relative_to(root.resolve())):
            raise SourceShareError('separate News-owned source and publication roots required')


def _identity_fingerprint(themes,snapshot):
    rows=[]
    for entity in sorted({e for t in themes if not t.get('supply_chain_evidence') for e in t['entity_ids']}):
        value=assessment_for(entity,snapshot)
        if value['status']=='AVAILABLE':
            rows.append([entity,value['entity_id'],value['security_id'],value['identity_evidence_sha256']])
    # A fresh price or financial display revision is NOT a new news identity.
    return rows


def _publish(root,sources,identity_root,now,previous,*,dry_run):
    old=previous[0] if previous else None
    old_bundle=_json(previous[1],'previous delivery') if previous else {'ThemeCandidates':[]}
    old_scopes=old['scopes'] if old else {}
    state={};exported=[];changed=False
    snapshot=None;identity_status='NOT_CONFIGURED'
    if identity_root:
        try:
            snapshot,skipped=read_identity(identity_root,as_of=now,now=now)
            identity_status='AVAILABLE' if snapshot else 'UNAVAILABLE'
        except ERRORS:identity_status='UNAVAILABLE'
    for scope,path in sorted(sources.items()):
        before=old_scopes.get(scope)
        old_themes=[deepcopy(t) for t in old_bundle['ThemeCandidates']
                    if t.get('material_publication_source',{}).get('scope')==scope]
        try:
            store=ThemeStore(path)
            # A valid source may not have produced any economic themes yet.
            # But a previously published immutable theme must never disappear
            # because a source DB was removed or a stale copy was restored.
            themes=store.search(as_of=now,now=now)
            theme_ids=sorted(t['theme_id'] for t in themes)
            if before and not set(before.get('source_theme_ids',[]))<=set(theme_ids):
                raise SourceShareError('previously published source themes unavailable')
            by_id={t['theme_id']:t for t in themes}
            for known in old_themes:
                origin=known.get('export_origin',{})
                source_id=origin.get('theme_id',known['theme_id'])
                last=origin.get('decision_at',known['decision_at'])
                if _when(by_id[source_id]['decision_at'],'source edition')<_when(last,'known edition'):
                    raise SourceShareError('source edition regressed')
            identity=_identity_fingerprint(themes,snapshot) if scope!='base' else []
            signature=sha256(_bytes({'themes':themes,'identity':identity,'method':SCHEMA})).hexdigest()
            identical=before and before.get('input_sha256')==signature
            if identical:
                next_themes=old_themes
                good_at=before['last_successful_input_at']
            else:
                since=(_when(before['last_successful_input_at'],'previous cutoff')+timedelta(microseconds=1)
                       if before and before.get('last_successful_input_at') else default_since(now))
                if since>now:raise SourceShareError('nonmonotonic publication cutoff')
                materials=materials_for_store(store,since=since,as_of=now,scope=scope,now=now)
                # Confirm both readers saw one coherent immutable source edition.
                reread=store.search(as_of=now,now=now)
                if _bytes(reread)!=_bytes(themes):raise SourceShareError('source changed during publication')
                next_themes=attach_material(themes if scope=='base' else project_themes(themes,scope,snapshot),materials)
                good_at=now.isoformat()
            for t in next_themes:
                t['material_publication_source']={'scope':scope,'status':'CURRENT_SNAPSHOT','input_available_at':good_at}
            entry={'status':'CURRENT_SNAPSHOT','input_sha256':signature,
                   'last_successful_input_at':good_at,'theme_count':len(next_themes),'source_theme_ids':theme_ids}
        except ERRORS as exc:
            next_themes=old_themes
            good_at=before.get('last_successful_input_at') if before else None
            entry={'status':'UNAVAILABLE','input_sha256':before.get('input_sha256') if before else None,
                   'last_successful_input_at':good_at,'theme_count':len(next_themes),'source_theme_ids':before.get('source_theme_ids',[]) if before else [],'error_type':type(exc).__name__}
            for t in next_themes:
                t['material_publication_source']={'scope':scope,'status':'LAST_GOOD_SOURCE_UNAVAILABLE','input_available_at':good_at}
        state[scope]=entry;exported.extend(next_themes)
        changed=changed or entry!=before
    removed=set(old_scopes)-set(sources)
    if removed:raise SourceShareError('source removal requires explicit withdrawal, not disappearance')
    failures=sum(x['status']=='UNAVAILABLE' for x in state.values())
    if old and not changed:
        return {'status':'ALREADY_PUBLISHED','sha256':old['payload_sha256'],
                'published_at':old['published_at'],'checkpoint_sha256':previous[2],
                'themes':len(exported),'unavailable_scopes':failures,'new_publication':False}
    if dry_run:return {'status':'WOULD_PUBLISH','themes':len(exported),'unavailable_scopes':failures,'new_publication':False}
    # Commit only after complete source->comparison->immutable payload succeeds.
    # A failing scope retains its own old cutoff; healthy scopes still progress.
    payload=build_theme_bundle(exported,decision_at=now,now=now)
    payload_sha=sha256(payload).hexdigest()
    checkpoint={'schema':SCHEMA,'published_at':now.isoformat(),'payload_sha256':payload_sha,
        'previous_checkpoint_sha256':previous[2] if previous else None,
        'scopes':state,'identity_status':identity_status,
        'consumer_acknowledgement':None,'selection_changed_by_publisher':False,'orders':0}
    saved=_bytes(checkpoint);checkpoint_sha=sha256(saved).hexdigest()
    _freeze(root/('theme_delivery_'+payload_sha+'.json'),payload)
    _freeze(root/('material_checkpoint_'+checkpoint_sha+'.json'),saved)
    _commit_pointer(root,checkpoint_sha)
    return {'status':'PUBLISHED_PARTIAL' if failures else 'PUBLISHED','sha256':payload_sha,
            'published_at':checkpoint['published_at'],'checkpoint_sha256':checkpoint_sha,
            'themes':len(exported),'unavailable_scopes':failures,'new_publication':True}


def publish_material(root,sources,*,identity_root=None,now=None,dry_run=False):
    """Called once by the existing approved RSS runner after its current tick."""
    at=_when((now or datetime.now(timezone.utc)).isoformat(),'publication now')
    root=Path(root);_paths(root,sources)
    if dry_run:
        previous=read_published(root,now=at)
        return _publish(root,sources,identity_root,at,previous,dry_run=True)
    root=_private_root(root)
    fd=os.open(root/'.publish.lock',os.O_WRONLY|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise SourceShareError('unsafe publication lock')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise SourceShareError('material publisher already running') from exc
        previous=read_published(root,now=at)
        if previous and _when(previous[0]['published_at'],'last publication')>at:
            raise SourceShareError('future previous publication')
        return _publish(root,sources,identity_root,at,previous,dry_run=False)
    finally:os.close(fd)
