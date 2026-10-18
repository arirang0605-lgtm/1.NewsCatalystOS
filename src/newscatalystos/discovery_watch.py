"""Stored event-first observations and their emerging subject/industry watchlist.

Reuse completed RSS analyses and ThemeStore. The watchlist is not a declaration
of verified sector supply-chain coverage, company benefit, or market novelty.
"""
from datetime import datetime,timezone
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from .theme_emergence import ThemeStore,_bytes
from .catalyst_material import materials_for_store,default_since,attach_material
from .research_dashboard import scan_saved_analysis
from .standard_delivery import build_theme_bundle
from .source_share import SourceShareError,_when


def read_discovery(root,*,as_of=None,since=None,now=None,_compare_outlook=True,include_common_causes=False):
    present=now or datetime.now(timezone.utc);at=as_of or present
    start=since or default_since(at)
    present=_when(present.isoformat(),'now');at=_when(at.isoformat(),'as of');start=_when(start.isoformat(),'since')
    if start>at or at>present:raise SourceShareError('invalid discovery interval')
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root:raise SourceShareError('unsafe discovery root')
    if not root.exists():
        return {'status':'NOT_STARTED','candidates':[],'counts':{'events':0,'unclassified_topics':0},'observed_industries':[],
                'theme_outlook':{'candidates':[],'counts':{'theme_hypotheses':0}}}
    themes=ThemeStore(root/'theme_history').search(as_of=at,now=present)
    materials=materials_for_store(ThemeStore(root/'theme_history'),since=start,as_of=at,scope='discovery',now=present,industry='ALL_DISCOVERED')
    parents=sorted(p for p in (root/'feed_analysis').glob('d_*') if p.is_dir() and not p.is_symlink())
    reports,coverage=scan_saved_analysis(root/'no_default_reports',as_of=at,now=present,
        additional_roots=tuple((p.name,p) for p in parents))
    titles={(r['provider'],r['source_event_sha256'],r['source_title_sha256']):r
            for r in reports if r.get('analysis_industry')=='ECONOMIC_DISCOVERY'}
    candidates=[]
    for theme in themes:
        matched=[];seen=set();links=[];connections=[];current_names={}
        for ref in theme['source_refs']:
            # Source-bound context may resolve the literal recipient of this
            # exact action. Never remove a name supported by another event.
            name_key=(ref['event_id'],ref['source_id'],ref['evidence_sha256'])
            if ref['polarity']=='SUPPORT' and ref['event_id'] in theme['event_ids']:
                current_names[name_key]=set(ref['entity_ids'])
            binding=ref.get('source_binding',{})
            key=(ref['source_id'],binding.get('source_event_sha256'),ref['evidence_sha256'])
            row=titles.get(key)
            if row is None:continue
            if key not in seen:
                matched.append({'provider_id':row['provider'],'headline':row['headline'],'source_url':row['source_url'],
                    'title_sha256':key[2],'source_event_sha256':key[1],
                    'source_available_at':row['source_available_at'],'analysis_available_at':row['analysis_available_at']})
                seen.add(key)
            for item in row.get('economic_discovery',[]):
                if item['change']['topic']==ref['topic'] and item['change']['action']==ref['action']:
                    for link in item['discovery']['industry_links']:
                        if link not in links:links.append(link)
            for context in row.get('discovery_source_connections',[]):
                if (context['topic'],context['action'],context['phase'])!=(ref['topic'],ref['action'],ref['phase']):continue
                value=deepcopy(context)
                value.update(event_id=ref['event_id'],source_id=ref['source_id'],source_url=ref['source_url'],
                    source_title_sha256=key[2],report_sha256=row.get('discovery_context_report_sha256',row['report_sha256']),
                    available_at=row.get('discovery_context_available_at',max(row['available_at'],row['analysis_available_at'])))
                if value not in connections:connections.append(value)
                if context['company_links'] and name_key in current_names:
                    current_names[name_key]={p['source_name'] for p in context['company_links']}
                for link in context['industry_links']:
                    if not any((x['industry'],x['source_phrase'],x['evidence_sha256'])==
                               (link['industry'],link['source_phrase'],link['evidence_sha256']) for x in links):
                        links.append(deepcopy(link))
        names=sorted(set().union(*current_names.values())) if current_names else []
        industries=sorted(set(theme['industry_tags'])|{l['industry'] for x in connections for l in x['industry_links']})
        candidates.append({'theme_id':theme['theme_id'],'watch_topic':theme['topic_aliases'][0],
            'status':'OBSERVATION_CANDIDATE','industry_tags':industries,
            'original_industry_tags':theme['industry_tags'],'original_source_companies':theme['entity_ids'],
            'source_context_connections':connections,
            'context_connected_at':max((c['available_at'] for c in connections),default=None),
            'industry_status':'SOURCE_WORD_HINTS' if industries else 'UNCLASSIFIED_OBSERVATION',
            'industry_links':links,'source_companies':names,
            'company_status':'SOURCE_NAME_ONLY' if names else 'COMPANY_UNSPECIFIED',
            'economic_actions':sorted({r['action'] for r in theme['source_refs'] if r['polarity']=='SUPPORT'}),
            'event_ids':theme['event_ids'],'source_version_count':len(matched),
            'distinct_event_count':theme['scores']['distinct_economic_events'],
            'first_observed_at':theme['first_detected_at'],'last_changed_at':theme['decision_at'],
            'source_evidence':matched,'material':materials.get(theme['theme_id']),
            'deep_industry_validation':False,'market_newness':'UNKNOWN','orders_enabled':False})
    candidates.sort(key=lambda r:(r['last_changed_at'],r['theme_id']),reverse=True)
    from .discovery_launch_comparison import compare_launch_observations
    comparisons=compare_launch_observations(themes,titles,as_of=at,now=present)
    for candidate in candidates:
        candidate['launch_comparison_group_ids']=[g['comparison_group_id'] for g in comparisons
                                                  if candidate['theme_id'] in g['theme_ids']]
    from .theme_outlook import build_theme_outlook,compare_outlooks
    outlook=build_theme_outlook(themes,titles,candidates,as_of=at,since=start,now=present)
    if _compare_outlook:
        previous=read_discovery(root,as_of=start,since=start,now=present,_compare_outlook=False)
        compare_outlooks(outlook,previous['theme_outlook'])
    causes={}
    if include_common_causes:
        from .discovery_cause_links import build_discovery_causes
        causes['common_cause_connections']=build_discovery_causes(themes,titles,candidates,as_of=at,since=start,now=present)
    return {**causes,'schema':'newscatalyst.economic_discovery_watch.v1','status':'READY','as_of':at.isoformat(),
        'theme_outlook':outlook,
        'launch_comparisons':comparisons,
        'comparison_since':start.isoformat(),'candidates':candidates,
        'counts':{'topics':len(candidates),'events':sum(c['distinct_event_count'] for c in candidates),
                  'unclassified_topics':sum(not c['industry_tags'] for c in candidates),
                  'observed_company_names':len({e for c in candidates for e in c['source_companies']}),
                  'analysis_title_versions':len(reports),
                  'source_context_enriched_topics':sum(bool(c['source_context_connections']) for c in candidates),
                  'launch_comparison_groups':len(comparisons),
                  'compared_launch_source_observations':sum(g['source_observation_count'] for g in comparisons)},
        'observed_industries':sorted({v for c in candidates for v in c['industry_tags']}),
        'source_coverage':coverage,'industry_module_required_for_detection':False,
        'scope_limit':'REGISTERED_SOURCES_STORED_TITLES_COMMON_ACTION_GRAMMAR_NOT_ALL_NEWS',
        'note':'업종명·기업·발행시각 미확인은 관측만 보존하며 심층검증·시장신규 재료를 인증하지 않음',
        'investment_rank':None,'orders_enabled':False}


