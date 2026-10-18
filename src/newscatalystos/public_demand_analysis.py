"""Append-only factual reading notes, separate from original news/title evidence.

No article body/quotes are accepted as a source-text field. Short paraphrases
and analyst classifications describe public-source claims, not verified facts.
Binding authenticates which saved event is being discussed, not the prose's
truth. No HTTP, provider permission expansion, event mutation or paid AI.
"""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import os,re,tempfile
from .theme_emergence import _bytes
from .source_share import SourceShareError,_json,_when
from .official_relation_intake import _private_input

SCHEMA='newscatalyst.public_demand_analysis.v1'
BIND=('provider_id','source_event_sha256','source_title_sha256','event_id','report_sha256')
FIELDS=set(BIND)|{'source_url','source_company','market_codes','factors','analysis_text','source_location'}
FACTOR_LABELS={'GRID_REPLACEMENT':'노후 전력망 교체','RENEWABLE_INTEGRATION':'신재생 발전의 전력망 연계',
'AI_LOAD':'AI·데이터센터 관련 전력 수요','TRANSMISSION_CONSTRAINTS':'송전 제약 해소',
'LOAD_GROWTH':'전력 수요 증가'}
MARKET_LABELS={'US':'미국','KR':'한국','GLOBAL':'글로벌','EU':'유럽'}
RELATIONS={'MARKET_BACKGROUND','PROJECT_PURPOSE','ACTION_REASON'}
ENTRY_FIELDS={'schema','note','available_at','source_basis_available_at','content_scope',
              'source_truth_verified','source_text_stored'}
SCOPE='ANALYSIS_PARAPHRASE_NO_SOURCE_TEXT'


def _text(value,limit):
    return isinstance(value,str) and 1<=len(value)<=limit and not any(ord(c)<32 for c in value)


def _validate(note):
    if not isinstance(note,dict) or set(note)!=FIELDS:
        raise SourceShareError('exact analysis-note fields required; source text not accepted')
    for key in BIND:
        if key.endswith('sha256') or key=='event_id':
            if not re.fullmatch('[0-9a-f]{64}',str(note[key])):raise SourceShareError('invalid source binding')
        elif not _text(note[key],120):raise SourceShareError('invalid provider')
    if any(not _text(note[k],limit) for k,limit in [
        ('source_url',2048),('source_company',120),('analysis_text',240),('source_location',100)]):
        raise SourceShareError('bounded analysis and source location required')
    markets=note['market_codes'];factors=note['factors']
    if (not isinstance(markets,list) or not 1<=len(markets)<=3
            or any(x not in MARKET_LABELS for x in markets) or len(set(markets))!=len(markets)
            or not isinstance(factors,list) or not 1<=len(factors)<=5):
        raise SourceShareError('bounded analyst demand classification required')
    if any(not isinstance(f,dict) or set(f)!={'code','relation'} or
           f['code'] not in FACTOR_LABELS or f['relation'] not in RELATIONS for f in factors):
        raise SourceShareError('invalid demand factor/relationship')
    if len({f['code'] for f in factors})!=len(factors):raise SourceShareError('duplicate factor')


def _folder(root,create=False):
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root or any('eraleader' in p.casefold() for p in root.parts):
        raise SourceShareError('separate News analysis root required')
    path=root/'analysis_notes'/'public_demand'
    if create:
        for p in (root/'analysis_notes',path):
            p.mkdir(mode=0o700,exist_ok=True)
            if p.resolve()!=p or p.stat().st_mode & 0o077:
                raise SourceShareError('owner-only analysis-note parent required')
    if path.exists() and (path.resolve()!=path or path.stat().st_mode & 0o077):
        raise SourceShareError('owner-only analysis-note folder required')
    return path


def sources_from_outlook(outlook):
    return {tuple(s[k] for k in BIND):s for g in outlook['candidates'] for s in g['source_evidence']}


def _bound(note,sources):
    source=sources.get(tuple(note[k] for k in BIND))
    if (source is None or note['source_url']!=source['source_url']
            or note['source_company'] not in source['source_companies']):
        raise SourceShareError('analysis must bind the exact active source/company/event/report')
    return source


