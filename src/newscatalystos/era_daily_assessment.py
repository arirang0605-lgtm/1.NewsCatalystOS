"""Consume an immutable EraLeader daily candidate publication, read-only.

No producer imports, database reads, valuation recomputation, fuzzy ticker
search, or original-theme writes. New local receipt time gates every join.
"""
from copy import deepcopy
from datetime import datetime, timezone, date
from hashlib import sha256
from pathlib import Path
import json
import re
import unicodedata

from .evidence_archive import _private_root, _read_once, _write_new
from .era_company_assessment import canonical
from .source_share import SourceShareError, _when, _must_sha, _json, _read_regular, _check_directory

SOURCE_SCHEMA = 'eraleader.kr_daily_candidate_explorer.v1'
SCHEMA = 'newscatalyst.era_daily_snapshot_receipt.v1'
LIMIT = 16 * 1024 * 1024


def _name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 150 or any(ord(x)<32 for x in value):
        raise SourceShareError('invalid company name')
    return ' '.join(unicodedata.normalize('NFKC', value).split()).casefold()


def validate_daily(raw, expected_sha, at):
    """Validate producer signature, same-company inputs and research-only flags."""
    if len(raw)>LIMIT or sha256(raw).hexdigest()!=_must_sha(expected_sha, 'daily file SHA'):
        raise SourceShareError('daily file SHA mismatch')
    doc = _json(raw, 'EraLeader daily publication')
    if (not isinstance(doc,dict) or doc.get('schema')!=SOURCE_SCHEMA
            or canonical(doc)+b'\n'!=raw
            or doc.get('research_only') is not True or doc.get('receiver_neutral') is not True
            or doc.get('orders')!=0 or doc.get('investment_rank_created') is not False):
        raise SourceShareError('unsupported daily publication')
    pin=_must_sha(doc['content_sha256'],'daily content SHA')
    if sha256(canonical({k:v for k,v in doc.items() if k!='content_sha256'})).hexdigest()!=pin:
        raise SourceShareError('daily content SHA mismatch')
    source=doc['source'];session=date.fromisoformat(source['market_session'])
    evaluated=_when(source['evaluated_at_utc'],'producer evaluated')
    if evaluated>at or session>at.date():raise SourceShareError('future producer assessment')
    for k in ('source_watch_sha256','source_evaluation_sha256','source_browser_file_sha256'):
        _must_sha(source[k],k)
    rows=doc['candidates']
    if not isinstance(rows,list) or not 0<=len(rows)<=100 or doc['candidate_count']!=len(rows):
        raise SourceShareError('bounded daily candidates required')
    seen=set()
    for row in rows:
        sid=row['security_id'];_name(row['name'])
        if (not isinstance(sid,str) or not re.fullmatch(r'[0-9]{6}',sid) or sid in seen
                or row.get('orders')!=0 or row.get('investment_rank') is not None):
            raise SourceShareError('daily duplicate or unsupported stock identity')
        seen.add(sid)
        financial=row.get('dart_annual_cfs',{})
        quote=row.get('krx_completed_close',{})
        for block in (financial,quote):
            if block.get('security_id')!=sid:raise SourceShareError('cross-company daily evidence')
            if block.get('first_local_received_at_utc'):
                if _when(block['first_local_received_at_utc'],'producer source received')>at:
                    raise SourceShareError('future financial/price evidence')
            if block.get('first_receipt_sha256'):_must_sha(block['first_receipt_sha256'],'official receipt')
            if block.get('standard_per') is not None or block.get('standard_pbr') is not None:
                raise SourceShareError('unsupported certified valuation')
        if financial.get('status')=='DART_VERIFIED_ANNUAL_CFS':
            if (not re.fullmatch(r'[0-9]{8}',str(financial.get('issuer_corp_code','')))
                    or type(financial.get('fiscal_year')) is not int
                    or not 2015<=financial['fiscal_year']<at.year
                    or financial.get('orders')!=0 or financial.get('valuation_score') is not None):
                raise SourceShareError('invalid official annual company/period')
            _must_sha(financial['first_receipt_sha256'],'annual first receipt')
        if quote.get('status')=='OBSERVED_COMPLETED_KRX_CLOSE':
            if (quote.get('source_market_session')!=source['market_session']
                    or quote.get('currency')!='KRW' or quote.get('live_quote') is not False):
                raise SourceShareError('invalid completed market quote')
            _must_sha(quote['raw_sha256'],'quote raw SHA')
        brief=row.get('evidence_brief',{})
        if brief:
            if (brief.get('security_id')!=sid or brief.get('market_session')!=source['market_session']
                    or brief.get('orders')!=0 or brief.get('investment_rank') is not None
                    or brief.get('formal_leader_promotion') is not False):
                raise SourceShareError('cross-company or actionable brief')
            for entry in brief.get('supporting_evidence',[])+brief.get('weakening_evidence',[]):
                if entry.get('order_instruction') is not False or entry.get('formal_leader_change') is not False:
                    raise SourceShareError('unsupported actionable assessment')
                if str(entry.get('basis','')).startswith('DART_') and entry.get('first_receipt_sha256')!=financial.get('first_receipt_sha256'):
                    raise SourceShareError('brief financial receipt mismatch')
    return doc


