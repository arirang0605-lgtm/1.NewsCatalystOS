"""Synthetic recovery pairs preserve literal causes, scope, actor and source history."""
from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from newscatalystos.economic_changes import extract_economic_changes, recovery_parallel_actions, demand_scope, _DEMAND_RECOVERY, market_entry
from newscatalystos.theme_emergence import ThemeStore, validate_change, economic_observation, _bytes
from newscatalystos.source_share import SourceShareError
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.comparison_export import query_comparison_export, read_comparison_export
from test_adjacent_demand_scope import observe
from test_policy_parallel_service_investment import case as stored_case
from test_cross_product_demand import view
from test_cross_product_period import run, T, END, LATER
from test_recovery_investment_comparison import observed_at


@pytest.fixture(params=[('DELIVERY_START','납품 개시'), ('CUSTOMER_ACQUISITION','신규 고객 확보'), ('MARKET_ENTRY','「차량용 검사」 시장 진출')])
def operation(request): return request.param


def text(operation, product='HBM', actor='가상전자', name='별빛검사', scope='AI 서버', basis='수요', reverse=False):
    parts=[f'「{name}」 서비스 개시',operation[1]]
    if reverse: parts.reverse()
    return f'{actor}, {scope+"용 " if scope else ""}{product} {basis} 회복으로 '+ ' 및 '.join(parts)


def sources(operation, **kwargs):
    return [text(operation,**kwargs),text(operation,product='DRAM',actor='새빛소재',name='바다검사',basis='주문',**kwargs)]


def case(tmp_path, operation, articles=None): return stored_case(tmp_path, articles or sources(operation))


@pytest.mark.parametrize('reverse',[False,True])
def test_literal_pair_stores_both_actions_without_extra_firm(tmp_path, operation, reverse):
    articles=sources(operation,reverse=reverse)
    for article in articles:
        rows=extract_economic_changes(article)
        assert {r['action'] for r in rows}=={'BUSINESS_START',operation[0]}
        assert extract_economic_changes(article,include_recovery_parallel=False)==[]
        assert extract_economic_changes(article,include_parallel_actions=False)==[]
        for row in rows:
            validate_change(row); proof=row['recovery_parallel_action']
            assert 'policy_parallel_action' not in row and 'policy_cause' not in row
            assert proof['source_expression']==article and proof['expression_sha256']==sha256(article.encode()).hexdigest()
            assert article[slice(*proof['action_span'])]==proof['action_expression']
            assert article[slice(*proof['cause_span'])]==row['demand_recovery_cause']['source_expression']
            assert row['phase']=='SOURCE_REPORTED'
            if row['action']=='MARKET_ENTRY': assert row['market_entry']['market_name']=='차량용 검사'
            if row['action']=='BUSINESS_START': assert row['service_name'] in {'별빛검사','바다검사'}
    store,themes,cs,comp,_=case(tmp_path,operation,articles)
    old=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
    group,=view(themes,cs,comp)['groups']
    assert group['economic_driver']=='DEMAND_RECOVERY' and group['distinct_action_groups']==4
    assert group['unresolved_company_contexts']==2 and len(cs)==2 and group['identified_company_count']==0
    assert all(t['scores']['company_breadth']==1 for t in themes)
    assert not group['verified_real_transaction'] and not group['verified_real_benefit']
    assert all(s['recovery_parallel_action'] and s['impact_paths']==[] for p in group['products'] for a in p['actions'] for s in a['sources'])
    assert view(themes,cs,comp,query='별빛검사')['groups'] and not view(themes,cs,comp,query='무관회사')['groups']
    assert build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)==old


def test_unscoped_recovery_still_forms_same_product_theme(tmp_path,operation):
    articles=[text(operation,scope=''),text(operation,scope='',actor='새빛소재',name='바다검사')]
    _,themes,cs,comp,_=case(tmp_path,operation,articles)
    theme,=themes
    assert theme['scores']['distinct_economic_events']==4 and theme['scores']['company_breadth']==2
    assert len(cs)==2 and view(themes,cs,comp)['groups']==[]
    assert all('demand_scope' not in r for r in theme['source_refs'])


