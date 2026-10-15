"""Source-grounded economic actions; no LLM/company-benefit certification.

Explicit action and topic must share a sentence. Unknown topics are accepted
in an explicit demand-response phrase, not from general headline similarity.
"""
from hashlib import sha256
import re
import unicodedata

TOPICS = (
    # Source-defined Korean/acronym pairs in licensed ministry article 171178.
    ('EUV', r'\bEUV\b|극자외선'), ('DUV', r'\bDUV\b|심자외선'),
    ('HBM', r'\bHBM\b|고대역폭\s*메모리'),
    ('액침냉각', r'액침\s*냉각|immersion\s+cooling'),
    ('DRAM', r'\bDRAM\b|디램'), ('NAND', r'\bNAND\b|낸드'),
    ('반도체', r'반도체|semiconductor'),
)
TOPIC_ALIASES = {
    'EUV': ('EUV','극자외선'), 'DUV': ('DUV','심자외선'),
    'HBM': ('HBM','고대역폭 메모리','고대역폭메모리'),
    'DRAM': ('DRAM','디램'), 'NAND': ('NAND','낸드'),
    '액침냉각': ('액침냉각','액침 냉각','immersion cooling'),
    '반도체': ('반도체','semiconductor'),
}
DRIVERS = {'POLICY_ENABLEMENT': '정책 기반 확대', 'DEMAND_EXPANSION': '수요 확대',
           'CAPACITY_EXPANSION': '생산능력 확대', 'SUPPLY_CONTRACTION': '공급 축소',
           'UNKNOWN': '공통 원인 미확인'}
ACTIONS = (
    ('POLICY_CHANGE', r'(?:개정안|개정령안|법안).{0,130}(?:의결|통과)|규제.{0,25}(?:폐지|완화)|허가.{0,20}(?:승인|취득)'),
    ('PRODUCTION_START', r'(?:양산|생산).{0,12}(?:시작|개시)|가동을?\s*시작'),
    ('CAPACITY_ADDITION', r'(?:생산능력|생산량|공급량).{0,30}(?:증가|확대|늘렸|증설)'),
    ('SUPPLY_REDUCTION', r'(?:생산|공급).{0,20}(?:중단|축소|감산)'),
    ('CONTRACT', r'(?:공급\s*계약|수주\s*계약|납품\s*계약).{0,20}(?:체결|수주)'),
    ('INVESTMENT', r'(?:신규|새로).{0,30}투자.{0,25}(?:결정|확정)|투자.{0,15}(?:결정|확정)'),
)
UNCERTAIN = re.compile(r'검토\s*중|논의\s*중|가능성|가정|미확정|계획이\s*없|하지\s*않|사실이\s*아니|체결되지|취득하지|의결되지')
PAST = re.compile(r'(?:지난해|작년|과거|기존|이미).{0,45}(?:의결|체결|시작|확대|결정)|지난\s*\d+월.{0,30}(?:체결|발표|결정)')
COMPANIES = re.compile(r'삼성전자|SK하이닉스|ASML|TSMC|마이크론|[가-힣A-Za-z]{2,20}(?:전자|반도체|소재|장비)')


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def mentions_name(text,name):
    """Whole source names with Korean particles; no fuzzy identity guessing."""
    return bool(re.search(r'(?<!\w)'+re.escape(normalized(name))+
        r'(?=$|[^\w]|(?:은|는|이|가|을|를|와|과|의|에|에게|에서|으로|로)(?=$|[^\w]))',normalized(text)))


# Prefer the demand subject over incidental product mentions. Multiword unknown
# terms must be quoted; unquoted unknown terms are a single explicit noun token.
_GENERIC_DEMAND = {'시장','제품','상품','관련','전체','국내','글로벌','해외','고객','기업',
                   '이런','이러한','해당','그','수출','산업','기술','수요','AI','인공지능'}
_DEMAND_TOPIC = '|'.join('(?:'+pattern+')' for _,pattern in TOPICS)
_DEMAND = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?P<topic>'+_DEMAND_TOPIC+
    r'|[「“\"\'][^」”\"\']{2,50}[」”\"\']|[가-힣A-Za-z][가-힣A-Za-z0-9-]{1,49}?)'
    r'\s*(?:의\s*)?수요(?:가)?\s*(?:증가|확대|급증)'
    r'(?:에\s*(?:대응(?:해|하여)?|따라|힘입어)|로\s*인해)', re.I)


