from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.standard_delivery import build_theme_bundle, read_theme_bundle
from newscatalystos.source_share import SourceShareError

T=datetime(2026,10,15,1,tzinfo=timezone.utc)


def event(number=1, *, topic='액침냉각', industry='SEMICONDUCTOR', company=None, polarity='SUPPORT', target=None):
    change={'topic':topic,'economic_driver':'DEMAND_EXPANSION','action':'CONTRACT',
            'phase':'SOURCE_REPORTED','entity_ids':[company or f'가상기업{number}'],
            'industry_tags':[industry],'source_paragraph_sha256':sha256(str(number).encode()).hexdigest(),
            'evidence_level':'OFFICIAL_SOURCE','verified_economic_effect':False}
    return economic_observation(change,origin_reference=f'https://example.org/official/{number}',
        source_url=f'https://example.org/official/{number}',source_id=f'issuer-{number}',
        source_available_at=T.isoformat(),polarity=polarity,supersedes_event_id=target)


def test_one_official_event_and_a_hundred_reprints_count_once(tmp_path):
    store=ThemeStore(tmp_path/'themes');original=event()
    copies=[original]
    for n in range(100):
        row=deepcopy(original);row['source_url']=f'https://press.example/news/{n}';row['source_id']=f'press-{n}'
        copies.append(row)
    row=store.ingest(copies,now=T)[0]
    assert row['status']=='CANDIDATE' and row['scores']['distinct_economic_events']==1
    assert row['scores']['distinct_claim_origins']==1 and len(row['source_refs'])==101
    assert store.ingest(copies,now=T+timedelta(hours=1))==[]
    assert store.search(as_of=T,now=T)==[row]


def test_distinct_companies_form_theme_without_future_entities_or_name(tmp_path):
    store=ThemeStore(tmp_path/'themes')
    first=store.ingest([event(1)],now=T)[0]
    later=store.ingest([event(2),event(3)],now=T+timedelta(hours=1))[0]
    assert later['status']=='EMERGING' and len(later['event_ids'])==3
    assert store.search(as_of=T,now=T+timedelta(hours=2))==[first]
    assert not store.search(as_of=T,query='가상기업3',now=T+timedelta(hours=2))
    assert store.search(query='가상기업3',now=T+timedelta(hours=2))[0]['theme_id']==first['theme_id']
    expanded=store.ingest([event(4,industry='DATA_CENTER')],now=T+timedelta(hours=2))[0]
    assert expanded['status']=='EXPANDING'
    assert all(x['relation_kind']=='THEMATIC_ONLY' and x['revenue_contribution'] is None for x in expanded['company_links'])
    assert expanded['verified_beneficiary_count']==0


def test_unrelated_topic_or_driver_does_not_merge_and_novel_topic_is_supported(tmp_path):
    rows=[event(1),event(2,topic='HBM'),event(3,topic='신규광자냉각')]
    store=ThemeStore(tmp_path/'themes');result=store.ingest(rows,now=T)
    assert len(result)==3
    row=event(4);row['change']['economic_driver']='POLICY_ENABLEMENT'
    row=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'change','event_id'}})
    store.ingest([row],now=T+timedelta(hours=1))
    assert len(store.search(now=T+timedelta(hours=1)))==4


def test_conflict_correction_reactivation_and_no_news_never_invalidates(tmp_path):
    store=ThemeStore(tmp_path/'themes');original=event(1)
    first=store.ingest([original],now=T)[0]
    assert store.search(now=T+timedelta(days=100))[0]['status']=='CANDIDATE'
    contradiction=event(2,polarity='CONTRADICT',target=original['event_id'])
    assert store.ingest([contradiction],now=T+timedelta(hours=1))[0]['status']=='WEAKENING'
    # Separate theme store for official correction + later independent support.
    store=ThemeStore(tmp_path/'corrected');store.ingest([original],now=T)
    correction=event(2,polarity='RETRACT',target=original['event_id'])
    assert store.ingest([correction],now=T+timedelta(hours=1))[0]['status']=='INVALIDATED'
    assert store.ingest([event(3)],now=T+timedelta(hours=2))[0]['status']=='REACTIVATED'
    assert store.search(as_of=T,now=T+timedelta(hours=2))[0]['status']==first['status']


