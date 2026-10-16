"""Economic event -> provisional theme, immutable PIT history and search.

Dedup uses source claim origin + action/subject, never article count. Theme
membership is an inference; it cannot certify a transaction or benefit.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import re
from urllib.parse import urlsplit, quote

from .economic_changes import DRIVERS, TOPIC_ALIASES, normalized, explicit_topic_aliases, policy_causes, policy_cause_key, investment_project, parse_demand_scope, market_entry, product_price_cause, demand_recovery_cause
from .evidence_archive import _private_root
from .incremental_ingest import _check_state_path
from .source_share import SourceShareError, _when, _must_sha

SCHEMA = 'newscatalyst.theme_candidate.v1'
RELATION_SCHEMA = 'newscatalyst.theme_candidate.v2'
QUALITIES = {'OFFICIAL_SOURCE','REPORTED','INFERRED','UNVERIFIED','UNKNOWN'}
ACTIONS = {'POLICY_CHANGE','PRODUCTION_START','CAPACITY_ADDITION','SUPPLY_REDUCTION','CONTRACT','INVESTMENT','INVESTMENT_EXECUTION','BUSINESS_START','CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY','SUPPLY_RESUMPTION'}
KNOWN_TOPICS = {'euv','duv','hbm','dram','nand','반도체','액침냉각'}
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


def validate_alias_evidence(proof,topic):
    if (not isinstance(proof,dict) or set(proof)!={'canonical_topic','abbreviation','source_expression','expression_sha256'}
            or not _text(proof['source_expression'],100)
            or proof not in explicit_topic_aliases(proof['source_expression'])
            or normalized(topic) not in {normalized(proof['canonical_topic']),normalized(proof['abbreviation'])}):
        raise SourceShareError('invalid explicit topic alias evidence')


def validate_policy_cause(proof, topic):
    if not isinstance(proof,dict) or not _text(proof.get('source_expression'),200):
        raise SourceShareError('invalid reported policy cause')
    parsed=policy_causes(proof['source_expression'])
    if len(parsed)!=1 or parsed[0][0]!=topic or parsed[0][2]!=proof:
        raise SourceShareError('policy cause does not match source expression')


def validate_investment_project(proof, action):
    if (not isinstance(proof,dict) or not _text(proof.get('source_expression'),120)
            or investment_project(proof['source_expression'],action)!=proof):
        raise SourceShareError('invalid explicit investment project')


def validate_demand_scope(proof, topic, driver):
    if (not isinstance(proof,dict) or not _text(proof.get('source_expression'),240)
            or parse_demand_scope(proof['source_expression'])!=(topic,driver,proof)):
        raise SourceShareError('invalid source demand scope')


def _demand_key(row):
    proof=row['change'].get('demand_scope')
    if not proof:return ()
    return ('DEMAND_SCOPE',normalized(proof['destination']) if proof['status']=='EXPLICIT' else row['event_id'])


def validate_market_entry(proof, action):
    if (action!='MARKET_ENTRY' or not isinstance(proof,dict)
            or not _text(proof.get('source_expression'),120)
            or market_entry(proof['source_expression'])!=proof):
        raise SourceShareError('invalid reported market entry')


def validate_product_price(proof,topic,driver):
    if (driver not in {'PRODUCT_PRICE_INCREASE','PRODUCT_PRICE_DECREASE'} or not isinstance(proof,dict)
            or not _text(proof.get('source_expression'),160)
            or product_price_cause(proof['source_expression'])!=proof or proof['product']!=topic
            or driver!='PRODUCT_PRICE_'+proof['change']):
        raise SourceShareError('invalid reported product price cause')


def validate_demand_recovery(proof,topic,driver,action):
    if (driver!='DEMAND_RECOVERY' or action!='SUPPLY_RESUMPTION' or not isinstance(proof,dict)
            or not _text(proof.get('source_expression'),160)
            or demand_recovery_cause(proof['source_expression'])!=proof or proof['product']!=topic):
        raise SourceShareError('invalid reported demand/order recovery cause')


def validate_change(change):
    if (not isinstance(change,dict) or set(change)-{'original_entity_ids','service_name','extraction_method','topic_alias_evidence','policy_cause','investment_project','demand_scope','market_entry','product_price_cause','demand_recovery_cause'}!=CHANGE_KEYS
            or not _text(change['topic'],80) or change['economic_driver'] not in DRIVERS
            or change['action'] not in ACTIONS or change['evidence_level'] not in QUALITIES
            or change['phase'] not in {'SOURCE_REPORTED','ADOPTED_NOT_YET_EFFECTIVE','PLANNED'}
            or change['verified_economic_effect'] is not False):
        raise SourceShareError('invalid source economic change')
    if change['economic_driver'] in {'PRODUCT_PRICE_INCREASE','PRODUCT_PRICE_DECREASE'} or 'product_price_cause' in change:
        validate_product_price(change.get('product_price_cause'),change['topic'],change['economic_driver'])
    if change['economic_driver']=='DEMAND_RECOVERY' or 'demand_recovery_cause' in change:
        validate_demand_recovery(change.get('demand_recovery_cause'),change['topic'],change['economic_driver'],change['action'])
    if change['action']=='MARKET_ENTRY' or 'market_entry' in change:
        validate_market_entry(change.get('market_entry'),change['action'])
    if 'demand_scope' in change:validate_demand_scope(change['demand_scope'],change['topic'],change['economic_driver'])
    if 'investment_project' in change:validate_investment_project(change['investment_project'],change['action'])
    if 'extraction_method' in change and change['extraction_method']!='AI_SOURCE_SPAN_MATCHED':
        raise SourceShareError('unsupported economic extraction method')
    if 'service_name' in change and (change['action']!='BUSINESS_START'
            or not _text(change['service_name'],80)):
        raise SourceShareError('invalid explicit service name')
    for field in ('entity_ids','industry_tags'):
        if (not isinstance(change[field],list) or len(change[field])>30
                or any(not _text(x) for x in change[field])):
            raise SourceShareError('invalid economic entities/tags')
    if 'original_entity_ids' in change:
        original=change['original_entity_ids']
        if (not isinstance(original,list) or len(original)>30
                or any(not _text(x) or x not in change['entity_ids'] for x in original)):
            raise SourceShareError('invalid original economic entities')
    _must_sha(change['source_paragraph_sha256'],'economic evidence')
    if 'topic_alias_evidence' in change:validate_alias_evidence(change['topic_alias_evidence'],change['topic'])
    if 'policy_cause' in change:
        validate_policy_cause(change['policy_cause'],change['topic'])
        if change['economic_driver']!='POLICY_ENABLEMENT' or change['action'] not in {
                'CONTRACT','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT','INVESTMENT_EXECUTION','CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY'}:
            raise SourceShareError('policy cause must describe a corporate response')


def topic_key(topic):
    key=normalized(topic)
    return next((normalized(name) for name,aliases in TOPIC_ALIASES.items()
                 if key in {normalized(alias) for alias in aliases}),key)


def theme_presentation(theme):
    """Read-only label from this snapshot's active source refs, never a rename."""
    at=_when(theme['decision_at'],'theme display decision')
    active=set(theme['event_ids'])-set(theme['invalidated_event_ids'])
    scopes={}
    for ref in theme['source_refs']:
        proof=ref.get('policy_cause')
        if (not proof or ref['event_id'] not in active or ref['polarity']!='SUPPORT'
                or _when(ref['recorded_at'],'recorded')>at
                or _when(ref['source_available_at'],'source')>at):continue
        validate_policy_cause(proof,ref['topic'])
        label=' · '.join((proof['jurisdiction'] or '관할 미확인',
                         proof['policy_name'] or '정책명 미확인',
                         *((['수출 목적지 '+proof['destination']] if 'destination' in proof else [])),
                         proof['restriction']+' '+proof['change']))
        scopes[(ref['topic'],label)]={'topic':ref['topic'],'label':label}
    labels=[scopes[key] for key in sorted(scopes)]
    name=(' / '.join(x['topic']+' · '+x['label'] for x in labels)+' · '+DRIVERS[theme['economic_driver']]
          if labels else theme['provisional_name'])
    return {'name':name,'stored_name':theme['provisional_name'],
            'policy_scopes':labels,'as_of':theme['decision_at']}



