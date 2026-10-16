"""PIT period changes derived from immutable theme versions; no collection/writes."""
from datetime import datetime, timezone
from hashlib import sha256

from .economic_changes import normalized
from .source_share import SourceShareError, _when
from .standard_delivery import build_theme_bundle
from .theme_emergence import _bytes, topic_key, theme_presentation

SCHEMA='newscatalyst.theme_changes.v1'
REASONS={
    'FIRST_OBSERVED':'이 기간에 처음 관측한 테마입니다.',
    'NEW_ECONOMIC_EVENTS':'새 독립 경제 행동의 근거가 추가됐습니다.',
    'ACTIVE_EVENTS_REMOVED':'기존 활성 사건이 제외됐습니다. 철회·정정 근거를 함께 확인하세요.',
    'CONTRADICTION':'기존 사건에 상충하는 근거가 추가됐습니다.',
    'RETRACTION':'특정 기존 사건을 대상으로 한 철회·정정 근거가 추가됐습니다.',
    'REPORTED_INVESTMENT_EXECUTION':'같은 명시 투자 프로젝트의 결정→집행 보도를 연결했습니다. 실제 지출·거래·수혜 확정은 아닙니다.',
    'REPORTED_REALIZATION':'계획과 개시 보도를 연결했습니다. 실제 실현·매출·수혜 확정은 아닙니다.',
    'IDENTITY_UPDATED':'같은 사건의 기업 식별 근거가 바뀌었습니다. 새 기업 확산으로 세지 않습니다.',
    'COMPANY_CONTEXT':'기존 사건의 기업·공급 관계 설명이 추가 또는 변경됐습니다.',
    'ADDITIONAL_SOURCE':'추가 출처 또는 같은 사건의 근거 판본이 확보됐습니다.',
    'COUNTING_UPDATED':'기존 행동의 중복·후속 연결에 따라 사건 집계가 달라졌습니다.',
    'NO_CHANGE':'선택 기간에 저장된 테마 변화가 없습니다. 뉴스 부재는 무효화 근거가 아닙니다.',
    'CONTEXT_UPDATED':'저장된 테마 설명이 갱신됐습니다.',
}


def _refs(theme):
    return {sha256(_bytes(r)).hexdigest():r for r in (theme or {}).get('source_refs',[])}


def _summary(theme):
    if theme is None:return None
    return {'snapshot_sha256':sha256(_bytes(theme)).hexdigest(),'decision_at':theme['decision_at'],
            'status':theme['status'],'scores':theme['scores']}


def _groups(before,after):
    """A recorded plan/start pair is one action across both comparison ends."""
    parent={}
    def find(key):
        parent.setdefault(key,key)
        if parent[key]!=key:parent[key]=find(parent[key])
        return parent[key]
    for theme in (before or {},after):
        for link in theme.get('event_followups',[]):
            a,b=find(link['planned_event_id']),find(link['realization_event_id'])
            parent[max(a,b)]=min(a,b)
        for link in theme.get('investment_stage_links',[]):
            a,b=find(link['decision_event_id']),find(link['execution_event_id'])
            parent[max(a,b)]=min(a,b)
    old={find(e) for e in (before or {}).get('event_ids',[])}
    new={find(e) for e in after['event_ids']}
    return find,old,new


def _identity_updates(before,after,added_refs,removed,added):
    pairs={}
    for fresh in added_refs:
        if fresh['polarity']!='SUPPORT' or not fresh.get('source_binding'):continue
        for old in (before or {}).get('source_refs',[]):
            if (old['event_id']!=fresh['event_id'] or old['polarity']!='SUPPORT'
                    or old.get('source_binding')!=fresh['source_binding']):continue
            old_ids={m['source_name']:m['entity_id'] for m in old.get('company_mappings',[])}
            for mapping in fresh.get('company_mappings',[]):
                prior=old_ids.get(mapping['source_name'],mapping['source_name'])
                target=mapping['entity_id']
                if prior in removed and target in added and prior in old['entity_ids']:
                    pairs.setdefault((prior,target),[]).append({'event_id':fresh['event_id'],**mapping})
    # Conflicting mappings stay explicit; never choose one identity arbitrarily.
    return [{'from_entity_id':a,'to_entity_id':b,'evidence':proofs}
            for (a,b),proofs in sorted(pairs.items())
            if sum(x==a for x,y in pairs)==1 and sum(y==b for x,y in pairs)==1]


