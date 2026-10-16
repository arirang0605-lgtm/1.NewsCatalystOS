"""Service starts alongside production/signing; synthetic reports, not realized benefits."""
from copy import deepcopy
from hashlib import sha256
import json
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from newscatalystos.economic_changes import extract_economic_changes, policy_parallel_actions
from newscatalystos.theme_emergence import validate_change, _bytes
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.comparison_export import query_comparison_export, read_comparison_export
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand_scope import observe
from test_policy_parallel_service_investment import case, text as investment_text
from test_cross_product_demand import view
from test_cross_product_period import run, T, END, LATER


@pytest.fixture(params=[('PRODUCTION_START', '생산 개시'), ('CONTRACT', '공급계약 체결')])
def operation(request):
    return request.param


def text(operation, **kwargs):
    return investment_text(**kwargs).replace('신규 공장 투자 집행', operation[1])


def sources(operation, **kwargs):
    return [text(operation, **kwargs), text(operation, product='DRAM', actor='새빛소재', name='바다검사', **kwargs)]


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('destination', ['', '중국'])
def test_literal_pair_keeps_legacy_id_company_count_and_source_spans(tmp_path, operation, reverse, destination):
    articles = sources(operation, reverse=reverse, destination=destination)
    for article in articles:
        rows = extract_economic_changes(article)
        assert {r['action'] for r in rows} == {'BUSINESS_START', operation[0]}
        old, = extract_economic_changes(article, include_policy_parallel=False)
        actual = next(r for r in rows if r['action'] == operation[0])
        assert observe(old, 0)['event_id'] == observe(actual, 0)['event_id']
        assert 'policy_parallel_action' not in old and 'policy_contract_action' not in old
        for row in rows:
            validate_change(row)
            proof = row['policy_parallel_action']
            assert proof['source_expression'] == article
            assert proof['expression_sha256'] == sha256(article.encode()).hexdigest()
            assert article[slice(*proof['action_span'])] == proof['action_expression']
            assert article[slice(*proof['cause_span'])] == row['policy_cause']['source_expression']
        if operation[0] == 'CONTRACT':
            assert actual['policy_contract_action'] == actual['policy_parallel_action']
    store, themes, candidates, comparisons, _ = case(tmp_path, articles)
    group, = view(themes, candidates, comparisons)['groups']
    assert group['distinct_action_groups'] == 4
    assert group['source_actor_name_count'] == 2 and len(candidates) == 2
    assert group['identified_company_count'] == 0
    assert not group['verified_real_transaction'] and not group['verified_real_benefit']
    assert all(t['scores']['company_breadth'] == 1 for t in themes)
    assert all(s['impact_paths'] == [] for p in group['products'] for a in p['actions'] for s in a['sources'])
    assert len(view(themes, candidates, comparisons, query='별빛검사')['groups']) == 1
    assert view(themes, candidates, comparisons, query='무관회사')['groups'] == []


@pytest.mark.parametrize('variant', ['계획', '목표', '결정', '의향', '취소', '전망', 'past', 'actor', 'pronoun', 'product', 'policy', 'duplicate', 'unnamed', 'anticipatory'])
def test_ambiguous_scopes_do_not_inherit_actual_pair(operation, variant):
    article = text(operation)
    if variant == 'past': article = article.replace('「별빛검사」', '지난해 「별빛검사」')
    elif variant == 'actor': article = article.replace('및 ', '및 새빛소재는 ')
    elif variant == 'pronoun': article = article.replace('및 ', '및 그 회사는 ')
    elif variant == 'product': article = article.replace('및 ', '및 DRAM ')
    elif variant == 'policy': article = article.replace('및 ', '및 일본 ‘별도통제법’ HBM 생산 규제 완화로 ')
    elif variant == 'duplicate': article += ' 및 '+operation[1]
    elif variant == 'unnamed': article = article.replace('「별빛검사」', '검사')
    elif variant == 'anticipatory': article = article.replace('완화로', '완화에 대비해')
    else: article += ' ' + variant
    assert policy_parallel_actions(article) is None
    assert not any('policy_parallel_action' in r for r in extract_economic_changes(article))


@pytest.mark.parametrize('fault', ['span', 'sha', 'actor', 'action'])
def test_bad_operation_proof_is_rejected_without_rewriting_history(tmp_path, operation, fault):
    _, themes, candidates, _, _ = case(tmp_path, sources(operation))
    target = themes[0]
    ref = next(r for r in target['source_refs'] if r['action'] == operation[0])
    proof = ref['policy_parallel_action']
    if fault == 'span': proof['action_span'] = [0, 3]
    elif fault == 'sha': proof['expression_sha256'] = 'f' * 64
    elif fault == 'actor': proof['actors'] = ['무관전자']
    else: proof['action'] = 'BUSINESS_START'
    for candidate in candidates:
        if candidate['theme_id'] == target['theme_id']:
            candidate['theme_snapshot_sha256'] = sha256(_bytes(target)).hexdigest()
    comparisons = common_cause_comparisons(themes, candidates)
    assert view(themes, candidates, comparisons)['groups'] == []