def economic_observation(change, *, origin_reference, source_url, source_id,
                         source_available_at, polarity='SUPPORT', supersedes_event_id=None,
                         source_binding=None, company_mappings=None, content_scope=None):
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
              change['action'],sorted(set(change.get('original_entity_ids',change['entity_ids'])))]
    # Identical title claims at multiple URLs are one observation candidate;
    # they cannot multiply an economic event or prove independent reporting.
    # This does not infer a publisher's original release URL.
    if content_scope=='RSS_TITLE_METADATA':
        identity[0]=['RSS_TITLE_METADATA',change['source_paragraph_sha256']]
    if 'policy_cause' in change:identity.append(policy_cause_key(change['policy_cause']))
    if 'market_entry' in change:identity.append(['MARKET_ENTRY',normalized(change['market_entry']['market_name'])])
    result = {'event_id':sha256(_bytes(identity)).hexdigest(),'change':change,
            'origin_reference':origin_reference,'source_url':source_url,'source_id':source_id,
            'source_available_at':source_available_at,'polarity':polarity,
            'supersedes_event_id':supersedes_event_id}
    if content_scope is not None:
        if content_scope not in {'RSS_TITLE_METADATA','LICENSED_ARTICLE_TEXT'}:
            raise SourceShareError('invalid economic evidence scope')
        if content_scope=='RSS_TITLE_METADATA' and change['evidence_level']!='REPORTED':
            raise SourceShareError('RSS title is a reported claim')
        result['content_scope']=content_scope
    if source_binding is not None:
        if not isinstance(source_binding,dict) or set(source_binding)!={'source_event_sha256','document_sha256'}:
            raise SourceShareError('invalid theme source binding')
        for key,value in source_binding.items():_must_sha(value,key)
        result['source_binding']=dict(source_binding)
    if company_mappings is not None:
        if source_binding is None or not isinstance(company_mappings,list) or len(company_mappings)>30:
            raise SourceShareError('document-bound company mappings required')
        names=set()
        for mapping in company_mappings:
            if (not isinstance(mapping,dict) or set(mapping)!={'source_name','entity_id','evidence_sha256'}
                    or mapping['source_name'] not in change['entity_ids']
                    or mapping['source_name'] in names
                    or not isinstance(mapping['entity_id'],str)
                    or not re.fullmatch(r'(?:SEC_CIK:[0-9]{1,10}|DART_CORP:[0-9]{8}|KRX_STOCK:[0-9]{6})',mapping['entity_id'])):
                raise SourceShareError('invalid or ambiguous company mapping')
            _must_sha(mapping['evidence_sha256'],'company identity evidence')
            names.add(mapping['source_name'])
        result['company_mappings']=[dict(m) for m in company_mappings]
    return result


