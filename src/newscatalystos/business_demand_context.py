"""Optional source-title demand context after event detection; never rewrite events.

Equipment vocabulary is a downstream source-word hint only. The causal grammar
itself accepts unmapped industries. Missing cause evidence remains missing;
matching company claims do not verify a common market shock.
"""
from collections import defaultdict
from hashlib import sha256
import re

from .economic_discovery import SUBJECT, NEGATIVE, CONTEXT
from .economic_changes import normalized
from .power_equipment import PRODUCTS

CAUSE=re.compile(
    r'(?P<scope>[가-힣A-Za-z0-9· -]{2,100}?)\s+(?P<basis>수요|주문)\s*'
    r'(?P<direction>폭증|급증|증가|확대|회복|감소|축소)'
    r'(?:에(?:\s*(?:대응해|따라))?|로\s*인해)\s+(?P<object>[^,;!?。\n]{2,160})\s*')
GENERIC={'국내','해외','글로벌','세계','시장','제품','고객','기업','산업','관련','전체','AI','인공지능'}


def enrich_source_objects(rows):
    """Reuse profile words only AFTER detection, with an exact title substring.

    Spacing in 초고압변압기/초고압 변압기 cannot sever the literal 변압기
    connection. No translated name, absent product or supply-chain edge is added.
    """
    for row in rows:
        expression=row['object_evidence']['text']
        found=[(label,re.search(pattern,expression,re.I)) for label,pattern in PRODUCTS]
        found=[(label,m) for label,m in found if m]
        if len(found)!=1:
            continue
        label,match=found[0]
        # Retain only the canonical word literally present in this input.
        # English aliases are left to the ordinary literal-object view.
        if match.group()!=label:
            continue
        key=('OBJECT',normalized(label))
        if key not in row['objects']:
            row['source_product_word_hint']={
                'label':label,'status':'LITERAL_SOURCE_WORD_HINT_NOT_DEEP_PRODUCT_VALIDATION'}
        row['objects'][key]=label


def stated_demand(row):
    text=row['headline'];subject=SUBJECT.match(text)
    if (not subject or row['source_companies']!=[subject['actor']]
            or NEGATIVE.search(text) or CONTEXT.search(text)):
        return None
    verb=row['action_evidence']
    if text[verb['start']:verb['end']]!=verb['text']:
        return None
    prefix=text[subject.end():verb['start']]
    match=CAUSE.fullmatch(prefix)
    if not match or len(list(re.finditer(r'수요|주문',prefix)))!=1:
        return None
    scope=match['scope'].strip()
    if not any(t not in GENERIC and len(t)>=2 for t in scope.split()):
        return None
    # Another named subject cannot borrow this issuer's demand explanation.
    if re.search(r'[,;!?。]|…|\.{2,}|(?:은|는|이|가)\s+',match['object']):
        return None
    start=subject.end()+match.start('scope')
    end=subject.end()+match.end('direction')
    expression=text[start:end]
    evidence={'text':expression,'start':start,'end':end,
              'sha256':sha256(expression.encode()).hexdigest()}
    direction=match['direction']
    driver=('DEMAND_CONTRACTION' if direction in {'감소','축소'} else
            'DEMAND_RECOVERY' if direction=='회복' else 'DEMAND_EXPANSION')
    return {'scope':scope,'basis':'ORDER' if match['basis']=='주문' else 'DEMAND',
            'economic_driver':driver,'cause_evidence':evidence,
            'source_event_sha256':row['source_event_sha256'],
            'source_title_sha256':row['source_title_sha256'],'provider_id':row['provider_id'],
            'source_companies':row['source_companies'][:],'headline':text,
            'action':row['action'],'phase':row['phase'],'source_url':row['source_url'],
            'basis_available_at':row['basis_available_at'],
            'source_claim_only':True,'market_demand_verified':False}


def demand_coverage(rows):
    claims=[claim for row in rows if (claim:=stated_demand(row)) is not None]
    grouped=defaultdict(list)
    for claim in claims:
        grouped[(claim['economic_driver'],claim['basis'],normalized(claim['scope']))].append(claim)
    matches=[]
    for key,members in sorted(grouped.items()):
        names=sorted({n for c in members for n in c['source_companies']})
        signatures={(normalized(c['headline']),c['action']) for c in members}
        if len(names)>=2 and len(signatures)>=2:
            matches.append({'economic_driver':key[0],'basis':key[1],
                            'source_scope':members[0]['scope'],'source_company_names':names})
    names=sorted({n for r in rows for n in r['source_companies']})
    covered=sorted({n for c in claims for n in c['source_companies']})
    return {'status':'CROSS_COMPANY_SOURCE_MATCH' if matches else
                     'PARTIAL_SOURCE_COVERAGE' if claims else 'NO_EXPLICIT_SOURCE_CAUSE',
            'claims':claims,'matching_source_cause_groups':matches,
            'companies_with_explicit_cause':covered,
            'companies_without_explicit_cause':sorted(set(names)-set(covered)),
            'cross_company_source_cause_match':bool(matches),
            'common_market_shock_verified':False,'verified_real_benefit':False,
            'interpretation_basis':'EXACT_TITLE_SUBJECT_CAUSE_CONNECTOR_ACTION',
            'interpretation_is_historical_record':False,
            'original_events_unchanged':True}
