"""Period comparisons must separate discovery time, execution and company evidence."""
from copy import deepcopy
from datetime import datetime,timezone
import pytest
from newscatalystos.recent_theme_followups import compare_followup_periods
from newscatalystos.era_daily_assessment import enrich_followup_assessments

AT=datetime(2026,10,18,tzinfo=timezone.utc)
def row(url,day,kind='REPORTED_CONTRACT',revision='a',**context):
    return {'source_company':'가상기업','note_id':revision,'analysis_fingerprint':revision,
        'note':{'recent_source':{'source_url':url},'reported_date':day,'evidence_kind':kind},
        'execution_context':context}
def outlook(rows):
    return {'candidates':[{'outlook_id':'group','source_company_names':['가상기업','자료없는기업'],
        'recent_news_comparison':{'notes':rows}}]}
def compare(rows,previous=()):
    current=outlook(rows);compare_followup_periods(current,outlook(previous),AT)
    return current['candidates'][0]['recent_news_comparison']['period_comparison']['company_results']

def test_old_discovered_now_and_undated_delivery_are_not_recent_demand_growth():
    result,missing=compare([row('old','2026-04-29'),row('undated',None,'REPORTED_DELIVERY')])
    assert result['status']=='HISTORICAL_READING_ADDED'
    assert result['execution_status']=='NO_NEW_EXECUTION_PROOF'
    assert result['later_publication_note_ids']==[]
    assert not result['market_demand_growth_verified']
    assert missing['status']=='NO_SUBSTANTIVE_CHANGE'

@pytest.mark.parametrize('kind,status',[
    ('REPORTED_CONTRACT','SUPPORT_ADDED'),('CANCELLATION','WEAKENING_EVIDENCE'),
    ('CONDITIONAL_FRAMEWORK','CONDITIONAL_SUPPORT_ONLY'),('PLAN_ONLY','NON_DIRECTIONAL_READING_ADDED')])
def test_dated_claim_kind_and_same_day_boundary(kind,status):
    assert compare([row('new','2026-10-19',kind)])[0]['status']==status
    assert compare([row('same-day','2026-10-18',kind)])[0]['status']=='HISTORICAL_READING_ADDED'

def test_revision_not_another_order_and_positive_negative_normal_paths():
    old=row('same','2026-10-19')
    revised=row('same','2026-10-19',revision='b',reported_execution_setback=True)
    result=compare([revised],[old])[0]
    assert result['status']=='READING_REVISED' and result['added_note_ids']==[]
    assert result['revised_note_ids']==['b'] and result['execution_status']=='SOURCE_REPORTED_SETBACK'
    result=compare([row('order','2026-10-19',reported_execution_progress=True),
                    row('cancel','2026-10-19','CANCELLATION',revision='c',reported_execution_setback=True)])[0]
    assert result['status']=='MIXED_EVIDENCE' and result['execution_status']=='MIXED_EXECUTION_EVIDENCE'
    assert compare([old],[old])[0]['status']=='NO_SUBSTANTIVE_CHANGE'
    assert compare([],[old])[0]['status']=='NO_SUBSTANTIVE_CHANGE' # revoked/missing != cancellation

def assessment(revenue=1000,price=100):
    return {'status':'AVAILABLE','source_sha256':'pin','entity_id':'DART_CORP:00164779',
        'value':{'dart_annual_cfs':{'fiscal_year':2025,'revenue_krw':revenue},
                 'krx_completed_close':{'close_krw':price}}}
@pytest.mark.parametrize('prior,current,status',[
    (assessment(),assessment(price=200),'UNCHANGED_ASSESSMENT'),
    (assessment(),assessment(revenue=1200),'ASSESSMENT_EVIDENCE_CHANGED'),
    ({'status':'NOT_AVAILABLE_AS_OF'},assessment(),'NEWLY_AVAILABLE_ASSESSMENT'),
    (assessment(),{'status':'COMPANY_NOT_IN_SNAPSHOT'},'ASSESSMENT_UNAVAILABLE')])
