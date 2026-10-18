"""Source-reported execution versus earlier plans; no separate store or fetcher."""
from datetime import date
import re
from .public_demand_analysis import _text
from .provider_registry import _safe_https_endpoint
from .source_share import SourceShareError,_when

FIELDS={'anchor_note_id','project_relation','matching_basis','evidence_stage','period_end','counter_reference'}
RELATIONS={'SAME_PROJECT_EXPLICIT','RELATED_BUSINESS_ONLY'}
STAGES={'ORDER_RESULTS':'REPORTED_ORDER_PERFORMANCE','DELIVERY_PLANNED':'PLAN_ONLY','INDIVIDUAL_ORDER':'REPORTED_CONTRACT',
        'DELIVERY_COMPLETED':'REPORTED_DELIVERY','SHIPMENT_COMPLETED':'REPORTED_SHIPMENT','DELIVERY_DELAY':'REPORTED_DELAY',
        'DEMAND_REDUCTION':'DEMAND_REDUCTION','CANCELLATION':'CANCELLATION','RISK_COMMENTARY':'RISK_ONLY'}
LABELS={'SOURCE_REPORTED_PROJECT_PROGRESS':'관련 프로젝트 출하 진전 · 기업별 납품 미확인',
        'SOURCE_REPORTED_PROGRESS':'원문상 개별 발주·납품 진전',
        'SOURCE_REPORTED_SETBACK':'원문상 이행 지연·취소·수요 감소',
        'MIXED_EXECUTION_EVIDENCE':'이행 진전·차질 근거 혼재',
        'NO_NEW_EXECUTION_PROOF':'개별 계약의 추가 이행 근거 미확보'}
COUNTER_FIELDS={'title','source_url','reported_date','analysis_text','access_basis'}

def validate_execution(note):
    x=note['execution']
    if not isinstance(x,dict) or set(x) not in (FIELDS,FIELDS|{'execution_scope'}):raise SourceShareError('exact execution comparison fields required')
    if not re.fullmatch('[0-9a-f]{64}',str(x['anchor_note_id'])):raise SourceShareError('exact earlier note required')
    if x['project_relation'] not in RELATIONS or not _text(x['matching_basis'],200):
        raise SourceShareError('bounded project relationship basis required')
    if x['evidence_stage'] not in STAGES or note['evidence_kind']!=STAGES[x['evidence_stage']]:
        raise SourceShareError('execution stage must match source claim kind')
    scope=x.get('execution_scope','NAMED_COMPANY')
    if scope not in {'NAMED_COMPANY','PROJECT_ONLY'}:
        raise SourceShareError('explicit company or project execution scope required')
    if x['evidence_stage']=='SHIPMENT_COMPLETED' and 'execution_scope' not in x:
        raise SourceShareError('shipment must declare its execution scope')
    if 'execution_scope' in x and x['evidence_stage']!='SHIPMENT_COMPLETED':
        raise SourceShareError('explicit execution scope currently supports shipment milestones')
    period=x['period_end']
    if period is not None and (note['reported_date'] is None or not isinstance(period,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',period)
                              or date.fromisoformat(period)>date.fromisoformat(note['reported_date'])):
        raise SourceShareError('reported period must end by the page date')
    counter=x['counter_reference']
    if counter is not None:
        if (not isinstance(counter,dict) or set(counter)!=COUNTER_FIELDS
                or not _text(counter['title'],256) or not _text(counter['analysis_text'],200)
                or counter['access_basis'] not in {'PUBLIC_SEARCH_RESULT_READING','PUBLIC_PAGE_READING'}):
            raise SourceShareError('bounded separate external risk reference required')
        _safe_https_endpoint(counter['source_url'])
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(counter['reported_date'])):
            raise SourceShareError('reported external reference date required')
        date.fromisoformat(counter['reported_date'])

def bind_anchor(note,company,anchors,at):
    x=note['execution'];anchor=anchors.get(x['anchor_note_id'])
    if (anchor is None or 'execution' in anchor['note']
            or anchor['source_company']!=company
            or anchor['note']['baseline_note_id']!=note['baseline_note_id']
            or _when(anchor['available_at'],'anchor available')>at):
        raise SourceShareError('same-company active earlier comparison required')
    counter=x['counter_reference']
    if counter and date.fromisoformat(counter['reported_date'])>at.date():
        raise SourceShareError('future external reference')
    return anchor

