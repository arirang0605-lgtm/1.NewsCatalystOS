"""Compare already observed product announcements without merging their events.

Exact source-named company/product only: no translation, alias dictionary,
issuer lookup or industry gate. Identity of an announcement is distinct from
identity of a product. The original source rows and counts remain untouched.
"""
from collections import defaultdict
from hashlib import sha256
import re

from .economic_changes import normalized
from .source_share import SourceShareError,_when
from .theme_emergence import _bytes

SCHEMA='newscatalyst.discovery_launch_comparison.v1'
REASONS={
    'IDENTICAL_TITLE_CONTENT': '제목 내용이 동일합니다. 추가 출처라는 이유만으로 새 출시 재료를 가산할 근거는 없습니다.',
    'SAME_SOURCE_TITLE_REVISION': '같은 제공자 문서의 제목 판본이 달라졌습니다. 단순 수정인지 실질 변경인지는 원문을 비교해야 합니다.',
    'REPORTED_PHASE_DIFFERENCE': '같은 회사·제품의 발표 단계가 다릅니다. 계획에서 출시로 진행됐을 가능성은 있으나 같은 계획의 이행으로 확정하지 않습니다.',
    'SAME_COMPANY_PRODUCT_ONLY': '회사명·제품명·출시 행동이 일치합니다. 번역·재배포 또는 별도 발표인지 제목만으로 확정할 수 없습니다.',
}


def _span(text,term,lo,hi):
    """Literal span, not a reconstructed quotation or a translated alias."""
    found=re.search(re.escape(term),text[lo:hi],re.I)
    if found is None:return None
    start=lo+found.start();end=lo+found.end()
    return {'text':text[start:end],'start':start,'end':end,'sha256':sha256(text[start:end].encode()).hexdigest()}


def _observations(themes,titles,at):
    seen={}
    for theme in themes:
        for ref in theme['source_refs']:
            if (ref.get('action')!='PRODUCT_LAUNCH' or ref['polarity']!='SUPPORT'
                    or ref['event_id'] not in theme['event_ids']
                    or ref['event_id'] in theme['conflicting_event_ids']
                    or ref['event_id'] in theme['invalidated_event_ids']):continue
            binding=ref.get('source_binding') or {}
            key=(ref['source_id'],binding.get('source_event_sha256'),ref['evidence_sha256'])
            row=titles.get(key)
            if row is None:continue
            matched=[v for v in row.get('economic_discovery',[]) if
                (v['change']['topic'],v['change']['action'],v['change']['phase'])==
                (ref['topic'],ref['action'],ref['phase'])]
            if len(matched)!=1:continue
            c=matched[0]['change'];d=matched[0]['discovery']
            if (len(c['entity_ids'])!=1 or d.get('topic_label_truncated')
                    or d.get('company_status')!='SOURCE_NAME_ONLY' or not d.get('object_evidence')):continue
            company=c['entity_ids'][0];product=c['topic'];headline=row['headline']
            if company not in ref.get('original_entity_ids',ref['entity_ids']):continue
            action=d['action_evidence'];obj=d['object_evidence']
            # Both literal identifiers are evidenced in the same validated
            # headline. Product-version digits/punctuation are not stripped.
            company_span=_span(headline,company,0,action['start'])
            product_span=_span(headline,product,obj['start'],obj['end'])
            if not company_span or not product_span:continue
            available=max(_when(row['available_at'],'saved report available'),
                          _when(ref['recorded_at'],'event recorded'),
                          _when(ref['source_available_at'],'source available'))
            if available>at:continue
            observation_id=sha256(_bytes({'provider':key[0],'source_event_sha256':key[1],
                'source_title_sha256':key[2],'economic_event_id':ref['event_id']})).hexdigest()
            value={'observation_id':observation_id,'theme_ids':[theme['theme_id']],
                'event_id':ref['event_id'],'provider_id':key[0],'source_event_sha256':key[1],
                'source_title_sha256':key[2],'headline_sha256':sha256(headline.encode()).hexdigest(),
                'headline':headline,'source_url':row['source_url'],'phase':c['phase'],
                'source_company_name':company,'source_product_name':product,
                'company_evidence':company_span,'product_evidence':product_span,
                'source_available_at':ref['source_available_at'],'report_sha256':row['report_sha256'],
                'basis_available_at':available.isoformat(),
                'title_script':'CONTAINS_KOREAN' if re.search(r'[가-힣]',headline) else 'NO_KOREAN_SCRIPT',
                'reported_published_at':None,'official_entity_id':None}
            previous=seen.get(observation_id)
            if previous:
                value['theme_ids']=sorted(set(previous['theme_ids'])|set(value['theme_ids']))
                value['basis_available_at']=max(previous['basis_available_at'],value['basis_available_at'])
            seen[observation_id]=value
    return list(seen.values())