def read_notes(root,sources,*,as_of,now):
    at=_when(as_of.isoformat(),'notes as of');present=_when(now.isoformat(),'notes now')
    if at>present:raise SourceShareError('future note query')
    folder=_folder(root)
    if not folder.exists():return []
    paths=sorted(folder.glob('*.json'))
    if len(paths)>200:raise SourceShareError('analysis-note store limit')
    rows=[]
    for path in paths:
        raw=_private_input(path,8192)
        if path.stem!=sha256(raw).hexdigest():raise SourceShareError('analysis-note digest mismatch')
        entry=_json(raw,'public reading analysis')
        if (set(entry)!=ENTRY_FIELDS or entry['schema']!=SCHEMA or entry['content_scope']!=SCOPE
                or entry['source_truth_verified'] is not False or entry['source_text_stored'] is not False):
            raise SourceShareError('invalid public reading analysis envelope')
        note=entry['note'];_validate(note)
        available=_when(entry['available_at'],'note available')
        source_basis=_when(entry['source_basis_available_at'],'source basis')
        if available<source_basis:raise SourceShareError('note predates source')
        if available>at:continue
        try:source=_bound(note,sources)
        except SourceShareError:continue  # revised/invalidated/unavailable source cannot lend a note
        if source_basis!=_when(source['basis_available_at'],'bound source basis'):continue
        rows.append({**entry,'note_id':path.stem,'analysis_fingerprint':sha256(_bytes(note)).hexdigest(),
                     'source_headline':source['headline'],'source_phase':source['phase']})
    # The latest available interpretation for one exact source and company.
    latest={}
    for row in rows:
        n=row['note'];key=tuple(n[k] for k in BIND)+(n['source_company'],)
        if key not in latest or (row['available_at'],row['note_id'])>(latest[key]['available_at'],latest[key]['note_id']):
            latest[key]=row
    return sorted(latest.values(),key=lambda r:r['note_id'])


def publish_notes(root,document,sources,*,now=None):
    at=_when((now or datetime.now(timezone.utc)).isoformat(),'publish now')
    if (not isinstance(document,dict) or set(document)!={'schema','notes'} or document['schema']!=SCHEMA
            or not isinstance(document['notes'],list) or not 1<=len(document['notes'])<=20):
        raise SourceShareError('bounded public reading notes input required')
    for note in document['notes']:
        _validate(note);source=_bound(note,sources)
        if _when(source['basis_available_at'],'source basis')>at:
            raise SourceShareError('source not available at analysis publication')
    existing=read_notes(root,sources,as_of=at,now=at)
    fingerprints={r['analysis_fingerprint'] for r in existing};created=0;ids=[]
    folder=_folder(root,create=True)
    for note in document['notes']:
        fingerprint=sha256(_bytes(note)).hexdigest()
        if fingerprint in fingerprints:continue
        source=_bound(note,sources)
        available=max(at,_when(source['basis_available_at'],'source basis'))
        entry={'schema':SCHEMA,'note':note,'available_at':available.isoformat(),
               'source_basis_available_at':source['basis_available_at'],'content_scope':SCOPE,
               'source_truth_verified':False,'source_text_stored':False}
        raw=_bytes(entry);digest=sha256(raw).hexdigest()
        fd,temp=tempfile.mkstemp(prefix='.demand-',suffix='.tmp',dir=folder)
        try:
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.link(temp,folder/(digest+'.json'))  # atomic, never replace a version
        finally:
            os.unlink(temp)
        fingerprints.add(fingerprint);created+=1;ids.append(digest)
    return {'schema':SCHEMA,'created':created,'note_ids':ids,'source_text_stored':False,'network_called':False}


def attach_comparisons(root,outlook,*,as_of,now):
    sources=sources_from_outlook(outlook)
    notes=read_notes(root,sources,as_of=as_of,now=now)
    for group in outlook['candidates']:
        keys={tuple(s[k] for k in BIND) for s in group['source_evidence']}
        selected=[n for n in notes if tuple(n['note'][k] for k in BIND) in keys]
        if not selected:continue
        names=group['source_company_names']
        covered=sorted({r['note']['source_company'] for r in selected})
        shared=[]
        for code,label in FACTOR_LABELS.items():
            support=[r for r in selected if any(f['code']==code for f in r['note']['factors'])]
            parties=sorted({r['note']['source_company'] for r in support})
            if len(parties)>=2:
                shared.append({'code':code,'label':label,'source_companies':parties,
                    'all_group_companies_covered':set(parties)==set(names),
                    'note_ids':[r['note_id'] for r in support],'analyst_classification_only':True})
        markets={tuple(sorted(r['note']['market_codes'])) for r in selected}
        group['public_page_demand_analysis']={
            'status':'COMPANY_NOTES_AVAILABLE' if set(covered)==set(names) else 'PARTIAL_COMPANY_NOTES',
            'notes':selected,'companies_with_notes':covered,'companies_without_notes':sorted(set(names)-set(covered)),
            'shared_background_factors':shared,'market_scope_comparison':'SAME_STATED_SCOPE' if len(markets)==1 else 'DIFFERENT_STATED_SCOPES',
            'comparison_is_analyst_hypothesis':True,'literal_common_cause_match_verified':False,
            'common_market_shock_verified':False,'source_text_stored':False,
            'basis_available_at':max(r['available_at'] for r in selected),
            'original_events_unchanged':True}
    return outlook


def article_notes(outlook,provider,event,title):
    selected={}
    for group in outlook['candidates']:
        for row in group.get('public_page_demand_analysis',{}).get('notes',[]):
            n=row['note']
            if (n['provider_id'],n['source_event_sha256'],n['source_title_sha256'])==(provider,event,title):
                selected[row['note_id']]=row
    return list(selected.values())