def test_future_unknown_correction_and_false_direct_benefit_rejected(tmp_path):
    store=ThemeStore(tmp_path/'themes')
    future=event();future['source_available_at']=(T+timedelta(days=1)).isoformat()
    with pytest.raises(SourceShareError,match='future'):store.ingest([future],now=T)
    bad=event(2,polarity='RETRACT',target='f'*64)
    with pytest.raises(SourceShareError,match='target'):store.ingest([bad],now=T)
    assert store.search(now=T)==[]
    themes=store.ingest([event()],now=T)
    themes[0]['company_links'][0]['relation_kind']='VERIFIED_DIRECT_TRANSACTION'
    with pytest.raises(SourceShareError,match='direct'):build_theme_bundle(themes,decision_at=T,now=T)


def test_versioned_delivery_pin_and_future_component(tmp_path):
    themes=ThemeStore(tmp_path/'themes').ingest([event()],now=T)
    raw=build_theme_bundle(themes,decision_at=T,now=T)
    assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=T,now=T)['ThemeCandidates']==themes
    with pytest.raises(SourceShareError):read_theme_bundle(raw,'0'*64,decision_at=T,now=T)
    with pytest.raises(SourceShareError):read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=T-timedelta(seconds=1),now=T)
    themes[0]['source_refs'][0]['recorded_at']=(T+timedelta(days=1)).isoformat()
    with pytest.raises(SourceShareError,match='future'):build_theme_bundle(themes,decision_at=T,now=T)


def test_policy_without_money_is_detected_but_awards_and_price_news_are_not():
    # Synthetic wording models the real 172284 omission without copying its body.
    policy='반도체 지원 전담 조직을 신설하는 직제 개정안이 국무회의에서 의결되었으며 다음 달 시행될 예정이다.'
    changes=extract_economic_changes(policy)
    assert changes[0]['action']=='POLICY_CHANGE'
    assert changes[0]['phase']=='ADOPTED_NOT_YET_EFFECTIVE'
    for text in ['반도체 설계대전 시상식이 개최되었다.','HBM 가격이 상승했다. 생산능력 확대는 검토 중이다.',
                 'HBM 공급 계약은 체결되지 않았다.','지난해 반도체 공장 생산을 시작했다.']:
        assert extract_economic_changes(text)==[]
    assert extract_economic_changes('가상전자는 HBM 양산을 시작했다.')[0]['action']=='PRODUCTION_START'
    assert extract_economic_changes('가상소재는 「신규광자냉각」 수요 증가에 대응하여 공급 계약을 체결했다.')[0]['topic']=='신규광자냉각'