def _validate_observation(row):
    if not isinstance(row,dict) or set(row)-{'source_binding','company_mappings','content_scope'}!={'event_id','change','origin_reference','source_url',
            'source_id','source_available_at','polarity','supersedes_event_id'}:
        raise SourceShareError('economic observation contract required')
    rebuilt=economic_observation(row['change'],**{k:row[k] for k in row if k not in {'change','event_id'}})
    if rebuilt!=row:raise SourceShareError('economic event identity mismatch')


def _theme_id(row):
    c=row['change']
    key=[topic_key(c.get('topic_alias_evidence',{}).get('canonical_topic',c['topic'])),c['economic_driver']]
    if 'policy_cause' in c:
        proof=c['policy_cause']
        # A named law does not identify the same individual permit for two actors.
        key.append(['REPORTED_POLICY',policy_cause_key(proof)]
                   if proof['policy_name'] and proof['jurisdiction'] and not proof['restriction'].endswith('허가') else row['event_id'])
    if 'demand_scope' in c:key.append(_demand_key(row))
    if c['economic_driver']=='UNKNOWN':
        key.append(row['event_id'] if row.get('content_scope')=='RSS_TITLE_METADATA'
                   else row['origin_reference'])
    return sha256(_bytes(key)).hexdigest()


def resolved_entities(row):
    mappings={m['source_name']:m['entity_id'] for m in row.get('company_mappings',[])}
    return sorted({mappings.get(name,name) for name in row['change']['entity_ids']})