def import_daily(era_root, manifest, expected_sha, output_root, *, now=None, check_only=False):
    at=now or datetime.now(timezone.utc);at=_when(at.isoformat(),'import now')
    era_root=Path(era_root);path=Path(manifest);out=Path(output_root)
    _check_directory(path.parent,era_root)
    if out.resolve().is_relative_to(era_root.resolve()):raise SourceShareError('producer writes prohibited')
    if (path.name!='report.json' or path.parent.parent!=era_root/'output/kr_daily_candidate_explorer'
            or not re.fullmatch(r'[a-f0-9]{64}',path.parent.name)):
        raise SourceShareError('completed daily snapshot folder required')
    raw=_read_regular(path,LIMIT);doc=validate_daily(raw,expected_sha,at)
    if doc['content_sha256']!=path.parent.name:raise SourceShareError('daily folder identity mismatch')
    _read_regular(path.with_name('index.html'),LIMIT)
    # Bind the same identities to the completed candidate-browser edition;
    # no name-only internet lookup or reconstruction of a WATCH snapshot.
    link=doc['links']['original_candidate_browser']
    match=re.fullmatch(r'../../candidate_browser/([a-f0-9]{64})/index.html',link)
    if not match:raise SourceShareError('invalid producer browser link')
    viewpath=era_root/'output/candidate_browser'/match[1]/'view.json'
    _check_directory(viewpath.parent,era_root)
    view_raw=_read_regular(viewpath,LIMIT)
    if sha256(view_raw).hexdigest()!=doc['source']['source_browser_file_sha256']:
        raise SourceShareError('producer browser SHA mismatch')
    view=_json(view_raw,'producer browser')
    if (view.get('source_watch_sha256')!=doc['source']['source_watch_sha256']
            or [(r['id'],r['name']) for r in view['rows']]!=[(r['security_id'],r['name']) for r in doc['candidates']]):
        raise SourceShareError('daily/browser company mismatch')
    if _read_regular(path,LIMIT)!=raw:raise SourceShareError('producer publication changed')
    if check_only:return {'status':'VERIFIED_READ_ONLY','source_sha256':expected_sha,'rows':len(doc['candidates'])}
    root=_private_root(out)
    existing=sorted(root.glob('era_daily_'+expected_sha+'_*.json'))
    if len(existing)>1:raise SourceShareError('conflicting local daily receipts')
    if existing:
        old,_=_load(existing[0],at)
        if old['source_sha256']!=expected_sha:raise SourceShareError('daily import conflict')
        return {'status':'ALREADY_IMPORTED','source_sha256':expected_sha,'imported_at':old['imported_at'],'rows':len(doc['candidates'])}
    receipt={'schema':SCHEMA,'source_sha256':expected_sha,'source_content_sha256':doc['content_sha256'],
             'source_payload':raw.decode(),'imported_at':at.isoformat(),'producer':'EraLeader',
             'source_version':path.parent.name,'identity_browser_sha256':sha256(view_raw).hexdigest()}
    stored=canonical(receipt)+b'\n'
    target=root/('era_daily_'+expected_sha+'_'+sha256(stored).hexdigest()+'.json')
    _write_new(target,stored)
    return {'status':'IMPORTED','source_sha256':expected_sha,'imported_at':at.isoformat(),'rows':len(doc['candidates'])}


