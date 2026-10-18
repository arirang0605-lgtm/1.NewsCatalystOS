"""Compare saved recent news with earlier source-bound reading analyses.

Only bounded analyst paraphrases/classifications are stored. A completed title
snapshot authenticates the recent article identity, not its body's claims.
No article bodies, event merges, market novelty scores or company alias rules.
"""
from datetime import datetime,timezone,date
from hashlib import sha256
import os,re,tempfile
from .theme_emergence import _bytes
from .source_share import SourceShareError,_json,_when
from .official_relation_intake import _private_input
from .public_demand_analysis import BIND,FACTOR_LABELS,MARKET_LABELS,_text,read_notes,sources_from_outlook,_folder
from .provider_registry import parse_provider_registry
from .federated_news_search import search_completed_workspaces

SCHEMA='newscatalyst.recent_theme_followup.v1'
SCHEMA_V2='newscatalyst.recent_theme_followup.v2'
SCHEMA_V3='newscatalyst.recent_theme_followup.v3'
from .execution_evidence import validate_execution,bind_anchor,attach_anchor,summarize_execution
RECENT_FIELDS={'search_scope','provider_id','event_id','title_sha256','headline','source_url','triage_evidence_sha256'}
FIELDS={'baseline_note_id','recent_source','reported_date','evidence_kind','factor_codes',
        'market_codes','analysis_text','limitation','source_location','product_scope'}
KINDS={
 'REPORTED_CONTRACT':'신규 계약 보도',
 'REPORTED_CAPACITY_OPERATION':'생산 능력 가동 보도',
 'CONDITIONAL_FRAMEWORK':'후속 발주가 필요한 기본 공급계약',
 'PLAN_ONLY':'계획·완료 미확인',
 'DEMAND_REDUCTION':'수요 감소 보도',
 'CANCELLATION':'취소 보도',
 'CONTEXT_ONLY':'배경·누적 실적 설명','REPORTED_ORDER_PERFORMANCE':'수주·매출 실적 보도',
 'REPORTED_DELIVERY':'납품 완료 보도','REPORTED_DELAY':'납품 지연 보도','RISK_ONLY':'위험·반론 설명'}
STATUS_LABELS={'SUPPORT_ADDED':'강화 근거 추가','CONDITIONAL_SUPPORT_ONLY':'조건부 강화 근거만 추가',
 'WEAKENING_EVIDENCE':'약화 근거 추가','MIXED_EVIDENCE':'강화·약화 근거 혼재',
 'NO_SUBSTANTIVE_CHANGE':'실질 변화 근거 미확보'}
POSITIVE={'REPORTED_CONTRACT','REPORTED_CAPACITY_OPERATION','REPORTED_ORDER_PERFORMANCE','REPORTED_DELIVERY'}
NEGATIVE={'DEMAND_REDUCTION','CANCELLATION'}
ENTRY_FIELDS={'schema','note','available_at','baseline_available_at','recent_available_at',
              'source_text_stored','source_truth_verified'}