def _service_key(row):
    """Exact source-named service and sole identified company, never similarity."""
    change=row['change']
    name=normalized(change.get('service_name',''))
    entities=resolved_entities(row)
    if (row['polarity']!='SUPPORT' or change['action']!='BUSINESS_START'
            or change['evidence_level'] not in {'REPORTED','OFFICIAL_SOURCE'}
            or not name or len(entities)!=1
            or name in {normalized(x) for x in ('AI','인공지능','신규','맞춤','서비스',*KNOWN_TOPICS)}):
        return None
    return (name,tuple(entities),topic_key(change['topic']),change['economic_driver'],
            tuple(sorted(change['industry_tags'])))+_demand_key(row)


def _investment_key(row):
    change=row['change'];proof=change.get('investment_project')
    entities=resolved_entities(row)
    if (not proof or row['polarity']!='SUPPORT' or len(entities)!=1
            or change['action'] not in {'INVESTMENT','INVESTMENT_EXECUTION'}
            or change['evidence_level'] not in {'REPORTED','OFFICIAL_SOURCE'}):return None
    return (normalized(proof['project_name']),tuple(entities),topic_key(change['topic']),
            change['economic_driver'],tuple(sorted(change['industry_tags'])),
            tuple(policy_cause_key(change['policy_cause'])) if 'policy_cause' in change else None)+_demand_key(row)


def _investment_pairs(rows):
    return _stage_pairs(rows,_investment_key,
        lambda c:c['action']=='INVESTMENT' and c['phase']=='SOURCE_REPORTED',
        lambda c:c['action']=='INVESTMENT_EXECUTION' and c['phase']=='SOURCE_REPORTED')


def _service_pairs(rows):
    return _stage_pairs(rows,_service_key,lambda c:c['phase']=='PLANNED',
                        lambda c:c['phase']=='SOURCE_REPORTED')


def _stage_pairs(rows,key_fn,first_stage,next_stage):
    blocked={r['supersedes_event_id'] or r['event_id'] for r in rows
             if r['polarity'] in {'RETRACT','CONTRADICT'}}
    groups={}
    for row in rows:
        key=key_fn(row)
        if key is not None and row['event_id'] not in blocked:
            group=groups.setdefault(key,{})
            old=group.get(row['event_id'])
            # A later republication cannot move the original plan after its
            # start. Preserve the earliest availability within the same phase.
            if (old is None or
                    (old['change']['phase']==row['change']['phase'] and
                     _when(row['source_available_at'],'source')<_when(old['source_available_at'],'source')) or
                    (old['change']['phase']!=row['change']['phase'] and
                     _when(row['source_available_at'],'source')>_when(old['source_available_at'],'source'))):
                group[row['event_id']]=row
    pairs=[]
    for group in groups.values():
        plans=[r for r in group.values() if first_stage(r['change'])]
        starts=[r for r in group.values() if next_stage(r['change'])]
        # Multiple plans/starts could be separate regions or versions. Without
        # an explicit disambiguator retain each observation independently.
        if (len(plans)==len(starts)==1 and plans[0]['event_id']!=starts[0]['event_id']
                and _when(plans[0]['source_available_at'],'plan source') <
                    _when(starts[0]['source_available_at'],'start source')):
            pairs.append((plans[0],starts[0]))
    return pairs