def test_document_to_theme_to_search_http_and_readonly_export(tmp_path):
    from argparse import Namespace
    from pathlib import Path
    import threading
    from urllib.request import urlopen
    from scripts.run_motir_document_analysis import evaluate
    from scripts.search_news import _with_saved_analysis
    from scripts.search_themes import main as export
    from scripts.open_research_dashboard import DashboardServer
    from test_motir_document_analysis import case
    _,args=case(tmp_path/'source', body=('반도체 전담 조직 신설에 관한 직제 개정안이 국무회의에서 의결되었다. ' * 3))
    # case() supplies a typed registry; write only its synthetic registry file.
    from newscatalystos.motir_document_collection import _registry_bytes
    registry_path=tmp_path/'registry.json'
    registry_path.write_bytes(_registry_bytes(args['article_registry'].providers[0]))
    registry_path.chmod(0o600)
    documents=tmp_path/'documents'
    opts=Namespace(binding_path=args['binding_path'],binding_sha256=args['binding_sha256'],
        archive_root=args['archive_root'],article_registry=registry_path,
        analysis_root=documents/args['binding_sha256'],model_config=None,ai_ledger=None,
        allow_paid=False,analyze_existing=False)
    code,result=evaluate(opts)
    assert code==0 and result['economic_changes']==1 and result['theme_versions_created']==1
    assert result['ai_status']=='AI_DISABLED_BY_CONFIGURATION'
    root=documents/'theme_history'
    assert len(_with_saved_analysis({},Namespace(theme_root=root,query='반도체'))['theme_candidates'])==1
    assert export(['--root',str(root),'--query','반도체','--export-root',str(tmp_path/'exports')])==0
    path=next((tmp_path/'exports').glob('theme_delivery_*.json'))
    raw=path.read_bytes()
    assert len(read_theme_bundle(raw,path.stem.removeprefix('theme_delivery_'),decision_at=datetime.now(timezone.utc))['ThemeCandidates'])==1
    server=DashboardServer(0,tmp_path/'empty',tmp_path/'notes',documents)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}'
        with urlopen(url+'/api/themes') as response:
            assert len(json.load(response)['ThemeCandidates'])==1
        day=datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul')).date().isoformat()
        with urlopen(url+'/api/period?view=day&date='+day) as response:
            result=json.load(response)
        assert len(result['themes'])==1
        assert result['items'][0]['economic_changes'][0]['action']=='POLICY_CHANGE'
        # Theme storage failure must not blank the existing news dashboard.
        (root/'themes.sqlite3').write_bytes(b'broken test database')
        with urlopen(url+'/api/period?view=day&date='+day) as response:
            result=json.load(response)
        assert result['theme_status']=='UNAVAILABLE' and result['items']
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_unknown_cause_never_groups_different_business_actions(tmp_path):
    store=ThemeStore(tmp_path/'themes');rows=[]
    for n in [1,2,3]:
        row=event(n);row['change']['economic_driver']='UNKNOWN'
        rows.append(economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'change','event_id'}}))
    assert len(store.ingest(rows,now=T))==3
    assert all(r['status']=='CANDIDATE' for r in store.search(now=T))


def test_dictionary_aliases_and_new_topic_provisional_name_preserved(tmp_path):
    store=ThemeStore(tmp_path/'themes')
    initial=store.ingest([event(1,topic='고대역폭 메모리')],now=T)[0]
    later=store.ingest([event(2,topic='HBM')],now=T+timedelta(hours=1))[0]
    assert initial['theme_id']==later['theme_id']
    assert initial['provisional_name']==later['provisional_name']
    assert later['topic_classification']=='KNOWN_TOPIC'
    assert store.ingest([event(3,topic='신규광자냉각')],now=T+timedelta(hours=2))[0]['topic_classification']=='PROVISIONAL_TOPIC'


def test_same_article_policy_screen_routes_through_existing_ai_cache(tmp_path,monkeypatch):
    from test_motir_document_analysis import case
    from newscatalystos.motir_document_analysis import analyze_motir_document
    from test_ai_gemini_transport import LocalOpener,packet
    monkeypatch.setenv('GEMINI_API_KEY','synthetic-gemini-key-only-for-offline-tests')
    _,args=case(tmp_path,body='반도체 공장 인허가 규제를 완화하기 위한 법안이 국회에서 통과되었다. '*3)
    opener=LocalOpener(packet())
    first=analyze_motir_document(**args,allow_paid=True,opener=opener)
    second=analyze_motir_document(**args,allow_paid=True,opener=opener)
    assert first['ai_eligible'] and first['new_ai_results']==1
    assert second['ai_status']=='CACHE_HIT' and opener.calls==1
    assert not first['verified_new_economic_event']


def test_normalized_saved_events_cli_is_pinned_and_idempotent(tmp_path):
    from scripts.run_theme_discovery import main
    packet={'schema':'newscatalyst.economic_observations.v1','observations':[event(1),event(2),event(3)]}
    path=tmp_path/'events.json';raw=json.dumps(packet).encode();path.write_bytes(raw);path.chmod(0o600)
    root=tmp_path/'themes'
    args=['--events-file',str(path),'--expected-sha256',sha256(raw).hexdigest(),'--root',str(root)]
    assert main(args)==0 and main(args)==0
    assert ThemeStore(root).search()[0]['status']=='EMERGING'
    assert len(ThemeStore(root).search()[0]['history'])==1
    with pytest.raises(SourceShareError,match='SHA'):
        main(['--events-file',str(path),'--expected-sha256','0'*64,'--root',str(root)])