def test_period_reprint_and_export_retain_two_actions_and_old_pit(tmp_path, operation):
    store, themes, candidates, comparisons, observations = case(tmp_path, sources(operation))
    old = build_theme_bundle(themes, decision_at=END, now=END, include_company_candidates=True)
    group, = run(store)[0]['groups']
    assert group['period_change']['formed_in_period']
    assert len(group['period_change']['new_action_group_ids']) == 2
    reprint = deepcopy(observations[0]); reprint['source_url'] = 'https://example.org/reprint'
    store.ingest([reprint], now=LATER)
    assert run(store, since=LATER, as_of=LATER, activity='all')[0]['groups'][0]['period_change']['new_action_group_ids'] == []
    assert build_theme_bundle(store.search(as_of=END, now=LATER), decision_at=END, now=LATER, include_company_candidates=True) == old
    raw = query_comparison_export(store, as_of=END, since=END, activity='changed', now=END)
    assert read_comparison_export(raw, sha256(raw).hexdigest(), decision_at=END, now=END)['comparison'] == run(store)[0]


@pytest.mark.parametrize('legacy', [False, True])
def test_feed_roundtrip_binds_original_title_and_keeps_legacy(tmp_path, operation, legacy):
    from test_feed_analysis import setup, run as analyze
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    report = analyze(setup(tmp_path, text(operation)))
    row = next(r for r in report['results'] if r['economic_changes'])
    if legacy:
        row['economic_changes'] = extract_economic_changes(row['headline'], include_policy_parallel=False)
        for change in row['economic_changes']: change['evidence_level'] = 'REPORTED'
    path, pin = publish_feed_analysis(report, tmp_path/'reports')
    assert consume_feed_analysis(path, path.parent, pin)['results'] == report['results']
    assert len(row['economic_changes']) == (1 if legacy else 2)
    if not legacy:
        other = extract_economic_changes(text(operation, actor='무관전자'))
        for change in other:
            change['evidence_level'] = 'REPORTED'
            change['source_paragraph_sha256'] = row['source_title_sha256']
        row['economic_changes'] = other
        with pytest.raises(SourceShareError):
            path, pin = publish_feed_analysis(report, tmp_path/'bad')
            consume_feed_analysis(path, path.parent, pin)


def test_http_search_and_export_share_stored_pair(tmp_path, operation):
    from scripts import open_research_dashboard as dashboard
    store, *_ = case(tmp_path, sources(operation))
    server = dashboard.DashboardServer(0, tmp_path/'reports', tmp_path/'notes', tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    def fetch(route, **query):
        with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(query)) as response:
            return response.read()
    try:
        result = json.loads(fetch('/api/company-research', q='가상전자', as_of=END.isoformat(), since=END.isoformat(), activity='all'))
        group, = result['cross_product_demand']['groups']
        assert group['distinct_action_groups'] == 4
        pin = result['comparison_export']
        raw = fetch('/api/comparison-export', **{k:v for k,v in pin['query'].items() if v is not None})
        assert sha256(raw).hexdigest() == pin['sha256']
        assert read_comparison_export(raw, pin['sha256'], decision_at=END, now=END)['comparison'] == result['cross_product_demand']
        assert text(operation) in json.dumps(result, ensure_ascii=False)
    finally:
        server.shutdown(); server.server_close(); thread.join(2)


def test_prior_service_plan_does_not_count_as_new_service_when_pair_starts(tmp_path, operation):
    from newscatalystos.theme_emergence import ThemeStore
    from test_policy_service_comparison import service
    from test_recovery_investment_comparison import observed_at
    store = ThemeStore(tmp_path/'theme_history')
    specs = [('HBM', '가상전자', '별빛검사'), ('DRAM', '새빛소재', '바다검사')]
    plans = [observe(extract_economic_changes(service(p,a,n,ending='개시 계획'))[0], i) for i,(p,a,n) in enumerate(specs)]
    store.ingest(plans, now=T)
    starts = [observed_at(c, i+2, END) for i,s in enumerate(sources(operation)) for c in extract_economic_changes(s)]
    store.ingest(starts, now=END)
    group, = run(store, activity='all')[0]['groups']
    change = group['period_change']
    assert group['distinct_action_groups'] == 4
    assert len(change['new_action_group_ids']) == 2
    assert len(change['service_stage_contexts']) == 2
    assert all(c['kind']=='STORED_SERVICE_FOLLOWUP' and not c['stored_followup']['is_realization_confirmed'] for c in change['service_stage_contexts'])


def test_comparison_renderers_show_source_pair_without_certifying_benefits(tmp_path, operation):
    import subprocess
    store, themes, candidates, comparisons, _ = case(tmp_path, sources(operation))
    data = {'cross_product_demand':view(themes,candidates,comparisons), 'theme':themes[0],
            'CompanyCandidates':candidates, 'common_cause_comparisons':comparisons}
    code = '''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(){this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:()=>new Element()},parent=new Element();
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCrossProductDemand(parent,input.cross_product_demand);renderCommonCauseComparison(parent,input.theme,input.CompanyCandidates,input.common_cause_comparisons);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
    rendered = subprocess.check_output(['node','-e',code], input=json.dumps(data).encode()).decode()
    assert '같은 원인·당사자의 병렬 행동' in rendered
    assert operation[1] in rendered and '별빛검사' in rendered
    assert text(operation) in rendered
