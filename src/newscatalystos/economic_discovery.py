"""Event-first discovery; industry knowledge enriches but never admits events.

Reuses the existing economic-action vocabulary and literal source evidence.
Unmapped products or missing companies remain observable, with empty industry /
company lists. Tags are source-word hints, never validated supply-chain coverage.
No model call, issuer-name lookup, investment score, or producer/source write.
"""
from hashlib import sha256
import re

from .economic_changes import ACTIONS,business_start_phase,market_entry,normalized
from .power_equipment import PRODUCTS

MODE='ECONOMIC_DISCOVERY'
RULE_VERSION='rss-event-first-v1'
# Action grammar is sector-independent. Specializations of the existing
# action vocabulary only bound the verb span; they do not require a product.
KOREAN=tuple((kind,re.compile(
    r'투자(?:를)?\s*(?:결정|확정)' if kind=='INVESTMENT' else pattern,re.I))
    for kind,pattern in ACTIONS)
SUBJECT=re.compile(r'^(?P<actor>[가-힣A-Za-z0-9][가-힣A-Za-z0-9&.·\- ]{1,69}?)(?:(?:은|는|이|가)\s+|\s*[,，]\s*)')
AUTHORITY=re.compile(r'^(?:정부|국회|국무회의|국무총리|대통령|산업부|중기부|과기정통부|NIST|'
                     r'(?:The )?Department\b|[가-힣 ]*(?:부처|위원회|청|부)$)',re.I)
GENERIC_PARTY={'기업','회사','업계','시장','관계자','당사','당사자','manufacturer','company','companies'}
NEGATIVE=re.compile(r'루머|추측|가능성|부인|사실\s*무근|미확정|검토\s*중|논의\s*중|'
    r'하지\s*않|하지\s*못|되지\s*않|체결되지|취소|철회|해지|무산|전망|예상|기대|'
    r'\b(?:rumou?r|denies|denied|unconfirmed|cancelled|canceled|rejected|may|might|not)\b',re.I)
CONTEXT=re.compile(r'(?:개시|시작|체결|집행).{0,12}(?:기념|주년|설명회|세미나|교육|방법|가능성|여부)'
                   r'|\b(?:conference|workshop|anniversary|funding opportunity)\b',re.I)
PLANNED=re.compile(r'예정|계획|추진|목표|방침|\b(?:plans?|will|intent|proposed|to amend)\b',re.I)
HISTORICAL=re.compile(r'지난해|작년|과거|지난달|기존|\b(?:previous|previously|last year|existing)\b',re.I)
EN_AWARD=re.compile(r'\b(?:Announces?\s+(?:the\s+)?Finalization\s+of|'
    r'(?:Announces?|Finalizes?)\s+(?:(?:a|the)\s+)?(?:Definitive|Direct\s+Funding)\s+Agreement|'
    r'Announces?\s+(?:an?\s+)?(?:Agreement|Letter\s+of\s+Intent)|Awards?\b)',re.I)
EN_BUSINESS=re.compile(r'\b(?:launch(?:es|ed)?|begins?|starts?)\s+(?:a\s+|an\s+|the\s+)?(?:[^.!?]{0,70}?\s+)?(?:service|production|deliveries)\b',re.I)
RECIPIENT=re.compile(r'\bwith\s+(?P<name>[A-Z][A-Za-z0-9&.\- ]{1,69}?)(?=\s+(?:for|to|and|with)\b|[,;]|$)',re.I)
PUBLIC_RECIPIENT=re.compile(r'\bto\s+(?P<name>[A-Z][A-Za-z0-9&.\- ]{1,69}?)(?=\s+to\s+(?:support|expand)|[,;]|$)')
# These labels are downstream hints, not sector-specific event detectors.
HINTS=(
 ('SEMICONDUCTOR','반도체',r'반도체|\b(?:semiconductors?|HBM|DRAM|NAND|EUV|DUV)\b'),
 ('POWER_EQUIPMENT','전력기기','|'.join(pattern for _,pattern in PRODUCTS)),
 ('QUANTUM_TECHNOLOGY','양자기술',r'양자\s*(?:기술|컴퓨팅|컴퓨터)|\bquantum\s+(?:technolog\w*|comput\w*)\b'),
 ('ROBOTICS','로봇',r'로봇|\brobots?\b|\brobotics\b'),
 ('CRITICAL_MINERALS','핵심광물',r'핵심\s*광물|희토류|\bcritical\s+minerals?\b|\bmine-to-magnet\b'),
 ('SOFTWARE_SERVICES','소프트웨어·디지털 서비스',r'소프트웨어|\bsoftware\b|\beSIM\b'),
)