def export_discovery(root,*,as_of=None,since=None,now=None,include_common_causes=False):
    present=now or datetime.now(timezone.utc);at=as_of or present;start=since or default_since(at)
    store=ThemeStore(Path(root)/'theme_history')
    themes=store.search(as_of=at,now=present)
    view=read_discovery(root,as_of=at,since=start,now=present,include_common_causes=include_common_causes)
    rows={c['theme_id']:c for c in view['candidates']}
    materials={k:c['material'] for k,c in rows.items() if c['material'] is not None}
    result=attach_material(themes,materials)
    for theme,original in zip(result,themes):
        row=rows.get(theme['theme_id'])
        if row and row['source_context_connections']:
            theme['discovery_source_context']={
                'source_theme_sha256':sha256(_bytes(original)).hexdigest(),
                'original_theme_decision_at':original['decision_at'],
                'available_at':row['context_connected_at'],
                'connections':row['source_context_connections'],
                'source_named_companies':row['source_companies'],
                'industry_word_hints':row['industry_tags'],
                'event_ids_unchanged':True,'new_economic_event':False,'ownership_or_benefit_verified':False}
            theme['decision_at']=max(theme['decision_at'],row['context_connected_at'])
        groups=[g for g in view['launch_comparisons'] if theme['theme_id'] in g['theme_ids']]
        if groups:
            theme['discovery_launch_comparison']={
                'source_theme_sha256':sha256(_bytes(original)).hexdigest(),
                'original_theme_decision_at':original['decision_at'],
                'comparison_groups':groups,'source_rows_merged':False,
                'basis_available_at':max(g['basis_available_at'] for g in groups),
                'new_economic_event':False,'independent_market_event_count':None}
            theme['decision_at']=max(theme['decision_at'],theme['discovery_launch_comparison']['basis_available_at'])
        causes=[g for g in view.get('common_cause_connections',{}).get('groups',[]) if theme['theme_id'] in g['theme_ids']]
        if causes:
            theme['discovery_common_causes']={
                'source_theme_sha256':sha256(_bytes(original)).hexdigest(),
                'original_theme_decision_at':original['decision_at'],
                'groups':causes,'interpretation_at':present.isoformat(),
                'interpretation_is_historical_record':False,'original_events_unchanged':True}
        outlooks=[c for c in view['theme_outlook']['candidates'] if theme['theme_id'] in c['theme_ids']]
        if outlooks:
            theme['discovery_theme_outlook']={
                'source_theme_sha256':sha256(_bytes(original)).hexdigest(),
                'original_theme_decision_at':original['decision_at'],
                'basis_available_at':max(c['basis_available_at'] for c in outlooks),
                'candidates':outlooks,'original_events_unchanged':True}
            theme['decision_at']=max(theme['decision_at'],theme['discovery_theme_outlook']['basis_available_at'])
    return build_theme_bundle(result,decision_at=at,now=present)