def _load(path,now):
    raw=_read_once(path,LIMIT*2)
    receipt=_json(raw,'daily receipt')
    if (receipt.get('schema')!=SCHEMA
            or path.name!='era_daily_'+receipt['source_sha256']+'_'+sha256(raw).hexdigest()+'.json'
            or receipt.get('producer')!='EraLeader'):
        raise SourceShareError('invalid daily receipt')
    when=_when(receipt['imported_at'],'daily imported')
    if when>now:raise SourceShareError('future daily import')
    doc=validate_daily(receipt['source_payload'].encode(),receipt['source_sha256'],when)
    if (receipt['source_content_sha256']!=doc['content_sha256']
            or receipt['identity_browser_sha256']!=doc['source']['source_browser_file_sha256']):
        raise SourceShareError('daily receipt provenance mismatch')
    return receipt,doc


def read_latest(root, *, as_of, now=None):
    now=now or datetime.now(timezone.utc)
    if as_of>now:raise SourceShareError('future daily assessment query')
    root=Path(root);eligible=[];skipped=0
    if not root.exists():return None,0
    if not root.is_absolute() or root.resolve()!=root:raise SourceShareError('unsafe daily cache')
    paths=sorted(root.glob('era_daily_*_*.json'))
    if len(paths)>1000:raise SourceShareError('too many daily publications')
    for path in paths:
        try:
            receipt,doc=_load(path,now)
            if _when(receipt['imported_at'],'imported')<=as_of:eligible.append((receipt,doc))
        except (SourceShareError,KeyError,TypeError,ValueError,OSError):skipped+=1
    latest=max(eligible,key=lambda x:(x[1]['source']['market_session'],
        x[1]['source']['evaluated_at_utc'],x[0]['imported_at'],x[0]['source_sha256']),default=None)
    from .era_individual_assessment import read_individuals
    individual,errors=read_individuals(root,as_of=as_of,now=now)
    skipped+=errors
    if individual:
        if latest:
            latest=({**latest[0],'individual_assessments':individual},latest[1])
        else:
            # Explicit local lookup context, never a fabricated WATCH edition.
            r,d=max(individual,key=lambda pair:pair[1]['published_at'])
            latest=({**r,'individual_assessments':individual},
                {'schema':'newscatalyst.individual_assessment_context.v1','candidates':[],
                 'source':{'market_session':d['market_source']['market_session'],
                           'evaluated_at_utc':d['published_at']}})
    return latest,skipped


def assessment_for(entity, snapshot):
    missing={'status':'NOT_AVAILABLE_AS_OF','value':None,'verified_real_benefit':False,'orders_enabled':False}
    if not snapshot:return missing
    receipt,doc=snapshot
    from .era_individual_assessment import assessment_for_individual
    individual=assessment_for_individual(entity,receipt.get('individual_assessments',[]))
    rows=doc['candidates'];official=bool(re.fullmatch(r'(DART_CORP:[0-9]{8}|KRX_STOCK:[0-9]{6})',entity))
    if entity.startswith('SEC_CIK:'):return {**missing,'status':'US_ASSESSMENT_NOT_CONNECTED'}
    matches=[r for r in rows if (entity in {'DART_CORP:'+str(r['dart_annual_cfs'].get('issuer_corp_code')),
                    'KRX_STOCK:'+r['security_id']} if official else _name(entity)==_name(r['name']))]
    if len(matches)!=1:
        return ({**missing,'status':'AMBIGUOUS_IDENTITY'} if len(matches)>1 else
                individual or {**missing,'status':'COMPANY_NOT_IN_SNAPSHOT'})
    row=matches[0];annual=row['dart_annual_cfs'];issuer=annual.get('issuer_corp_code')
    if annual.get('status')!='DART_VERIFIED_ANNUAL_CFS' or not issuer:
        return individual or {**missing,'status':'OFFICIAL_IDENTITY_UNAVAILABLE'}
    # More than one security of this issuer cannot silently collapse to one.
    if sum(r['dart_annual_cfs'].get('issuer_corp_code')==issuer for r in rows)!=1:
        return {**missing,'status':'AMBIGUOUS_IDENTITY'}
    return {'status':'AVAILABLE','producer':'EraLeader','value':deepcopy(row),
        'entity_id':'DART_CORP:'+issuer,'security_id':row['security_id'],'source_name':row['name'],
        'identity_method':'EXACT_PUBLISHED_NAME_AND_OFFICIAL_DART_ROW' if not official else 'EXACT_OFFICIAL_ID',
        'identity_evidence_sha256':annual['first_receipt_sha256'],
        'source_sha256':receipt['source_sha256'],'source_content_sha256':doc['content_sha256'],
        'producer_evaluated_at':doc['source']['evaluated_at_utc'],
        'market_session':doc['source']['market_session'],'imported_at':receipt['imported_at'],
        'evidence_level':'PRODUCER_ASSESSMENT_NOT_INDEPENDENT_CERTIFICATION',
        'investment_merit':'NOT_ASSESSED','verified_real_benefit':False,'orders_enabled':False}