def _span(text,start,end):
    return {'text':text[start:end],'start':start,'end':end,
            'sha256':sha256(text[start:end].encode()).hexdigest()}


def _companies(actor):
    value=actor.strip(' ,，')
    if (len(value)<2 or normalized(value) in {normalized(v) for v in GENERIC_PARTY}
            or AUTHORITY.search(value) or re.search(r'\b(?:a subsidiary of|up to|more than|million|billion)\b',value,re.I)
            or (re.search(r'[가-힣]',value) and ' ' in value)
            or re.search(r'(?:확대하|추진하|묻|하|되)$',value)):
        return []
    # Keep a stated organizational name, not a guessed ticker or inferred buyer.
    return [value] if len(value)<=80 else []


def _raw_events(text):
    if NEGATIVE.search(text) or CONTEXT.search(text):return []
    events=[]
    # Preserve offsets in the original title; don't translate or rewrite it.
    units=list(re.finditer(r'[^\n!?。]+[!?。]?',text))
    for unit in units:
        clause=unit.group().strip();offset=unit.start()+len(unit.group())-len(unit.group().lstrip())
        if not clause:continue
        subject=SUBJECT.match(clause)
        if subject and not (_companies(subject['actor']) or AUTHORITY.search(subject['actor'])):
            subject=None  # sentence fragments are not automatically company names
        body_start=subject.end() if subject else 0
        body=clause[body_start:];candidates=[]
        for action,pattern in KOREAN:
            for match in pattern.finditer(body):
                candidates.append((action,match))
        # '생산 재개' is one action; don't let a nested expression double count.
        if len(candidates)==1:
            action,match=candidates[0]
            if action=='BUSINESS_START' and business_start_phase(clause) is None:continue
            if action=='INVESTMENT' and re.search(r'자사주|주주환원|주식|채권|부동산',body):continue
            a=body_start+match.start();b=body_start+match.end()
            object_text=body[:match.start()].strip(' ,，·')
            # If broad action regex spans the object, retain a literal phrase
            # rather than suppressing the action because no industry is known.
            topic=object_text[-120:] if object_text else clause[a:b]
            names=_companies(subject['actor']) if subject else []
            if action=='POLICY_CHANGE' and re.search(r'개정안|개정령안|법안',clause):
                names=[]  # legislative subject or policy purpose, not a corporate actor
            # A rhetorical preface before ellipsis is not the service object.
            if not names and action=='BUSINESS_START':
                local=re.split(r'\.{2,}|…+',object_text)[-1].strip()
                if local:topic=local
            # Never assign another subject's action to a heading's company.
            # Keep the event as a missing-company observation instead.
            if subject and SUBJECT.search(body[:match.start()]):names=[]
            if names and names[0] in {'변압기','반도체','신약','소프트웨어','제품','생산량','공급량'}:names=[]
            events.append((action,topic,names,clause,offset+a,offset+b,
                           bool(object_text),subject['actor'] if subject else None))
            continue
        # Generic English signed government support/intent grammar. Issuer and
        # recipient come from this title; no hard-coded program/company/product.
        action=EN_AWARD.search(clause)
        if action:
            issuer=clause[:action.start()].strip()
            if not AUTHORITY.search(issuer):continue
            tail=clause[action.end():].strip()
            recipients=list(RECIPIENT.finditer(tail))
            if len(recipients)>1:continue
            recipient=recipients[0] if recipients else None
            if recipient:names=_companies(recipient['name'])
            else:
                recipient=PUBLIC_RECIPIENT.search(tail)
                names=_companies(recipient['name']) if recipient else []
            # A program object is still a useful observation when its actual
            # industry/recipient is not specified. Never infer quantum from a
            # recipient's company name or semiconductor from the CHIPS label.
            if recipient:topic=tail[:recipient.start()].strip(' ,')
            else:topic=tail
            if not topic:topic=action.group()
            # A literal purpose phrase can clarify an otherwise generic signed
            # agreement without moving its recipients into the industry tags.
            purpose=re.search(r'\b(?:to Support|to Expand|to Develop|to Accelerate)\s+(.+)$',tail,re.I)
            if purpose:topic=purpose[1].strip(' .')
            if len(topic)>120:topic=topic[:120].rsplit(' ',1)[0]
            events.append(('POLICY_CHANGE',topic,names,clause,offset+action.start(),
                           offset+action.end(),True,issuer))
            continue
        english=EN_BUSINESS.search(clause)
        if english:
            actor=clause[:english.start()].strip(' ,')
            if not actor or AUTHORITY.search(actor):continue
            phrase=english.group()
            kind='PRODUCTION_START' if re.search(r'\bproduction\b',phrase,re.I) else 'DELIVERY_START' if re.search(r'\bdeliveries\b',phrase,re.I) else 'BUSINESS_START'
            topic=re.sub(r'^(?:launch(?:es|ed)?|begins?|starts?)\s+(?:(?:a|an|the)\s+)?','',phrase,flags=re.I)
            events.append((kind,topic,_companies(actor),clause,offset+english.start(),offset+english.end(),True,actor))
    return events[:30]