@pytest.mark.parametrize('variant',['계획','목표','결정','의향','취소','전망','past','actor','pronoun','product','growth','policy','second_recovery','third','scope','unnamed','anticipatory'])
def test_ambiguous_or_mixed_scopes_do_not_gain_shared_actuals(operation,variant):
    article=text(operation)
    if variant=='past': article=article.replace('「별빛검사」','지난해 「별빛검사」')
    elif variant=='actor': article=article.replace('및 ','및 달빛전자는 ')
    elif variant=='pronoun': article=article.replace('및 ','및 그 회사는 ')
    elif variant=='product': article=article.replace('및 ','및 NAND ')
    elif variant=='growth': article=article.replace('및 ','및 DRAM 수요 증가로 ')
    elif variant=='policy': article=article.replace('및 ','및 미국 ‘첨단칩통제법’ HBM 수출 규제 완화로 ')
    elif variant=='second_recovery': article=article.replace('및 ','및 스마트폰용 HBM 수요 회복으로 ')
    elif variant=='third': article+=' 및 생산 개시'
    elif variant=='scope': article=article.replace('AI 서버용','AI 서버 및 스마트폰용')
    elif variant=='unnamed': article=article.replace('「별빛검사」','검사')
    elif variant=='anticipatory': article=article.replace('회복으로','회복에 대비해')
    else: article+=' '+variant
    assert recovery_parallel_actions(article) is None
    assert not any('recovery_parallel_action' in r for r in extract_economic_changes(article))


@pytest.mark.parametrize('operation',[('DELIVERY_START','달빛전자에 납품 개시'),('CUSTOMER_ACQUISITION','달빛전자를 신규 고객으로 확보')])
def test_customer_object_remains_searchable_without_becoming_actor(tmp_path,operation):
    rows=extract_economic_changes(text(operation))
    assert len(rows)==2 and all(r['entity_ids']==['가상전자'] for r in rows)
    _,themes,cs,comp,_=case(tmp_path,operation)
    assert view(themes,cs,comp,query='달빛전자')['groups'][0]['unresolved_company_contexts']==2
    assert all(c['entity_id']!='달빛전자' for c in cs)


def test_other_end_use_market_is_not_borrowed():
    article=text(('MARKET_ENTRY','「스마트폰용 HBM」 시장 진출'))
    assert recovery_parallel_actions(article) is None
    assert extract_economic_changes(article)==[]


@pytest.mark.parametrize('fault',['span','sha','actor','scope','market','service'])
def test_valid_looking_but_mismatched_proof_rejected_locally(tmp_path,fault):
    operation=('MARKET_ENTRY','「차량용 검사」 시장 진출')
    rows=extract_economic_changes(text(operation)); row=next(r for r in rows if r['action']==('BUSINESS_START' if fault=='service' else 'MARKET_ENTRY'))
    if fault=='span': row['recovery_parallel_action']['action_span']=[0,3]
    elif fault=='sha': row['recovery_parallel_action']['expression_sha256']='f'*64
    elif fault=='actor': row['recovery_parallel_action']['actors']=['달빛전자']
    elif fault=='scope':
        other=text(operation,scope='스마트폰');row['demand_scope']=demand_scope(other,_DEMAND_RECOVERY.search(other))
    elif fault=='market': row['market_entry']=market_entry('「항공 검사」 시장 진출')
    else: row['service_name']='다른검사'
    with pytest.raises(SourceShareError): validate_change(row)
    _,themes,cs,_,_=case(tmp_path,operation)
    target=themes[0];ref=next(r for r in target['source_refs'] if r['action']==row['action'])
    # Use the same product's row so the selected mutation is the only mismatch.
    if target['topic_aliases']!=['HBM']:
        target=next(t for t in themes if 'HBM' in t['topic_aliases']);ref=next(r for r in target['source_refs'] if r['action']==row['action'])
    for k in ['recovery_parallel_action','demand_scope','market_entry','service_name']:
        if k in row: ref[k]=deepcopy(row[k])
    for c in cs:
        if c['theme_id']==target['theme_id']: c['theme_snapshot_sha256']=sha256(_bytes(target)).hexdigest()
    assert not view(themes,cs,common_cause_comparisons(themes,cs))['groups']


