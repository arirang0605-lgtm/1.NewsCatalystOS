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
_NON_COMPANY_TERMS = {'첨단반도체','대한민국반도체','한국반도체','산업소재','노광장비','첨단장비','반도체소재'}


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
    r'(?P<connector>에\s*(?:대응(?:해|하여)?|따라|힘입어|대비(?:해|하여))'
    r'|(?:으)?로(?:\s*인해)?)(?=$|[\s,])', re.I)
_DEMAND_DENIAL = re.compile(r'취소|철회|무산|부인|사실\s*무근|아니라|아닌|되지\s*않|하지\s*못|되지\s*못')


def _demand_topic(sentence, company_names=()):
    """Return the sole demand topic and its connector, preserving action scope."""
    matches=list(_DEMAND.finditer(sentence))
    topics={}
    for match in matches:
        # A demand observation alone is not a new contract/production event.
        if not any(re.search(pattern,sentence[match.end():],re.I) for _,pattern in ACTIONS):
            continue
        term=match['topic'].strip('「」“”"\'').strip()
        if normalized(term) in {normalized(t) for t in _GENERIC_DEMAND}:continue
        if (normalized(term) in {normalized(n) for n in company_names}
                or (COMPANIES.fullmatch(term) and term not in _NON_COMPANY_TERMS)):
            continue  # An issuer name is not an identified product-demand cause.
        # Do not pick just the last member of a coordinated demand subject.
        prefix=sentence[:match.start()].rstrip()
        # News titles commonly separate the actor from its action with a comma:
        # "회사명, 신기술 수요 증가에 대응해 ..." is not a topic list.
        actor_prefix = (prefix.endswith(',') and any(
            normalized(prefix[:-1].strip()) == normalized(name)
            for name in (*company_names, *COMPANIES.findall(prefix))))
        if re.search(r'(?:및|와|과|또는|,)\s*$',prefix) and not actor_prefix:continue
        term=next((name for name,pattern in TOPICS if re.fullmatch(pattern,term,re.I)),term)
        topics[term]=match
    return next(iter(topics.items())) if len(topics)==1 else None


