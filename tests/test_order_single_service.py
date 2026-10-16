"""Synthetic single-service order claims retain source phases and stored followups."""
from copy import deepcopy
from hashlib import sha256
import json,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,order_service_actions,demand_scope,_ORDER_EXPANSION
from newscatalystos.theme_emergence import ThemeStore,validate_change,_bytes
from newscatalystos.source_share import SourceShareError
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import observed_at
from test_policy_parallel_service_investment import case as stored_case
from test_cross_product_demand import view
from test_cross_product_period import run,T,END,LATER


def text(product='HBM',actor='가상전자',name='별빛검사',scope='AI 서버',tail='',cause='주문 확대로',cause_first=False):
    prefix=f'{scope+"용 " if scope else ""}{product} {cause}'
    return (prefix+' '+actor+'는 ' if cause_first else actor+', '+prefix+' ')+f'「{name}」 서비스 개시'+tail


def sources(**kwargs):
    return [text(**kwargs),text(product='DRAM',actor='새빛소재',name='바다검사',**kwargs)]


@pytest.mark.parametrize('scope',['AI 서버',''])
@pytest.mark.parametrize('cause',['주문 확대로','주문 증가에 따라','주문이 급증해'])
@pytest.mark.parametrize('tail,phase',[('','SOURCE_REPORTED'),('했다','SOURCE_REPORTED'),(' 계획','PLANNED'),(' 목표','PLANNED'),('한다','PLANNED')])
def test_literal_phases_and_stored_sources(tmp_path,scope,cause,tail,phase):
    article=text(scope=scope,cause=cause,tail=tail)
    row,=extract_economic_changes(article);validate_change(row)
    assert row['phase']==phase and row['service_name']=='별빛검사' and row['entity_ids']==['가상전자']
    assert 'growth_parallel_action' not in row and 'service_event_key' not in row
    p=row['order_service_action'];assert p['phase']==phase
    assert p['source_expression']==article and p['expression_sha256']==sha256(article.encode()).hexdigest()
    assert article[slice(*p['action_span'])]==p['action_expression']==f'「별빛검사」 서비스 개시{tail}'
    assert article[slice(*p['cause_span'])]=='HBM '+cause
    assert extract_economic_changes(article,include_order_services=False)==[]
    assert extract_economic_changes(article,include_order_growth=False)==extract_economic_changes(article,include_order_growth=False,include_order_services=False)
    assert extract_economic_changes(article,include_demand_scopes=False)==[]
    _,themes,cs,comp,_=stored_case(tmp_path,sources(scope=scope,cause=cause,tail=tail))
    assert len(cs)==2 and all(t['scores']['company_breadth']==1 for t in themes)
    groups=view(themes,cs,comp)['groups']
    assert bool(groups)==bool(scope and phase=='SOURCE_REPORTED')
    if groups:
        assert groups[0]['distinct_action_groups']==2 and groups[0]['unresolved_company_contexts']==2
        assert not groups[0]['verified_real_transaction'] and not groups[0]['verified_real_benefit']
    assert all(s['service_name'] and s['order_service_action'] for c in comp.values() for r in c['rows'] for s in r['sources'])
    raw=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
    assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['CompanyCandidates']==cs


@pytest.mark.parametrize('cause_first',[False,True])
def test_explicit_actor_boundary_and_anticipation(cause_first):
    row,=extract_economic_changes(text(cause_first=cause_first,cause='주문 확대에 대비해'))
    assert row['phase']=='PLANNED' and row['entity_ids']==['가상전자']
    validate_change(row)


@pytest.mark.parametrize('variant',['의향','취소','부인','past','actor','pronoun','product','scope','ambiguous_scope','recovery','demand','third','unnamed','empty_actor'])
def test_no_inheritance_from_ambiguous_or_other_claims(variant):
    article=text()
    if variant=='past':article=article.replace('「별빛검사」','지난해 「별빛검사」')
    elif variant=='actor':article=article.replace('「별빛검사」','달빛전자는 「별빛검사」')
    elif variant=='pronoun':article=article.replace('「별빛검사」','그 회사는 「별빛검사」')
    elif variant=='product':article=article.replace('별빛검사','NAND 검사')
    elif variant=='scope':article=article.replace('별빛검사','스마트폰용 HBM 검사')
    elif variant=='ambiguous_scope':article=article.replace('AI 서버용','AI 서버 및 스마트폰용')
    elif variant=='recovery':article=article.replace('「별빛검사」','DRAM 수요 회복으로 「별빛검사」')
    elif variant=='demand':article=article.replace('「별빛검사」','DRAM 수요 증가로 「별빛검사」')
    elif variant=='third':article+=' 및 납품 개시 계획'
    elif variant=='unnamed':article=article.replace('「별빛검사」','검사')
    elif variant=='empty_actor':article=article.replace('가상전자, ','')
    else:article+=' '+variant
    assert order_service_actions(article) is None
    assert extract_economic_changes(article)==[]


