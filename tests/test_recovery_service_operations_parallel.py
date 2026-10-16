"""Existing bounded production/investment/supply actions share a recovery service source."""
from copy import deepcopy
from hashlib import sha256
import pytest
from newscatalystos.economic_changes import extract_economic_changes, investment_project
from newscatalystos.theme_emergence import ThemeStore, validate_change, _bytes
from newscatalystos.source_share import SourceShareError
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export
from test_adjacent_demand_scope import observe
from test_recovery_investment_comparison import named,observed_at
from test_cross_product_demand import view
from test_cross_product_period import run,T,END
from test_recovery_service_commercial_parallel import (
    text,sources,case,
    test_literal_pair_stores_both_actions_without_extra_firm,
    test_unscoped_recovery_still_forms_same_product_theme,
    test_ambiguous_or_mixed_scopes_do_not_gain_shared_actuals,
    test_period_reprint_followup_and_old_pit,
    test_future_and_other_destination_do_not_form_shared_comparison,
    test_feed_roundtrip_and_raw_rebinding_or_stripping_rejected,
    test_http_three_views_and_fixed_json,
)


@pytest.fixture(params=[('PRODUCTION_START','생산 개시'),('CONTRACT','공급계약 체결'),
                        ('CAPACITY_ADDITION','생산능력 확대'),('INVESTMENT_EXECUTION','신규 공장 투자 집행'),
                        ('SUPPLY_RESUMPTION','공급 재개')])
def operation(request):return request.param


def test_first_service_identity_and_disabled_modes(operation):
    article=text(operation);rows=extract_economic_changes(article)
    start=next(r for r in rows if r['action']=='BUSINESS_START')
    single,=extract_economic_changes(article.split(' 및 ')[0])
    assert observe(start,0)['event_id']==observe(single,0)['event_id']
    assert 'service_event_key' not in start
    prior,=extract_economic_changes(article.split('「')[0]+operation[1])
    operation_row=next(r for r in rows if r['action']==operation[0])
    assert observe(prior,0)['event_id']==observe(operation_row,0)['event_id']
    flag={'INVESTMENT_EXECUTION':'include_investment_execution','SUPPLY_RESUMPTION':'include_resumption'}.get(operation[0])
    if flag:assert extract_economic_changes(article,**{flag:False})==[]
    if operation[0]=='INVESTMENT_EXECUTION':assert all('investment_project' not in r for r in rows)


@pytest.mark.parametrize('reverse',[False,True])
def test_explicit_project_is_bound_to_investment_slice_and_export(tmp_path,reverse):
    operation=('INVESTMENT_EXECUTION','「청해공장」 투자 집행')
    articles=sources(operation,reverse=reverse)
    for article in articles:
        rows=extract_economic_changes(article)
        start=next(r for r in rows if r['action']=='BUSINESS_START')
        execution=next(r for r in rows if r['action']=='INVESTMENT_EXECUTION')
        assert start['service_name'] in {'별빛검사','바다검사'} and 'investment_project' not in start
        assert execution['investment_project']['project_name']=='청해공장'
        assert execution['investment_project']['source_expression']==execution['recovery_parallel_action']['action_expression']
        assert 'investment_event_key' not in execution
        assert extract_economic_changes(article,include_investment_projects=False)==[]
        single=article.split(' 및 ')[1] if not reverse else article.split(' 및 ')[0]
        if not reverse:single=article.split('「')[0]+single
        row,=extract_economic_changes(single)
        assert observe(row,0)['event_id']==observe(execution,0)['event_id']
    store,themes,cs,comp,_=case(tmp_path,operation,articles)
    group,=view(themes,cs,comp)['groups']
    assert {s['investment_project']['project_name'] for p in group['products'] for a in p['actions'] for s in a['sources'] if s['action']=='INVESTMENT_EXECUTION'}=={'청해공장'}
    assert all('investment_project' in s for c in comp.values() for row in c['rows'] for s in row['sources'] if s['action']=='INVESTMENT_EXECUTION')
    raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
    assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['comparison']==run(store,activity='all')[0]


def test_service_brand_ending_in_factory_is_not_investment_target():
    article=text(('INVESTMENT_EXECUTION','신규 공장 투자 집행'),name='별빛공장')
    rows=extract_economic_changes(article)
    assert len(rows)==2 and all('investment_project' not in r for r in rows)
    assert next(r for r in rows if r['action']=='BUSINESS_START')['service_name']=='별빛공장'