def _difference(before,after):
    old=before or {};old_refs=_refs(before);new_refs=_refs(after)
    refs_added=[{'ref_sha256':key,**new_refs[key]} for key in sorted(new_refs.keys()-old_refs.keys())]
    refs_removed=[{'ref_sha256':key,**old_refs[key]} for key in sorted(old_refs.keys()-new_refs.keys())]
    prior_events=set(old.get('event_ids',[]));events=set(after['event_ids'])
    find,old_groups,new_groups=_groups(before,after)
    known={r['event_id'] for r in old_refs.values()}
    new_actions={e for e in events if find(e) in new_groups-old_groups}
    def event_row(e,kind):
        refs={**old_refs,**new_refs}
        supporting=[r for r in refs.values() if r['event_id']==e and r['polarity']=='SUPPORT']
        latest=max(supporting,key=lambda r:(_when(r['recorded_at'],'recorded'),_bytes(r))) if supporting else None
        return {'event_id':e,'action_group_id':find(e),'kind':kind,'source_ref_sha256s':sorted(k for k,r in refs.items()
            if r['event_id']==e or r['supersedes_event_id']==e),'supporting_source':latest}
    event_added=[event_row(e,'NEW_ECONOMIC_EVENT' if e in new_actions else
                          'EXISTING_EVENT_UPDATE' if e in known else 'FOLLOWUP_OBSERVATION')
                 for e in sorted(events-prior_events)]
    event_removed=[event_row(e,'EXCLUDED_FROM_ACTIVE_EVENTS') for e in sorted(prior_events-events)]
    old_companies={c['entity_id']:c for c in old.get('company_links',[])}
    companies={c['entity_id']:c for c in after['company_links']}
    added=set(companies)-set(old_companies);removed=set(old_companies)-set(companies)
    identity=_identity_updates(before,after,refs_added,removed,added)
    added-={m['to_entity_id'] for m in identity};removed-={m['from_entity_id'] for m in identity}
    def company_row(entity,c,kind):
        return {'entity_id':entity,'kind':kind,'event_ids':c['event_ids'],
                'supply_chain_links':c.get('supply_chain_links',[])}
    company_added=[company_row(e,companies[e],
        'NEW_EVENT_PARTICIPANT' if new_actions.intersection(companies[e]['event_ids']) and e in after['entity_ids']
        else 'SUPPLY_CONTEXT' if companies[e].get('supply_chain_links') else 'EXISTING_EVENT_COMPANY_CONTEXT')
        for e in sorted(added)]
    company_removed=[company_row(e,old_companies[e],'EXCLUDED_FROM_ACTIVE_CONTEXT') for e in sorted(removed)]
    old_followups={(l['planned_event_id'],l['realization_event_id']) for l in old.get('event_followups',[])}
    followups=[l for l in after.get('event_followups',[]) if (l['planned_event_id'],l['realization_event_id']) not in old_followups]
    old_investments={(l['decision_event_id'],l['execution_event_id']) for l in old.get('investment_stage_links',[])}
    investments=[l for l in after.get('investment_stage_links',[]) if (l['decision_event_id'],l['execution_event_id']) not in old_investments]
    codes=[]
    if before is None:codes.append('FIRST_OBSERVED')
    if new_groups-old_groups:codes.append('NEW_ECONOMIC_EVENTS')
    if event_removed:codes.append('ACTIVE_EVENTS_REMOVED')
    for polarity,code in [('CONTRADICT','CONTRADICTION'),('RETRACT','RETRACTION')]:
        if any(r['polarity']==polarity for r in refs_added):codes.append(code)
    if followups:codes.append('REPORTED_REALIZATION')
    if investments:codes.append('REPORTED_INVESTMENT_EXECUTION')
    if identity or any(c['kind']=='EXISTING_EVENT_COMPANY_CONTEXT' for c in company_added):codes.append('IDENTITY_UPDATED')
    if company_added or company_removed or old.get('supply_chain_evidence',[])!=after.get('supply_chain_evidence',[]):
        codes.append('COMPANY_CONTEXT')
    if refs_added:codes.append('ADDITIONAL_SOURCE')
    count_delta=after['scores']['distinct_economic_events']-old.get('scores',{}).get('distinct_economic_events',0)
    if count_delta!=len(new_groups-old_groups)-len(old_groups-new_groups):codes.append('COUNTING_UPDATED')
    if not codes:codes.append('NO_CHANGE' if before==after else 'CONTEXT_UPDATED')
    return {'events':{'added':event_added,'removed':event_removed,
                     'independent_actions_added':len(new_groups-old_groups),'independent_actions_removed':len(old_groups-new_groups)},
            'companies':{'added':company_added,'removed':company_removed,'identity_updates':identity,
                         'new_event_participant_count':sum(c['kind']=='NEW_EVENT_PARTICIPANT' for c in company_added)},
            'sources':{'added':refs_added,'removed':refs_removed},'followups_added':followups,
            **({'investment_stage_links_added':investments} if investments else {}),
            'reasons':[{'code':code,'text':REASONS[code]} for code in codes]}


