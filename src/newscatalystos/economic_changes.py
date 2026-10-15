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
_QUOTED_NAME = r'(?:‘[^’\n]{2,80}’|“[^”\n]{2,80}”|「[^」\n]{2,80}」|"[^"\n]{2,80}"|\'[^\'\n]{2,80}\')'
_START_VERB = r'(?:개시|시작|출시|나선다|나설)(?=$|[\s,.!…·]|했|하|해|한|할|됐|되|된|를|에)'
_START_MODIFIER = r'(?:(?:정식|공식|본격|국내|전국|글로벌|상업)\s*)?'
BUSINESS_ACTION = (r'(?:서비스|사업|운영)(?:을|를|에|가|는)?\s*(?:'+_QUOTED_NAME+r'\s*)?'
                   +_START_MODIFIER+_START_VERB)
_BUSINESS_CONTEXT = re.compile(
    r'(?:개시|시작|출시).{0,15}(?:기념|주년|행사|설명회|세미나|방법|가능성|위한|위해|협약|양해각서|하지\s*않|하지\s*못|되지\s*않)'
    r'|(?:체험|시범|시험)\s*(?:서비스|운영)|취소|철회|무산|부인|사실\s*무근'
    r'|(?:지난해|지난달|작년|과거|이미).{0,60}(?:개시|시작|출시)')
_BUSINESS_PLAN = re.compile(r'예정|계획|추진|준비|검토|목표|예고|나선다|나설|앞두|앞둔')


def business_start_phase(text):
    """Explicit service/business operation claim; intention is not operation."""
    if not re.search(BUSINESS_ACTION, text) or _BUSINESS_CONTEXT.search(text):
        return None
    return 'PLANNED' if _BUSINESS_PLAN.search(text) else 'SOURCE_REPORTED'


def business_start_names(text):
    if business_start_phase(text) is None:
        return []
    result=[]
    for match in re.finditer(_QUOTED_NAME, text):
        before,after=text[:match.start()],text[match.end():]
        direct_after=re.match(r'\s*(?:서비스|사업)(?:을|를|가|는)?\s*'+_START_MODIFIER+_START_VERB,after)
        direct_before=(re.search(r'(?:서비스|사업)\s*$',before) and
                       re.match(r'\s*'+_START_MODIFIER+_START_VERB,after))
        name=match.group()[1:-1].strip()
        if (direct_after or direct_before) and name and name not in result:
            result.append(name)
    return result[:10]


_SERVICE_FUNCTION = re.compile(r'(?:추천|검색|매칭|분석|검사|진단|번역|예약|배송|정산|결제|관리|모니터링)$')
_SERVICE_GENERIC = {'AI', '인공지능', '기반', '맞춤', '맞춤형', '통합', '자동', '신규',
                    '새', '새로운', '혁신', '혁신적', '혁신적인', '스마트', '디지털',
                    '고객', '기업', '개인', '국내', '글로벌', '온라인', '실시간'}


def business_start_functions(text):
    """Exact service object + function, only when no service brand is named.

    A purpose phrase is a source description, not evidence of shared demand.
    Require a concrete object as well as the function; AI/matched/new alone
    cannot become a theme. Do not carry context across sentences or clauses.
    """
    if business_start_phase(text) is None or business_start_names(text):
        return []
    result=[]
    for action in re.finditer(BUSINESS_ACTION, text):
        if not action.group().startswith('서비스'):
            continue
        prefix=re.split(r'[,，:;.!?。…\n]', text[:action.start()])[-1].strip()
        # A technology qualifier is not the service's object or its company.
        prefix=re.split(r'(?<!\w)(?:AI|인공지능)\s*기반\s+', prefix, flags=re.I)[-1]
        words=prefix.split()
        if (not 2 <= len(words) <= 8 or len(prefix)>80
                or not re.fullmatch(r'[가-힣A-Za-z0-9/· -]+',prefix)
                or not _SERVICE_FUNCTION.fullmatch(words[-1])
                or any(re.search(r'(?:은|는|에서|에게|위해|따라)$',w) for w in words[:-1])
                or not any(w.casefold() not in {x.casefold() for x in _SERVICE_GENERIC}
                           for w in words[:-1])):
            continue
        if prefix not in result:
            result.append(prefix)
    return result[:10]


ACTIONS = (
    ('POLICY_CHANGE', r'(?:개정안|개정령안|법안).{0,130}(?:의결|통과)|규제.{0,25}(?:폐지|완화)|허가.{0,20}(?:승인|취득)'),
    ('PRODUCTION_START', r'(?:양산|생산).{0,12}(?:시작|개시)|가동을?\s*시작'),
    ('CAPACITY_ADDITION', r'(?:생산능력|생산량|공급량).{0,30}(?:증가|확대|늘렸|증설)'),
    ('SUPPLY_REDUCTION', r'(?:생산|공급).{0,20}(?:중단|축소|감산)'),
    ('CONTRACT', r'(?:공급\s*계약|수주\s*계약|납품\s*계약).{0,20}(?:체결|수주)'),
    ('INVESTMENT', r'(?:신규|새로).{0,30}투자.{0,25}(?:결정|확정)|투자.{0,15}(?:결정|확정)'),
    ('BUSINESS_START', BUSINESS_ACTION),
)
UNCERTAIN = re.compile(r'검토\s*중|논의\s*중|가능성|(?<!\w)가정(?=$|[^\w]|하|한|해)|미확정|계획이\s*없|하지\s*않|사실이\s*아니|체결되지|취득하지|의결되지')
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
        business_phase=business_start_phase(line)
        names=business_start_names(line) if business_phase else []
        demand=_demand_topic(line, company_names)
        action = next((name for name, pattern in ACTIONS if re.search(pattern, evidence_line, re.I)
                       and (name!='BUSINESS_START' or business_phase)), None)
        functions=business_start_functions(line) if action=='BUSINESS_START' else []
        topic=demand or next((name for name,pattern in TOPICS
            if re.search(pattern,evidence_line,re.I)),None) or (names[0] if len(names)==1 else None)
        # Existing named/known topics retain their event identity.
        topic=topic or (functions[0] if len(functions)==1 else None)
        if topic is None or action is None:
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
                     else business_phase if action == 'BUSINESS_START'
                     else 'PLANNED' if re.search(r'예정|할 계획|할 방침', line) else 'SOURCE_REPORTED'),
            'entity_ids':companies,
            **({'original_entity_ids':original_companies} if companies!=original_companies else {}),
            'industry_tags':['SEMICONDUCTOR'] if re.search(r'반도체|HBM|DRAM|NAND|메모리|EUV|DUV|극자외선|심자외선',line,re.I) else [],
            'source_paragraph_sha256':sha256(paragraph.strip().encode()).hexdigest(),
            'evidence_level':'OFFICIAL_SOURCE', 'verified_economic_effect':False})
        if len(changes) >= 30:
            break
    return changes
