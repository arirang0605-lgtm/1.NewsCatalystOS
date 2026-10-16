"""Source-grounded economic actions; no LLM/company-benefit certification.

Actions and topics share a sentence, with a bounded literal two-sentence
demand-link extension. Unknown topics are accepted
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
DRIVERS = {'DEMAND_RECOVERY':'수요·주문 회복', 'PRODUCT_PRICE_INCREASE':'제품 가격 상승', 'PRODUCT_PRICE_DECREASE':'제품 가격 하락', 'POLICY_ENABLEMENT': '정책 기반 확대', 'DEMAND_EXPANSION': '수요 확대',
           'DEMAND_CONTRACTION': '수요·주문 축소',
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


def investment_project(text, action):
    """One literally named investment target; never infer from issuer/product."""
    if action not in {'INVESTMENT','INVESTMENT_EXECUTION'}:return None
    names=list(re.finditer(_QUOTED_NAME,text))
    if len(names)!=1:return None
    match=names[0];name=match.group()[1:-1].strip()
    if (not re.search(r'(?:공장|시설|설비|라인|프로젝트)$',name)
            or re.search(r'[,·/]| 및 |와 |과 ',name)
            or re.fullmatch(r'(?:(?:신규|새|신|반도체|HBM|DRAM|NAND)\s*)*(?:공장|시설|설비|라인|프로젝트)',name,re.I)
            or re.search(r'취소|철회|보류|중단|지연|부인|무산|않|못|지난해|지난달|과거|이미'
                         r'|여부|설명회|가능성|전망|예상|위한|위해|기준',text)):
        return None
    verb=r'(?:결정|확정)' if action=='INVESTMENT' else '집행'
    tail=re.match(r'\s*투자(?:를)?\s*'+verb+r'(?=$|[\s,.!]|했|하|해|한|할|됐|되|된)',text[match.end():])
    if tail is None:return None
    expression=text[match.start():match.end()+tail.end()]
    return {'project_name':name,'source_expression':expression,
            'expression_sha256':sha256(expression.encode()).hexdigest()}


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
    ('SUPPLY_REDUCTION', r'(?:생산|공급).{0,20}(?:중단|축소|감산)|감산(?:을)?\s*(?:결정|시작|실시|단행|추진|계획)|감산(?:했다|한다|에\s*착수)'),
    ('CONTRACT', r'(?:공급\s*계약|수주\s*계약|납품\s*계약).{0,20}(?:체결|수주)'),
    ('INVESTMENT', r'(?:신규|새로).{0,30}투자.{0,25}(?:결정|확정)|투자.{0,15}(?:결정|확정)'),
    ('INVESTMENT_EXECUTION', r'(?<![가-힣])투자(?:를)?\s*집행'),
    ('BUSINESS_START', BUSINESS_ACTION),
    ('MARKET_ENTRY', r'시장(?:에|으로)?\s*(?:(?:신규|본격|첫)\s*)?진출'),
    ('SUPPLY_RESUMPTION', r'(?:생산|공급)(?:을)?\s*재개'),
    ('DELIVERY_START', r'(?:납품|공급)(?:을)?\s*(?:시작|개시)'),
    ('CUSTOMER_ACQUISITION', r'신규\s*고객(?:사)?(?:를|을|으로|로)?\s*확보'),
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


TECH_ALIAS_PAIR = re.compile(r'(?<![가-힣A-Za-z0-9])(?P<name>[가-힣]{2,40})\s*\((?P<abbreviation>[A-Z][A-Z0-9]{1,11})\)')


def explicit_topic_aliases(text, company_names=()):
    """Local literal definitions only; never a persistent global acronym map."""
    pairs=list(TECH_ALIAS_PAIR.finditer(text));result=[]
    known=lambda term:next((k for k,values in TOPIC_ALIASES.items()
        if normalized(term) in {normalized(v) for v in values}),None)
    for match in pairs:
        name,short=match['name'],match['abbreviation']
        if (name in {'기술','제품','회사','기업','서비스','사업','시장','산업','인공지능'}
                or name in company_names or (COMPANIES.fullmatch(name) and name not in _NON_COMPANY_TERMS)):
            continue
        if (len({m['name'] for m in pairs if m['abbreviation']==short})!=1
                or len({m['abbreviation'] for m in pairs if m['name']==name})!=1):continue
        if (known(name) or known(short)) and known(name)!=known(short):continue
        proof={'canonical_topic':known(name) or name,'abbreviation':short,
               'source_expression':match.group(),'expression_sha256':sha256(match.group().encode()).hexdigest()}
        if proof not in result:result.append(proof)
    return result


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
_CONTRACTION_MENTION = re.compile(r'(?:수요|주문)(?:가|이)?\s*(?:감소|축소|급감)')
_DEMAND_CONTRACTION = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?P<topic>'+_DEMAND_TOPIC+
    r'|[「“\"\'][^」”\"\']{2,50}[」”\"\']|[가-힣A-Za-z][가-힣A-Za-z0-9-]{1,49}?)'
    r'\s*(?:의\s*)?(?:수요|주문)(?:가|이)?\s*(?:감소|축소|급감)'
    r'(?P<connector>에\s*(?:대응(?:해|하여)?|따라|대비(?:해|하여))'
    r'|(?:으)?로(?:\s*인해)?|해|하여)(?=$|[\s,])',re.I)
# Same source-topic/connector grammar as demand growth, with the natural Korean
# subject particle for orders. This does not equate an order with realized sales.
_ORDER_EXPANSION = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?P<topic>'+_DEMAND_TOPIC+
    r'|[「“\"\'][^」”\"\']{2,50}[」”\"\']|[가-힣A-Za-z][가-힣A-Za-z0-9-]{1,49}?)'
    r'\s*(?:의\s*)?주문(?:이|가)?\s*(?:증가|확대|급증)'
    r'(?P<connector>에\s*(?:대응(?:해|하여)?|따라|힘입어|대비(?:해|하여))'
    r'|(?:으)?로(?:\s*인해)?|해|하여)(?=$|[\s,])',re.I)
_ORDER_GROWTH_MENTION = re.compile(r'주문(?:이|가)?\s*(?:증가|확대|급증)')


_DEMAND_RECOVERY = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?P<topic>'+_DEMAND_TOPIC+r')'
    r'\s*(?:의\s*)?(?P<basis>수요|주문)(?:이|가)?\s*회복'
    r'(?P<connector>에\s*(?:대응(?:해|하여)?|따라|힘입어|대비(?:해|하여))'
    r'|(?:으)?로(?:\s*인해)?|해|하여)(?=$|[\s,])',re.I)


def demand_recovery_cause(expression):
    match=_DEMAND_RECOVERY.fullmatch(expression)
    if match is None:return None
    topic=next(name for name,p in TOPICS if re.fullmatch(p,match['topic'],re.I))
    return {'product':topic,'basis':'DEMAND' if match['basis']=='수요' else 'ORDER',
            'change':'RECOVERY','source_expression':expression,
            'expression_sha256':sha256(expression.encode()).hexdigest()}


# Product prices only: securities/share/ETF price clauses are not products.
_PRODUCT_PRICE = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?P<topic>'+_DEMAND_TOPIC+r')'
    r'\s*(?:제품\s*)?(?:의\s*)?가격(?:이|가)?\s*(?P<movement>상승|인상|급등|하락|인하|급락)'
    r'(?P<connector>에\s*(?:대응(?:해|하여)?|따라|힘입어|대비(?:해|하여))'
    r'|(?:으)?로(?:\s*인해)?)(?=$|[\s,])',re.I)


def product_price_cause(expression):
    match=_PRODUCT_PRICE.fullmatch(expression)
    if match is None:return None
    topic=next(name for name,p in TOPICS if re.fullmatch(p,match['topic'],re.I))
    direction='DECREASE' if match['movement'] in {'하락','인하','급락'} else 'INCREASE'
    return {'product':topic,'change':direction,'source_expression':expression,
            'expression_sha256':sha256(expression.encode()).hexdigest()}


def _demand_topic(sentence, company_names=(), pattern=_DEMAND, *, actions=ACTIONS):
    """Return the sole demand topic and its connector, preserving action scope."""
    matches=list(pattern.finditer(sentence))
    topics={}
    for match in matches:
        # A demand observation alone is not a new contract/production event.
        if not any(re.search(pattern,sentence[match.end():],re.I) for _,pattern in actions):
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


def company_clauses(sentence, company_names=(), *, include_investment_execution=True, include_new_customers=True, include_delivery_start=True, include_market_entry=True, include_resumption=True):
    """Split only explicit named subjects after an economic-action conjunction.

    Joint subjects and quoted names/statements remain intact. No pronoun or
    omitted subject is resolved to a company from another clause.
    """
    patterns=[(kind,p) for kind,p in ACTIONS
              if (include_investment_execution or kind!='INVESTMENT_EXECUTION')
              and (include_new_customers or kind!='CUSTOMER_ACQUISITION')
              and (include_delivery_start or kind!='DELIVERY_START')
              and (include_market_entry or kind!='MARKET_ENTRY')
              and (include_resumption or kind!='SUPPLY_RESUMPTION')]
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
                or not any(re.search(p,prefix,re.I) for _,p in patterns)
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


def _parallel_actions(action_text, cause, actors, *, include_investment_execution=True):
    """A bounded nominal 'action 및 action' list shares an explicit subject/cause.

    None preserves the ordinary single-action path; [] leaves an ambiguous
    multi-action claim unclassified. Never carry subjects over finite clauses.
    """
    parts=re.split(r'\s+및\s+',action_text.strip().rstrip('.。!'))
    supported={'CONTRACT','INVESTMENT','PRODUCTION_START','CAPACITY_ADDITION'}
    if include_investment_execution:supported.add('INVESTMENT_EXECUTION')
    patterns=[(kind,pattern) for kind,pattern in ACTIONS if kind in supported]
    if len(parts)<2 or not all(any(re.search(p,part,re.I) for _,p in patterns) for part in parts):return None
    if not cause:return None
    if not actors or len(parts)>4:return []
    # Each item must be an entire, explicit action phrase. Extra topics,
    # subjects, dates, objectives and unresolved plan scope are not inherited.
    syntax={
        'CONTRACT':r'(?:공급|납품|수주)\s*계약(?:을)?\s*(?:체결|수주)',
        'INVESTMENT':r'(?:(?:신규|새로)\s*)?(?:(?:공장|시설|설비)\s*)?투자(?:를)?\s*(?:결정|확정)',
        'INVESTMENT_EXECUTION':r'(?:(?:신규|새로)\s*)?(?:(?:공장|시설|설비)\s*)?투자(?:를)?\s*집행',
        'PRODUCTION_START':r'(?:양산|생산)(?:을)?\s*(?:시작|개시)',
        'CAPACITY_ADDITION':r'(?:생산능력|생산량|공급량)(?:을)?\s*(?:증가|확대|증설)',
    }
    kinds=[]
    for index,part in enumerate(parts):
        ending=r'(?:했다|한다|했고|했으며|하고|하며|했지만)?' if index==len(parts)-1 else r'(?:했다|한다)?'
        matches=[kind for kind,pattern in patterns if re.search(pattern,part,re.I)
                 and re.fullmatch(syntax[kind]+ending,part)]
        if len(matches)!=1:return []
        kinds.append(matches[0])
    return list(dict.fromkeys(kinds))


_POLICY_COUNTRIES = r'미국|한국|일본|중국|EU|유럽연합'
_POLICY_NAME = r'(?:(?P<name>'+_QUOTED_NAME+r')\s+)?'
_POLICY_BODY = (
    r'(?P<topic>'+_DEMAND_TOPIC+r')\s+'
    r'(?:(?P<restriction>수출\s*규제|수입\s*규제|생산\s*규제)\s*(?P<change>완화|폐지)'
    r'|(?P<permit>수출\s*허가|수입\s*허가|생산\s*허가)\s*(?P<approval>승인|취득))'
    r'(?P<connector>(?:으)?로(?:\s*인해)?|에\s*(?:따라|대응해|대비해))(?=$|[\s,])')
_POLICY_CAUSE_LEGACY = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?:(?P<jurisdiction>'+_POLICY_COUNTRIES+r')\s+)?'
    +_POLICY_NAME+_POLICY_BODY,re.I)
_POLICY_CAUSE = re.compile(
    r'(?<![가-힣A-Za-z0-9])(?:(?P<jurisdiction>'+_POLICY_COUNTRIES+r')(?:의)?\s+)?'
    +_POLICY_NAME+r'(?:(?P<destination>'+_POLICY_COUNTRIES+r')향\s+)?'+_POLICY_BODY,re.I)


def policy_causes(text, *, include_destinations=True):
    """Literal reported cause, not a certified removal of a prior barrier.

    An unnamed restriction cannot establish the same policy across articles.
    Unlike barrier_changes, this needs no prior fact state and certifies nothing.
    """
    result=[]
    pattern=_POLICY_CAUSE if include_destinations else _POLICY_CAUSE_LEGACY
    for match in pattern.finditer(text):
        destination=match.groupdict().get('destination')
        # Do not take a suffix of an unsupported or compound geographic scope.
        if include_destinations and re.search(r'(?:향|의)\s*(?:(?:및|와|과|또는|,)\s*)?$',text[:match.start()]):
            continue
        scope=re.sub(r'\s+','',match['permit'] or match['restriction'])
        if destination and scope not in {'수출허가','수출규제'}:continue
        name=(match['name'] or '').strip('‘’“”「」\"\'')
        if name and not re.search(r'법|규정|규칙|정책|제도|고시|조치',name):continue
        proof={'policy_name':name or None,'jurisdiction':match['jurisdiction'],
               'restriction':re.sub(r'\s+','',match['restriction'] or match['permit']),
               'change':match['change'] or match['approval'],
               **({'destination':destination} if destination else {}),
               'source_expression':match.group(),
               'expression_sha256':sha256(match.group().encode()).hexdigest()}
        topic=next(name for name,pattern in TOPICS if re.fullmatch(pattern,match['topic'],re.I))
        result.append((topic,match,proof))
    return result


def policy_cause_key(proof):
    key=[normalized(proof[k] or '') for k in ('policy_name','jurisdiction','restriction','change')]
    if 'destination' in proof:key.extend(['destination',normalized(proof['destination'])])
    return key


def _leading_company_subject(text, names):
    """Only an explicit leading subject, never an object, quote or pronoun."""
    names=set(names)-_NON_COMPANY_TERMS
    if not names:return None
    name='(?:'+'|'.join(re.escape(n) for n in sorted(names,key=lambda n:(-len(n),n)))+')'
    match=re.match(r'\s*(?P<subject>'+name+r'(?:\s*(?:와|과|및|,|·)\s*'+name+
                   r')*)(?:(?:은|는|이|가)\s+|,\s+)',text)
    if match is None:return None
    actors={n for n in names if mentions_name(match['subject'],n)}
    return actors,text[match.end():]


def demand_scope(text, match, company_names=(), *, topic_start=None):
    """Literal end-use qualifier immediately before a demand/order product.

    No customer/entity inference or cross-sentence inheritance. An ambiguous
    qualifier remains source evidence, but cannot join another event's theme.
    """
    prefix=text[:match.start() if topic_start is None else topic_start]
    if not prefix.rstrip().endswith('용'):return None
    subject=_leading_company_subject(prefix,set(company_names)|set(COMPANIES.findall(prefix)))
    qualifier=(subject[1] if subject else prefix).strip()
    if not qualifier or len(qualifier)>160:return None
    destination=qualifier[:-1].strip()
    ambiguous=(not re.fullmatch(r'[가-힣A-Za-z0-9 -]{1,80}',destination)
        or len(destination.split())>4
        or re.search(r'용|(?:^|\s)(?:및|또는|관련|해당|일부|여러|복수|미확인|기타|각종|범용)(?:$|\s)|[가-힣](?:와|과)(?:$|\s)',destination)
        or re.search(r'(?:은|는|에서|위한|따른)(?:$|\s)',destination))
    # Keep exact whitespace rather than a reconstructed source quotation.
    start=prefix.rfind(qualifier)
    expression=text[start:match.end()]
    return {'status':'UNRESOLVED' if ambiguous else 'EXPLICIT',
            'destination':None if ambiguous else destination,
            'source_expression':expression,'expression_sha256':sha256(expression.encode()).hexdigest()}


def parse_demand_scope(expression):
    matches=[(pattern,m) for pattern in (_DEMAND,_ORDER_EXPANSION,_DEMAND_CONTRACTION,_PRODUCT_PRICE,_DEMAND_RECOVERY)
             for m in pattern.finditer(expression)]
    if not matches:
        from .adjacent_demand import CAUSE,REDUCTION_CAUSE
        for pattern,driver in ((CAUSE,'DEMAND_EXPANSION'),(REDUCTION_CAUSE,'DEMAND_CONTRACTION')):
            match=pattern.fullmatch(expression)
            if match and match['qualifier']:
                return match['product'],driver,demand_scope(expression,match,topic_start=match.start('product'))
    if len(matches)!=1:return None
    pattern,match=matches[0]
    topic=match['topic'].strip('「」“”"\'').strip()
    topic=next((name for name,p in TOPICS if re.fullmatch(p,topic,re.I)),topic)
    return topic,('PRODUCT_PRICE_'+product_price_cause(match.group())['change'] if pattern is _PRODUCT_PRICE else 'DEMAND_RECOVERY' if pattern is _DEMAND_RECOVERY else 'DEMAND_CONTRACTION' if pattern is _DEMAND_CONTRACTION else 'DEMAND_EXPANSION'),demand_scope(expression,match)


def market_entry(text):
    """Literal named market and entry verb; no country/customer inference."""
    match=re.match(r'(?P<market>'+_QUOTED_NAME+r'|[가-힣A-Za-z0-9][가-힣A-Za-z0-9 -]{0,79}?)'
                   r'\s+시장(?:에|으로)?\s*(?:(?:신규|본격|첫)\s*)?진출(?=$|[\s,.!]|했|하|해|한|할|에)',text)
    if match is None:return None
    name=match['market'].strip('「」“”‘’"\'').strip()
    if (not name or len(name.split())>4 or COMPANIES.search(name)
            or re.search(r'(?:^|\s)(?:및|또는|신규|새로운|기존|해당|관련|그|다른|어떤|미확인)(?:$|\s)|[가-힣](?:와|과)(?:$|\s)|[,/·&]',name)
            or re.search(r'(?:은|는|에게|에서|위한|따른|확보|시작|체결|진출|위해|후|전)(?:$|\s)',name)):
        return None
    expression=match.group()
    return {'market_name':name,'source_expression':expression,
            'expression_sha256':sha256(expression.encode()).hexdigest()}


def _cause_subject(line,cause,names,scope=None):
    """Explicit leading actor or cause-first actor, with a literal end-use scope."""
    prefix=line[:cause[1].start()];tail=line[cause[1].end():].strip().rstrip('.。!')
    if scope:
        # Remove only the literal qualifier just parsed, preserving the actor.
        qualifier=scope['source_expression'][:-len(cause[1].group())]
        if prefix.endswith(qualifier):prefix=prefix[:-len(qualifier)]
    subject=_leading_company_subject(prefix,names)
    if subject is not None:
        actors,remaining=subject
        if remaining.strip(' ,;'):return None
    elif not prefix.strip(' ,;'):
        subject=_leading_company_subject(tail,names)
        if subject is None:return None
        actors,tail=subject
    else:return None
    return actors,tail


def _commercial_claim(line, cause, company_names, action, scope=None):
    """Literal commercial action with a named actor and explicit cause.

    A customer object remains in the source excerpt; it is not a second actor,
    a contract counterparty, or a verified beneficiary.
    """
    if cause is None or re.search(r'지난해|지난달|작년|과거|이미|지난\s*\d+월|전망|예상|우려',line):return None
    if action=='CUSTOMER_ACQUISITION' and '기존' in line:return None
    names=set(company_names)|set(COMPANIES.findall(line))
    subject=_cause_subject(line,cause,names,scope)
    if subject is None:return None
    actors,tail=subject
    customer='(?:'+_QUOTED_NAME+'|'+'|'.join(re.escape(n) for n in sorted(names,key=lambda n:(-len(n),n)))+')'
    phrase=r'(?:신규\s*고객(?:사)?(?:를|을)?\s*확보|'+customer+r'(?:을|를)\s+신규\s*고객(?:사)?(?:으로|로)\s*확보)'
    if action=='BUSINESS_START':
        # Resolve only an entire source-named service or concrete function after
        # the explicit actor/cause. No brand inferred from a shared product.
        if business_start_phase(tail) is None:return None
        service_names=business_start_names(tail)
        functions=business_start_functions(tail)
        if len(service_names)==1:
            target=service_names[0]
            quoted=next(m.group() for m in re.finditer(_QUOTED_NAME,tail)
                        if m.group()[1:-1].strip()==target)
            named=re.escape(quoted)
            service=r'(?:'+named+r'\s*(?:서비스|사업)(?:을|를|가|는)?|(?:서비스|사업)\s*'+named+r')'
        elif len(functions)==1:
            target=functions[0]
            service=re.escape(target)+r'\s+서비스(?:를|가|는)?'
        else:return None
        if any(n not in {cause[0],'반도체'} and re.search(p,target,re.I) for n,p in TOPICS):return None
        if scope and scope['status']=='EXPLICIT':
            product='(?:'+'|'.join(re.escape(t) for t in TOPIC_ALIASES.get(cause[0],(cause[0],)))+')'
            scoped_target=re.match(r'(.+?)용\s+'+product+r'(?=$|\s)',target,re.I)
            if scoped_target and normalized(scoped_target[1])!=normalized(scope['destination']):return None
        phrase=service+r'\s*'+_START_MODIFIER+r'(?:개시|시작|출시)'
    if action=='DELIVERY_START':
        target=r'(?:(?:(?:신규|기존)\s*)?고객(?:사)?|'+customer+')'
        topics=TOPIC_ALIASES.get(cause[0],(cause[0],))
        product='(?:'+'|'.join(re.escape(t) for t in topics)+')'
        phrase=(r'(?:'+target+r'(?:에게|에)\s*)?(?:'+product+r'(?:을|를)?\s*)?'
                r'(?:본격\s*|정식\s*)?(?:납품|공급)(?:을)?\s*(?:시작|개시)')
    if action=='CONTRACT':
        topics=TOPIC_ALIASES.get(cause[0],(cause[0],))
        product='(?:'+'|'.join(re.escape(t) for t in topics)+')'
        phrase=(r'(?:'+customer+r'(?:와|과)\s*)?(?:'+product+r'\s*)?'
                r'(?:공급|납품)\s*계약(?:을)?\s*체결')
    if action=='PRODUCTION_START':
        topics=TOPIC_ALIASES.get(cause[0],(cause[0],))
        product='(?:'+'|'.join(re.escape(t) for t in topics)+')'
        phrase=r'(?:'+product+r'(?:을|를)?\s*)?(?:생산|양산)(?:을)?\s*(?:시작|개시)'
    if action=='CAPACITY_ADDITION':
        topics=TOPIC_ALIASES.get(cause[0],(cause[0],))
        product='(?:'+'|'.join(re.escape(t) for t in topics)+')'
        phrase=r'(?:'+product+r'\s*)?생산능력(?:을)?\s*(?:확대|증설)'
    if action in {'INVESTMENT','INVESTMENT_EXECUTION'}:
        topics=TOPIC_ALIASES.get(cause[0],(cause[0],))
        product='(?:'+'|'.join(re.escape(t) for t in topics)+')'
        project=investment_project(tail,action)
        if project and any(n not in {cause[0],'반도체'} and re.search(p,project['project_name'],re.I) for n,p in TOPICS):return None
        target=re.escape(next(re.finditer(_QUOTED_NAME,tail)).group()) if project else r'(?:(?:신규|새로)\s*)?(?:공장|시설|설비)'
        verb=r'(?:결정|확정)' if action=='INVESTMENT' else '집행'
        phrase=r'(?:'+product+r'\s*)?'+target+r'\s+투자(?:를)?\s*'+verb
    if action=='SUPPLY_RESUMPTION':
        topics=TOPIC_ALIASES.get(cause[0],(cause[0],))
        product='(?:'+'|'.join(re.escape(t) for t in topics)+')'
        phrase=r'(?:'+product+r'(?:을|를)?\s*)?(?:생산|공급)(?:을)?\s*재개'
    market=None
    if action=='MARKET_ENTRY':
        market=market_entry(tail.strip())
        if (market is None or any(mentions_name(market['market_name'],n) for n in names)
                or any(n not in {cause[0],'반도체'} and re.search(p,market['market_name'],re.I)
                       for n,p in TOPICS)):
            return None
        phrase=re.escape(market['source_expression'])
    ending=r'(?P<ending>(?:했다|했습니다|한다|했으며|했고|하고|하며|했지만|할)|에\s*성공(?:했다|했고)?)?'
    plan=r'(?P<plan>\s*(?:예정|계획|목표|추진|검토|방침)(?:이다)?)?'
    if action in {'SUPPLY_RESUMPTION','CONTRACT','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT','INVESTMENT_EXECUTION'}:
        plan=r'(?P<plan>\s*(?:예정|계획|목표|추진|검토|방침|결정)(?:이다|했다)?)?'
    match=re.fullmatch(phrase+ending+plan,tail.strip(),re.I)
    if match is None:return None
    planned=bool(match['plan']) or match['ending'] in {'할','한다'}
    return {'actors':sorted(actors),'phase':'PLANNED' if planned else 'SOURCE_REPORTED',
            **({'market_entry':market} if market else {})}


def policy_capacity_action(text, *, company_names=()):
    """Bound the existing commercial-action decision to one literal policy clause."""
    if not isinstance(text,str) or not 0<len(text)<=800 or any(ord(c)<32 for c in text):return None
    policies=policy_causes(text)
    if len(policies)!=1:return None
    topic,match,policy=policies[0]
    claim=_commercial_claim(text,(topic,match),company_names,'CAPACITY_ADDITION')
    if claim is None:return None
    return {'source_expression':text,'expression_sha256':sha256(text.encode()).hexdigest(),
        'actors':claim['actors'],'phase':'PLANNED' if '대비' in match['connector'] else claim['phase']}


def price_curtailment_phase(text,topic):
    """A reported cut versus a planned cut; a decision is not physical execution."""
    products='(?:'+'|'.join(re.escape(t) for t in TOPIC_ALIASES.get(topic,(topic,)))+')'
    action=(r'(?:'+products+r'\s+)?(?:(?:생산|공급)(?:을|를)?\s*(?:축소|중단)'
            r'|감산(?:을)?\s*(?:결정|시작|실시|단행|추진|계획)|감산(?:에\s*착수)?)')
    ending=r'(?P<ending>했다|했습니다|한다|했으며|했고|하고|하며|했지만|할)?'
    intent=r'(?P<intent>\s*(?:계획|예정|목표|추진|검토|방침|결정)(?:이다|했다)?)?'
    match=re.fullmatch(action+ending+intent,text.strip().rstrip('.。!'),re.I)
    if match is None:return None
    planned=(bool(match['intent']) or match['ending'] in {'한다','할'}
             or bool(re.search(r'결정|추진|계획',match.group())))
    return 'PLANNED' if planned else 'SOURCE_REPORTED'


def investment_execution_phase(text):
    """Reported execution versus planned execution, never certified expenditure."""
    if (not re.search(r'(?<![가-힣])투자(?:를)?\s*집행',text)
            or _DEMAND_DENIAL.search(text)
            or re.search(r'미집행|미실행|보류|중단|지연|불발|전망|예상|우려|지난해|지난달|과거|이미',text)
            or re.search(r'집행(?:의|률|에\s*관한)|집행(?:을)?\s*(?:위한|여부|설명|교육|기준|지침|방법|현황|실적)',text)):
        return None
    return 'PLANNED' if re.search(r'계획|예정|추진|검토|방침|결정|확정',text) else 'SOURCE_REPORTED'


def extract_economic_changes(text, *, company_names=(), include_order_growth=True, include_parallel_actions=True,
                             include_policy_causes=True, include_policy_destinations=True, include_policy_capacity_actions=True, include_investment_execution=True,
                             include_investment_projects=True, include_new_customers=True, include_delivery_start=True, include_demand_scopes=True, include_market_entry=True, include_product_prices=True, include_resumption=True, include_demand_recovery=True, include_adjacent_demand=True, include_adjacent_scopes=True, include_adjacent_contracts=True, include_adjacent_amounts=True, include_adjacent_reductions=True):
    """Return bounded source claims, including policy adoption before its effect.

    Corporate actions without an explicit common demand cause retain their own
    supply/capacity driver. A price-only article is not a capacity event.
    include_order_growth=False is only for matching pre-existing stored evidence;
    it must not be used to rewrite old events with newly interpreted causes.
    include_parallel_actions=False likewise preserves the prior single-action reader.
    include_policy_causes=False matches old policy-only records without rewriting them.
    include_policy_destinations=False reads earlier policy causes without reinterpreting scope.
    include_policy_capacity_actions=False reads older capacity phases without enriching or rewriting them.
    include_investment_execution=False reads earlier investment decisions and clause boundaries.
    include_new_customers=False matches old actions/clauses without reclassifying saved events.
    include_delivery_start=False reads earlier records without changing their clause boundaries.
    include_demand_scopes=False reads old evidence without retroactive theme reassignment.
    include_market_entry=False reads earlier actions and company-clause boundaries.
    include_product_prices=False matches saved pre-price causes without reclassification.
    include_resumption=False reads earlier actions and company-clause boundaries.
    include_demand_recovery=False reads earlier causes without reinterpretation.
    include_adjacent_demand=False matches saved pre-adjacency claims unchanged.
    include_adjacent_scopes=False matches earlier adjacency proofs without scope enrichment.
    include_adjacent_contracts=False matches earlier capacity-only adjacency extraction.
    include_adjacent_amounts=False matches earlier contract wording without amount enrichment.
    include_adjacent_reductions=False preserves pre-reduction adjacency claims.
    """
    if (not isinstance(company_names,(list,tuple)) or len(company_names)>100
            or any(not isinstance(n,str) or not n.strip() or len(n)>120 for n in company_names)):
        raise ValueError('bounded source company names required')
    action_patterns=[(kind,p) for kind,p in ACTIONS
              if (include_investment_execution or kind!='INVESTMENT_EXECUTION')
              and (include_new_customers or kind!='CUSTOMER_ACQUISITION')
              and (include_delivery_start or kind!='DELIVERY_START')
              and (include_market_entry or kind!='MARKET_ENTRY')
              and (include_resumption or kind!='SUPPLY_RESUMPTION')]
    changes = []
    seen = {}
    conflicting_scopes = set()
    first_services = {}
    first_projects = {}
    units=((paragraph,clause,len(clauses)>1) for paragraph in text.splitlines()
           if paragraph.strip() and len(paragraph)<=5000
           for sentence in re.split(r'(?<=[.!?。])\s+',paragraph.strip()) if sentence.strip()
           for clauses in [company_clauses(sentence.strip(),company_names,include_investment_execution=include_investment_execution,include_new_customers=include_new_customers,include_delivery_start=include_delivery_start,include_market_entry=include_market_entry,include_resumption=include_resumption)] for clause in clauses)
    for paragraph,line,scoped in units:
        past=PAST.search(line)
        # An existing customer does not make a newly reported delivery historical.
        customer_context=(include_delivery_start and past and not PAST.search(
            re.sub(r'기존\s*고객(?:사)?(?=에게|에)','고객',line)))
        if len(line) > 5000 or UNCERTAIN.search(line) or (past and not customer_context):
            continue
        # Demand and economic action must be in the same sentence; unrelated
        # context elsewhere in the paragraph cannot supply the common cause.
        evidence_line=line
        policies=policy_causes(line,include_destinations=include_policy_destinations) if include_policy_causes else []
        policy=policies[0] if len(policies)==1 else None
        if policies and (len(policies)>1 or _DEMAND_DENIAL.search(line)
                or re.search(r'전망|예상|우려|지난해|지난달|과거|이미',line)):
            continue
        if policy and re.search(r'(?:및|와|과|또는)\s*$',line[:policy[1].start()]):continue
        alias_proofs=explicit_topic_aliases(line,company_names)
        # Resolve the paired noun in demand syntax, but retain a later bare
        # acronym as the source topic so an existing event ID cannot change.
        for proof in alias_proofs:
            if proof['canonical_topic'] not in TOPIC_ALIASES:
                line=line.replace(proof['source_expression'],proof['canonical_topic'])
        contraction_mentioned=bool(_CONTRACTION_MENTION.search(line))
        reduction_mentioned=contraction_mentioned or bool(re.search(r'감산',line))
        order_mentioned=include_order_growth and bool(_ORDER_GROWTH_MENTION.search(line))
        if order_mentioned and (re.search(r'전망|예상|우려',line) or _DEMAND_DENIAL.search(line)
                or re.search(r'(?:지난해|지난달|작년|과거|이미|지난\s*\d+월)',line)):
            continue
        if reduction_mentioned and (re.search(r'전망|예상|우려',line)
                or _DEMAND_DENIAL.search(line)
                or re.search(r'(?:지난해|지난달|작년|과거|기존|이미|지난\s*\d+월).{0,60}(?:감산|축소|중단)',line)):
            continue
        order_matches=list(_ORDER_EXPANSION.finditer(line)) if include_order_growth else []
        recovery_matches=list(_DEMAND_RECOVERY.finditer(line)) if include_demand_recovery else []
        recovery=_demand_topic(line,company_names,_DEMAND_RECOVERY,actions=action_patterns) if recovery_matches else None
        if recovery_matches and (not recovery or _DEMAND_DENIAL.search(line)
                or re.search(r'전망|예상|우려|지난해|지난달|작년|과거|이미|지난\s*\d+월',line)):continue
        demand_matches=list(_DEMAND.finditer(line))+list(_DEMAND_CONTRACTION.finditer(line))+order_matches+recovery_matches
        price_matches=list(_PRODUCT_PRICE.finditer(line)) if include_product_prices else []
        price=_demand_topic(line,company_names,_PRODUCT_PRICE,actions=action_patterns) if price_matches else None
        if price_matches and (not price or len(price_matches)!=1 or demand_matches or policies
                or _DEMAND_DENIAL.search(line)
                or re.search(r'전망|예상|우려|지난해|지난달|작년|과거|이미|지난\s*\d+월',line)):
            continue
        if (demand_matches or scoped) and _DEMAND_DENIAL.search(line):continue
        contraction=_demand_topic(line,company_names,_DEMAND_CONTRACTION,actions=action_patterns)
        order_cause=_demand_topic(line,company_names,_ORDER_EXPANSION,actions=action_patterns) if order_matches else None
        if order_matches and order_cause is None:continue
        if policy and demand_matches:continue
        cause=(policy[:2] if policy else None) or contraction or _demand_topic(line, company_names,actions=action_patterns) or order_cause or recovery or price
        # Multiple unresolved causes cannot borrow a known topic or actor from
        # another clause (including pronouns and omitted subjects).
        if len(demand_matches)>1:continue
        # Without a named subject boundary, a second predicate cannot inherit
        # the first actor. This also covers pronouns and omitted subjects.
        if any(any(re.search(p,line[:m.start()],re.I) for _,p in action_patterns)
               and any(re.search(p,line[m.end():],re.I) for _,p in action_patterns)
               for m in re.finditer(r'했고|했으며|하고|하며|됐고|되었고|했지만',line)):
            continue
        if scoped and re.search(r'해지|계약\s*없|루머|광고|unconfirmed|rumou?r',line,re.I):continue
        demand=cause[0] if cause else None
        # A preceding, unrelated action cannot inherit a later demand cause.
        action_text=line[cause[1].end():] if cause else line
        scope=demand_scope(line,cause[1],company_names) if include_demand_scopes and cause and not policy else None
        # Alias expansion may change offsets; preserve only an exact source proof.
        if scope and scope['source_expression'] not in evidence_line:scope=None
        recovery_proof=demand_recovery_cause(recovery[1].group()) if recovery else None
        price_proof=product_price_cause(price[1].group()) if price else None
        price_drop=bool(price_proof and price_proof['change']=='DECREASE')
        if price:
            subject=_cause_subject(line,cause,set(company_names)|set(COMPANIES.findall(line)),scope)
            if subject is None:continue
            price_actors,action_text=subject
        cut_phase=price_curtailment_phase(action_text,price[0]) if price_drop else None
        if price_drop and cut_phase is None:continue
        commercial_claims={kind:_commercial_claim(line,cause,company_names,kind,scope)
            for kind,enabled in [('CUSTOMER_ACQUISITION',include_new_customers),('DELIVERY_START',include_delivery_start),('MARKET_ENTRY',include_market_entry),('SUPPLY_RESUMPTION',include_resumption and bool(cause) and not price and not policy),('CONTRACT',bool(recovery)),('PRODUCTION_START',bool(recovery)),('CAPACITY_ADDITION',bool(recovery)),('INVESTMENT',bool(recovery)),('INVESTMENT_EXECUTION',bool(recovery) and include_investment_execution),('BUSINESS_START',bool(recovery))]
            if enabled and not contraction}
        commercial_claim=next((c for c in commercial_claims.values() if c),None)
        if commercial_claim and policy:policy_actors=set(commercial_claim['actors'])
        if price:
            if (any(n not in {price[0],'반도체'} and re.search(p,action_text,re.I) for n,p in TOPICS)
                    or re.search(r'소개|설명회|여부|위한|위해|협약|양해각서|준비|시범|실패|보류|지연',action_text)):
                continue
            if commercial_claim is None and (
                    any(mentions_name(action_text,n) for n in (set(company_names)|set(COMPANIES.findall(line)))-price_actors)
                    or re.search(r'(?:그|해당|다른)\s*(?:회사|기업)|(?<!\w)\w+(?:은|는)\s',action_text)):
                continue
        if (order_cause or policy) and commercial_claim is None:
            actors=set(company_names)|set(COMPANIES.findall(line))
            earlier={n for n in actors if mentions_name(line[:cause[1].start()],n)}
            later={n for n in actors if mentions_name(action_text,n)}
            if earlier and later-earlier:continue
            policy_actors=earlier
            if policy and not earlier:
                # A cause-first sentence can name its own subject. Do not carry
                # another actor or unparsed introductory clause across the cause.
                if line[:cause[1].start()].strip(' ,;'):continue
                subject=_leading_company_subject(action_text,actors)
                if subject is None:continue
                policy_actors,action_text=subject
                if not policy_actors or later-policy_actors:continue
            if policy and (re.search(r'(?:그|해당|다른)\s*(?:회사|기업)|(?<!\w)\w+(?:은|는)\s',action_text)
                    or any(name not in {policy[0],'반도체'} and re.search(pattern,action_text,re.I)
                           for name,pattern in TOPICS)):
                continue
        business_phase=business_start_phase(action_text)
        names=business_start_names(action_text) if business_phase else []
        # Anticipatory demand is kept in the planned path, never realized demand.
        demand_planned=bool(cause and '대비' in cause[1]['connector'])
        action = next((name for name, pattern in action_patterns if re.search(pattern, action_text, re.I)
                       and (name!='BUSINESS_START' or business_phase)), None)
        if recovery and commercial_claims.get('INVESTMENT_EXECUTION'):
            action='INVESTMENT_EXECUTION'
        actors=[n for n in set(company_names)|set(COMPANIES.findall(line))
                if n not in _NON_COMPANY_TERMS and cause and mentions_name(line[:cause[1].start()],n)]
        if policy:actors=sorted(policy_actors)
        if price:actors=sorted(price_actors)
        parallel=_parallel_actions(action_text,cause,actors,include_investment_execution=include_investment_execution) if include_parallel_actions else None
        actions=[action] if parallel is None else parallel
        if parallel and (re.search(r'계획|예정|추진|전망|예상|지난달|과거|이미',line)
                         or _DEMAND_DENIAL.search(line)):
            continue
        for action in actions:
            if customer_context and action!='DELIVERY_START':continue
            if action in {'CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY','SUPPLY_RESUMPTION'} and not commercial_claims.get(action):continue
            execution_text=(next(p for p in re.split(r'\s+및\s+',action_text)
                                 if re.search(r'투자(?:를)?\s*집행',p))
                            if parallel and action=='INVESTMENT_EXECUTION' else action_text)
            execution_phase=investment_execution_phase(execution_text) if action=='INVESTMENT_EXECUTION' else None
            if action=='INVESTMENT_EXECUTION':
                if execution_phase is None or re.search(r'지난해|지난달|과거|이미|지난\s*\d+월',line):continue
                if cause and not policy and not price and not recovery:
                    known=set(company_names)|set(COMPANIES.findall(line))
                    before={n for n in known if mentions_name(line[:cause[1].start()],n)}
                    after={n for n in known if mentions_name(action_text,n)}
                    if not before or after-before:continue
                if cause and any(n not in {cause[0],'반도체'} and re.search(p,action_text,re.I)
                                 for n,p in TOPICS):continue
            if policy and action not in {'CONTRACT','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT','INVESTMENT_EXECUTION','CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY'}:
                continue
            policy_capacity=(policy_capacity_action(line,company_names=company_names) if policy and action=='CAPACITY_ADDITION' and include_policy_capacity_actions else None)
            if recovery and (action not in {'SUPPLY_RESUMPTION','CONTRACT','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT','INVESTMENT_EXECUTION','DELIVERY_START','CUSTOMER_ACQUISITION','MARKET_ENTRY','BUSINESS_START'} or not commercial_claims.get(action)):continue
            if recovery and action=='MARKET_ENTRY' and scope and scope['status']=='EXPLICIT':
                # A geographic/sector market is not a demand destination. Only
                # a literal end-use + same-product target can contradict it.
                product='(?:'+'|'.join(re.escape(t) for t in TOPIC_ALIASES.get(cause[0],(cause[0],)))+')'
                target=commercial_claims[action]['market_entry']['market_name']
                scoped_target=re.fullmatch(r'(.+?)용\s+'+product,target,re.I)
                if scoped_target and normalized(scoped_target[1])!=normalized(scope['destination']):continue
            if action=='SUPPLY_RESUMPTION' and not (cause and not contraction and not policy and not price):continue
            if price_drop and action!='SUPPLY_REDUCTION':continue
            if (order_cause or (price and not price_drop)) and action not in {'CONTRACT','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT','INVESTMENT_EXECUTION','CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY','SUPPLY_RESUMPTION'}:
                continue
            functions=business_start_functions(action_text) if action=='BUSINESS_START' else []
            topic=demand or next((name for name,pattern in TOPICS
                if re.search(pattern,evidence_line,re.I)),None) or (names[0] if len(names)==1 else None)
            # Existing named/known topics retain their event identity.
            topic=topic or (functions[0] if len(functions)==1 else None)
            if topic is None or action is None:
                continue
            alias=next((p for p in alias_proofs if normalized(topic) in
                        {normalized(p['canonical_topic']),normalized(p['abbreviation'])}),None)
            if alias is None and any(normalized(topic) in {normalized(m['name']),normalized(m['abbreviation'])}
                                    for m in TECH_ALIAS_PAIR.finditer(evidence_line)):
                continue  # Conflicting definitions, issuer names or reserved acronyms.
            if contraction and (action!='SUPPLY_REDUCTION' or not re.search(
                    r'반도체|HBM|DRAM|NAND|메모리|EUV|DUV|극자외선|심자외선',line,re.I)):
                continue
            driver = ('POLICY_ENABLEMENT' if policy or action == 'POLICY_CHANGE' else
                      'DEMAND_RECOVERY' if recovery else
                      'PRODUCT_PRICE_'+price_proof['change'] if price else
                      'DEMAND_CONTRACTION' if contraction else
                      'SUPPLY_CONTRACTION' if action == 'SUPPLY_REDUCTION' else
                      'DEMAND_EXPANSION' if demand else
                      'CAPACITY_EXPANSION' if action in {'PRODUCTION_START','CAPACITY_ADDITION'}
                          or (action == 'INVESTMENT' and re.search(r'공장|생산|증설', line))
                          or (action == 'INVESTMENT_EXECUTION' and re.search(r'공장|생산|증설|설비|시설', line)) else 'UNKNOWN')
            entity_line=evidence_line.replace(scope['source_expression'],cause[1].group()) if scope else evidence_line
            companies = sorted(set(COMPANIES.findall(entity_line)))
            companies = [x for x in companies if x not in _NON_COMPANY_TERMS][:30]
            original_companies=companies[:]
            for name in company_names:
                if mentions_name(entity_line,name) and not any(normalized(x)==normalized(name) for x in companies):
                    companies.append(name)
            companies=sorted(set(companies[:30]))
            if policy:
                companies=sorted(policy_actors-_NON_COMPANY_TERMS)
                original_companies=companies[:]
            if price:
                companies=sorted(price_actors-_NON_COMPANY_TERMS);original_companies=companies[:]
            if scoped:
                # Explicit source-named actors anchor separate clause events even
                # when their names came from the pinned directory, not a suffix rule.
                original_companies=companies[:]
            if action in {'CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY','SUPPLY_RESUMPTION'} or (recovery and action in {'CONTRACT','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT','INVESTMENT_EXECUTION','BUSINESS_START'}):
                companies=commercial_claims[action]['actors'];original_companies=companies[:]
            project=investment_project(action_text,action) if include_investment_projects else None
            key = (alias['canonical_topic'] if alias else topic, driver, action, tuple(original_companies),
                   tuple(policy_cause_key(policy[2])) if policy else None)
            if action=='MARKET_ENTRY':key+=('MARKET_ENTRY',normalized(commercial_claims[action]['market_entry']['market_name']))
            service_event_key=None
            if recovery and action=='BUSINESS_START' and len(names)==1:
                # The first claim keeps its legacy identity. Explicit siblings
                # in this source need their own stable, source-bounded identity.
                name=normalized(names[0])
                first=first_services.setdefault(key,name)
                if name!=first:service_event_key=sha256(name.encode()).hexdigest()
                key+=('SOURCE_NAMED_SERVICE',name)
            investment_event_key=None
            if recovery and project:
                name=normalized(project['project_name'])
                first=first_projects.setdefault(key,name)
                if name!=first:investment_event_key=sha256(name.encode()).hexdigest()
                key+=('SOURCE_NAMED_INVESTMENT',name)
            if key in seen:
                index=seen[key]
                prior=changes[index].get('demand_scope')
                scope_key=lambda p:(p['status'],normalized(p['destination'] or '')) if p else None
                if scope_key(prior)!=scope_key(scope):conflicting_scopes.add(index)
                continue
            seen[key]=len(changes)
            changes.append({'topic':topic, 'economic_driver':driver, 'action':action,
                'phase':('ADOPTED_NOT_YET_EFFECTIVE' if action == 'POLICY_CHANGE' and '시행될 예정' in line
                         else policy_capacity['phase'] if policy_capacity else 'PLANNED' if demand_planned or (project and _BUSINESS_PLAN.search(action_text))
                         else cut_phase if price_drop
                         else commercial_claims[action]['phase'] if action in {'CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY','SUPPLY_RESUMPTION'} or (recovery and action in {'CONTRACT','PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT','INVESTMENT_EXECUTION','BUSINESS_START'})
                         else execution_phase if action == 'INVESTMENT_EXECUTION'
                         else business_phase if action == 'BUSINESS_START'
                         else 'PLANNED' if re.search(r'예정|할 계획|할 방침', line)
                             or (price and re.search(r'계획|예정|목표|추진|검토|방침|한다|할(?=$|\s)',action_text))
                             or ((scoped or reduction_mentioned or order_mentioned or policy)
                                 and re.search(r'계획|추진|검토',action_text if policy else line)) else 'SOURCE_REPORTED'),
                'entity_ids':companies,
                **({'policy_cause':policy[2]} if policy else {}),
                **({'policy_capacity_action':policy_capacity} if policy_capacity else {}),
                **({'demand_recovery_cause':recovery_proof} if recovery_proof else {}),
                **({'product_price_cause':price_proof} if price_proof else {}),
                **({'topic_alias_evidence':alias} if alias and alias['canonical_topic'] not in TOPIC_ALIASES else {}),
                **({'investment_project':project} if project else {}),
                **({'investment_event_key':investment_event_key} if investment_event_key else {}),
                **({'demand_scope':scope} if scope else {}),
                **({'market_entry':commercial_claims[action]['market_entry']} if action=='MARKET_ENTRY' else {}),
                **({'service_name':names[0]} if action=='BUSINESS_START' and len(names)==1 else {}),
                **({'service_event_key':service_event_key} if service_event_key else {}),
                **({'original_entity_ids':original_companies} if companies!=original_companies else {}),
                'industry_tags':['SEMICONDUCTOR'] if re.search(r'반도체|HBM|DRAM|NAND|메모리|EUV|DUV|극자외선|심자외선',line,re.I) else [],
                'source_paragraph_sha256':sha256(paragraph.strip().encode()).hexdigest(),
                'evidence_level':'OFFICIAL_SOURCE', 'verified_economic_effect':False})
            if len(changes) >= 30:
                break
        if len(changes)>=30:break
    # One source/actor/action with conflicting scopes has no unambiguous event
    # identity under the existing contract; do not silently keep the first scope.
    result=[c for i,c in enumerate(changes) if i not in conflicting_scopes]
    if include_adjacent_demand:
        from .adjacent_demand import attach_adjacent_demand
        result=attach_adjacent_demand(text,result,company_names,include_scopes=include_adjacent_scopes and include_demand_scopes,include_contracts=include_adjacent_contracts,include_amounts=include_adjacent_amounts,include_reductions=include_adjacent_reductions)
    return result
