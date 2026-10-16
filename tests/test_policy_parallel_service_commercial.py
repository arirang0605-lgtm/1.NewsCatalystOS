"""Synthetic commercial pairs reuse the stored policy/source-span pipeline."""
from hashlib import sha256
import json
import pytest

from newscatalystos.economic_changes import extract_economic_changes, market_entry
from newscatalystos.theme_emergence import validate_change, _bytes
from newscatalystos.source_share import SourceShareError
from newscatalystos.common_cause_comparison import common_cause_comparisons
from test_adjacent_demand_scope import observe
from test_policy_parallel_service_investment import case
from test_policy_service_comparison import service
from test_cross_product_demand import view
from test_cross_product_period import END, LATER
from test_policy_parallel_service_operations import (
    text, sources,
    test_ambiguous_scopes_do_not_inherit_actual_pair,
    test_bad_operation_proof_is_rejected_without_rewriting_history,
    test_period_reprint_and_export_retain_two_actions_and_old_pit,
    test_http_search_and_export_share_stored_pair,
    test_prior_service_plan_does_not_count_as_new_service_when_pair_starts,
    test_comparison_renderers_show_source_pair_without_certifying_benefits,
)


@pytest.fixture(params=[('DELIVERY_START','납품 개시'),
                        ('CUSTOMER_ACQUISITION','신규 고객 확보'),
                        ('MARKET_ENTRY','「차량용 검사」 시장 진출')])
def operation(request):
    return request.param


@pytest.mark.parametrize('reverse', [False, True])
def test_named_service_commercial_pair_reaches_two_product_candidates(tmp_path, operation, reverse):
    articles = sources(operation, reverse=reverse)
    for article in articles:
        rows = extract_economic_changes(article)
        assert {r['action'] for r in rows} == {'BUSINESS_START', operation[0]}
        assert extract_economic_changes(article, include_policy_parallel=False) == []
        for row in rows:
            validate_change(row)
            proof = row['policy_parallel_action']
            assert proof['source_expression'] == article
            assert proof['expression_sha256'] == sha256(article.encode()).hexdigest()
            assert article[slice(*proof['action_span'])] == proof['action_expression']
            assert article[slice(*proof['cause_span'])] == row['policy_cause']['source_expression']
            assert row['phase'] == 'SOURCE_REPORTED'
            if row['action'] == 'MARKET_ENTRY':
                assert row['market_entry']['market_name'] == '차량용 검사'
                assert row['market_entry']['source_expression'] == proof['action_expression']
                assert 'service_name' not in row
            elif row['action'] == 'BUSINESS_START':
                assert row['service_name'] in {'별빛검사','바다검사'} and 'market_entry' not in row
    _, themes, candidates, comparisons, _ = case(tmp_path, articles)
    group, = view(themes, candidates, comparisons)['groups']
    assert group['distinct_action_groups'] == 4 and group['source_actor_name_count'] == 2
    assert len(candidates) == 2 and group['identified_company_count'] == 0
    assert all(t['scores']['company_breadth'] == 1 for t in themes)
    assert not group['verified_real_transaction'] and not group['verified_real_benefit']
    assert view(themes,candidates,comparisons,query='별빛검사')['groups']
    assert view(themes,candidates,comparisons,query='무관회사')['groups'] == []


@pytest.mark.parametrize('operation', [('DELIVERY_START','달빛전자에 납품 개시'),
                                      ('CUSTOMER_ACQUISITION','달빛전자를 신규 고객으로 확보')])
def test_named_customer_is_object_not_second_actor(tmp_path, operation):
    rows = extract_economic_changes(text(operation))
    assert {r['action'] for r in rows} == {'BUSINESS_START', operation[0]}
    assert all(r['entity_ids'] == ['가상전자'] for r in rows)
    _, themes, candidates, comparisons, _ = case(tmp_path, sources(operation))
    group, = view(themes,candidates,comparisons)['groups']
    assert group['source_actor_name_count'] == 2 and len(candidates) == 2
    assert all(s['impact_paths']==[] for p in group['products'] for a in p['actions'] for s in a['sources'])
    # Source text is searchable without creating a candidate for the customer.
    matched, = view(themes,candidates,comparisons,query='달빛전자')['groups']
    assert matched['source_actor_name_count'] == 2
    assert all(c['entity_id'] != '달빛전자' for c in candidates)


def test_disabled_action_and_first_service_identity_preserve_old_readers(operation):
    flag = {'DELIVERY_START':'include_delivery_start','CUSTOMER_ACQUISITION':'include_new_customers','MARKET_ENTRY':'include_market_entry'}[operation[0]]
    assert extract_economic_changes(text(operation), **{flag:False}) == []
    assert extract_economic_changes(text(operation), include_parallel_actions=False) == []
    rows = extract_economic_changes(text(operation))
    assert [r['action'] for r in extract_economic_changes(text(operation), include_policy_services=False)] == [operation[0]]
    start = next(r for r in rows if r['action']=='BUSINESS_START')
    single, = extract_economic_changes(service())
    assert observe(start,0)['event_id'] == observe(single,0)['event_id']
    assert 'service_event_key' not in start


def test_valid_other_market_cannot_be_borrowed_by_shared_action(tmp_path):
    operation = ('MARKET_ENTRY','「차량용 검사」 시장 진출')
    rows = extract_economic_changes(text(operation))
    entry = next(r for r in rows if r['action']=='MARKET_ENTRY')
    entry['market_entry'] = market_entry('「항공 검사」 시장 진출')
    with pytest.raises(SourceShareError): validate_change(entry)
    _, themes, candidates, _, _ = case(tmp_path,sources(operation))
    target = themes[0]
    next(r for r in target['source_refs'] if r['action']=='MARKET_ENTRY')['market_entry'] = entry['market_entry']
    for candidate in candidates:
        if candidate['theme_id'] == target['theme_id']:
            candidate['theme_snapshot_sha256'] = sha256(_bytes(target)).hexdigest()
    assert view(themes,candidates,common_cause_comparisons(themes,candidates))['groups'] == []


def test_future_shared_action_does_not_add_product(tmp_path, operation):
    _, themes, candidates, _, _ = case(tmp_path,sources(operation))
    target = themes[0]
    for ref in target['source_refs']: ref['source_available_at'] = LATER.isoformat()
    for candidate in candidates:
        if candidate['theme_id'] == target['theme_id']:
            candidate['theme_snapshot_sha256'] = sha256(_bytes(target)).hexdigest()
    assert view(themes,candidates,common_cause_comparisons(themes,candidates))['groups'] == []


def test_feed_roundtrip_preserves_spans_and_rejects_other_source(tmp_path, operation):
    from test_feed_analysis import setup, run as analyze
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    report = analyze(setup(tmp_path,text(operation)))
    row = next(r for r in report['results'] if r['economic_changes'])
    assert len(row['economic_changes']) == 2
    path,pin = publish_feed_analysis(report,tmp_path/'reports')
    assert consume_feed_analysis(path,path.parent,pin)['results'] == report['results']
    other = extract_economic_changes(text(operation,name='다른검사'))
    for change in other:
        change['evidence_level']='REPORTED'; change['source_paragraph_sha256']=row['source_title_sha256']
    row['economic_changes'] = other
    with pytest.raises(SourceShareError):
        path,pin = publish_feed_analysis(report,tmp_path/'bad')
        consume_feed_analysis(path,path.parent,pin)