@pytest.mark.parametrize('scope',['AI 서버',''])
def test_plan_start_followup_preserves_pit_and_counts_one_action(tmp_path,scope):
    store=ThemeStore(tmp_path/'theme_history')
    plans=[observe(c,i) for i,a in enumerate(sources(scope=scope,tail=' 계획')) for c in extract_economic_changes(a)]
    store.ingest(plans,now=T)
    old=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
    starts=[observed_at(c,i+2,END) for i,a in enumerate(sources(scope=scope)) for c in extract_economic_changes(a)]
    store.ingest(starts,now=END)
    themes=store.search(now=END)
    for theme in themes:
        assert theme['first_detected_at']==T.isoformat() and theme['scores']['distinct_economic_events']==1
        link,=theme['event_followups'];assert not link['is_realization_confirmed']
        assert len(link['evidence_sha256'])==2
    period,_,_=run(store,activity='all')
    if scope:
        group,=period['groups'];change=group['period_change']
        assert group['distinct_action_groups']==2 and change['new_action_group_ids']==[]
        assert len(change['service_stage_contexts'])==2
    else:assert period['groups']==[]
    old_again=build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
    assert old_again==old
    reprint=deepcopy(starts[0]);reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=LATER)
    if scope:assert run(store,since=LATER,as_of=LATER,activity='all')[0]['groups'][0]['period_change']['new_action_group_ids']==[]
    raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
    assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['comparison']==period


@pytest.mark.parametrize('fault',['span','sha','actor','service','scope','phase','driver','cause'])
def test_proof_tamper_is_rejected_before_storage_and_comparison(tmp_path,fault):
    row,=extract_economic_changes(text())
    if fault=='span':row['order_service_action']['action_span']=[True,3]
    elif fault=='sha':row['order_service_action']['expression_sha256']='f'*64
    elif fault=='actor':row['order_service_action']['actors']=['달빛전자']
    elif fault=='service':row['service_name']='다른검사'
    elif fault=='scope':
        other=text(scope='스마트폰');row['demand_scope']=demand_scope(other,_ORDER_EXPANSION.search(other))
    elif fault=='phase':row['phase']='PLANNED'
    elif fault=='driver':row['economic_driver']='DEMAND_RECOVERY'
    else:row['order_service_action']['cause_span']=[0,1]
    with pytest.raises(SourceShareError):validate_change(row)
    _,themes,cs,_,_=stored_case(tmp_path,sources())
    target=next(t for t in themes if 'HBM' in t['topic_aliases']);ref=target['source_refs'][0]
    for k in ['order_service_action','service_name','demand_scope','phase','economic_driver']:
        if k in row:ref[k]=deepcopy(row[k])
    for c in cs:
        if c['theme_id']==target['theme_id']:c['theme_snapshot_sha256']=sha256(_bytes(target)).hexdigest()
    assert view(themes,cs,common_cause_comparisons(themes,cs))['groups']==[]


@pytest.mark.parametrize('scope',['AI 서버',''])
@pytest.mark.parametrize('tail',['',' 계획'])
def test_feed_roundtrip_rebind_strip_and_phase_promotion(tmp_path,scope,tail):
    from test_feed_analysis import setup,run as analyze
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    report=analyze(setup(tmp_path,text(scope=scope,tail=tail)));row=report['results'][0]
    assert len(row['economic_changes'])==1
    path,pin=publish_feed_analysis(report,tmp_path/'reports')
    assert consume_feed_analysis(path,path.parent,pin)['results']==report['results']
    original=deepcopy(row['economic_changes'])
    for variant in ['strip','other_service','phase']:
        changes=deepcopy(original)
        if variant=='strip':changes[0].pop('order_service_action')
        elif variant=='other_service':changes=extract_economic_changes(text(scope=scope,tail=tail,name='다른검사'))
        else:changes[0]['phase']='PLANNED' if not tail else 'SOURCE_REPORTED'
        for c in changes:c.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
        row['economic_changes']=changes
        with pytest.raises(SourceShareError):
            p,h=publish_feed_analysis(report,tmp_path/variant);consume_feed_analysis(p,p.parent,h)


def test_sibling_services_keep_first_identity_and_deduplicate_repeats(tmp_path):
    a=text();b=text(name='바다검사')
    rows=extract_economic_changes(a+'\n'+b+'\n'+a)
    assert len(rows)==2 and 'service_event_key' not in rows[0]
    assert rows[1]['service_event_key']==sha256('바다검사'.encode()).hexdigest()
    assert observe(rows[0],0)['event_id']==observe(extract_economic_changes(a)[0],0)['event_id']
    store=ThemeStore(tmp_path/'theme_history');theme,=store.ingest([observe(r,0) for r in rows],now=T)
    assert theme['scores']['company_breadth']==1 and theme['scores']['distinct_economic_events']==2