@pytest.mark.parametrize('fault',['other_project','missing_project','wrong_key'])
def test_valid_other_project_or_key_cannot_replace_shared_evidence(tmp_path,fault):
    operation=('INVESTMENT_EXECUTION','「청해공장」 투자 집행')
    row=next(r for r in extract_economic_changes(text(operation)) if r['action']=='INVESTMENT_EXECUTION')
    if fault=='other_project':row['investment_project']=investment_project('「바다공장」 투자 집행','INVESTMENT_EXECUTION')
    elif fault=='missing_project':row.pop('investment_project')
    else:row['investment_event_key']='f'*64
    with pytest.raises(SourceShareError):validate_change(row)
    _,themes,cs,_,_=case(tmp_path,operation)
    target=next(t for t in themes if 'HBM' in t['topic_aliases'])
    ref=next(r for r in target['source_refs'] if r['action']=='INVESTMENT_EXECUTION')
    for key in ['investment_project','investment_event_key']:
        if key in row:ref[key]=deepcopy(row[key])
        else:ref.pop(key,None)
    for c in cs:
        if c['theme_id']==target['theme_id']:c['theme_snapshot_sha256']=sha256(_bytes(target)).hexdigest()
    assert view(themes,cs,common_cause_comparisons(themes,cs))['groups']==[]


def test_service_and_investment_stages_are_not_new_independent_actions(tmp_path):
    store=ThemeStore(tmp_path/'theme_history')
    specs=[('HBM','가상전자','별빛검사','청해공장'),('DRAM','새빛소재','바다검사','바다공장')]
    plans=[];actual=[]
    for i,(p,a,n,j) in enumerate(specs):
        article=text(('INVESTMENT_EXECUTION',f'「{j}」 투자 집행'),product=p,actor=a,name=n)
        service_plan=article.split(' 및 ')[0]+' 계획'
        for k,s in enumerate([service_plan,named(p,a,j,verb='결정')]):
            plans.extend(observe(c,i*2+k) for c in extract_economic_changes(s))
        actual.extend(observed_at(c,i+10,END) for c in extract_economic_changes(article))
    store.ingest(plans,now=T)
    old=build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
    store.ingest(actual,now=END)
    result,selected,_=run(store,activity='all');group,=result['groups'];change=group['period_change']
    assert group['distinct_action_groups']==4 and change['new_action_group_ids']==[]
    assert len(change['service_stage_contexts'])==len(change['investment_stage_contexts'])==2
    for c in change['service_stage_contexts']:
        assert not c['stored_followup']['is_realization_confirmed'] and len(c['sources'])==2
    for c in change['investment_stage_contexts']:
        link=c['stored_stage_link'];assert not link['is_execution_confirmed'] and len(link['sources'])==2
        assert {link['decision_event_id'],link['execution_event_id']}<={r['event_id'] for r in plans+actual}
    assert all(t['scores']['distinct_economic_events']==2 for t in selected)
    assert old==build_theme_bundle(store.search(as_of=T,now=END),decision_at=T,now=END,include_company_candidates=True)
    raw=query_comparison_export(store,as_of=END,since=END,activity='all',now=END)
    assert read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)['comparison']==result


def test_two_named_projects_services_in_one_article_keep_existing_selection_keys(tmp_path):
    first=text(('INVESTMENT_EXECUTION','「청해공장」 투자 집행'))
    second=text(('INVESTMENT_EXECUTION','「바다공장」 투자 집행'),name='바다검사')
    rows=extract_economic_changes(first+'\n'+second)
    assert len(rows)==4 and all(r['entity_ids']==['가상전자'] for r in rows)
    executions=[r for r in rows if r['action']=='INVESTMENT_EXECUTION']
    services=[r for r in rows if r['action']=='BUSINESS_START']
    assert 'investment_event_key' not in executions[0] and 'service_event_key' not in services[0]
    assert executions[1]['investment_event_key']==sha256('바다공장'.encode()).hexdigest()
    assert services[1]['service_event_key']==sha256('바다검사'.encode()).hexdigest()
    for row in rows:validate_change(row)
    store=ThemeStore(tmp_path/'theme_history');store.ingest([observe(c,0) for c in rows],now=END)
    theme,=store.search(now=END)
    assert theme['scores']['company_breadth']==1 and theme['scores']['distinct_economic_events']==4


def test_named_investment_http_keeps_project_in_three_views(tmp_path):
    test_http_three_views_and_fixed_json(tmp_path,('INVESTMENT_EXECUTION','「청해공장」 투자 집행'))