def period_activity(theme, since):
    """Classify the selected PIT snapshot, never a future/latest live version."""
    if _when(theme['first_detected_at'],'theme first detection')>=since:return 'new'
    if _when(theme['decision_at'],'theme last update')>=since:return 'updated'
    return 'unchanged'


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
            observation_changed=set()
            if _relation is not None:
                from .theme_supply_chain import validate_evidence
                validate_evidence(_relation,at)
                cursor=db.execute('INSERT OR IGNORE INTO supply_graphs VALUES(?,?)',
                                  (_relation['payload_sha256'],_bytes(_relation)))
                if cursor.rowcount:
                    changed.update(x[0] for x in db.execute('SELECT DISTINCT theme_id FROM observations'))
            stored=[(json.loads(raw),theme) for raw,theme in
                    db.execute('SELECT payload,theme_id FROM observations ORDER BY recorded_at,rowid')]
            assignments={row['event_id']:theme for row,theme in stored}
            pairs=_service_pairs([row for row,_ in stored]+observations)+_investment_pairs([row for row,_ in stored]+observations)
            for plan,start in pairs:
                plan_theme=assignments.get(plan['event_id'],_theme_id(plan))
                # Existing theme IDs/history are never moved or overwritten.
                if start['event_id'] not in assignments:
                    assignments[start['event_id']]=plan_theme
            for row in observations:
                raw=_bytes(row);digest=sha256(raw).hexdigest()
                theme_id=assignments.get(row['event_id'],_theme_id(row))
                cursor=db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?)',
                                  (digest,theme_id,raw,at.isoformat()))
                if cursor.rowcount:
                    changed.add(theme_id)
                    observation_changed.add(theme_id)
            # Correction targets must already be known in this theme, including
            # targets in this same transaction. Bad corrections roll back together.
            for row in observations:
                if row['supersedes_event_id']:
                    candidates=db.execute('SELECT payload FROM observations WHERE theme_id=?',(assignments.get(row['event_id'],_theme_id(row)),))
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
                if previous and _relation is not None and theme_id not in observation_changed:
                    # Unmatched publications do not create theme history noise.
                    if result.get('supply_chain_evidence',[])==previous.get('supply_chain_evidence',[]):
                        continue
                raw=_bytes(result);digest=sha256(raw).hexdigest()
                db.execute('INSERT INTO versions VALUES(?,?,?,?)',(digest,theme_id,raw,at.isoformat()))
                results.append(result)
            return results

    def ingest_supply_graph(self, folder, out_root, expected_sha256, *, graph_version='v2', now=None,
                            observations=None):
        """Read a completed pinned graph and join matching existing/future events."""
        from .theme_supply_chain import read_evidence
        at=now or datetime.now(timezone.utc)
        relation=read_evidence(folder,out_root,expected_sha256,graph_version=graph_version,now=at)
        return self.ingest(observations or [],now=at,_relation=relation)

    def search(self, *, as_of=None, query='', now=None, since=None, activity='all'):
        at=_when((as_of or now or datetime.now(timezone.utc)).isoformat(),'as of')
        present=_when((now or datetime.now(timezone.utc)).isoformat(),'now')
        if at>present or not isinstance(query,str) or len(query)>200:
            raise SourceShareError('invalid theme query')
        if activity not in {'all','changed','new','updated'}:
            raise SourceShareError('invalid theme activity filter')
        start=_when(since.isoformat(),'period start') if since is not None else None
        if (activity!='all' and start is None) or (start is not None and start>at):
            raise SourceShareError('valid theme period start required')
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
            queries={normalized(query),topic_key(query)}
            selected=[row for row in latest.values()
                if (activity=='all' or period_activity(row,start) in ({'new','updated'} if activity=='changed' else {activity}))
                and any(q in normalized(json.dumps(row,ensure_ascii=False)+' '+theme_presentation(row)['name'])
                        for q in queries)]
            # Show the most recently changed candidates first, stably on ties.
            return sorted(selected,key=lambda row:(row['decision_at'],row['theme_id']),reverse=True)
        finally:db.close()

    def period_versions(self, *, since, as_of, now=None):
        """One consistent read: latest pre-period version plus in-period versions."""
        start=_when(since.isoformat(),'period start')
        end=_when(as_of.isoformat(),'period end')
        present=_when((now or datetime.now(timezone.utc)).isoformat(),'now')
        if start>end or end>present:raise SourceShareError('invalid theme comparison period')
        path=self.root/'themes.sqlite3'
        if not path.exists():return {}
        if self.root.resolve()!=self.root or path.is_symlink():raise SourceShareError('unsafe theme store')
        db=sqlite3.connect('file:'+quote(str(path))+'?mode=ro',uri=True)
        try:
            versions={}
            for digest,theme_id,raw,decision in db.execute(
                    'SELECT digest,theme_id,payload,decision_at FROM versions WHERE decision_at<=? ORDER BY decision_at,rowid',
                    (end.isoformat(),)):
                if sha256(raw).hexdigest()!=digest:raise SourceShareError('theme version SHA mismatch')
                row=json.loads(raw)
                if row['theme_id']!=theme_id or row['decision_at']!=decision:
                    raise SourceShareError('theme version metadata mismatch')
                group=versions.setdefault(theme_id,[])
                if _when(decision,'version decision')<start:group[:]=[row]
                else:group.append(row)
            return versions
        finally:db.close()