def discover_economic_events(text):
    """Detect -> bind literal object/party -> optional industry hints, in order.

    Unknown vocabulary is a stored watch topic, not a reason to drop an event.
    Grammar uncertainty is different: incidental/negated verbs do not establish
    a new economic action. Missing date, sector or recipient stays explicitly N/A.
    """
    if not isinstance(text,str) or not 0<len(text)<=5000 or '\x00' in text:
        raise ValueError('bounded original news title required')
    result=[]
    for action,topic,names,clause,start,end,has_object,issuer in _raw_events(text):
        # Linking occurs only AFTER an event exists. Removing every label rule
        # below must not change the number of detected events or their parties.
        links=[]
        for tag,label,pattern in HINTS:
            found=re.search(pattern,topic,re.I)
            if found:links.append({'industry':tag,'label':label,'source_phrase':found.group(),
                'evidence_sha256':sha256(found.group().encode()).hexdigest(),'status':'SOURCE_WORD_HINT_NOT_SUPPLY_CHAIN_VALIDATION'})
        phase='PLANNED' if (action=='INVESTMENT' or PLANNED.search(clause)
                              or (action=='BUSINESS_START' and business_start_phase(clause)=='PLANNED')) else 'SOURCE_REPORTED'
        driver=('POLICY_ENABLEMENT' if action=='POLICY_CHANGE' else 'SUPPLY_CONTRACTION' if action=='SUPPLY_REDUCTION'
                else 'CAPACITY_EXPANSION' if action in {'PRODUCTION_START','CAPACITY_ADDITION','INVESTMENT_EXECUTION'}
                or (action=='INVESTMENT' and re.search(r'공장|설비|시설|생산|factory|facility|production',topic,re.I)) else 'UNKNOWN')
        bounded_topic=topic if len(topic)<=80 else topic[:80].rsplit(' ',1)[0]
        change={'topic':bounded_topic,'action':action,'phase':phase,'economic_driver':driver,
                'entity_ids':names,'industry_tags':[l['industry'] for l in links],
                'source_paragraph_sha256':sha256(text.encode()).hexdigest(),
                'evidence_level':'REPORTED','verified_economic_effect':False}
        if action=='MARKET_ENTRY':
            market=market_entry(topic+' '+text[start:end])
            if market is None:continue  # existing delivery requires a source-named market
            change['market_entry']=market
        observation={'mode':MODE,'event_first':True,'industry_required_for_detection':False,
            'action_evidence':_span(text,start,end),'object_expression':topic,
            'normalized_headline_sha256':sha256(text.encode()).hexdigest(),
            'topic_label_truncated':bounded_topic!=topic,
            'object_status':'SOURCE_STATED' if has_object else 'UNSPECIFIED_OBJECT_ACTION_RETAINED',
            'source_named_issuer':issuer,'company_status':'SOURCE_NAME_ONLY' if names else 'COMPANY_UNSPECIFIED',
            'industry_status':'LINKED_BY_SOURCE_WORDS' if links else 'UNCLASSIFIED_OBSERVATION',
            'industry_links':links,'watch_topic':bounded_topic,'source_reports_historical_context':bool(HISTORICAL.search(clause)),
            'market_newness':'UNKNOWN','deep_industry_validation':False,'new_provider_permission_granted':False}
        if not any(x['change']==change for x in result):result.append({'change':change,'discovery':observation})
    return result


# Post-detection context: never changes an existing economic event or industry
# admission rule. These spans are saved with their own analysis availability.
_PURPOSE_CONTEXT=re.compile(r'\bto\s+(?:Support|Expand|Develop|Accelerate|Enhance|Increase|Boost)\s+(?P<object>.+)$',re.I)
_SUBSIDIARY_RECIPIENT=re.compile(
    r'\b(?:to|with)\s+(?:a|an)\s+(?:wholly[- ]owned\s+)?subsidiary\s+of\s+'
    r'(?P<parent>[A-Za-z][A-Za-z0-9&.\x27\- ]{1,79}?)\s*'
    r'\((?P<recipient>[A-Za-z][A-Za-z0-9&.\x27\- ]{1,79})\)'
    r'(?=\s+to\s+(?:Support|Expand|Develop|Accelerate|Enhance|Increase|Boost)\b|\s*$)',re.I)