def _validate(note,*,allow_undated=False):
    if not isinstance(note,dict) or set(note) not in (FIELDS,FIELDS|{'execution'}):
        raise SourceShareError('exact bounded follow-up fields required; no source text')
    if not re.fullmatch('[0-9a-f]{64}',str(note['baseline_note_id'])):
        raise SourceShareError('exact baseline note required')
    if 'execution' in note:validate_execution(note)
    elif note['evidence_kind'] not in {'REPORTED_CONTRACT','REPORTED_CAPACITY_OPERATION','CONDITIONAL_FRAMEWORK','PLAN_ONLY','DEMAND_REDUCTION','CANCELLATION','CONTEXT_ONLY'}:
        raise SourceShareError('new execution kind requires versioned comparison')
    r=note['recent_source']
    if not isinstance(r,dict) or set(r)!=RECENT_FIELDS:
        raise SourceShareError('exact completed recent title required')
    for k in RECENT_FIELDS:
        if not _text(r[k],2048 if k=='source_url' else 512):
            raise SourceShareError('invalid recent source')
    for k in ('event_id','title_sha256','triage_evidence_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',r[k]):raise SourceShareError('invalid recent source digest')
    if note['evidence_kind'] not in KINDS:raise SourceShareError('invalid evidence kind')
    for k,limit in [('analysis_text',300),('limitation',240),('source_location',100),('product_scope',100)]:
        if not _text(note[k],limit):raise SourceShareError('bounded follow-up paraphrase required')
    if note['reported_date'] is None and allow_undated and 'execution' in note:
        pass  # Collection time must never be substituted for an absent page date.
    else:
        if not isinstance(note['reported_date'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',note['reported_date']):
            raise SourceShareError('reported page date required')
        date.fromisoformat(note['reported_date'])
    for k,allowed in [('factor_codes',FACTOR_LABELS),('market_codes',MARKET_LABELS)]:
        values=note[k]
        if (not isinstance(values,list) or not 1<=len(values)<=len(allowed)
                or any(v not in allowed for v in values) or len(set(values))!=len(values)):
            raise SourceShareError('invalid follow-up classification')

def metadata_resolver(workspaces,*,now):
    """Current approvals/checkpoint/SHA + earliest completed availability, no HTTP."""
    cache={}
    def resolve(recent):
        identity=(recent['provider_id'],recent['event_id'],recent['title_sha256'])
        key=(recent['search_scope'],*identity)
        if key not in cache:
            result=search_completed_workspaces(tuple(workspaces),recent['headline'][:80],
                registry_reader=lambda p:parse_provider_registry(_private_input(p,32768),now=now),
                exact_identity=identity,exact_source_only=True,limit=1,now=now)
            rows=result['results']
            cache[key]=rows[0] if len(rows)==1 else None
        row=cache[key]
        if row is None or any(row[k]!=recent[k] for k in RECENT_FIELDS):
            raise SourceShareError('recent article no longer matches completed approved metadata')
        return row
    return resolve

def _bound(note,baselines,resolve,at):
    baseline=baselines.get(note['baseline_note_id'])
    if baseline is None:raise SourceShareError('active baseline reading note required')
    row=resolve(note['recent_source'])
    if (_when(row['source_available_at'],'recent availability')>at
            or _when(baseline['available_at'],'baseline availability')>at):
        raise SourceShareError('follow-up source not yet available')
    if note['reported_date'] is not None and date.fromisoformat(note['reported_date'])>at.date():
        raise SourceShareError('future reported page date')
    old=baseline['note']
    if (old['provider_id'],old['source_event_sha256'],old['source_title_sha256'])==(
            row['provider_id'],row['event_id'],row['title_sha256']):
        raise SourceShareError('baseline article is not new follow-up evidence')
    return baseline,row

def _store(root,create=False):
    parent=_folder(root,create=create).parent
    path=parent/'recent_followups'
    if create:path.mkdir(mode=0o700,exist_ok=True)
    if path.exists() and (path.resolve()!=path or path.stat().st_mode & 0o077):
        raise SourceShareError('owner-only follow-up store required')
    return path

def read_followups(root,baselines,resolve,*,as_of,now):
    at=_when(as_of.isoformat(),'follow-up as of')
    if at>_when(now.isoformat(),'follow-up now'):raise SourceShareError('future follow-up query')
    paths=sorted(_store(root).glob('*.json'))
    if len(paths)>200:raise SourceShareError('follow-up store limit')
    latest={};valid=[]
    for path in paths:
        raw=_private_input(path,8192)
        if path.stem!=sha256(raw).hexdigest():raise SourceShareError('follow-up digest mismatch')
        entry=_json(raw,'recent follow-up');note=entry.get('note')
        if (set(entry)!=ENTRY_FIELDS or entry['schema'] not in {SCHEMA,SCHEMA_V2,SCHEMA_V3}
                or entry['source_text_stored'] is not False or entry['source_truth_verified'] is not False):
            raise SourceShareError('invalid follow-up envelope')
        _validate(note,allow_undated=entry['schema']==SCHEMA_V3)
        if (entry['schema'] in {SCHEMA_V2,SCHEMA_V3})!=('execution' in note):raise SourceShareError('follow-up version mismatch')
        available=_when(entry['available_at'],'follow-up availability')
        if available<max(_when(entry[k],k) for k in ('baseline_available_at','recent_available_at')):
            raise SourceShareError('follow-up predates evidence')
        if available>at:continue
        try:base,row=_bound(note,baselines,resolve,at)
        except (SourceShareError,OSError,ValueError):continue
        if (entry['baseline_available_at']!=base['available_at']
                or entry['recent_available_at']!=row['source_available_at']):continue
        # One interpretation per company and canonical article. Revisions,
        # repeated input and cross-provider copies cannot become extra votes.
        company=base['note']['source_company']
        key=(company,row['source_url'])
        value={**entry,'note_id':path.stem,'analysis_fingerprint':sha256(_bytes(note)).hexdigest(),
               'source_company':company,'baseline_headline':base['source_headline'],
               'baseline_analysis':base['note']['analysis_text'],'baseline_source_url':base['note']['source_url'],
               'baseline_factor_codes':[f['code'] for f in base['note']['factors']]}
        valid.append((key,value))
    current_anchors={}
    for key,r in valid:
        if 'execution' not in r['note'] and (key not in current_anchors or
                (r['available_at'],r['note_id'])>(current_anchors[key]['available_at'],current_anchors[key]['note_id'])):
            current_anchors[key]=r
    anchors={r['note_id']:r for r in current_anchors.values()}
    for key,value in valid:
        if 'execution' in value['note']:
            try:
                anchor=bind_anchor(value['note'],value['source_company'],anchors,_when(value['available_at'],'follow-up availability'))
                value=attach_anchor(value,anchor)
            except (SourceShareError,ValueError):continue
        if key not in latest or (value['available_at'],value['note_id'])>(latest[key]['available_at'],latest[key]['note_id']):
            latest[key]=value
    return sorted(latest.values(),key=lambda r:(r['note']['reported_date'] or '',r['source_company']))

def publish_followups(root,document,baselines,resolve,*,now=None):
    at=now or datetime.now(timezone.utc)
    if (not isinstance(document,dict) or set(document)!={'schema','notes'} or document['schema'] not in {SCHEMA,SCHEMA_V2,SCHEMA_V3}
            or not isinstance(document['notes'],list) or not 1<=len(document['notes'])<=20):
        raise SourceShareError('bounded follow-up notes required')
    for note in document['notes']:
        _validate(note,allow_undated=document['schema']==SCHEMA_V3);_bound(note,baselines,resolve,at)
        if (document['schema'] in {SCHEMA_V2,SCHEMA_V3})!=('execution' in note):raise SourceShareError('input comparison version mismatch')
    current=read_followups(root,baselines,resolve,as_of=at,now=at)
    anchors={r['note_id']:r for r in current if 'execution' not in r['note']}
    for note in document['notes']:
        if 'execution' in note:
            company=baselines[note['baseline_note_id']]['note']['source_company']
            bind_anchor(note,company,anchors,at)
    fingerprints={r['analysis_fingerprint'] for r in current}
    folder=_store(root,create=True);ids=[]
    for note in document['notes']:
        fingerprint=sha256(_bytes(note)).hexdigest()
        if fingerprint in fingerprints:continue
        base,row=_bound(note,baselines,resolve,at)
        entry={'schema':document['schema'],'note':note,'available_at':at.isoformat(),
               'baseline_available_at':base['available_at'],'recent_available_at':row['source_available_at'],
               'source_text_stored':False,'source_truth_verified':False}
        raw=_bytes(entry);digest=sha256(raw).hexdigest()
        fd,temp=tempfile.mkstemp(prefix='.followup-',dir=folder)
        try:
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.link(temp,folder/(digest+'.json'))
        finally:os.unlink(temp)
        fingerprints.add(fingerprint);ids.append(digest)
    return {'schema':document['schema'],'created':len(ids),'note_ids':ids,'source_text_stored':False,'network_called':False}

def assess(rows,companies):
    kinds={r['note']['evidence_kind'] for r in rows}
    positive=bool(kinds & POSITIVE);conditional='CONDITIONAL_FRAMEWORK' in kinds;negative=bool(kinds & NEGATIVE)
    status=('MIXED_EVIDENCE' if negative and (positive or conditional) else
            'WEAKENING_EVIDENCE' if negative else 'SUPPORT_ADDED' if positive else
            'CONDITIONAL_SUPPORT_ONLY' if conditional else 'NO_SUBSTANTIVE_CHANGE')
    covered={r['source_company'] for r in rows};shared=[]
    for code,label in FACTOR_LABELS.items():
        parties=sorted({r['source_company'] for r in rows if code in r['note']['factor_codes']})
        if len(parties)>=2:shared.append({'code':code,'label':label,'source_companies':parties,
                                         'all_group_companies_covered':set(parties)==set(companies)})
    return {'status':status,'status_label':STATUS_LABELS[status],'notes':rows,
            'companies_with_followups':sorted(covered),'companies_without_followups':sorted(set(companies)-covered),
            'conditional_evidence_present':conditional,'weakening_evidence_present':negative,
            'shared_recent_factors':shared,'basis_available_at':max(r['available_at'] for r in rows),
            'assessment_scope':'BROADER_POWER_INFRASTRUCTURE_ANALYST_COMPARISON',
            'article_count_used_as_strength':False,'independent_market_events':None,
            'common_market_shock_verified':False,'original_events_unchanged':True}

def attach_followups(root,outlook,workspaces,*,as_of,now):
    if not workspaces or not _store(root).exists():return
    baselines=read_notes(root,sources_from_outlook(outlook),as_of=as_of,now=now)
    rows=read_followups(root,{n['note_id']:n for n in baselines},
                       metadata_resolver(workspaces,now=now),as_of=as_of,now=now)
    for group in outlook['candidates']:
        ids={n['note_id'] for n in group.get('public_page_demand_analysis',{}).get('notes',[])}
        selected=[r for r in rows if r['note']['baseline_note_id'] in ids]
        if selected:
            comparison=assess(selected,group['source_company_names'])
            execution=summarize_execution(selected,group['source_company_names'])
            if execution:comparison['execution_comparison']=execution
            group['recent_news_comparison']=comparison

def article_followups(outlook,provider,event,title):
    rows={}
    for group in outlook['candidates']:
        for row in group.get('recent_news_comparison',{}).get('notes',[]):
            r=row['note']['recent_source']
            if (r['provider_id'],r['event_id'],r['title_sha256'])==(provider,event,title):rows[row['note_id']]=row
    return list(rows.values())
