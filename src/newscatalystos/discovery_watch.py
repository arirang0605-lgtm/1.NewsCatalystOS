"""Stored event-first observations and their emerging subject/industry watchlist.

Reuse completed RSS analyses and ThemeStore. The watchlist is not a declaration
of verified sector supply-chain coverage, company benefit, or market novelty.
"""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

from .theme_emergence import ThemeStore
from .catalyst_material import materials_for_store,default_since,attach_material
from .research_dashboard import scan_saved_analysis
from .standard_delivery import build_theme_bundle
from .source_share import SourceShareError,_when


def read_discovery(root,*,as_of=None,since=None,now=None):
    present=now or datetime.now(timezone.utc);at=as_of or present
    start=since or default_since(at)
    present=_when(present.isoformat(),'now');at=_when(at.isoformat(),'as of');start=_when(start.isoformat(),'since')
    if start>at or at>present:raise SourceShareError('invalid discovery interval')
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root:raise SourceShareError('unsafe discovery root')
    if not root.exists():
        return {'status':'NOT_STARTED','candidates':[],'counts':{'events':0,'unclassified_topics':0},'observed_industries':[]}
    themes=ThemeStore(root/'theme_history').search(as_of=at,now=present)
    materials=materials_for_store(ThemeStore(root/'theme_history'),since=start,as_of=at,scope='discovery',now=present,industry='ALL_DISCOVERED')
    parents=sorted(p for p in (root/'feed_analysis').glob('d_*') if p.is_dir() and not p.is_symlink())
    reports,coverage=scan_saved_analysis(root/'no_default_reports',as_of=at,now=present,
        additional_roots=tuple((p.name,p) for p in parents))
    titles={(r['provider'],r['source_event_sha256'],r['source_title_sha256']):r
            for r in reports if r.get('analysis_industry')=='ECONOMIC_DISCOVERY'}
    candidates=[]
    for theme in themes:
        matched=[];seen=set();links=[]
        for ref in theme['source_refs']:
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
        candidates.append({'theme_id':theme['theme_id'],'watch_topic':theme['topic_aliases'][0],
            'status':'OBSERVATION_CANDIDATE','industry_tags':theme['industry_tags'],
            'industry_status':'SOURCE_WORD_HINTS' if theme['industry_tags'] else 'UNCLASSIFIED_OBSERVATION',
            'industry_links':links,'source_companies':theme['entity_ids'],
            'company_status':'SOURCE_NAME_ONLY' if theme['entity_ids'] else 'COMPANY_UNSPECIFIED',
            'economic_actions':sorted({r['action'] for r in theme['source_refs'] if r['polarity']=='SUPPORT'}),
            'event_ids':theme['event_ids'],'source_version_count':len(matched),
            'distinct_event_count':theme['scores']['distinct_economic_events'],
            'first_observed_at':theme['first_detected_at'],'last_changed_at':theme['decision_at'],
            'source_evidence':matched,'material':materials.get(theme['theme_id']),
            'deep_industry_validation':False,'market_newness':'UNKNOWN','orders_enabled':False})
    candidates.sort(key=lambda r:(r['last_changed_at'],r['theme_id']),reverse=True)
    return {'schema':'newscatalyst.economic_discovery_watch.v1','status':'READY','as_of':at.isoformat(),
        'comparison_since':start.isoformat(),'candidates':candidates,
        'counts':{'topics':len(candidates),'events':sum(c['distinct_event_count'] for c in candidates),
                  'unclassified_topics':sum(not c['industry_tags'] for c in candidates),
                  'observed_company_names':len({e for c in candidates for e in c['source_companies']}),
                  'analysis_title_versions':len(reports)},
        'observed_industries':sorted({v for c in candidates for v in c['industry_tags']}),
        'source_coverage':coverage,'industry_module_required_for_detection':False,
        'scope_limit':'REGISTERED_SOURCES_STORED_TITLES_COMMON_ACTION_GRAMMAR_NOT_ALL_NEWS',
        'note':'업종명·기업·발행시각 미확인은 관측만 보존하며 심층검증·시장신규 재료를 인증하지 않음',
        'investment_rank':None,'orders_enabled':False}


def export_discovery(root,*,as_of=None,since=None,now=None):
    present=now or datetime.now(timezone.utc);at=as_of or present;start=since or default_since(at)
    store=ThemeStore(Path(root)/'theme_history')
    themes=store.search(as_of=at,now=present)
    materials=materials_for_store(store,since=start,as_of=at,now=present,scope='discovery',industry='ALL_DISCOVERED')
    return build_theme_bundle(attach_material(themes,materials),decision_at=at,now=present)
