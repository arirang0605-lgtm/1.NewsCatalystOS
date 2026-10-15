"""Economic event -> provisional theme, immutable PIT history and search.

Dedup uses source claim origin + action/subject, never article count. Theme
membership is an inference; it cannot certify a transaction or benefit.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit, quote

from .economic_changes import DRIVERS, normalized
from .evidence_archive import _private_root
from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _when, _must_sha

SCHEMA = 'newscatalyst.theme_candidate.v1'
RELATION_SCHEMA = 'newscatalyst.theme_candidate.v2'
QUALITIES = {'OFFICIAL_SOURCE','REPORTED','INFERRED','UNVERIFIED','UNKNOWN'}
ACTIONS = {'POLICY_CHANGE','PRODUCTION_START','CAPACITY_ADDITION','SUPPLY_REDUCTION','CONTRACT','INVESTMENT'}
KNOWN_TOPICS = {'hbm','dram','nand','반도체','액침냉각'}
CHANGE_KEYS = {'topic','economic_driver','action','phase','entity_ids','industry_tags',
               'source_paragraph_sha256','evidence_level','verified_economic_effect'}


def _bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def _text(value, limit=120):
    return isinstance(value,str) and 0 < len(value) <= limit and not any(ord(c)<32 for c in value)


def _url(value):
    if not _text(value,2000):return False
    parsed=urlsplit(value)
    return parsed.scheme=='https' and bool(parsed.hostname) and not parsed.username and not parsed.password


def validate_change(change):
    if (not isinstance(change,dict) or set(change)!=CHANGE_KEYS
            or not _text(change['topic'],80) or change['economic_driver'] not in DRIVERS
            or change['action'] not in ACTIONS or change['evidence_level'] not in QUALITIES
            or change['phase'] not in {'SOURCE_REPORTED','ADOPTED_NOT_YET_EFFECTIVE','PLANNED'}
            or change['verified_economic_effect'] is not False):
        raise SourceShareError('invalid source economic change')
    for field in ('entity_ids','industry_tags'):
        if (not isinstance(change[field],list) or len(change[field])>30
                or any(not _text(x) for x in change[field])):
            raise SourceShareError('invalid economic entities/tags')
    _must_sha(change['source_paragraph_sha256'],'economic evidence')


def topic_key(topic):
    key=normalized(topic)
    return {'고대역폭 메모리':'hbm','고대역폭메모리':'hbm','immersion cooling':'액침냉각',
            '액침 냉각':'액침냉각','디램':'dram','낸드':'nand','semiconductor':'반도체'}.get(key,key)


def economic_observation(change, *, origin_reference, source_url, source_id,
                         source_available_at, polarity='SUPPORT', supersedes_event_id=None,
                         source_binding=None):
    validate_change(change)
    if not _url(origin_reference) or not _url(source_url) or not _text(source_id):
        raise SourceShareError('explicit source and claim origin required')
    if polarity not in {'SUPPORT','CONTRADICT','RETRACT'}:
        raise SourceShareError('invalid economic polarity')
    if supersedes_event_id is not None:_must_sha(supersedes_event_id,'superseded event')
    if polarity=='RETRACT' and (supersedes_event_id is None or change['evidence_level']!='OFFICIAL_SOURCE'):
        raise SourceShareError('retraction requires a targeted official correction')
    source_available_at=_when(source_available_at,'source availability').isoformat()
    # Same release across any number of publishers remains one event.
    identity=[origin_reference,topic_key(change['topic']),change['economic_driver'],
              change['action'],sorted(set(change['entity_ids']))]
    result = {'event_id':sha256(_bytes(identity)).hexdigest(),'change':change,
            'origin_reference':origin_reference,'source_url':source_url,'source_id':source_id,
            'source_available_at':source_available_at,'polarity':polarity,
            'supersedes_event_id':supersedes_event_id}
    if source_binding is not None:
        if not isinstance(source_binding,dict) or set(source_binding)!={'source_event_sha256','document_sha256'}:
            raise SourceShareError('invalid theme source binding')
        for key,value in source_binding.items():_must_sha(value,key)
        result['source_binding']=dict(source_binding)
    return result


def _validate_observation(row):
    if not isinstance(row,dict) or set(row)-{'source_binding'}!={'event_id','change','origin_reference','source_url',
            'source_id','source_available_at','polarity','supersedes_event_id'}:
        raise SourceShareError('economic observation contract required')
    rebuilt=economic_observation(row['change'],**{k:row[k] for k in row if k not in {'change','event_id'}})
    if rebuilt!=row:raise SourceShareError('economic event identity mismatch')


def _theme_id(row):
    c=row['change']
    key=[topic_key(c['topic']),c['economic_driver']]
    if c['economic_driver']=='UNKNOWN':key.append(row['origin_reference'])
    return sha256(_bytes(key)).hexdigest()


class ThemeStore:
    def __init__(self,root):
        self.root=Path(root)

    def ingest(self, observations, *, now=None, _relation=None):
        at=_when((now or datetime.now(timezone.utc)).isoformat(),'theme decision')
        if not isinstance(observations,list) or len(observations)>1000:
            raise SourceShareError('bounded economic observations required')
        for row in observations:
            _validate_observation(row)
            if _when(row['source_available_at'],'source availability')>at:
                raise SourceShareError('future economic evidence')
        root=_private_root(self.root)
        path=_check_state_path(root/'themes.sqlite3')
        with sqlite3.connect(str(path)) as db:
            db.execute('CREATE TABLE IF NOT EXISTS observations(digest TEXT PRIMARY KEY,theme_id TEXT,payload BLOB,recorded_at TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS versions(digest TEXT PRIMARY KEY,theme_id TEXT,payload BLOB,decision_at TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS supply_graphs(digest TEXT PRIMARY KEY,payload BLOB)')
            db.commit()
            db.execute('BEGIN IMMEDIATE')
            latest=db.execute('SELECT max(decision_at) FROM versions').fetchone()[0]
            if latest and _when(latest,'last decision')>at:
                raise SourceShareError('theme history cannot be backdated')
            changed=set()
            if _relation is not None:
                from .theme_supply_chain import validate_evidence
                validate_evidence(_relation,at)
                cursor=db.execute('INSERT OR IGNORE INTO supply_graphs VALUES(?,?)',
                                  (_relation['payload_sha256'],_bytes(_relation)))
                if cursor.rowcount:
                    changed.update(x[0] for x in db.execute('SELECT DISTINCT theme_id FROM observations'))
            for row in observations:
                raw=_bytes(row);digest=sha256(raw).hexdigest();theme_id=_theme_id(row)
                cursor=db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?)',
                                  (digest,theme_id,raw,at.isoformat()))
                if cursor.rowcount:changed.add(theme_id)
            # Correction targets must already be known in this theme, including
            # targets in this same transaction. Bad corrections roll back together.
            for row in observations:
                if row['supersedes_event_id']:
                    candidates=db.execute('SELECT payload FROM observations WHERE theme_id=?',(_theme_id(row),))
                    if not any(json.loads(x[0])['event_id']==row['supersedes_event_id'] for x in candidates):
                        raise SourceShareError('correction target is not a known same-theme event')
            results=[]
            relations=[json.loads(x[0]) for x in db.execute('SELECT payload FROM supply_graphs ORDER BY digest')]
            for theme_id in sorted(changed):
                rows=[(json.loads(raw),seen) for raw,seen in db.execute(
                    'SELECT payload,recorded_at FROM observations WHERE theme_id=? ORDER BY recorded_at,digest',(theme_id,))]
                previous=db.execute('SELECT payload FROM versions WHERE theme_id=? ORDER BY decision_at DESC,rowid DESC LIMIT 1',(theme_id,)).fetchone()
                previous=json.loads(previous[0]) if previous else None
                result=_snapshot(theme_id,rows,at,previous)
                from .theme_supply_chain import enrich_theme
                enrich_theme(result,relations)
                if previous and _relation is not None:
                    # Unmatched publications do not create theme history noise.
                    if result.get('supply_chain_evidence',[])==previous.get('supply_chain_evidence',[]):
                        continue
                raw=_bytes(result);digest=sha256(raw).hexdigest()
                db.execute('INSERT INTO versions VALUES(?,?,?,?)',(digest,theme_id,raw,at.isoformat()))
                results.append(result)
            return results

    def ingest_supply_graph(self, folder, out_root, expected_sha256, *, graph_version='v2', now=None):
        """Read a completed pinned graph and join matching existing/future events."""
        from .theme_supply_chain import read_evidence
        at=now or datetime.now(timezone.utc)
        relation=read_evidence(folder,out_root,expected_sha256,graph_version=graph_version,now=at)
        return self.ingest([],now=at,_relation=relation)

    def search(self, *, as_of=None, query='', now=None):
        at=_when((as_of or now or datetime.now(timezone.utc)).isoformat(),'as of')
        present=_when((now or datetime.now(timezone.utc)).isoformat(),'now')
        if at>present or not isinstance(query,str) or len(query)>200:
            raise SourceShareError('invalid theme query')
        path=self.root/'themes.sqlite3'
        if not path.exists():return []
        if self.root.resolve()!=self.root or path.is_symlink():
            raise SourceShareError('unsafe theme store')
        # URI read-only: browsing/export cannot create DBs or alter history.
        db=sqlite3.connect('file:'+quote(str(path))+'?mode=ro',uri=True)
        try:
            rows=db.execute('SELECT payload FROM versions WHERE decision_at<=? ORDER BY decision_at,rowid',(at.isoformat(),))
            latest={}
            for raw, in rows:
                row=json.loads(raw);latest[row['theme_id']]=row
            q=normalized(query)
            return [row for _,row in sorted(latest.items()) if not q or q in normalized(json.dumps(row,ensure_ascii=False))]
        finally:db.close()


def _snapshot(theme_id, rows, at, previous):
    events={}
    # Each evidence version remains in source_refs; latest observation resolves
    # same-event state, with conflicts explicitly marked below.
    rank={'OFFICIAL_SOURCE':4,'REPORTED':3,'INFERRED':2,'UNVERIFIED':1,'UNKNOWN':0}
    for row,seen in rows:
        if row['polarity']!='SUPPORT':continue
        old=events.get(row['event_id'])
        if old is None or rank[row['change']['evidence_level']]>rank[old['change']['evidence_level']]:
            events[row['event_id']]=row
    invalid=set()
    conflicts=set()
    for row,_ in rows:
        target=row['supersedes_event_id']
        if row['polarity']=='RETRACT':invalid.add(target)
        if row['polarity']=='CONTRADICT':conflicts.add(target or row['event_id'])
    active=[r for key,r in events.items() if key not in invalid and r['polarity']=='SUPPORT']
    entities=sorted({e for row in active for e in row['change']['entity_ids']})
    industries=sorted({e for row in active for e in row['change']['industry_tags']})
    sources=sorted({r['origin_reference'] for r in active})
    # Counts show distinct claim origins, not a false claim of independent verification.
    reliable=[r for r in active if r['change']['evidence_level'] in {'OFFICIAL_SOURCE','REPORTED'}]
    reliable_entities={e for r in reliable for e in r['change']['entity_ids']}
    if not active and invalid:state='INVALIDATED'
    elif conflicts or invalid:state='WEAKENING'
    elif len(reliable)>=4 and len(reliable_entities)>=3 and len(industries)>=2:state='EXPANDING'
    elif len(reliable)>=3 and len(reliable_entities)>=3:state='EMERGING'
    else:state='CANDIDATE'
    # A new positive event after an invalidation may reactivate the hypothesis.
    if previous and previous['status']=='INVALIDATED' and active and not conflicts:
        state='REACTIVATED'
    elif previous and previous['status']=='REACTIVATED' and active and not conflicts and state=='WEAKENING':
        state='REACTIVATED'
    first=rows[0][0]['change']
    refs=[{'event_id':row['event_id'],'origin_reference':row['origin_reference'],
           'source_url':row['source_url'],'source_id':row['source_id'],
           'source_available_at':row['source_available_at'],'recorded_at':seen,
           'evidence_sha256':row['change']['source_paragraph_sha256'],
           'evidence_level':row['change']['evidence_level'],'action':row['change']['action'],
           'entity_ids':row['change']['entity_ids'],'industry_tags':row['change']['industry_tags'],
           **({'source_binding':row['source_binding']} if 'source_binding' in row else {}),
           'phase':row['change']['phase'],'polarity':row['polarity'],
           'supersedes_event_id':row['supersedes_event_id']} for row,seen in rows]
    history=(previous['history'][:] if previous else [])
    history.append({'status':state,'decision_at':at.isoformat(),'event_count':len(active)})
    return {'schema_version':SCHEMA,'theme_id':theme_id,
        'provisional_name':(previous['provisional_name'] if previous else first['topic']+' · '+DRIVERS[first['economic_driver']]),
        'parent_theme_id':('taxonomy:semiconductor' if topic_key(first['topic']) in {'hbm','dram','nand'} else None),
        'topic_classification':'KNOWN_TOPIC' if topic_key(first['topic']) in KNOWN_TOPICS else 'PROVISIONAL_TOPIC',
        'economic_driver':first['economic_driver'],'status':state,
        'first_detected_at':previous['first_detected_at'] if previous else at.isoformat(),
        'last_evidence_at':max(r['source_available_at'] for r,_ in rows),
        'decision_at':at.isoformat(),'event_ids':sorted(r['event_id'] for r in active),
        'entity_ids':entities,'industry_tags':industries,
        'company_links':[{'entity_id':e,'relation_kind':'THEMATIC_ONLY','evidence_level':'INFERRED',
            'event_ids':sorted(r['event_id'] for r in active if e in r['change']['entity_ids']),
            'revenue_contribution':None} for e in entities],
        'source_refs':refs,'history':history,
        'scores':{'distinct_economic_events':len(active),'distinct_claim_origins':len(sources),
                  'company_breadth':len(entities),'industry_breadth':len(industries),
                  'official_events':sum(r['change']['evidence_level']=='OFFICIAL_SOURCE' for r in active)},
        'source_freshness':{'as_of':at.isoformat(),'last_evidence_at':max(r['source_available_at'] for r,_ in rows)},
        'verified_vs_inferred':'THEME_HYPOTHESIS','verified_beneficiary_count':0,
        'conflicting_event_ids':sorted(conflicts),'invalidated_event_ids':sorted(invalid)}