@pytest.mark.parametrize('topic',['광인터커넥트','광인터커넥트의','「광인터커넥트」'])
def test_unlisted_unquoted_demand_subject_is_detected(topic):
    changes=extract_economic_changes(f'가상전자는 {topic} 수요 확대에 대응해 공급 계약을 체결했다.')
    assert len(changes)==1
    assert changes[0]['topic']=='광인터커넥트'
    assert changes[0]['economic_driver']=='DEMAND_EXPANSION'


def test_demand_subject_wins_over_incidental_product_and_stays_in_its_sentence():
    text='HBM 업체인 가상소재는 액침 냉각 수요 증가에 따라 공급 계약을 체결했다.'
    change=extract_economic_changes(text)[0]
    assert change['topic']=='액침냉각' and change['economic_driver']=='DEMAND_EXPANSION'
    separate='가상전자는 HBM 수요 확대에 대응해 생산능력 확대를 검토 중이다. 다른소재는 액침냉각 공급 계약을 체결했다.'
    rows=extract_economic_changes(separate)
    assert len(rows)==1 and rows[0]['topic']=='액침냉각'
    assert rows[0]['entity_ids']==['다른소재'] and rows[0]['economic_driver']=='UNKNOWN'
    assert rows[0]['source_paragraph_sha256']==sha256(separate.encode()).hexdigest()


@pytest.mark.parametrize('text',[
    '가상전자는 광인터커넥트 수요 확대에 대응해 공급 계약을 검토 중이다.',
    '가상전자는 광인터커넥트 수요 확대를 기대했다.',
    '가상전자는 시장 수요 확대에 대응해 공급 계약을 체결했다.',
    '가상전자는 AI 수요 확대에 대응해 공급 계약을 체결했다.',
    '가상전자는 광인터커넥트 및 양자냉각 수요 확대에 대응해 공급 계약을 체결했다.',
])
def test_broad_or_unresolved_demand_never_creates_specific_theme(text):
    assert extract_economic_changes(text)==[]


def test_raw_articles_find_one_new_theme_and_deliver_company_reasons(tmp_path):
    """Synthetic articles, no prelabelled event JSON, no external calls."""
    from scripts.open_research_dashboard import DashboardServer
    from urllib.request import urlopen
    import threading
    articles=[
        '가상전자는 광인터커넥트 수요 확대에 대응해 공급 계약을 체결했다.',
        '새빛소재는 광인터커넥트의 수요 증가에 따라 생산을 시작했다.',
        '미래장비는 「광인터커넥트」 수요 급증에 대응하여 생산능력을 확대했다.',
    ]
    docs=tmp_path/'documents';store=ThemeStore(docs/'theme_history')
    def observation(text,n):
        change=extract_economic_changes(text)[0]
        return economic_observation(change,origin_reference=f'https://example.org/release/{n}',
            source_url=f'https://example.org/release/{n}',source_id='synthetic-source',
            source_available_at=T.isoformat())
    originals=[observation(text,n) for n,text in enumerate(articles)]
    first=store.ingest(originals[:1],now=T)[0]
    later=store.ingest(originals[1:],now=T+timedelta(seconds=1))[0]
    assert first['status']=='CANDIDATE' and later['status']=='EMERGING'
    assert later['topic_classification']=='PROVISIONAL_TOPIC'
    assert later['scores']['distinct_economic_events']==3
    assert later['scores']['distinct_claim_origins']==3
    assert set(later['entity_ids'])=={'가상전자','새빛소재','미래장비'}
    assert {r['action'] for r in later['source_refs']}=={'CONTRACT','PRODUCTION_START','CAPACITY_ADDITION'}
    assert all(r['topic']=='광인터커넥트' and r['economic_driver']=='DEMAND_EXPANSION' for r in later['source_refs'])
    assert store.search(as_of=T,now=T+timedelta(seconds=2))==[first]
    assert not store.search(as_of=T,query='미래장비',now=T+timedelta(seconds=2))
    assert store.ingest(originals*10,now=T+timedelta(seconds=2))==[]
    unrelated=observation('별빛전자는 양자냉각 수요 확대에 대응해 공급 계약을 체결했다.',4)
    store.ingest([unrelated],now=T+timedelta(seconds=3))
    assert len(store.search(now=T+timedelta(seconds=3)))==2
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/themes?q='+__import__('urllib.parse',fromlist=['quote']).quote('광인터커넥트')) as response:
            raw=response.read()
        bundle=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=datetime.now(timezone.utc))
        assert len(bundle['ThemeCandidates'])==1
        shown=bundle['ThemeCandidates'][0]
        assert shown['entity_ids']==later['entity_ids']
        assert shown['source_refs']==later['source_refs']
        assert shown['verified_beneficiary_count']==0
    finally:server.shutdown();server.server_close();thread.join(2)


