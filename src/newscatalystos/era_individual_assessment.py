"""Read a completed single-company result of Era's existing evaluator.

No producer imports, API requests, financial calculations or WATCH changes.
Producer facts remain attributed; local import time gates every lookup.
"""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import re
from .era_company_assessment import canonical
from .evidence_archive import _private_root,_read_once,_write_new
from .source_share import SourceShareError,_json,_when,_must_sha,_read_regular,_check_directory

SOURCE='eraleader.individual_company_assessment.v1'
SCHEMA='newscatalyst.era_individual_assessment_receipt.v1'
METHOD='WATCH_FUNDAMENTAL_EVIDENCE_AND_RISK_V1'
LIMIT=2_000_000

def validate_document(raw,pin,at):
    if sha256(raw).hexdigest()!=_must_sha(pin,'individual file'):
        raise SourceShareError('individual report SHA mismatch')
    d=_json(raw,'individual assessment')
    if (d.get('schema')!=SOURCE or d.get('producer')!='EraLeader'
            or d.get('research_only') is not True or d.get('orders')!=0
            or d.get('watch_membership_changed') is not False or d.get('investment_rank_created') is not False
            or d.get('method')!=METHOD or canonical(d)+b'\n'!=raw):
        raise SourceShareError('unsupported individual assessment')
    if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}',str(d['producer_code_sha'])):
        raise SourceShareError('producer Git revision required')
    if sha256(canonical({k:v for k,v in d.items() if k!='content_sha256'})).hexdigest()!=d['content_sha256']:
        raise SourceShareError('individual content SHA mismatch')
    published=_when(d['published_at'],'individual published')
    if published>at:raise SourceShareError('future individual assessment')
    c=d['company'];a=d['assessment'];f=d['financial'];m=d['market_source'];inputs=a['inputs']
    if (not re.fullmatch(r'[0-9]{6}',str(c['security_id']))
            or not re.fullmatch(r'[0-9]{8}',str(c['issuer_corp_code']))
            or not isinstance(c['name'],str) or not 1<=len(c['name'])<=150
            or a['method']!=METHOD or a['security_id']!=c['security_id']
            or a['issuer_corp_code']!=c['issuer_corp_code'] or inputs['security_id']!=c['security_id']
            or a['orders_enabled'] is not False or a['leader_score_unchanged'] is not True
            or a['valuation']['status']!='N/A' or a['competitiveness']['score_20'] is not None
            or a['source_market_session']!=m['market_session']
            or any(f.get(k)!=v for k,v in inputs.items() if k not in {'security_id','observed_industry_code'}
                   and not k.startswith('dart_cashflow_'))):
        raise SourceShareError('individual company/input mismatch')
    if _when(m['available_at'],'market available')>published:
        raise SourceShareError('future individual market')
    _must_sha(m['file_sha256'],'market file');_must_sha(m['content_sha256'],'market content')
    sources=d['annual_sources'];year=f['dart_latest_cfs_business_year']
    if (type(year) is not int or not 2015<=year<at.year or a['annual_fiscal_year']!=year
            or f['dart_cfs_issuer_corp_code']!=c['issuer_corp_code']
            or not isinstance(sources,list) or len(sources)!=2
            or sorted(x['fiscal_year'] for x in sources)!=[year-1,year]):
        raise SourceShareError('individual annual pair required')
    for s in sources:
        old=s['fiscal_year']==year-1;prefix='dart_cfs_previous_' if old else 'dart_cfs_'
        reference=a['sources']['previous_annual' if old else 'annual']
        if (s['security_id']!=c['security_id'] or s['issuer_corp_code']!=c['issuer_corp_code']
                or (s['statement'],s['report_code'],s['currency'])!=('CFS','11011','KRW')
                or not re.fullmatch(r'[0-9]{14}',s['report_accession'])
                or _when(s['available_at'],'annual available')>published
                or f[prefix+'first_receipt_sha256']!=s['first_receipt_sha256']
                or f[prefix+'first_received_at_utc']!=s['available_at']
                or reference['first_receipt_sha256']!=s['first_receipt_sha256']
                or reference['issuer_corp_code']!=c['issuer_corp_code'] or reference['fiscal_year']!=s['fiscal_year']):
            raise SourceShareError('individual annual source mismatch')
        _must_sha(s['first_receipt_sha256'],'annual receipt');_must_sha(s['raw_sha256'],'annual raw')
    return d

