"""Read-only reported contract amounts from exact linked RSS title versions.

The existing followup link supplies identity, never company/title similarity.
Amounts are source claims, not realized sales, profit or verified benefits.
"""
from decimal import Decimal
import re

from .economic_changes import mentions_name
from .fact_extraction import MONEY
from .feed_analysis import _category, _krw, PLANNED
from .source_share import _when, SourceShareError

REASONS = {
    'READY': '같은 문서의 명시적 감액 보도와 저장된 이전 계약 제목을 비교했습니다.',
    'NO_STORED_REVISION': '조회 시점에 연결 가능한 저장 금액 변경이 없습니다.',
    'AMOUNT_UNKNOWN': '계약 금액 또는 단위를 명확하게 확인할 수 없습니다.',
    'MULTIPLE_AMOUNTS': '여러 금액 또는 계약이 있어 비교 대상을 확정할 수 없습니다.',
    'CURRENCY_UNSUPPORTED': '통화가 다르거나 원화로 명시되지 않아 비교하지 않습니다.',
    'ZERO_BASE': '이전 또는 변경 후 금액이 0이어서 차액·증감률을 계산하지 않습니다.',
    'TARGET_AMOUNT_UNCLEAR': '감액분과 변경 후 계약 총액을 구별할 수 없습니다.',
    'DIRECTION_MISMATCH': '보도된 감액 방향과 두 금액이 일치하지 않습니다.',
}
CONTRACT = re.compile(r'(?:공급|납품|수주)\s*계약')


def compare_amounts(before, after):
    """One explicitly denominated KRW contract total per title; no FX guessing."""
    result = dict(status='AMOUNT_UNKNOWN', before_amount=None, after_amount=None,
                  currency=None, difference=None, percent_change=None)
    mentions = [[m.group().strip() for m in MONEY.finditer(t)] for t in (before, after)]
    if any(len(m)>1 for m in mentions) or any(len(CONTRACT.findall(t))!=1 for t in (before, after)):
        result['status']='MULTIPLE_AMOUNTS'
    elif all(len(m)==1 for m in mentions):
        a,b=mentions[0][0],mentions[1][0]
        result.update(before_amount=a,after_amount=b)
        if max(sum(c.isdigit() for c in m) for m in (a,b))>15:
            result['reason']=REASONS[result['status']];return result
        left,right=_krw(a),_krw(b)
        if (left is None or right is None or
                any(re.search(r'\$|USD|EUR|JPY|CNY|달러|유로|엔화|위안',t,re.I) for t in (before,after))):
            result['status']='CURRENCY_UNSUPPORTED'
        elif not re.search(re.escape(b)+r'\s*(?:으로|로)\s*(?:감액|감소|축소|삭감)',after):
            result['status']='TARGET_AMOUNT_UNCLEAR'
        elif left==0 or right==0:
            result['status']='ZERO_BASE'
        elif right>=left:
            result['status']='DIRECTION_MISMATCH'
        else:
            result.update(status='READY',currency='KRW',before_value=str(left),after_value=str(right),
                          difference=str(right-left),percent_change=str(((right-left)/left*100).quantize(Decimal('.01'))))
    result['reason']=REASONS[result['status']]
    return result


def contract_amount_history(before, ref, reports, *, at, read_source):
    """Attach saved reductions to the original contract's company evidence card.

    Future reports are skipped entirely, including their existence/count. Each
    returned title has passed the existing current-rights/checkpoint/SHA reader.
    Repeated analysis of a version does not create another amount change.
    """
    result={'status':'NO_STORED_REVISION','changes':[],
            'evidence_limit':'REPORTED_CONTRACT_AMOUNT_NOT_REALIZED_REVENUE_OR_BENEFIT'}
    if _category(before['headline'])!='NEW_CONTRACT' or PLANNED.search(before['headline']):
        result['reason']=REASONS['NO_STORED_REVISION'];return result
    names=[m['source_name'] for m in ref.get('company_mappings',[])] or ref['entity_ids']
    seen=set()
    for row,available,pin,body in sorted(reports,key=lambda r:(r[1],r[2])):
        if body or _when(available,'report')>at:continue
        if any(row[k]!=before[k] for k in ('provider_id','document_id','source_event_sha256','source_url')):continue
        if _when(row['source_available_at'],'revision')<=_when(before['source_available_at'],'original'):continue
        link=row.get('followup_change')
        if not isinstance(link,dict):continue
        if (link.get('change_kind')!='CONTRACT_REDUCED' or link.get('status')!='WEAKENED_CANDIDATE'
                or link.get('scope')!='SAME_PROVIDER_DOCUMENT_AND_EXPLICIT_PRIOR_CONTRACT_TITLE'
                or link.get('prior_title_sha256')!=before['source_title_sha256']
                or link.get('prior_available_at')!=before['source_available_at']):continue
        try:
            if not _when(row['source_available_at'],'revision')<=_when(link.get('available_at'),'followup')<=_when(available,'report')<=at:continue
        except (SourceShareError,TypeError,ValueError):continue
        if (_category(row['headline'])!='CONTRACT_REDUCTION'
                or not any(mentions_name(row['headline'],n) for n in names)
                or re.search(r'별도|다른\s*계약|신규\s*계약',row['headline'])):continue
        if row['source_title_sha256'] in seen:continue
        source_ref=dict(source_id=row['provider_id'],evidence_sha256=row['source_title_sha256'],
                        source_url=row['source_url'],source_available_at=row['source_available_at'])
        text,status=read_source(source_ref,row)
        if text is None:
            # No title or numeric disclosure when rights/original evidence fails.
            result['status']=status;continue
        seen.add(row['source_title_sha256'])
        comparison=compare_amounts(before['headline'],text)
        comparison['after_source']={k:row[k] for k in ('provider_id','document_id','source_event_sha256',
            'analysis_event_sha256','source_title_sha256','source_url','source_available_at')}
        comparison['after_source'].update(headline=text,analysis_available_at=available,report_sha256=pin)
        comparison['before_source']={k:before[k] for k in ('provider_id','document_id','source_event_sha256',
            'analysis_event_sha256','source_title_sha256','source_url','source_available_at')}
        comparison['before_source']['headline']=before['headline']
        result['changes'].append(comparison)
    if result['changes']:result['status']='AVAILABLE'
    result['reason']=REASONS.get(result['status'],'저장된 금액 변경 근거입니다.' if result['changes'] else '변경 판본의 사용권·원본 근거를 확인할 수 없습니다.')
    return result