def compare_themes(store, *, since, as_of, query='', activity='all', now=None):
    start=_when(since.isoformat(),'period start');end=_when(as_of.isoformat(),'period end')
    present=_when((now or datetime.now(timezone.utc)).isoformat(),'now')
    if not isinstance(query,str) or len(query)>200 or activity not in {'all','changed','new','updated'}:
        raise SourceShareError('invalid theme change query')
    results=[]
    for theme_id,versions in store.period_versions(since=start,as_of=end,now=present).items():
        for version in versions:build_theme_bundle([version],decision_at=end,now=present)
        before=versions[0] if _when(versions[0]['decision_at'],'version')<start else None
        after=versions[-1];change=_difference(before,after)
        state='new' if before is None else 'unchanged' if before==after else 'updated'
        transitions=[];previous=before
        for version in versions[(1 if before else 0):]:
            if previous is None or previous['status']!=version['status']:
                detail=_difference(previous,version)
                transitions.append({'from_status':previous['status'] if previous else None,'to_status':version['status'],
                    'decision_at':version['decision_at'],'snapshot_sha256':sha256(_bytes(version)).hexdigest(),
                    'reasons':detail['reasons'],'evidence':detail['sources']['added'],
                    'before_scores':previous['scores'] if previous else None,'after_scores':version['scores']})
            previous=version
        item={'theme_id':theme_id,'provisional_name':after['provisional_name'],'activity':state,
              'first_detected_at':after['first_detected_at'],'before':_summary(before),'after':_summary(after),
              **change,'status_transitions':transitions,'verified_vs_inferred':'THEME_HYPOTHESIS'}
        if activity!='all' and state not in ({'new','updated'} if activity=='changed' else {activity}):continue
        text=normalized(_bytes([item,before,after]).decode()+' '+theme_presentation(after)['name'])
        if not any(term in text for term in {normalized(query),topic_key(query)}):continue
        results.append(item)
    return {'schema':SCHEMA,'since':start.isoformat(),'as_of':end.isoformat(),
            'baseline':'LATEST_STRICTLY_BEFORE_SINCE','end_inclusive':True,
            'ThemeChanges':sorted(results,key=lambda x:(x['after']['decision_at'],x['theme_id']),reverse=True),
            'orders_enabled':False,'original_content_included':False}
