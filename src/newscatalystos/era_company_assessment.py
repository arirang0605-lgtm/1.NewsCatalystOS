"""Read completed EraLeader WATCH assessments; never import producer code or DBs.

Producer judgments are attributed observations, not a second financial evaluator.
Local receipt time prevents newly imported context leaking into past queries.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .evidence_archive import _private_root, _read_once, _write_new
from .source_share import SourceShareError, _when, _must_sha, _json, _read_regular, _check_directory

METHOD='WATCH_FUNDAMENTAL_EVIDENCE_AND_RISK_V1'
SCHEMA='newscatalyst.era_watch_assessment_receipt.v1'
MAX_BYTES=16*1024*1024


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def validate_watch(raw, expected_sha256, at):
    if sha256(raw).hexdigest()!=_must_sha(expected_sha256,'WATCH pin'):
        raise SourceShareError('WATCH file SHA mismatch')
    doc=_json(raw,'WATCH assessment')
    if (doc.get('schema')!='eraleader.kr_early_watch_queue.v1' or doc.get('market')!='KR'
            or doc.get('company_assessment_method')!=METHOD
            or any(doc.get(k) is not False for k in ('orders_enabled','order_instruction','execution_authority','investment_priority_certified'))
            or doc.get('watch_only') is not True):
        raise SourceShareError('unsupported or nonresearch WATCH')
    unsigned={k:v for k,v in doc.items() if k!='content_sha256'}
    if sha256(canonical(unsigned)).hexdigest()!=doc['content_sha256']:
        raise SourceShareError('WATCH content SHA mismatch')
    published=_when(doc['watch_published_at_utc'],'WATCH published')
    day=date.fromisoformat(doc['company_assessment_day'])
    if not day<=published.astimezone(ZoneInfo('Asia/Seoul')).date() or published>at:
        raise SourceShareError('future WATCH assessment')
    rows=doc['review_queue']
    if not isinstance(rows,list) or not 0<=len(rows)<=100:
        raise SourceShareError('bounded WATCH rows required')
    if sha256(canonical([r['company_assessment'] for r in rows])).hexdigest()!=doc['source_company_assessment_sha256']:
        raise SourceShareError('assessment content SHA mismatch')
    seen=set()
    for row in rows:
        a=row['company_assessment'];inputs=a['inputs'];sid=row['security_id']
        issuer=a['issuer_corp_code'];year=a['annual_fiscal_year']
        if (not re.fullmatch(r'[0-9]{6}',sid) or sid in seen
                or a['security_id']!=sid or inputs['security_id']!=sid
                or a['method']!=METHOD or a['assessment_day']!=doc['company_assessment_day']
                or a['source_market_session']!=doc['source_market_session']
                or date.fromisoformat(a['source_market_session'])>day
                or any(row.get(k)!=v for k,v in inputs.items())
                or issuer!=row.get('dart_cfs_issuer_corp_code')
                or (issuer is not None and not re.fullmatch(r'[0-9]{8}',issuer))
                or a['orders_enabled'] is not False or a['leader_score_unchanged'] is not True
                or a['competitiveness']['score_20'] is not None or a['valuation']['status']!='N/A'):
            raise SourceShareError('assessment identity, input or method mismatch')
        seen.add(sid)
        for key,source in a['sources'].items():
            available=_when(source['available_at_utc'],'assessment source')
            if available>published or available.astimezone(ZoneInfo('Asia/Seoul')).date()>day:
                raise SourceShareError('future assessment source')
            if key=='market_sample':
                if (source['market_session']!=a['source_market_session']
                        or source['content_sha256']!=doc['source_marketwide_sha256']):
                    raise SourceShareError('market source mismatch')
            elif key in {'annual','previous_annual'}:
                target_year=year-(key=='previous_annual') if isinstance(year,int) else None
                if (source['issuer_corp_code']!=issuer or source['fiscal_year']!=target_year
                        or type(year) is not int or not 2015<=year<day.year
                        or source['currency']!='KRW' or source['statement']!='CFS' or source['report_code']!='11011'):
                    raise SourceShareError('assessment company, currency or period mismatch')
                _must_sha(source['first_receipt_sha256'],'financial receipt')
            else: raise SourceShareError('unsupported assessment source')
        for block in (a['competitiveness']['supporting'],a['competitiveness']['weakening'],a['financial_risk']['signals']):
            for item in block:
                if (any(k not in a['sources'] for k in item['source_refs'])
                        or any(inputs.get(k)!=v for k,v in item['observations'].items())):
                    raise SourceShareError('assessment claim without input evidence')
    return doc


def _reports(root, now):
    root=Path(root)
    if not root.exists():return [],0
    if not root.is_absolute() or root.resolve()!=root:raise SourceShareError('unsafe assessment cache')
    paths=sorted(root.glob('era_assessment_*.json'))
    if len(paths)>1000:raise SourceShareError('too many assessment receipts')
    valid=[];skipped=0
    for path in paths:
        try:
            raw=_read_once(path,MAX_BYTES*2)
            if path.name!='era_assessment_'+sha256(raw).hexdigest()+'.json':
                raise SourceShareError('assessment receipt changed')
            report=_json(raw,'assessment receipt')
            if report['schema']!=SCHEMA:raise SourceShareError('unsupported assessment receipt')
            imported=_when(report['imported_at'],'assessment imported')
            if imported>now:raise SourceShareError('future import')
            doc=validate_watch(report['source_payload'].encode(),report['source_sha256'],imported)
            valid.append((report,doc,sha256(raw).hexdigest()))
        except (SourceShareError,KeyError,TypeError,ValueError,OSError):skipped+=1
    return valid,skipped


def import_watch(era_root, manifest, expected_sha256, output_root, *, now=None):
    at=_when((now or datetime.now(timezone.utc)).isoformat(),'import time')
    era_root=Path(era_root);manifest=Path(manifest)
    _check_directory(manifest.parent,era_root)
    if Path(output_root).resolve().is_relative_to(era_root.resolve()):
        raise SourceShareError('cannot write assessment cache into producer project')
    if (manifest.name!='watch_queue.json'
            or manifest.parent.parent!=era_root/'output/early_leader_watch_queue'
            or not re.fullmatch(r'KR_[0-9]{8}_[a-f0-9]{16}',manifest.parent.name)):
        raise SourceShareError('completed immutable WATCH folder required')
    # Producer publishes JSON + HTML together by atomic directory rename.
    _read_regular(manifest.parent/'index.html',MAX_BYTES)
    raw=_read_regular(manifest,MAX_BYTES)
    doc=validate_watch(raw,expected_sha256,at)
    if _read_regular(manifest,MAX_BYTES)!=raw:raise SourceShareError('WATCH changed during import')
    root=_private_root(output_root)
    prior,_=_reports(root,at)
    for report,_,digest in prior:
        if report['source_sha256']==expected_sha256:
            return {'status':'ALREADY_IMPORTED','receipt_sha256':digest,'rows':len(doc['review_queue'])}
    report={'schema':SCHEMA,'source_sha256':expected_sha256,'source_payload':raw.decode(),
            'imported_at':at.isoformat(),'source_version':manifest.parent.name}
    receipt=canonical(report)+b'\n';digest=sha256(receipt).hexdigest()
    _write_new(root/('era_assessment_'+digest+'.json'),receipt)
    return {'status':'IMPORTED','receipt_sha256':digest,'rows':len(doc['review_queue'])}


def enrich_candidates(candidates, root, *, as_of, now=None, identity_root=None):
    present=_when((now or datetime.now(timezone.utc)).isoformat(),'now')
    at=_when(as_of.isoformat(),'research as of')
    if at>present:raise SourceShareError('future research query')
    identity_skipped=0
    if identity_root is not None:
        from .theme_company_identity import resolve_candidates
        candidates,identity_skipped=resolve_candidates(candidates,identity_root,as_of=at,now=present)
    reports,skipped=_reports(root,present)
    eligible=[x for x in reports if _when(x[0]['imported_at'],'import')<=at]
    # Select one coherent publication; do not silently fill missing new rows with old data.
    latest=max(eligible,key=lambda x:(_when(x[1]['watch_published_at_utc'],'published'),x[0]['source_sha256']),default=None)
    results=deepcopy(candidates)
    for candidate in results:
        if _when(candidate['decision_at'],'candidate decision')>at:
            raise SourceShareError('future company candidate')
        entity=(candidate.get('resolved_entity_id',candidate['entity_id']) if identity_root is not None else candidate['entity_id']);matches=[]
        identified=bool(re.fullmatch(r'(?:DART_CORP:[0-9]{8}|KRX_STOCK:[0-9]{6})',entity))
        if latest and identified:
            matches=[r for r in latest[1]['review_queue'] if entity in
                     {'KRX_STOCK:'+r['security_id'],'DART_CORP:'+str(r['company_assessment']['issuer_corp_code'])}]
        status=('IDENTITY_UNRESOLVED' if not identified else 'NOT_AVAILABLE_AS_OF' if not latest
                else 'AMBIGUOUS_IDENTITY' if len(matches)>1 else 'COMPANY_NOT_IN_SNAPSHOT' if not matches else 'AVAILABLE')
        candidate['schema_version']='newscatalyst.theme_company_candidate.v2'
        candidate['financial_assessment']={'status':status,'value':None}
        if len(matches)==1:
            report,doc,digest=latest;a=matches[0]['company_assessment']
            candidate['financial_assessment']={'status':'AVAILABLE' if a['financial_risk']['assessed_items'] else 'INSUFFICIENT_DATA',
                'value':a,'producer':'EraLeader','source_sha256':report['source_sha256'],
                'receipt_sha256':digest,'source_version':report['source_version'],
                'published_at':doc['watch_published_at_utc'],'imported_at':report['imported_at'],
                'evidence_level':'PRODUCER_ASSESSMENT_NOT_INDEPENDENT_CERTIFICATION'}
            candidate['uncertainties']=[x for x in candidate['uncertainties'] if x!='매출 기여·재무·현재 가격 평가는 연결되지 않아 미확인']
            candidate['uncertainties'].append('EraLeader의 보관 재무 관측이며 현재 가격 매력·매출 기여·재무 안전성 확정은 아님')
    return {'schema':'newscatalyst.company_research.v1','decision_at':at.isoformat(),
            'CompanyCandidates':results,'assessment_source_status':'PARTIAL_UNAVAILABLE' if skipped else 'READY' if latest else 'NOT_AVAILABLE_AS_OF',
            'assessment_receipts_skipped':skipped,'identity_receipts_skipped':identity_skipped,'orders_enabled':False}