def import_individual(era_root,manifest,expected_sha,output_root,*,now=None,check_only=False):
    at=now or datetime.now(timezone.utc);era_root=Path(era_root);p=Path(manifest);out=Path(output_root)
    _check_directory(p.parent,era_root)
    if (p.name!='report.json' or p.parent.parent!=era_root/'output/news_company_assessment'
            or out.resolve().is_relative_to(era_root.resolve())):
        raise SourceShareError('completed individual output and separate News receipt required')
    raw=_read_regular(p,LIMIT);d=validate_document(raw,expected_sha,at)
    if p.parent.name!=d['content_sha256']:raise SourceShareError('individual folder mismatch')
    _read_regular(p.with_name('index.html'),LIMIT)
    m=d['market_source'];market=Path(m['file']);_check_directory(market.parent,era_root)
    original=_read_regular(market,16*1024*1024)
    md=_json(original,'completed market')
    company=d['company']
    matches=[r for r in md['securities'] if r['security_id']==company['security_id']]
    if (sha256(original).hexdigest()!=m['file_sha256'] or md['content_sha256']!=m['content_sha256']
            or md['market_session']!=m['market_session'] or md['built_at_utc']!=m['available_at']
            or len(matches)!=1 or matches[0]['name']!=company['name']
            or matches[0]['current_dart_directory_matched'] is not True):
        raise SourceShareError('individual original market/identity mismatch')
    for s in d['annual_sources']:
        folder=Path(s['folder']);_check_directory(folder,era_root)
        if folder.parent!=era_root/'output/official_api_capture':
            raise SourceShareError('individual official capture path required')
        receipt=_read_regular(folder/'first_receipt.json',32768);meta=_json(receipt,'annual first receipt')
        original=_read_regular(folder/'raw_response.json',24*1024*1024)
        if (sha256(receipt).hexdigest()!=s['first_receipt_sha256']
                or sha256(original).hexdigest()!=s['raw_sha256'] or meta['raw_sha256']!=s['raw_sha256']
                or meta['raw_length']!=len(original) or meta['stock_code']!=company['security_id']
                or meta['corp_code']!=company['issuer_corp_code'] or meta['bsns_year']!=s['fiscal_year']
                or meta['statement']!='CFS' or meta['reprt_code']!='11011'
                or meta['report_accessions']!=[s['report_accession']]
                or meta['first_local_received_at_utc']!=s['available_at']):
            raise SourceShareError('individual original annual mismatch')
    if _read_regular(p,LIMIT)!=raw:raise SourceShareError('individual publication changed')
    if check_only:
        return {'status':'VERIFIED_READ_ONLY','source_sha256':expected_sha,
                'security_id':company['security_id']}
    root=_private_root(out/'individual')
    for receipt,_ in read_individuals(out,as_of=at,now=at)[0]:
        if receipt['source_sha256']==expected_sha:
            return {'status':'ALREADY_IMPORTED','source_sha256':expected_sha,'imported_at':receipt['imported_at']}
    receipt={'schema':SCHEMA,'source_sha256':expected_sha,'source_payload':raw.decode(),'imported_at':at.isoformat()}
    stored=canonical(receipt)+b'\n';h=sha256(stored).hexdigest()
    _write_new(root/('individual_'+h+'.json'),stored)
    return {'status':'IMPORTED','source_sha256':expected_sha,'imported_at':receipt['imported_at']}

def read_individuals(root,*,as_of,now):
    folder=Path(root)/'individual';latest={};skipped=0
    if not folder.exists():return [],0
    if as_of>now:raise SourceShareError('future individual query')
    paths=sorted(folder.glob('individual_*.json'))
    if len(paths)>200:raise SourceShareError('too many individual receipts')
    for p in paths:
        try:
            raw=_read_once(p,LIMIT*2);r=_json(raw,'individual receipt')
            if p.name!='individual_'+sha256(raw).hexdigest()+'.json' or r['schema']!=SCHEMA:
                raise SourceShareError('individual receipt mismatch')
            imported=_when(r['imported_at'],'individual import')
            if imported>now:raise SourceShareError('future individual receipt')
            d=validate_document(r['source_payload'].encode(),r['source_sha256'],imported)
            if imported>as_of:continue
            key=d['company']['security_id'];order=(d['published_at'],r['imported_at'],r['source_sha256'])
            if key not in latest or order>latest[key][0]:latest[key]=(order,(r,d))
        except (SourceShareError,KeyError,TypeError,ValueError,OSError):skipped+=1
    return [v[1] for v in latest.values()],skipped

def assessment_for_individual(entity,records):
    from .era_daily_assessment import _name
    rows=[(r,d) for r,d in records if entity in {'KRX_STOCK:'+d['company']['security_id'],
        'DART_CORP:'+d['company']['issuer_corp_code']} or _name(entity)==_name(d['company']['name'])]
    if not rows:return None
    if len(rows)!=1:return {'status':'AMBIGUOUS_IDENTITY','value':None,'verified_real_benefit':False,'orders_enabled':False}
    r,d=rows[0];c=d['company'];f=d['financial']
    annual={'status':'DART_VERIFIED_ANNUAL_CFS','security_id':c['security_id'],'issuer_corp_code':c['issuer_corp_code'],
        'fiscal_year':f['dart_latest_cfs_business_year'],'first_receipt_sha256':f['dart_cfs_first_receipt_sha256'],
        'first_local_received_at_utc':f['dart_cfs_first_received_at_utc'],'existing_financial_assessment':deepcopy(d['assessment'])}
    for target,field in [('revenue_krw','revenue_krw'),('operating_income_krw','operating_income_krw'),
        ('net_income_krw','net_income_krw'),('operating_margin_pct','operating_margin_pct'),
        ('operating_cashflow_krw','operating_cashflow_krw'),('cash_after_ppe_intangibles_krw','cash_after_ppe_intangibles_krw')]:
        annual[target]=f.get('dart_cfs_'+field)
    return {'status':'AVAILABLE','producer':'EraLeader','assessment_scope':'INDIVIDUAL_COMPANY_RESEARCH',
        'value':{'name':c['name'],'security_id':c['security_id'],'dart_annual_cfs':annual,
                 'formal_selection_state':'INDIVIDUAL_COMPANY_RESEARCH','krx_completed_close':{'status':'N/A'},
                 'official_annual_sources':deepcopy(d['annual_sources']),'investment_rank':None,'orders':0},
        'entity_id':'DART_CORP:'+c['issuer_corp_code'],'security_id':c['security_id'],'source_name':c['name'],
        'identity_method':'EXACT_OFFICIAL_COMPANY_RECEIPTS','identity_evidence_sha256':annual['first_receipt_sha256'],
        'source_sha256':r['source_sha256'],'source_content_sha256':d['content_sha256'],
        'producer_evaluated_at':d['published_at'],'market_session':d['market_source']['market_session'],
        'imported_at':r['imported_at'],'evidence_level':'PRODUCER_ASSESSMENT_NOT_INDEPENDENT_CERTIFICATION',
        'investment_merit':'NOT_ASSESSED','verified_real_benefit':False,'orders_enabled':False}