def _snapshot(theme_id, rows, at, previous):
    events={}
    # Each evidence version remains in source_refs; latest observation resolves
    # same-event state, with conflicts explicitly marked below.
    rank={'OFFICIAL_SOURCE':4,'REPORTED':3,'INFERRED':2,'UNVERIFIED':1,'UNKNOWN':0}
    for row,seen in rows:
        if row['polarity']!='SUPPORT':continue
        old=events.get(row['event_id'])
        quality=lambda r:(rank[r['change']['evidence_level']],len(r.get('company_mappings',[])),len(r['change']['entity_ids']))
        if old is None or quality(row)>=quality(old):
            events[row['event_id']]=row
    invalid=set()
    conflicts=set()
    for row,_ in rows:
        target=row['supersedes_event_id']
        if row['polarity']=='RETRACT':invalid.add(target)
        if row['polarity']=='CONTRADICT':conflicts.add(target or row['event_id'])
    active=[r for key,r in events.items() if key not in invalid and r['polarity']=='SUPPORT']
    active_by_id={r['event_id']:r for r in active}
    pairs=_service_pairs([r for r,_ in rows if r['event_id'] in active_by_id
        and r['event_id'] not in conflicts
        and r['change']['phase']==active_by_id[r['event_id']]['change']['phase']
        and _service_key(r)==_service_key(active_by_id[r['event_id']])])
    followups=[{'planned_event_id':plan['event_id'],'realization_event_id':start['event_id'],
        'service_name':start['change']['service_name'],'entity_ids':resolved_entities(start),
        'status':'SOURCE_REPORTED_REALIZATION','is_realization_confirmed':False,
        'decision_at':at.isoformat(),
        'evidence_sha256':[plan['change']['source_paragraph_sha256'],start['change']['source_paragraph_sha256']]}
        for plan,start in pairs]
    investment_pairs=_investment_pairs([r for r,_ in rows if r['event_id'] in active_by_id
        and r['event_id'] not in conflicts
        and r['change']['phase']==active_by_id[r['event_id']]['change']['phase']
        and _investment_key(r)==_investment_key(active_by_id[r['event_id']])])
    investment_links=[{'decision_event_id':decision['event_id'],'execution_event_id':execution['event_id'],
        'project_name':execution['change']['investment_project']['project_name'],
        'entity_ids':resolved_entities(execution),'status':'SOURCE_REPORTED_EXECUTION',
        'is_execution_confirmed':False,'decision_at':at.isoformat(),
        'sources':[{'event_id':r['event_id'],'source_url':r['source_url'],
                    'evidence_sha256':r['change']['source_paragraph_sha256'],
                    'project_evidence':r['change']['investment_project']} for r in (decision,execution)]}
        for decision,execution in investment_pairs]
    realized_plans={plan['event_id'] for plan,_ in pairs+investment_pairs}
    independent=[r for r in active if r['event_id'] not in realized_plans]
    entities=sorted({e for row in active for e in resolved_entities(row)})
    industries=sorted({e for row in active for e in row['change']['industry_tags']})
    sources=sorted({r['origin_reference'] for r in active})
    # Counts show distinct claim origins, not a false claim of independent verification.
    reliable=[r for r in independent if r['change']['evidence_level'] in {'OFFICIAL_SOURCE','REPORTED'}]
    reliable_entities={e for r in reliable for e in resolved_entities(r)}
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
    display_topic=first.get('topic_alias_evidence',{}).get('canonical_topic',first['topic'])
    aliases=next((list(aliases) for name,aliases in TOPIC_ALIASES.items()
                  if topic_key(name)==topic_key(display_topic)),[display_topic])
    for event in active:
        proof=event['change'].get('topic_alias_evidence')
        if proof and topic_key(proof['canonical_topic'])==topic_key(display_topic):
            aliases.extend(n for n in (proof['canonical_topic'],proof['abbreviation']) if n not in aliases)
    refs=[{'event_id':row['event_id'],'origin_reference':row['origin_reference'],
           'source_url':row['source_url'],'source_id':row['source_id'],
           'source_available_at':row['source_available_at'],'recorded_at':seen,
           'evidence_sha256':row['change']['source_paragraph_sha256'],
           'evidence_level':row['change']['evidence_level'],'action':row['change']['action'],
           **({'extraction_method':row['change']['extraction_method']} if 'extraction_method' in row['change'] else {}),
           'topic':row['change']['topic'],'economic_driver':row['change']['economic_driver'],
           'entity_ids':resolved_entities(row),'industry_tags':row['change']['industry_tags'],
           **({'company_mappings':row['company_mappings']} if 'company_mappings' in row else {}),
           **({'source_binding':row['source_binding']} if 'source_binding' in row else {}),
           **({'content_scope':row['content_scope']} if 'content_scope' in row else {}),
           **({'investment_project':row['change']['investment_project']} if 'investment_project' in row['change'] else {}),
           **({'demand_scope':row['change']['demand_scope']} if 'demand_scope' in row['change'] else {}),
           **({'market_entry':row['change']['market_entry']} if 'market_entry' in row['change'] else {}),
           **({'demand_recovery_cause':row['change']['demand_recovery_cause']} if 'demand_recovery_cause' in row['change'] else {}),
           **({'product_price_cause':row['change']['product_price_cause']} if 'product_price_cause' in row['change'] else {}),
           **({'service_name':row['change']['service_name']} if 'service_name' in row['change'] else {}),
           **({'topic_alias_evidence':row['change']['topic_alias_evidence']} if 'topic_alias_evidence' in row['change'] else {}),
           **({'policy_cause':row['change']['policy_cause']} if 'policy_cause' in row['change'] else {}),
           'phase':row['change']['phase'],'polarity':row['polarity'],
           'supersedes_event_id':row['supersedes_event_id']} for row,seen in rows]
    history=(previous['history'][:] if previous else [])
    history.append({'status':state,'decision_at':at.isoformat(),'event_count':len(independent)})
    return {'schema_version':SCHEMA,'theme_id':theme_id,
        'provisional_name':(previous['provisional_name'] if previous else display_topic+' · '+
            ((first['policy_cause']['policy_name'] or '정책명 미확인')+' · ' if 'policy_cause' in first else '')+
            ((first['demand_scope']['destination']+'용' if first['demand_scope']['status']=='EXPLICIT' else '수요처 범위 미확인')+' · ' if 'demand_scope' in first else '')+
            DRIVERS[first['economic_driver']]),
        'parent_theme_id':('taxonomy:semiconductor' if topic_key(first['topic']) in {'hbm','dram','nand','euv','duv'} else None),
        'topic_classification':'KNOWN_TOPIC' if topic_key(first['topic']) in KNOWN_TOPICS else 'PROVISIONAL_TOPIC',
        'topic_aliases':aliases,
        'economic_driver':first['economic_driver'],'status':state,
        'first_detected_at':previous['first_detected_at'] if previous else at.isoformat(),
        'last_evidence_at':max(r['source_available_at'] for r,_ in rows),
        'decision_at':at.isoformat(),'event_ids':sorted(r['event_id'] for r in active),
        'entity_ids':entities,'industry_tags':industries,
        'company_links':[{'entity_id':e,'relation_kind':'THEMATIC_ONLY','evidence_level':'INFERRED',
            'event_ids':sorted(r['event_id'] for r in active if e in resolved_entities(r)),
            'revenue_contribution':None} for e in entities],
        'source_refs':refs,'history':history,
        **({'investment_stage_links':investment_links} if investment_links else {}),
        **({'event_followups':followups} if followups else {}),
        'scores':{'distinct_economic_events':len(independent),'distinct_claim_origins':len(sources),
                  'company_breadth':len(entities),'industry_breadth':len(industries),
                  'official_events':sum(r['change']['evidence_level']=='OFFICIAL_SOURCE' for r in independent)},
        'source_freshness':{'as_of':at.isoformat(),'last_evidence_at':max(r['source_available_at'] for r,_ in rows)},
        'verified_vs_inferred':'THEME_HYPOTHESIS','verified_beneficiary_count':0,
        'conflicting_event_ids':sorted(conflicts),'invalidated_event_ids':sorted(invalid)}