def test_period_reprint_followup_and_old_pit(tmp_path,operation):
    store=ThemeStore(tmp_path/'theme_history')
    articles=sources(operation)
    plans=[observe(extract_economic_changes(a.split(' 및 ')[0]+' 계획')[0],i) for i,a in enumerate(articles)]
    store.ingest(plans,now=T)
    old=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
    starts=[observed_at(c,i+2,END) for i,a in enumerate(articles) for c in extract_economic_changes(a)]
    store.ingest(starts,now=END)
    group,=run(store,activity='all')[0]['groups'];change=group['period_change']
    assert group['distinct_action_groups']==4 and len(change['new_action_group_ids'])==2
    assert len(change['service_stage_contexts'])==2
    assert all(not c['stored_followup']['is_realization_confirmed'] for c in change['service_stage_contexts'])
    reprint=deepcopy(starts[0]);reprint['source_url']='https://example.org/reprint';store.ingest([reprint],now=LATER)
    assert run(store,since=LATER,as_of=LATER,activity='all')[0]['groups'][0]['period_change']['new_action_group_ids']==[]
    assert old==build_theme_bundle(store.search(as_of=T,now=LATER),decision_at=T,now=LATER,include_company_candidates=True)
    raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
    assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['comparison']==run(store,activity='all')[0]


def test_future_and_other_destination_do_not_form_shared_comparison(tmp_path,operation):
    _,themes,cs,_,_=case(tmp_path,operation)
    target=themes[0]
    for ref in target['source_refs']: ref['source_available_at']=LATER.isoformat()
    for c in cs:
        if c['theme_id']==target['theme_id']: c['theme_snapshot_sha256']=sha256(_bytes(target)).hexdigest()
    assert not view(themes,cs,common_cause_comparisons(themes,cs))['groups']
    _,themes,cs,comp,_=case(tmp_path/'other',operation,[text(operation),text(operation,product='DRAM',actor='새빛소재',scope='스마트폰')])
    assert not view(themes,cs,comp)['groups']


def test_feed_roundtrip_and_raw_rebinding_or_stripping_rejected(tmp_path,operation):
    from test_feed_analysis import setup, run as analyze
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    report=analyze(setup(tmp_path,text(operation)))
    row=next(r for r in report['results'] if r['economic_changes']);assert len(row['economic_changes'])==2
    original=deepcopy(row['economic_changes'])
    path,pin=publish_feed_analysis(report,tmp_path/'reports')
    assert consume_feed_analysis(path,path.parent,pin)['results']==report['results']
    for stripped in [False,True]:
        other=deepcopy(original) if stripped else extract_economic_changes(text(operation,name='다른검사'))
        for c in other:
            c['evidence_level']='REPORTED';c['source_paragraph_sha256']=row['source_title_sha256']
            if stripped: c.pop('recovery_parallel_action')
        row['economic_changes']=other
        with pytest.raises(SourceShareError):
            path,pin=publish_feed_analysis(report,tmp_path/('stripped' if stripped else 'bad'))
            consume_feed_analysis(path,path.parent,pin)


def test_http_three_views_and_fixed_json(tmp_path,operation):
    from scripts import open_research_dashboard as dashboard
    store,*_=case(tmp_path,operation)
    server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def fetch(route,**query):
        with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(query)) as response:return response.read()
    try:
        data=json.loads(fetch('/api/company-research',q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='all'))
        assert data['cross_product_demand']['groups'][0]['distinct_action_groups']==4
        pin=data['comparison_export']; raw=fetch('/api/comparison-export',**{k:v for k,v in pin['query'].items() if v is not None})
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
        assert rendered.count('같은 원인·당사자의 병렬 행동')==8 and '회복 원인 범위' in rendered
        assert text(operation) in rendered and operation[1] in rendered and '별빛검사' in rendered
    finally:server.shutdown();server.server_close();thread.join(2)


def test_first_service_id_and_disabled_feature_modes(operation):
    article=text(operation)
    start=next(r for r in extract_economic_changes(article) if r['action']=='BUSINESS_START')
    single,=extract_economic_changes(article.split(' 및 ')[0])
    assert observe(start,0)['event_id']==observe(single,0)['event_id']
    assert 'service_event_key' not in start
    flag={'DELIVERY_START':'include_delivery_start','CUSTOMER_ACQUISITION':'include_new_customers','MARKET_ENTRY':'include_market_entry'}[operation[0]]
    assert extract_economic_changes(article,**{flag:False})==[]
    assert extract_economic_changes(article,include_demand_scopes=False)==[]