def test_source_defined_lithography_terms_group_without_merging_euv_and_duv(tmp_path):
    store=ThemeStore(tmp_path/'themes');rows=[]
    for number,term in enumerate(['극자외선','EUV','심자외선','DUV']):
        change=extract_economic_changes(f'가상전자는 {term} 수요 증가에 대응해 공급 계약을 체결했다.')[0]
        rows.append(economic_observation(change,origin_reference=f'https://example.org/{number}',
            source_url=f'https://example.org/{number}',source_id='synthetic',source_available_at=T.isoformat()))
    result=store.ingest(rows,now=T)
    assert len(result)==2 and all(len(r['event_ids'])==2 for r in result)
    assert {r['provisional_name'] for r in result}=={'EUV · 수요 확대','DUV · 수요 확대'}
    assert all(r['parent_theme_id']=='taxonomy:semiconductor' for r in result)
    assert store.search(query='극자외선',now=T)==store.search(query='EUV',now=T)
    assert store.search(query='심자외선',now=T)==store.search(query='DUV',now=T)
    assert '극자외선' in store.search(query='EUV',now=T)[0]['topic_aliases']


def test_filing_names_enrich_same_event_without_adding_an_event(tmp_path):
    text='별빛공업은 HBM 수요 확대에 대응해 공급 계약을 체결했다. 다른회사도 행사에 참석했다.'
    old=extract_economic_changes(text)[0]
    new=extract_economic_changes(text,company_names=['별빛공업','다른회사'])[0]
    assert old['entity_ids']==[] and new['entity_ids']==['별빛공업']
    assert new['original_entity_ids']==[]
    args=dict(origin_reference='https://example.org/1',source_url='https://example.org/1',
              source_id='synthetic',source_available_at=T.isoformat())
    first=economic_observation(old,**args);second=economic_observation(new,**args)
    assert first['event_id']==second['event_id']
    store=ThemeStore(tmp_path/'themes');before=store.ingest([first],now=T)[0]
    after=store.ingest([second],now=T+timedelta(seconds=1))[0]
    assert after['scores']['distinct_economic_events']==1 and after['entity_ids']==['별빛공업']
    assert store.search(as_of=T,now=T+timedelta(seconds=1))==[before]
    assert extract_economic_changes('별빛공업서비스는 HBM 공급 계약을 체결했다.',company_names=['별빛공업'])[0]['entity_ids']==[]