def enrich_daily(candidates, root, *, as_of, now=None, snapshot=None):
    now=now or datetime.now(timezone.utc)
    snap=read_latest(root,as_of=as_of,now=now)[0] if snapshot is None else snapshot
    out=deepcopy(candidates)
    for candidate in out:
        if _when(candidate['decision_at'],'candidate decision')>as_of:raise SourceShareError('future candidate')
        candidate['era_daily_assessment']=assessment_for(candidate['entity_id'],snap)
    return out


def project_themes(themes, scope, snapshot):
    """Derived export only. Stored source theme and event IDs are unchanged.

    Namespacing prevents independent same-topic stores from overwriting each
    other in EraLeader. Local identity time advances the derived decision,
    never backdates a DART identity into the original news observation.
    """
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}',scope):raise SourceShareError('invalid export scope')
    output=[]
    for source in themes:
        t=deepcopy(source);bindings={}
        # Complex separately signed supply graphs must retain their original
        # entity IDs. Their review still receives a separate evaluation join.
        if not t.get('supply_chain_evidence'):
            for entity in t['entity_ids']:
                a=assessment_for(entity,snapshot)
                if (a['status']=='AVAILABLE' and entity!=a['entity_id']
                        and a.get('assessment_scope')!='INDIVIDUAL_COMPANY_RESEARCH'):bindings[entity]=a
        t['theme_id']=sha256(canonical({'scope':scope,'theme_id':source['theme_id']})).hexdigest()
        t['export_origin']={'scope':scope,'theme_id':source['theme_id'],
            'theme_sha256':sha256(canonical(source)).hexdigest(),'decision_at':source['decision_at'],
            'identity_receipt_sha256':snapshot[0]['source_sha256'] if bindings else None}
        if bindings:
            known=max([_when(t['decision_at'],'decision')]+[_when(a['imported_at'],'import') for a in bindings.values()]).isoformat()
            replace_id=lambda e:bindings[e]['entity_id'] if e in bindings else e
            t['decision_at']=known
            t['entity_ids']=sorted(set(replace_id(e) for e in t['entity_ids']))
            for link in t['company_links']:link['entity_id']=replace_id(link['entity_id'])
            for ref in t['source_refs']:
                names=[e for e in ref['entity_ids'] if e in bindings]
                if not names:continue
                ref['original_entity_ids']=ref.get('original_entity_ids',ref['entity_ids'][:])
                ref['entity_ids']=[replace_id(e) for e in ref['entity_ids']]
                ref['source_recorded_at']=ref['recorded_at']
                ref['recorded_at']=max(_when(ref['recorded_at'],'recorded'),_when(known,'identity')).isoformat()
                ref['company_mappings']=ref.get('company_mappings',[])+[
                    {'source_name':name,'entity_id':bindings[name]['entity_id'],
                     'evidence_sha256':bindings[name]['identity_evidence_sha256']} for name in names]
        output.append(t)
    return output


def refresh_daily(config, output_root, *, now=None, check_only=False):
    """Follow only the producer's current home link into a completed snapshot.

    Repeated identical publication is idempotent; changed editions receive a
    new first-local receipt. Invalid/missing producer files leave news intact.
    """
    settings=_json(_read_once(Path(config),8192),'daily connection settings')
    if set(settings)!={'era_root','source'} or settings['source']!='OPERATIONS_CURRENT_KR_DAILY':
        raise SourceShareError('unsupported daily connection configuration')
    root=Path(settings['era_root'])
    home=root/'output/operations/site/index.html'
    _check_directory(home.parent,root)
    raw=_read_regular(home,4*1024*1024)
    links=re.findall(r'href=["\']([^"\']+)["\']',raw.decode('utf8'))
    ids=set()
    for link in links:
        match=re.fullmatch(r'(?:\.\./)+kr_daily_candidate_explorer/([a-f0-9]{64})/index\.html',link)
        if match:ids.add(match[1])
    if len(ids)!=1:raise SourceShareError('one current completed daily publication required')
    path=root/'output/kr_daily_candidate_explorer'/next(iter(ids))/'report.json'
    _check_directory(path.parent,root)
    pin=sha256(_read_regular(path,LIMIT)).hexdigest()
    return import_daily(root,path,pin,output_root,now=now,check_only=check_only)