@pytest.mark.parametrize('tail',['',' 계획'])
def test_http_three_views_preserve_phase_and_fixed_json(tmp_path,tail):
    from scripts import open_research_dashboard as dashboard
    store,*_=stored_case(tmp_path,sources(tail=tail))
    server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def fetch(route,**query):
        with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(query)) as r:return r.read()
    try:
        data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
        assert bool(data['cross_product_demand']['groups'])==(not bool(tail))
        pin=data['comparison_export'];raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
        assert sha256(raw).hexdigest()==pin['sha256']
        assert read_comparison_export(raw,pin['sha256'],decision_at=END,now=END)['comparison']==data['cross_product_demand']
        data['theme']=next(t for t in store.search(now=END) if t['theme_id']==data['CompanyCandidates'][0]['theme_id'])
        data['search']={c['candidate_id']:{'match_kind':'DIRECT_COMPANY'} for c in data['CompanyCandidates']}
        code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input.cross_product_demand);renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);renderCompanyTimelines(parent,input.company_timelines,"가상전자",input.search);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
        rendered=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
        assert rendered.count('주문 확대에 따른 서비스 '+('계획' if tail else '개시 보도'))==(2 if tail else 4)
        assert text(tail=tail) in rendered and '별빛검사' in rendered and '성장 원인 범위' in rendered
    finally:server.shutdown();server.server_close();thread.join(2)


def test_future_sources_and_different_scope_cannot_form_comparison(tmp_path):
    _,themes,cs,_,_=stored_case(tmp_path,sources())
    target=themes[0];target['source_refs'][0]['source_available_at']=LATER.isoformat()
    for c in cs:
        if c['theme_id']==target['theme_id']:c['theme_snapshot_sha256']=sha256(_bytes(target)).hexdigest()
    assert view(themes,cs,common_cause_comparisons(themes,cs))['groups']==[]
    _,themes,cs,comp,_=stored_case(tmp_path/'other',[text(),text(product='DRAM',actor='새빛소재',scope='스마트폰')])
    assert view(themes,cs,comp)['groups']==[]


def test_single_service_to_existing_parallel_path_keeps_id_and_first_detection(tmp_path):
    article=text();single,=extract_economic_changes(article)
    pair=extract_economic_changes(article+' 및 생산 개시')
    first=observe(single,0);later=[observe(r,0) for r in pair]
    assert first['event_id']==next(r['event_id'] for r in later if r['change']['action']=='BUSINESS_START')
    store=ThemeStore(tmp_path/'theme_history');prior,=store.ingest([first],now=T)
    old=build_theme_bundle([prior],decision_at=T,now=T,include_company_candidates=True)
    latest,=store.ingest(later,now=END)
    assert latest['first_detected_at']==prior['first_detected_at'] and latest['scores']['distinct_economic_events']==2
    assert old==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)


def test_pre_order_growth_unknown_service_report_remains_readable(tmp_path):
    from test_feed_analysis import setup,run as analyze
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    report=analyze(setup(tmp_path,text(scope='')));row=report['results'][0]
    row['economic_changes']=extract_economic_changes(row['headline'],include_order_growth=False,include_order_services=False)
    assert row['economic_changes'][0]['economic_driver']=='UNKNOWN'
    for c in row['economic_changes']:c.update(evidence_level='REPORTED',source_paragraph_sha256=row['source_title_sha256'])
    path,pin=publish_feed_analysis(report,tmp_path/'legacy')
    assert consume_feed_analysis(path,path.parent,pin)['results']==report['results']


def test_explicit_unknown_product_can_form_same_product_candidate(tmp_path):
    articles=[text(product='「광자 검사칩」',scope=''),text(product='「광자 검사칩」',scope='',actor='새빛소재',name='바다검사')]
    _,themes,cs,comp,_=stored_case(tmp_path,articles)
    theme,=themes
    assert theme['topic_classification']=='PROVISIONAL_TOPIC' and theme['scores']['distinct_economic_events']==2
    assert len(cs)==2 and all(s['cause']['status']=='STORED_EXPRESSION' for r in comp[theme['theme_id']]['rows'] for s in r['sources'])


@pytest.mark.parametrize('scope',['AI 서버',''])
@pytest.mark.parametrize('tail',['',' 계획'])
def test_existing_concrete_function_grammar_does_not_invent_brand(tmp_path,scope,tail):
    article=text(scope=scope,tail=tail).replace('「별빛검사」','HBM 검사')
    row,=extract_economic_changes(article);validate_change(row)
    assert row['phase']==('PLANNED' if tail else 'SOURCE_REPORTED')
    assert 'service_name' not in row and 'service_event_key' not in row
    assert row['order_service_action']['action_expression']=='HBM 검사 서비스 개시'+tail
    store=ThemeStore(tmp_path/'theme_history');theme,=store.ingest([observe(row,0)],now=T)
    assert not theme.get('event_followups')
    raw=build_theme_bundle([theme],decision_at=T,now=T,include_company_candidates=True)
    assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=T,now=T)['CompanyCandidates']
    changed=deepcopy(row);changed['service_name']='만든이름'
    with pytest.raises(SourceShareError):validate_change(changed)