def test_unpriced_early_investment_reaches_theme_without_ai_call(tmp_path):
    from pathlib import Path
    from scripts.run_motir_document_analysis import evaluate
    from test_article_company_identity import opts_for
    from test_motir_document_analysis import case
    from newscatalystos.motir_document_collection import _registry_bytes
    _,args=case(tmp_path/'source',body='새빛소재는 EUV 수요 확대에 대응해 신규 공장 투자를 결정했다. '*3)
    registry=tmp_path/'registry.json'
    registry.write_bytes(_registry_bytes(args['article_registry'].providers[0]));registry.chmod(0o600)
    root=tmp_path/'documents'
    code,result=evaluate(opts_for(args,root,registry))
    assert code==0 and result['economic_changes']==1 and result['theme_versions_created']==1
    assert result['ai_status']=='NOT_ELIGIBLE' and result['new_ai_results']==0
    theme=ThemeStore(root/'theme_history').search(query='극자외선')[0]
    assert theme['entity_ids']==['새빛소재'] and theme['status']=='CANDIDATE'
    assert theme['verified_beneficiary_count']==0
    assert not list(root.rglob('ai_costs.sqlite3'))


def test_period_new_updated_and_unchanged_use_selected_snapshot(tmp_path):
    store=ThemeStore(tmp_path/'themes')
    first=store.ingest([event(1,topic='EUV'),event(2,topic='HBM')],now=T)
    start=T+timedelta(hours=1)
    store.ingest([event(3,topic='EUV'),event(4,topic='DUV')],now=start)
    later=T+timedelta(hours=2)
    assert len(store.search(as_of=later,since=start,activity='changed',now=later))==2
    assert store.search(as_of=later,since=start,activity='new',now=later)[0]['provisional_name'].startswith('DUV')
    assert store.search(as_of=later,since=start,activity='updated',now=later)[0]['provisional_name'].startswith('EUV')
    assert len(store.search(as_of=later,since=start,activity='all',now=later))==3
    assert store.search(as_of=T,since=T,activity='updated',now=later)==[]
    assert len(store.search(as_of=T,since=T,activity='new',now=later))==2
    assert store.search(as_of=T,query='가상기업3',now=later)==[]
    assert store.ingest([event(3,topic='EUV'),event(4,topic='DUV')],now=later)==[]
    assert store.search(as_of=later,since=later,activity='changed',now=later)==[]
    assert store.search(as_of=later,since=start,activity='updated',query='극자외선',now=later)
    for kwargs in ({'activity':'new'},{'activity':'bad'},{'since':later,'as_of':T}):
        with pytest.raises(SourceShareError):store.search(now=later,**kwargs)


def test_period_api_and_cli_filter_themes_without_rewriting_history(tmp_path):
    from scripts.open_research_dashboard import DashboardServer
    from scripts.search_themes import main
    from urllib.request import urlopen
    from urllib.parse import urlencode
    import threading
    root=tmp_path/'documents';store=ThemeStore(root/'theme_history')
    yesterday=T-timedelta(days=1)
    old1=event(1,topic='EUV');old2=event(2,topic='HBM')
    old1['source_available_at']=old2['source_available_at']=yesterday.isoformat()
    store.ingest([old1,old2],now=yesterday)
    store.ingest([event(3,topic='EUV'),event(4,topic='DUV')],now=T)
    before=(root/'theme_history/themes.sqlite3').read_bytes()
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',root)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        for mode,count in [('all',3),('changed',2),('new',1),('updated',1)]:
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/period?view=day&date=2026-10-15&theme_activity='+mode) as response:
                data=json.load(response)
            assert len(data['themes'])==count and data['theme_status']=='READY'
            if mode=='new':assert set(data['theme_activity'].values())=={'new'}
            if mode=='updated':assert set(data['theme_activity'].values())=={'updated'}
        query=urlencode({'since':T.isoformat(),'activity':'updated','q':'극자외선'})
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/themes?'+query) as response:
            assert len(json.load(response)['ThemeCandidates'])==1
        # A future selected day has no new/updated candidates; other UI data remains valid.
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/period?view=day&date=2099-01-01&theme_activity=changed') as response:
            assert json.load(response)['themes']==[]
    finally:server.shutdown();server.server_close();thread.join(2)
    assert main(['--root',str(root/'theme_history'),'--since',T.isoformat(),
                 '--activity','updated','--query','극자외선','--export-root',str(tmp_path/'export')])==0
    assert (root/'theme_history/themes.sqlite3').read_bytes()==before