def test_completed_evaluation_change_is_not_an_inferred_rating(monkeypatch,prior,current,status):
    calls=[]
    def read(root,*,as_of,now):
        calls.append(as_of);return (('current' if as_of>AT else 'previous'),0)
    monkeypatch.setattr('newscatalystos.era_daily_assessment.read_latest',read)
    monkeypatch.setattr('newscatalystos.era_daily_assessment.assessment_for',
        lambda company,snapshot:deepcopy(current if snapshot=='current' else prior))
    view=outlook([row('news','2026-10-19')])
    enrich_followup_assessments(view,'unused',since=AT,
        as_of=datetime(2026,10,19,tzinfo=timezone.utc),now=datetime(2026,10,19,tzinfo=timezone.utc))
    results=view['candidates'][0]['recent_news_comparison']['company_assessment_comparison']
    assert len(calls)==2
    for item in results['company_results']:
        assert item['status']==status and not item['news_changes_financial_rating']
        assert item['investment_merit']=='NOT_ASSESSED'

def test_date_only_publication_does_not_cross_same_korean_day(monkeypatch):
    import newscatalystos.recent_theme_followups as followups
    current=outlook([row('korea','2026-10-19')])
    start=datetime(2026,10,18,18,30,tzinfo=timezone.utc) # Oct19 03:30 KST
    followups.compare_followup_periods(current,outlook([]),start)
    result=current['candidates'][0]['recent_news_comparison']['period_comparison']['company_results'][0]
    assert result['status']=='HISTORICAL_READING_ADDED'
    assert result['later_publication_note_ids']==[]

def test_financial_receipt_failure_does_not_hide_news_comparison(monkeypatch):
    from newscatalystos.source_share import SourceShareError
    def fail(*args,**kwargs):raise SourceShareError('unreadable financial cache')
    monkeypatch.setattr('newscatalystos.era_daily_assessment.read_latest',fail)
    view=outlook([row('news','2026-10-19')])
    enrich_followup_assessments(view,'unused',since=AT,as_of=AT,now=AT)
    comparison=view['candidates'][0]['recent_news_comparison']
    assert len(comparison['notes'])==1
    assert comparison['company_assessment_comparison']['skipped_receipts']==2
    assert all(r['status']=='ASSESSMENT_UNAVAILABLE' for r in comparison['company_assessment_comparison']['company_results'])

def test_receipt_revision_is_not_new_finance_and_risk_delta_is_visible(monkeypatch):
    prior=assessment();current=assessment()
    prior['value']['dart_annual_cfs']['first_receipt_sha256']='old-receipt'
    current['value']['dart_annual_cfs']['first_receipt_sha256']='new-receipt'
    current['source_sha256']='new-publication'
    records={'previous':prior,'current':current}
    monkeypatch.setattr('newscatalystos.era_daily_assessment.read_latest',
        lambda root,as_of,now:(('current' if as_of>AT else 'previous'),0))
    monkeypatch.setattr('newscatalystos.era_daily_assessment.assessment_for',
        lambda company,snapshot:deepcopy(records[snapshot]))
    def result():
        view=outlook([row('news','2026-10-19')])
        enrich_followup_assessments(view,'unused',since=AT,as_of=datetime(2026,10,19,tzinfo=timezone.utc),now=datetime(2026,10,19,tzinfo=timezone.utc))
        return view['candidates'][0]['recent_news_comparison']['company_assessment_comparison']['company_results'][0]
    assert result()['status']=='UNCHANGED_ASSESSMENT'
    current['value']['dart_annual_cfs']['revenue_krw']=1200
    prior['value']['evidence_brief']={'supporting_evidence':[{'reason':'이전 긍정'}]}
    current['value']['evidence_brief']={'supporting_evidence':[{'reason':'새 긍정'}],'weakening_evidence':[{'reason':'새 위험'}]}
    diff=result()
    assert diff['status']=='ASSESSMENT_EVIDENCE_CHANGED'
    assert diff['observation_changes']['metrics']==[{'field':'revenue_krw','previous':1000,'current':1200}]
    assert diff['observation_changes']['support_added']==['새 긍정']
    assert diff['observation_changes']['support_removed']==['이전 긍정']
    assert diff['observation_changes']['risk_added']==['새 위험']
    assert not diff['news_changes_financial_rating']
