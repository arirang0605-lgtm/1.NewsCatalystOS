"""Project shipment must not become a named supplier's final delivery."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,subprocess
import pytest
from test_execution_evidence import fixture
from newscatalystos.recent_theme_followups import (SCHEMA_V4,SCHEMA_V3,publish_followups,
    read_followups,metadata_resolver,assess,compare_followup_periods)
from newscatalystos.execution_evidence import summarize_execution
from newscatalystos.discovery_watch import export_discovery,read_discovery
from newscatalystos.source_share import SourceShareError


def shipment(doc,scope='PROJECT_ONLY'):
    data=deepcopy(doc);data['schema']=SCHEMA_V4;data['notes']=data['notes'][:1];n=data['notes'][0]
    n.update(evidence_kind='REPORTED_SHIPMENT',market_codes=['EU'],reported_date=datetime.now(timezone.utc).date().isoformat(),
        analysis_text='합성: 같은 프로젝트의 변전소 상부구조물 출항을 EPC 수행사가 보도했다.',
        limitation='합성: 공급사별 장비 납품·대금·최종 인수와 현장 가동은 미확인이다.')
    n['execution'].update(evidence_stage='SHIPMENT_COMPLETED',period_end=None,counter_reference=None,
        project_relation='SAME_PROJECT_EXPLICIT',execution_scope=scope,
        matching_basis='합성: 앞선 EPC 발표와 프로젝트·발주처·변전소 범위가 같고 공급사의 역할은 앞선 별도 원문에만 명시된다.')
    return data


def test_project_shipment_positive_path_period_export_and_replay(tmp_path,monkeypatch):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch);before=datetime.now(timezone.utc)
    saved=export_discovery(root,as_of=before,now=before,include_common_causes=True,recent_workspaces=(ws,))
    data=shipment(doc);resolve=metadata_resolver((ws,),now=datetime.now(timezone.utc))
    assert publish_followups(root,data,bases,resolve)['created']==1
    assert publish_followups(root,data,bases,resolve)['created']==0
    now=datetime.now(timezone.utc)
    rows=read_followups(root,bases,resolve,as_of=now,now=now);row,=[r for r in rows if r['schema']==SCHEMA_V4]
    x=row['execution_context'];assert x['reported_project_execution_progress']
    assert not x['reported_execution_progress'] and not x['reported_execution_setback']
    assert not x['shipment_is_final_delivery'] and not x['shipment_is_grid_operation']
    result=summarize_execution(rows,[r['source_company'] for r in rows])
    assert result['status']=='SOURCE_REPORTED_PROJECT_PROGRESS'
    assert not result['aggregate_results_imply_specific_contract_delivery']
    current=read_discovery(root,as_of=now,now=now,include_common_causes=True,recent_workspaces=(ws,))['theme_outlook']
    previous=read_discovery(root,as_of=before,now=now,include_common_causes=True,recent_workspaces=(ws,))['theme_outlook']
    compare_followup_periods(current,previous,before)
    g=next(g for g in current['candidates'] if g.get('recent_news_comparison'))
    changed=next(r for r in g['recent_news_comparison']['period_comparison']['company_results'] if r['source_company']==row['source_company'])
    assert changed['execution_status']=='SOURCE_REPORTED_PROJECT_PROGRESS'
    assert changed['status']=='SUPPORT_ADDED' or changed['status']=='HISTORICAL_READING_ADDED'
    assert export_discovery(root,as_of=before,now=now,include_common_causes=True,recent_workspaces=(ws,))==saved
    assert SCHEMA_V4 in export_discovery(root,as_of=now,now=now,include_common_causes=True,recent_workspaces=(ws,)).decode()


@pytest.mark.parametrize('change',[
    {'project_relation':'RELATED_BUSINESS_ONLY'},
    {'reported_date':None},
    {'reported_date':'2000-01-01'}])
def test_unmatched_or_undated_shipment_is_not_project_progress(tmp_path,monkeypatch,change):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch);data=shipment(doc);n=data['notes'][0]
    for k,v in change.items():
        if k=='project_relation':n['execution'][k]=v
        else:n[k]=v
    now=datetime.now(timezone.utc);resolve=metadata_resolver((ws,),now=now)
    publish_followups(root,data,bases,resolve,now=now)
    rows=read_followups(root,bases,resolve,as_of=now,now=now);row,=[r for r in rows if r['schema']==SCHEMA_V4]
    assert not row['execution_context']['reported_project_execution_progress']
    assert not row['execution_context']['reported_execution_progress']


@pytest.mark.parametrize('change',[
    {'scope':'UNVERIFIED'}, {'schema':SCHEMA_V3}, {'missing_scope':True},
    {'stage':'DELIVERY_COMPLETED'}, {'extra':True}])
def test_scope_version_and_claim_mismatch_do_not_publish(tmp_path,monkeypatch,change):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch);data=shipment(doc);n=data['notes'][0]
    if 'scope' in change:n['execution']['execution_scope']=change['scope']
    if 'schema' in change:data['schema']=change['schema']
    if 'missing_scope' in change:n['execution'].pop('execution_scope')
    if 'stage' in change:n['execution']['evidence_stage']=change['stage'];n['evidence_kind']='REPORTED_DELIVERY'
    if 'extra' in change:n['execution']['supplier_delivery_verified']=True
    with pytest.raises(SourceShareError):publish_followups(root,data,bases,metadata_resolver((ws,),now=datetime.now(timezone.utc)))
    assert not any(json.loads(p.read_text())['schema']==SCHEMA_V4 for p in (root/'analysis_notes/recent_followups').glob('*.json'))


def test_explicit_company_shipment_keeps_final_delivery_unconfirmed(tmp_path,monkeypatch):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch);data=shipment(doc,'NAMED_COMPANY');now=datetime.now(timezone.utc)
    resolve=metadata_resolver((ws,),now=now);publish_followups(root,data,bases,resolve,now=now)
    row,=[r for r in read_followups(root,bases,resolve,as_of=now,now=now) if r['schema']==SCHEMA_V4]
    assert row['execution_context']['reported_execution_progress']
    assert not row['execution_context']['reported_project_execution_progress']
    assert not row['execution_context']['shipment_is_final_delivery']
    assert '최종 납품 미확인' in summarize_execution([row],[row['source_company']])['company_results'][0]['status_label']


def test_project_shipment_ui_states_scope_and_links(tmp_path,monkeypatch):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch);now=datetime.now(timezone.utc)
    resolve=metadata_resolver((ws,),now=now);publish_followups(root,shipment(doc),bases,resolve,now=now)
    rows=read_followups(root,bases,resolve,as_of=now,now=now);row,=[r for r in rows if r['schema']==SCHEMA_V4]
    data=assess([row],[row['source_company']]);data['execution_comparison']=summarize_execution([row],[row['source_company']])
    code=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8'),data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,text){return {textContent:text||'',children:[],append(...x){this.children.push(...x)},addEventListener(){}}}
const p=node('div'),ctx={node};vm.runInNewContext(s.slice(s.indexOf('function renderRecentThemeComparison('),s.indexOf('function renderPublicDemandNotes(')),ctx);
ctx.renderRecentThemeComparison(p,data);function all(n){return [n,...n.children.flatMap(all)]}
const text=all(p).map(n=>n.textContent).join(' ');
for(const x of ['출하·출항 보도 · 최종 납품과 구분','관련 프로젝트 출하 진전 · 기업별 납품 미확인','개별 장비 납품·최종 인수·계통 가동은 미확인'])assert(text.includes(x),x);
assert(!text.includes('undefined'));assert(all(p).some(n=>n.href===data.notes[0].execution_context.anchor_source_url));
"""
    subprocess.run(['node','-e',code],input=json.dumps(data),text=True,capture_output=True,check=True,cwd=Path(__file__).resolve().parent.parent)


def test_project_shipment_and_separate_company_setback_are_both_retained(tmp_path,monkeypatch):
    root,_,_,ws,bases,_,doc,_=fixture(tmp_path,monkeypatch);data=shipment(doc)
    cancel=deepcopy(doc['notes'][1]);cancel.update(evidence_kind='CANCELLATION',reported_date=datetime.now(timezone.utc).date().isoformat())
    cancel['execution'].update(evidence_stage='CANCELLATION',project_relation='SAME_PROJECT_EXPLICIT',period_end=None,counter_reference=None)
    data['notes'].append(cancel);now=datetime.now(timezone.utc);resolve=metadata_resolver((ws,),now=now)
    publish_followups(root,data,bases,resolve,now=now)
    rows=read_followups(root,bases,resolve,as_of=now,now=now)
    result=summarize_execution(rows,[r['source_company'] for r in rows])
    assert result['status']=='MIXED_EXECUTION_EVIDENCE'
    assert {r['status'] for r in result['company_results']} >= {'SOURCE_REPORTED_PROJECT_PROGRESS','SOURCE_REPORTED_SETBACK'}
    assert not result['aggregate_results_imply_specific_contract_delivery']