def attach_anchor(row,anchor):
    x=row['note']['execution'];n=row['note'];old=anchor['note']
    # Publication after an announcement cannot turn a prior accounting period
    # into performance of that announcement. Dates are claims, not PIT clocks.
    if n['reported_date'] is None:timing='PUBLICATION_DATE_UNAVAILABLE'
    elif n['reported_date']<old['reported_date']:timing='EARLIER_PUBLICATION'
    elif x['period_end'] is not None and x['period_end']<old['reported_date']:
        timing='LATER_PUBLICATION_PRIOR_PERIOD'
    else:timing='ON_OR_AFTER_ANCHOR'
    same=x['project_relation']=='SAME_PROJECT_EXPLICIT'
    eligible=same and timing=='ON_OR_AFTER_ANCHOR'
    company_scope=x.get('execution_scope','NAMED_COMPANY')=='NAMED_COMPANY'
    progress=eligible and company_scope and x['evidence_stage'] in {'INDIVIDUAL_ORDER','DELIVERY_COMPLETED','SHIPMENT_COMPLETED'}
    project_progress=eligible and not company_scope and x['evidence_stage']=='SHIPMENT_COMPLETED'
    setback=eligible and x['evidence_stage'] in {'DEMAND_REDUCTION','CANCELLATION','DELIVERY_DELAY'}
    result=dict(row,execution_context={
        'anchor_note_id':anchor['note_id'],'anchor_headline':old['recent_source']['headline'],
        'anchor_reported_date':old['reported_date'],'anchor_source_url':old['recent_source']['source_url'],
        'anchor_available_at':anchor['available_at'],'chronology':timing,
        'project_relation':x['project_relation'],'matching_basis':x['matching_basis'],
        'reported_execution_progress':progress,'reported_execution_setback':setback,
        'project_identity_independently_verified':False,'source_claim_not_independent_fact':True})
    if 'execution_scope' in x:
        result['execution_context'].update(execution_scope=x['execution_scope'],
            reported_project_execution_progress=project_progress,
            shipment_is_final_delivery=False,shipment_is_grid_operation=False)
    return result

def summarize_execution(rows,companies):
    selected=[r for r in rows if 'execution_context' in r]
    if not selected:return None
    results=[]
    for company in sorted(companies):
        members=[r for r in selected if r['source_company']==company]
        progress=any(r['execution_context']['reported_execution_progress'] for r in members)
        setback=any(r['execution_context']['reported_execution_setback'] for r in members)
        project_progress=any(r['execution_context'].get('reported_project_execution_progress') for r in members)
        status=('MIXED_EXECUTION_EVIDENCE' if (progress or project_progress) and setback else
                'SOURCE_REPORTED_PROGRESS' if progress else 'SOURCE_REPORTED_SETBACK' if setback else 'SOURCE_REPORTED_PROJECT_PROGRESS' if project_progress else 'NO_NEW_EXECUTION_PROOF')
        risk=[r for r in members if r['note']['execution']['counter_reference'] is not None
              or r['note']['execution']['evidence_stage']=='RISK_COMMENTARY']
        results.append({'source_company':company,'status':status,'status_label':('원문상 개별 출하·출항 진전 · 최종 납품 미확인' if status=='SOURCE_REPORTED_PROGRESS' and any(r['note']['execution']['evidence_stage']=='SHIPMENT_COMPLETED' for r in members) else LABELS[status]),
            'evidence_note_ids':[r['note_id'] for r in members],
            'risk_reference_note_ids':[r['note_id'] for r in risk],
            'unavailable_is_weakening':False})
    progress=any(r['status'] in {'SOURCE_REPORTED_PROGRESS','MIXED_EXECUTION_EVIDENCE'} for r in results)
    setback=any(r['status'] in {'SOURCE_REPORTED_SETBACK','MIXED_EXECUTION_EVIDENCE'} for r in results)
    project_progress=any(r['status']=='SOURCE_REPORTED_PROJECT_PROGRESS' for r in results)
    status=('MIXED_EXECUTION_EVIDENCE' if (progress or project_progress) and setback else
            'SOURCE_REPORTED_PROGRESS' if progress else 'SOURCE_REPORTED_SETBACK' if setback else 'SOURCE_REPORTED_PROJECT_PROGRESS' if project_progress else 'NO_NEW_EXECUTION_PROOF')
    label=('원문상 개별 출하·출항 진전 · 최종 납품 미확인' if status=='SOURCE_REPORTED_PROGRESS' and any(r['note']['execution']['evidence_stage']=='SHIPMENT_COMPLETED' for r in selected) else LABELS[status])
    return {'status':status,'status_label':label,'company_results':results,
            'basis_available_at':max(r['available_at'] for r in selected),
            'risk_commentary_is_actual_reversal':False,'article_count_used_as_strength':False,
            'aggregate_results_imply_specific_contract_delivery':False,
            'source_truth_independently_verified':False}