def enrich_followup_assessments(outlook,root,*,since,as_of,now):
    """Compare completed producer assessment contents, never rate news as finance."""
    if not any(g.get('recent_news_comparison') for g in outlook.get('candidates',[])):return
    def safe_read(at):
        try:return read_latest(root,as_of=at,now=now)
        except (SourceShareError,OSError,ValueError,KeyError,TypeError):return None,1
    current,errors=safe_read(as_of)
    previous,old_errors=safe_read(since)
    cache={}
    for group in outlook.get('candidates',[]):
        comparison=group.get('recent_news_comparison')
        if not comparison:continue
        results=[]
        for company in group['source_company_names']:
            if company not in cache:
                latest=assessment_for(company,current);prior=assessment_for(company,previous)
                available=latest['status']=='AVAILABLE';had=prior['status']=='AVAILABLE'
                # Compare displayed observations, excluding receipt and market metadata.
                def content(a):
                    v=a['value'];annual=v.get('dart_annual_cfs',{})
                    existing=annual.get('existing_financial_assessment',{})
                    brief=v.get('evidence_brief',{})
                    reasons=lambda values:sorted({r['reason'] for r in values if isinstance(r,dict) and isinstance(r.get('reason'),str)})
                    return {'metrics':{k:annual.get(k) for k in (
                        'fiscal_year','revenue_krw','operating_income_krw','net_income_krw',
                        'operating_margin_pct','operating_cashflow_krw','cash_after_ppe_intangibles_krw')},
                        'support':reasons(brief.get('supporting_evidence',existing.get('competitiveness',{}).get('supporting',[]))),
                        'risk':reasons(brief.get('weakening_evidence',existing.get('competitiveness',{}).get('weakening',[])+existing.get('financial_risk',{}).get('signals',[]))),
                        'limitations':sorted(set(brief.get('unavailable_or_limited',existing.get('missing',[])+existing.get('limitations',[]))))}
                changes=None
                if available and had:
                    old=content(prior);new=content(latest)
                    changes={'metrics':[{'field':k,'previous':v,'current':new['metrics'][k]}
                        for k,v in old['metrics'].items() if v!=new['metrics'][k]]}
                    for k in ('support','risk','limitations'):
                        changes[k+'_added']=sorted(set(new[k])-set(old[k]))
                        changes[k+'_removed']=sorted(set(old[k])-set(new[k]))
                    same=(latest['entity_id']==prior['entity_id'] and not any(changes.values()))
                    status='UNCHANGED_ASSESSMENT' if same else 'ASSESSMENT_EVIDENCE_CHANGED'
                elif available:status='NEWLY_AVAILABLE_ASSESSMENT'
                else:status='ASSESSMENT_UNAVAILABLE'
                cache[company]={'source_company':company,'status':status,
                    'status_label':{'UNCHANGED_ASSESSMENT':'기존 기업 평가 근거 유지',
                        'ASSESSMENT_EVIDENCE_CHANGED':'기업 평가 근거 변경 · 방향은 항목별 확인',
                        'NEWLY_AVAILABLE_ASSESSMENT':'기업 평가 첫 연결 · 평가 상향 아님',
                        'ASSESSMENT_UNAVAILABLE':'기업 평가 미확보 · 약화 판정 아님'}[status],
                    'current':latest,'previous_status':prior['status'],
                    'previous_source_sha256':prior.get('source_sha256'),
                    'previous_producer_evaluated_at':prior.get('producer_evaluated_at'),'observation_changes':changes,
                    'news_changes_financial_rating':False,'investment_merit':'NOT_ASSESSED'}
            results.append(deepcopy(cache[company]))
        comparison['company_assessment_comparison']={'since':since.isoformat(),'as_of':as_of.isoformat(),
            'company_results':results,'skipped_receipts':errors+old_errors,
            'assessment_direction_inferred_from_news':False}