def compare_launch_observations(themes,titles,*,as_of,now):
    """Bounded adjacent comparisons within exact source-name/product groups.

    Chronology is LOCAL OBSERVATION chronology, not a claimed publication or
    release date. A long interval does not turn a product match into a duplicate.
    Pair IDs use original observations, never request time, order or language.
    """
    at=_when(as_of.isoformat(),'comparison as of');present=_when(now.isoformat(),'now')
    if at>present:raise SourceShareError('future product comparison')
    groups=defaultdict(list)
    for row in _observations(themes,titles,at):
        groups[(normalized(row['source_company_name']),normalized(row['source_product_name']))].append(row)
    output=[]
    for key,rows in sorted(groups.items()):
        if len(rows)<2:continue
        rows.sort(key=lambda r:(_when(r['source_available_at'],'source observed'),r['observation_id']))
        pairs=[]
        for left,right in zip(rows,rows[1:]):
            same_source=(left['provider_id'],left['source_event_sha256'])==(right['provider_id'],right['source_event_sha256'])
            same_title=left['headline_sha256']==right['headline_sha256']
            phase_diff=left['phase']!=right['phase']
            status=('IDENTICAL_TITLE_CONTENT' if same_title else 'SAME_SOURCE_TITLE_REVISION' if same_source
                    else 'REPORTED_PHASE_DIFFERENCE' if phase_diff else 'SAME_COMPANY_PRODUCT_ONLY')
            pair_id=sha256(_bytes({'method':SCHEMA,'observations':sorted([left['observation_id'],right['observation_id']])})).hexdigest()
            pairs.append({'comparison_id':pair_id,'left_observation_id':left['observation_id'],
                'right_observation_id':right['observation_id'],'status':status,'reason':REASONS[status],
                'source_document_same':same_source,'title_content_same':same_title,
                'source_phase_differs':phase_diff,'scripts_differ':left['title_script']!=right['title_script'],
                'observed_title_time_gap_seconds':abs((_when(right['source_available_at'],'right source')-
                                                      _when(left['source_available_at'],'left source')).total_seconds()),
                'observed_times_are_release_dates':False,'translation_verified':False,
                'same_market_announcement_verified':False,'economic_change_confirmed':False,
                'independent_market_event_count':None,
                'additional_new_material_supported':False if same_title else None,
                'news_use':'NO_NEW_TITLE_CONTENT' if same_title else 'COMPARE_SOURCE_EVIDENCE_BEFORE_ADDITIONAL_CATALYST',
                'basis_available_at':max(left['basis_available_at'],right['basis_available_at'])})
        group_id=sha256(_bytes({'method':SCHEMA,'source_company':key[0],'source_product':key[1]})).hexdigest()
        output.append({'schema':SCHEMA,'comparison_group_id':group_id,
            'source_company_name':rows[0]['source_company_name'],'source_product_name':rows[0]['source_product_name'],
            'match_basis':'EXACT_NFKC_CASEFOLD_WHITESPACE_SOURCE_NAMES_NO_ALIAS_OR_TRANSLATION',
            'theme_ids':sorted({t for r in rows for t in r['theme_ids']}),
            'event_ids':sorted({r['event_id'] for r in rows}),'observations':rows,'pairs':pairs,
            'basis_available_at':max(p['basis_available_at'] for p in pairs),
            'source_observation_count':len(rows),'comparison_pair_count':len(pairs),
            'source_rows_merged':False,'economic_event_ids_changed':False,
            'independent_market_event_count':None,'leader_score_adjustment':None,
            'selection_owner':'EraLeader','orders_enabled':False})
    return output