def connect_discovered_source_context(text,records):
    """Read literal same-award recipients/purpose AFTER economic detection.

    An explicit parent is a source-stated relationship, not the recipient,
    confirmed legal ownership, or a listed beneficiary. Ordinary industry
    hints reuse HINTS; company/program names supply no absent sector evidence.
    Older extraction output stays byte-compatible and keeps its event identity.
    """
    if not isinstance(text,str) or not 0<len(text)<=5000 or not isinstance(records,list) or len(records)>30:
        raise ValueError('bounded existing discoveries required')
    connected=[]
    for index,record in enumerate(records):
        change=record['change'];meta=record['discovery'];action=meta['action_evidence']
        issuer=meta.get('source_named_issuer') or ''
        if (change['action']!='POLICY_CHANGE' or not AUTHORITY.search(issuer)
                or not EN_AWARD.fullmatch(text[action['start']:action['end']])):
            continue
        remainder=text[action['end']:]
        # A distinct sentence, another announcement or recipient list cannot
        # lend its industry or subsidiary to this action.
        if re.search(r'[;\n!?。]|(?<![A-Z])\.(?=\s+[A-Z][a-z])',remainder) or EN_AWARD.search(remainder):continue
        purposes=list(_PURPOSE_CONTEXT.finditer(remainder))
        purpose=purposes[0] if len(purposes)==1 else None
        if purpose and re.search(r'\bto\s+(?:Support|Expand|Develop|Accelerate|Enhance|Increase|Boost)\b',purpose['object'],re.I):continue
        recipients=list(_SUBSIDIARY_RECIPIENT.finditer(remainder))
        recipient=recipients[0] if len(recipients)==1 else None
        parties=[];industry=[];purpose_span=None
        if recipient:
            child=recipient['recipient'].strip();parent=recipient['parent'].strip()
            unambiguous=(not re.search(r'\band\b|\bor\b',parent+' '+child,re.I)
                         and not re.search(r'\b(?:with|to)\s+',remainder[:recipient.start()],re.I))
            if (unambiguous and _companies(child)==[child] and _companies(parent)==[parent]
                    and normalized(child)!=normalized(parent)):
                offset=action['end']
                parties.append({'source_name':child,'role':'SOURCE_NAMED_SUBSIDIARY_RECIPIENT',
                    'name_evidence':_span(text,offset+recipient.start('recipient'),offset+recipient.end('recipient')),
                    'relation_evidence':_span(text,offset+recipient.start(),offset+recipient.end()),
                    'source_parent_name':parent,
                    'parent_name_evidence':_span(text,offset+recipient.start('parent'),offset+recipient.end('parent')),
                    'parent_is_direct_recipient':False,'ownership_verified':False,
                    'official_entity_id':None,'listed_security_verified':False,'verified_real_benefit':False})
        if purpose:
            lo=action['end']+purpose.start('object');hi=action['end']+purpose.end('object')
            purpose_span=_span(text,lo,hi)
            for tag,label,pattern in HINTS:
                found=re.search(pattern,purpose['object'],re.I)
                if found:
                    span=_span(text,lo+found.start(),lo+found.end())
                    industry.append({'industry':tag,'label':label,'source_phrase':span['text'],
                        'evidence_sha256':span['sha256'],'evidence':span,
                        'status':'SOURCE_WORD_HINT_NOT_SUPPLY_CHAIN_VALIDATION'})
        new_industries={l['industry'] for l in industry}-set(change['industry_tags'])
        # Store only concrete missing connections, not another copy of every
        # already understood source. Full purpose remains exact, not truncated.
        if not parties and not new_industries:continue
        connected.append({'schema':'newscatalyst.discovery_source_context.v1',
            'event_index':index,'topic':change['topic'],'action':change['action'],'phase':change['phase'],
            'original_entity_ids':change['entity_ids'][:],'original_industry_tags':change['industry_tags'][:],
            'action_evidence':action,'normalized_headline_sha256':sha256(text.encode()).hexdigest(),
            'company_links':parties,'industry_links':industry,'purpose_evidence':purpose_span,
            'event_identity_changed':False,'new_economic_event':False,'deep_industry_validation':False,
            'market_newness':'UNKNOWN','investment_rank':None,'orders_enabled':False})
    return connected
