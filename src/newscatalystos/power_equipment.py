"""Opt-in V1.1 power-equipment title profile; V1 semiconductor rules unchanged.

The initial Korean action grammar requires one explicit subject, equipment and
business action in the same sentence. A grid/data-centre story is not a vendor
order. Transformer AI models and power semiconductors are not transformers.
No web access, issuer-code guessing, new financial score or paid AI.
"""
from hashlib import sha256
import re

INDUSTRY='POWER_EQUIPMENT'
RULE_VERSION='rss-power-equipment-v1'
PRODUCTS=(
    ('변압기',r'변압기|\b(?:power|distribution|ultra.high.voltage)\s+transformers?\b'),
    ('차단기',r'차단기|\bcircuit\s+breakers?\b'),
    ('배전설비',r'수배전반|수배전\s*설비|배전반|배전\s*설비|\bswitchgear\b|\bswitchboards?\b'),
)
SUBJECT=re.compile(r'^(?P<name>[가-힣A-Za-z0-9][가-힣A-Za-z0-9&.·\- ]{1,69}?)(?:(?:은|는|이|가)\s+|\s*,\s*)')
COMPANY_SUFFIX=re.compile(r'(?:전기|전력|전자|중공업|일렉트릭|Electric|ELECTRIC)$')
EXCLUDED_NAME=re.compile(r'변압기|차단기|배전|송전|수요|시장|업계|정부|장관|대통령|산업부|보도')
UNCERTAIN=re.compile(r'루머|추측|미확인|검토|검토설|전망|예상|기대|가능성|부인|사실\s*무근|'
    r'취소|철회|해지|보류|무산|않|못|기념|세미나|설명회|교육|소개|주년|\b(?:rumou?r|denies|unconfirmed|cancelled|canceled)\b',re.I)
PLANNED=re.compile(r'계획|예정|추진|방침|목표|\b(?:plan\w*|will|proposed)\b',re.I)
ACTION_PATTERNS=(
    ('CONTRACT',r'(?:공급|납품|수주)\s*계약(?:을|를)?\s*(?:체결|수주)'),
    ('INVESTMENT_EXECUTION',r'투자(?:를)?\s*집행'),
    ('INVESTMENT',r'투자(?:를)?\s*(?:결정|확정)'),
    ('CAPACITY_ADDITION',r'생산능력(?:을|를)?\s*(?:[0-9.,]+\s*(?:배|%)(?:로|만큼)?\s*)?(?:확대|증설)'),
    ('PRODUCTION_START',r'(?:양산|생산|가동)(?:을|를)?\s*(?:개시|시작)'),
    ('DELIVERY_START',r'납품(?:을|를)?\s*(?:개시|시작)'),
)


def matched_equipment(text):
    if not isinstance(text,str) or len(text)>5000:return ()
    return tuple(dict.fromkeys(m.group() for _,pattern in PRODUCTS for m in re.finditer(pattern,text,re.I)))


def extract_power_equipment_changes(text,*,company_names=()):
    if (not isinstance(text,str) or len(text)>5000
            or not isinstance(company_names,(list,tuple)) or len(company_names)>100
            or any(not isinstance(x,str) or not 0<len(x)<=120 for x in company_names)):
        raise ValueError('bounded title/company input required')
    out=[]
    for paragraph in text.splitlines():
        if not paragraph.strip():continue
        for sentence in re.split(r'(?<=[!?。])\s+|(?<=\.)(?<!\.\.)\s+',paragraph.strip()):
            subject=SUBJECT.match(sentence)
            if not subject or UNCERTAIN.search(sentence):continue
            actor=subject['name'].strip()
            if (EXCLUDED_NAME.search(actor) or (actor not in company_names and not COMPANY_SUFFIX.search(actor))):continue
            tail=sentence[subject.end():]
            topics=[(name,m) for name,pattern in PRODUCTS for m in re.finditer(pattern,tail,re.I)]
            unique={name for name,_ in topics}
            if len(unique)!=1:continue
            # No borrowed equipment context across a second explicit company,
            # or a semiconductor event sharing the same headline.
            if re.search(r'[가-힣A-Za-z0-9]+(?:전기|전력|전자|중공업|일렉트릭)(?:은|는|이|가|,)',tail):continue
            if any(n!=actor and re.search(re.escape(n)+r'(?:은|는|이|가|,)',tail) for n in company_names):continue
            if re.search(r'반도체|\b(?:HBM|DRAM|NAND|SiC|IGBT)\b',tail,re.I):continue
            actions=[(kind,m) for kind,pattern in ACTION_PATTERNS for m in re.finditer(pattern,tail)]
            if len(actions)!=1:continue
            action,verb=actions[0]
            # The equipment must be the action's literal preceding object,
            # not incidental context added after an unrelated corporate act.
            eligible=[(topic,m) for topic,m in topics if m.end()<=verb.start() and verb.start()-m.end()<=110]
            if not eligible:continue
            topic,mention=eligible[-1]
            if re.search(r'주가|주식|자사주|지분|채권|배당|부동산',tail[mention.end():verb.end()]):continue
            if action.startswith('INVESTMENT') and not re.search(r'공장|생산|설비|시설|증설|라인',tail):continue
            phase='PLANNED' if action=='INVESTMENT' or PLANNED.search(sentence) else 'SOURCE_REPORTED'
            driver='CAPACITY_EXPANSION' if action in {'INVESTMENT','INVESTMENT_EXECUTION','CAPACITY_ADDITION','PRODUCTION_START'} else 'UNKNOWN'
            row={'topic':topic,'economic_driver':driver,'action':action,'phase':phase,
                 'entity_ids':[actor],'industry_tags':[INDUSTRY],
                 'source_paragraph_sha256':sha256(paragraph.encode()).hexdigest(),
                 'evidence_level':'REPORTED','verified_economic_effect':False}
            if row not in out:out.append(row)
    return out[:30]
