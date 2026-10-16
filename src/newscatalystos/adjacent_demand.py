"""Literal adjacent-sentence demand links; never synthesize source sentences."""
from copy import deepcopy
from hashlib import sha256
import re
from .fact_extraction import MONEY

PRODUCT=r'HBM|DRAM|NAND'
CAUSE=re.compile(r'(?:(?P<qualifier>[가-힣A-Za-z0-9 ,/·&-]{1,120}용)\s+)?(?P<product>'+PRODUCT+r')\s+수요가\s+증가(?:하고\s+있다|했다)[.!。]')
REDUCTION_CAUSE=re.compile(CAUSE.pattern.replace('증가','감소'))
ACTION=re.compile(r'이에\s+따라\s+(?P<actor>[가-힣A-Za-z0-9·& ]{2,70})(?:은|는)\s+(?P<product>'+PRODUCT+r')\s+(?:(?P<amount>(?i:'+MONEY.pattern+r'))\s+)?(?:(?P<capacity>생산능력을\s+확대했다)|(?P<contract>공급계약을\s+체결했다)|(?P<reduction>생산을\s+(?:축소했다|감산했다)))[.!。]')


def legacy_driver(action):
    return {'CONTRACT':'UNKNOWN','SUPPLY_REDUCTION':'SUPPLY_CONTRACTION'}.get(action,'CAPACITY_EXPANSION')


def demand_driver(action):
    return 'DEMAND_CONTRACTION' if action=='SUPPLY_REDUCTION' else 'DEMAND_EXPANSION'


def parse_adjacent_demand(expression,*,include_scopes=True,include_contracts=True,include_amounts=True,include_reductions=True):
    """A deliberately small grammar: one factual cause, one named actor/action."""
    if not isinstance(expression,str) or len(expression)>500:return None
    sentences=list(re.finditer(r'(?:[^.!?。]|\.(?=\d))+[.!?。]',expression))
    if len(sentences)!=2 or expression[sentences[-1].end():].strip():return None
    left,right=[m.group().strip() for m in sentences]
    cause=CAUSE.fullmatch(left) or (REDUCTION_CAUSE.fullmatch(left) if include_reductions else None);action=ACTION.fullmatch(right)
    if not cause or not action or cause['product']!=action['product']:return None
    if bool(REDUCTION_CAUSE.fullmatch(left))!=bool(action['reduction']):return None
    if action['contract'] and not include_contracts:return None
    amount=action['amount']
    if amount:
        if not include_amounts or not action['contract'] or len(list(MONEY.finditer(expression)))!=1:return None
        from .feed_analysis import _krw
        if sum(c.isdigit() for c in amount)>15 or _krw(amount.strip()) is None or _krw(amount.strip())<=0:return None
    qualifier=cause['qualifier']
    if qualifier and (not include_scopes or re.search(r'HBM|DRAM|NAND|수요|주문|증가|감소|지난|과거|전망|예상|부인|않|취소|인용',qualifier)):return None
    if qualifier:
        from .economic_changes import COMPANIES
        if COMPANIES.search(qualifier):return None
    actor=action['actor']
    if re.search(r'(?:전자|소재|반도체|기업)(?:와|과)',actor):return None
    if actor in {'이회사','그회사','해당회사','회사','당사','동사','업체','그업체','해당기업','이기업','기업'}:return None
    # Positions refer to the exact stored source expression, including spaces.
    l=expression.index(left);r=expression.index(right,l+len(left))
    reported_amount=None
    if amount:
        value=amount.strip();start=r+action.start('amount')+len(amount)-len(amount.lstrip())
        reported_amount={'status':'SOURCE_REPORTED_TOTAL','currency':'KRW','source_expression':value,
            'expression_sha256':sha256(value.encode()).hexdigest(),'span':[start,start+len(value)],
            'verified_real_transaction':False,'verified_revenue':False}
    return {'source_expression':expression,'expression_sha256':sha256(expression.encode()).hexdigest(),
        'cause_expression':left,'cause_sha256':sha256(left.encode()).hexdigest(),'cause_span':[l,l+len(left)],
        'action_expression':right,'action_sha256':sha256(right.encode()).hexdigest(),'action_span':[r,r+len(right)],
        'product':cause['product'],'source_actor':actor,'connector':'이에 따라',
        **({'action':'CONTRACT'} if action['contract'] else {'action':'SUPPLY_REDUCTION'} if action['reduction'] else {}),
        **({'contract_amount':reported_amount} if reported_amount else {})}


def attach_adjacent_demand(text,changes,company_names,*,include_scopes=True,include_contracts=True,include_amounts=True,include_reductions=True):
    from .economic_changes import COMPANIES,extract_economic_changes,parse_demand_scope
    result=deepcopy(changes);matches={}
    for paragraph in text.splitlines():
        paragraph=paragraph.strip()
        if not paragraph or len(paragraph)>5000:continue
        sentences=list(re.finditer(r'(?:[^.!?。]|\.(?=\d))+[.!?。]',paragraph))
        if len(sentences)!=2 or paragraph[sentences[-1].end():].strip():continue
        for a,b in zip(sentences,sentences[1:]):
            expression=paragraph[a.start():b.end()].strip()
            proof=parse_adjacent_demand(expression,include_scopes=include_scopes,include_contracts=include_contracts,include_amounts=include_amounts,include_reductions=include_reductions)
            if not proof:continue
            actor=proof['source_actor']
            if actor not in company_names and actor not in COMPANIES.findall(actor):continue
            base=extract_economic_changes(proof['action_expression'],company_names=company_names,include_adjacent_demand=False)
            if len(base)!=1:continue
            row=base[0]
            expected_action=proof.get('action','CAPACITY_ADDITION')
            old_driver=legacy_driver(expected_action)
            if (row['topic']!=proof['product'] or row['action']!=expected_action
                or row['economic_driver']!=old_driver or row['phase']!='SOURCE_REPORTED'
                or row['entity_ids']!=[actor]):continue
            proof['paragraph_sha256']=sha256(paragraph.encode()).hexdigest()
            key=(proof['paragraph_sha256'],row['topic'],tuple(row['entity_ids']),row['action'])
            matches.setdefault(key,[]).append(proof)
    for row in result:
        key=(row['source_paragraph_sha256'],row['topic'],tuple(row['entity_ids']),row['action'])
        proofs=matches.get(key,[])
        # A competing assertion for the same action never picks a first cause.
        if len(proofs)!=1:continue
        expected_action=proofs[0].get('action','CAPACITY_ADDITION')
        old_driver=legacy_driver(expected_action)
        if row['action']!=expected_action or row['economic_driver']!=old_driver:continue
        row['economic_driver']=demand_driver(expected_action);row['adjacent_demand_cause']=proofs[0]
        scoped=parse_demand_scope(proofs[0]['cause_expression'])
        if scoped:row['demand_scope']=scoped[2]
    return result