def company_clauses(sentence, company_names=()):
    """Split only explicit named subjects after an economic-action conjunction.

    Joint subjects and quoted names/statements remain intact. No pronoun or
    omitted subject is resolved to a company from another clause.
    """
    names=set(company_names)|set(COMPANIES.findall(sentence))
    names-=_NON_COMPANY_TERMS
    if not names:return [sentence]
    name='(?:'+'|'.join(re.escape(n) for n in sorted(names,key=lambda n:(-len(n),n)))+')'
    subject=re.compile(r'(?<!\w)'+name+r'(?:\s*(?:와|과|및|,|·)\s*'+name+r')*(?:은|는|이|가)(?=\s)')
    quoted=[(m.start(),m.end()) for m in re.finditer(_QUOTED_NAME,sentence)]
    cuts=[0]
    for match in subject.finditer(sentence):
        prefix=sentence[cuts[-1]:match.start()]
        if (any(a<=match.start()<b for a,b in quoted)
                or not any(re.search(p,prefix,re.I) for _,p in ACTIONS)
                or not any(mentions_name(prefix,n) for n in names)
                or not re.search(r'(?:했고|했으며|하고|하며|됐고|되었고|했지만|한\s*반면|한\s*뒤|한\s*후|[,;])\s*[,;]?\s*(?:(?:반면|한편|또한)\s*)?$',prefix)):
            continue
        cuts.append(match.start())
    if len(cuts)==1:return [sentence]
    # A shared denial of the entire quoted/joint account has unclear scope.
    if re.search(r'(?:모두|양사|두\s*회사|해당\s*보도).{0,30}(?:부인|취소|철회|사실\s*무근)',sentence):
        return [sentence]
    cuts.append(len(sentence))
    return [sentence[a:b].strip(' ,;') for a,b in zip(cuts,cuts[1:])]


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
    units=((paragraph,clause,len(clauses)>1) for paragraph in text.splitlines()
           if paragraph.strip() and len(paragraph)<=5000
           for sentence in re.split(r'(?<=[.!?。])\s+',paragraph.strip()) if sentence.strip()
           for clauses in [company_clauses(sentence.strip(),company_names)] for clause in clauses)
    for paragraph,line,scoped in units:
        if len(line) > 5000 or UNCERTAIN.search(line) or PAST.search(line):
            continue
        # Demand and economic action must be in the same sentence; unrelated
        # context elsewhere in the paragraph cannot supply the common cause.
        evidence_line=line
        demand_matches=list(_DEMAND.finditer(line))
        if (demand_matches or scoped) and _DEMAND_DENIAL.search(line):continue
        cause=_demand_topic(line, company_names)
        # Multiple unresolved causes cannot borrow a known topic or actor from
        # another clause (including pronouns and omitted subjects).
        if len(demand_matches)>1:continue
        # Without a named subject boundary, a second predicate cannot inherit
        # the first actor. This also covers pronouns and omitted subjects.
        if any(any(re.search(p,line[:m.start()],re.I) for _,p in ACTIONS)
               and any(re.search(p,line[m.end():],re.I) for _,p in ACTIONS)
               for m in re.finditer(r'했고|했으며|하고|하며|됐고|되었고|했지만',line)):
            continue
        if scoped and re.search(r'해지|계약\s*없|루머|광고|unconfirmed|rumou?r',line,re.I):continue
        demand=cause[0] if cause else None
        # A preceding, unrelated action cannot inherit a later demand cause.
        action_text=line[cause[1].end():] if cause else line
        business_phase=business_start_phase(action_text)
        names=business_start_names(action_text) if business_phase else []
        # Anticipatory demand is kept in the planned path, never realized demand.
        demand_planned=bool(cause and '대비' in cause[1]['connector'])
        action = next((name for name, pattern in ACTIONS if re.search(pattern, action_text, re.I)
                       and (name!='BUSINESS_START' or business_phase)), None)
        functions=business_start_functions(action_text) if action=='BUSINESS_START' else []
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
        companies = [x for x in companies if x not in _NON_COMPANY_TERMS][:30]
        original_companies=companies[:]
        for name in company_names:
            if mentions_name(line,name) and not any(normalized(x)==normalized(name) for x in companies):
                companies.append(name)
        companies=sorted(set(companies[:30]))
        if scoped:
            # Explicit source-named actors anchor separate clause events even
            # when their names came from the pinned directory, not a suffix rule.
            original_companies=companies[:]
        key = (topic, driver, action, tuple(original_companies))
        if key in seen:
            continue
        seen.add(key)
        changes.append({'topic':topic, 'economic_driver':driver, 'action':action,
            'phase':('ADOPTED_NOT_YET_EFFECTIVE' if action == 'POLICY_CHANGE' and '시행될 예정' in line
                     else 'PLANNED' if demand_planned
                     else business_phase if action == 'BUSINESS_START'
                     else 'PLANNED' if re.search(r'예정|할 계획|할 방침', line)
                         or (scoped and re.search(r'계획|추진|검토',line)) else 'SOURCE_REPORTED'),
            'entity_ids':companies,
            **({'service_name':names[0]} if action=='BUSINESS_START' and len(names)==1 else {}),
            **({'original_entity_ids':original_companies} if companies!=original_companies else {}),
            'industry_tags':['SEMICONDUCTOR'] if re.search(r'반도체|HBM|DRAM|NAND|메모리|EUV|DUV|극자외선|심자외선',line,re.I) else [],
            'source_paragraph_sha256':sha256(paragraph.strip().encode()).hexdigest(),
            'evidence_level':'OFFICIAL_SOURCE', 'verified_economic_effect':False})
        if len(changes) >= 30:
            break
    return changes