def _demand_topic(sentence, company_names=()):
    matches=list(_DEMAND.finditer(sentence))
    topics=set()
    for match in matches:
        # A demand observation alone is not a new contract/production event.
        if not any(re.search(pattern,sentence[match.end():],re.I) for _,pattern in ACTIONS):
            continue
        term=match['topic'].strip('「」“”"\'').strip()
        if normalized(term) in {normalized(t) for t in _GENERIC_DEMAND}:continue
        # Do not pick just the last member of a coordinated demand subject.
        prefix=sentence[:match.start()].rstrip()
        # News titles commonly separate the actor from its action with a comma:
        # "회사명, 신기술 수요 증가에 대응해 ..." is not a topic list.
        actor_prefix = (prefix.endswith(',') and any(
            normalized(prefix[:-1].strip()) == normalized(name)
            for name in (*company_names, *COMPANIES.findall(prefix))))
        if re.search(r'(?:및|와|과|또는|,)\s*$',prefix) and not actor_prefix:continue
        term=next((name for name,pattern in TOPICS if re.fullmatch(pattern,term,re.I)),term)
        topics.add(term)
    return next(iter(topics)) if len(topics)==1 else None


def extract_economic_changes(text, *, company_names=()):
    """Return bounded source claims, including policy adoption before its effect.

    Corporate actions without an explicit common demand cause retain their own
    supply/capacity driver. A price-only article is not a capacity event.
    """
    if (not isinstance(company_names,(list,tuple)) or len(company_names)>100
            or any(not isinstance(n,str) or not n.strip() or len(n)>120 for n in company_names)):
        raise ValueError('bounded source company names required')
    changes = []
    seen = set()
    units=((paragraph,sentence.strip()) for paragraph in text.splitlines()
           if paragraph.strip() and len(paragraph)<=5000
           for sentence in re.split(r'(?<=[.!?。])\s+',paragraph.strip()) if sentence.strip())
    for paragraph,line in units:
        if len(line) > 5000 or UNCERTAIN.search(line) or PAST.search(line):
            continue
        # Demand and economic action must be in the same sentence; unrelated
        # context elsewhere in the paragraph cannot supply the common cause.
        evidence_line=line
        demand=_demand_topic(line, company_names)
        topic=demand or next((name for name,pattern in TOPICS
            if re.search(pattern,evidence_line,re.I)),None)
        if topic is None:
            continue
        action = next((name for name, pattern in ACTIONS if re.search(pattern, evidence_line, re.I)), None)
        if action is None:
            continue
        driver = ('POLICY_ENABLEMENT' if action == 'POLICY_CHANGE' else
                  'SUPPLY_CONTRACTION' if action == 'SUPPLY_REDUCTION' else
                  'DEMAND_EXPANSION' if demand else
                  'CAPACITY_EXPANSION' if action in {'PRODUCTION_START','CAPACITY_ADDITION'}
                      or (action == 'INVESTMENT' and re.search(r'공장|생산|증설', line)) else 'UNKNOWN')
        companies = sorted(set(COMPANIES.findall(evidence_line)))
        companies = [x for x in companies if x not in {'첨단반도체','대한민국반도체','한국반도체','산업소재','노광장비','첨단장비','반도체소재'}][:30]
        original_companies=companies[:]
        for name in company_names:
            if mentions_name(line,name) and not any(normalized(x)==normalized(name) for x in companies):
                companies.append(name)
        companies=sorted(set(companies[:30]))
        key = (topic, driver, action, tuple(original_companies))
        if key in seen:
            continue
        seen.add(key)
        changes.append({'topic':topic, 'economic_driver':driver, 'action':action,
            'phase':('ADOPTED_NOT_YET_EFFECTIVE' if action == 'POLICY_CHANGE' and '시행될 예정' in line
                     else 'PLANNED' if re.search(r'예정|할 계획|할 방침', line) else 'SOURCE_REPORTED'),
            'entity_ids':companies,
            **({'original_entity_ids':original_companies} if companies!=original_companies else {}),
            'industry_tags':['SEMICONDUCTOR'] if re.search(r'반도체|HBM|DRAM|NAND|메모리|EUV|DUV|극자외선|심자외선',line,re.I) else [],
            'source_paragraph_sha256':sha256(paragraph.strip().encode()).hexdigest(),
            'evidence_level':'OFFICIAL_SOURCE', 'verified_economic_effect':False})
        if len(changes) >= 30:
            break
    return changes
