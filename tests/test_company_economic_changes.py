"""Bound news -> company economics -> existing Era selector, no new events/scores."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import importlib, json, os, sys

import pytest

from newscatalystos.material_publication import publish_material, read_published
from newscatalystos.theme_emergence import ThemeStore, _bytes
from newscatalystos.recent_theme_followups import publish_followups, metadata_resolver
from test_recent_theme_followups import scenario
from test_theme_emergence import event, T
from test_federated_news_search import fingerprint


def setup_bridge(tmp_path, monkeypatch):
    root, _, _, workspace, baselines, document, _ = scenario(tmp_path,monkeypatch)
    now=datetime.now(timezone.utc)
    publish_followups(root,document,baselines,metadata_resolver((workspace,),now=now),now=now)
    rows=[]
    for name,code,issuer in [('가상전기','005930','00126380'),('가상배전','000660','00164779'),
                             ('가상중공업','000001','00000001')]:
        rows.append({'name':name,'security_id':code,'dart_annual_cfs':{
            'status':'DART_VERIFIED_ANNUAL_CFS','issuer_corp_code':issuer,'first_receipt_sha256':'a'*64}})
    snapshot=({'source_sha256':'b'*64,'imported_at':now.isoformat()},
              {'content_sha256':'e'*64,'candidates':rows,
               'source':{'evaluated_at_utc':now.isoformat(),'market_session':now.date().isoformat()}})
    monkeypatch.setattr('newscatalystos.material_publication.read_identity',lambda *a,**kw:(snapshot,0))
    legacy=ThemeStore(tmp_path/'legacy');legacy.ingest([event()],now=T)
    out=tmp_path/'outbox';sources={'base':legacy.root}
    opts=dict(identity_root=tmp_path/'identity',economic_discovery_root=root,recent_workspaces=(workspace,))
    at=now+timedelta(seconds=1)
    first=publish_material(out,sources,now=at,**opts)
    return root,workspace,out,sources,opts,at,first


def test_saved_company_changes_publish_with_exact_identity_and_economic_conditions(tmp_path,monkeypatch):
    root,w,out,sources,opts,at,result=setup_bridge(tmp_path,monkeypatch)
    record,payload,_=read_published(out,now=at)
    bundle=json.loads(payload);entries=[e for t in bundle['ThemeCandidates']
        for e in t.get('company_economic_changes',{}).get('entries',[])]
    assert result['status']=='PUBLISHED' and len(entries)==3
    assert all(e['identity']['status']=='AVAILABLE' for e in entries)
    assert {e['identity']['entity_id'] for e in entries}=={'DART_CORP:00126380','DART_CORP:00164779','DART_CORP:00000001'}
    assert record['scopes']['discovery']['status']=='CURRENT_SNAPSHOT'
    assert all(e['hypotheses'] and e['realized_revenue'] is None and not e['verified_real_benefit'] for e in entries)
    assert any(e['evidence_kind']=='CONDITIONAL_FRAMEWORK' for e in entries)
    assert all(e['basis_available_at']<=bundle['decision_at'] for e in entries)
    original={t['theme_id']:t for t in ThemeStore(root/'theme_history').search(now=at)}
    for theme in bundle['ThemeCandidates']:
        if theme.get('export_origin',{}).get('scope')!='discovery':continue
        old=original[theme['export_origin']['theme_id']]
        assert theme['event_ids']==old['event_ids']
        assert theme['scores']==old['scores']
    pins=fingerprint(tmp_path)
    again=publish_material(out,sources,now=at+timedelta(days=1),**opts)
    assert again['status']=='ALREADY_PUBLISHED' and again['sha256']==result['sha256']
    assert read_published(out,as_of=at-timedelta(microseconds=1),now=at) is None
    assert fingerprint(tmp_path)==pins


def test_missing_company_analysis_keeps_previous_publication_stale_without_global_failure(tmp_path,monkeypatch):
    root,w,out,sources,opts,at,result=setup_bridge(tmp_path,monkeypatch)
    before=read_published(out,now=at)[1]
    import newscatalystos.discovery_watch as module
    read=module.read_discovery
    def unavailable(*a,**kw):
        view=read(*a,**kw);view['theme_outlook']['recent_news_comparison_status']='UNAVAILABLE';return view
    monkeypatch.setattr(module,'read_discovery',unavailable)
    later=at+timedelta(minutes=2);new=publish_material(out,sources,now=later,**opts)
    assert new['status']=='PUBLISHED_PARTIAL'
    record,payload,_=read_published(out,now=later)
    assert record['scopes']['base']['status']=='CURRENT_SNAPSHOT'
    assert record['scopes']['discovery']['status']=='UNAVAILABLE'
    assert any(t.get('company_economic_changes') for t in json.loads(payload)['ThemeCandidates'])
    assert read_published(out,as_of=at,now=later)[1]==before


@pytest.fixture
def era_modules(monkeypatch):
    location=os.environ.get('ERALEADER_SOURCE_ROOT')
    if not location:pytest.skip('set ERALEADER_SOURCE_ROOT for the existing receiver contract')
    repo=Path(location)
    monkeypatch.syspath_prepend(str(repo/'tests'));monkeypatch.syspath_prepend(str(repo/'src'))
    helper=importlib.import_module('test_kr_news_candidate_priority')
    receiver=importlib.import_module('eraleader.news_catalyst_adapter')
    return helper,receiver,importlib.import_module('eraleader.kr_news_candidate_priority')


def received_case(tmp_path,monkeypatch,era_modules):
    _,_,out,_,_,at,_=setup_bridge(tmp_path,monkeypatch)
    helper,receiver,selector=era_modules
    project=tmp_path/'receiver';(project/'output').mkdir(parents=True)
    source=receiver.read_material_source(project=project,publication_root=out,clock=at)
    document,priority=helper.comparable()
    for row,name in zip(document['candidates'],('가상전기','가상배전')):row['name']=name
    return document,priority,source,selector,at


def test_actual_existing_receiver_evaluates_first_claim_and_shows_company_impacts(tmp_path,monkeypatch,era_modules):
    document,priority,source,selector,at=received_case(tmp_path,monkeypatch,era_modules)
    current=selector.attach(priority,document=document,source=source)
    context=current['news_material']
    assert context['quarantined_themes']==[]
    assert 'DART_CORP:00000001' in context['unmapped_entity_ids']
    decisions={r['security_id']:r for r in context['candidate_decisions']}
    assert all(r['action']=='MAINTAIN' for r in decisions.values())
    assert all(any(m.get('company_change_evidence') for m in r['materials']) for r in decisions.values())
    html=selector.render(context)
    assert '합성 분석' in html and '반증/미확보' in html
    selector.validate_order(current)
    assert current['priority_candidates'][0]['security_id']==priority['priority_candidates'][0]['security_id']


def seal(entry):
    entry['content_sha256']=sha256(_bytes({k:v for k,v in entry.items() if k!='content_sha256'})).hexdigest()


@pytest.mark.parametrize('fault',['hash','company','future','baseline','wrong_issuer','mapping'])
def test_receiver_quarantines_wrong_company_future_and_invalid_binding_only(tmp_path,monkeypatch,era_modules,fault):
    doc,priority,source,selector,at=received_case(tmp_path,monkeypatch,era_modules)
    bad=deepcopy(source);t=next(t for t in bad['bundle']['ThemeCandidates']
        if any(e['source_company']=='가상배전' for e in t.get('company_economic_changes',{}).get('entries',[])))
    entry=next(e for e in t['company_economic_changes']['entries'] if e['source_company']=='가상배전')
    if fault=='hash':entry['hypotheses'][0]['premise']='altered'
    elif fault=='company':entry['source_company']='가상전기';seal(entry)
    elif fault=='future':entry['basis_available_at']=(at+timedelta(days=1)).isoformat();seal(entry)
    elif fault=='baseline':entry['baseline']['note']['event_id']='0'*64;seal(entry)
    elif fault=='wrong_issuer':entry['identity']['entity_id']='DART_CORP:00126380';seal(entry)
    elif fault=='mapping':entry['identity']['identity_evidence_sha256']='c'*64;seal(entry)
    result=selector.attach(priority,document=doc,source=bad)
    # Wrong/missing issuer is left unmapped; other malformed extensions are
    # quarantined. The old material layer and unaffected source remain usable.
    if fault=='wrong_issuer':assert 'DART_CORP:00126380' in result['news_material']['unmapped_entity_ids']
    else:assert result['news_material']['quarantined_themes']
    assert all(r['action']=='MAINTAIN' for r in result['news_material']['candidate_decisions'])


@pytest.mark.parametrize('relation,stage,expected',[
    ('SAME_PROJECT_EXPLICIT','DELIVERY_COMPLETED','STRENGTHEN'),
    ('RELATED_BUSINESS_ONLY','DELIVERY_COMPLETED','MAINTAIN'),
    ('SAME_PROJECT_EXPLICIT','CANCELLATION','WEAKEN')])
def test_explicit_progress_or_setback_changes_existing_peer_order_without_new_score(tmp_path,monkeypatch,era_modules,relation,stage,expected):
    doc,priority,source,selector,at=received_case(tmp_path,monkeypatch,era_modules)
    value=deepcopy(source)
    entry=next(e for t in value['bundle']['ThemeCandidates'] for e in t.get('company_economic_changes',{}).get('entries',[])
               if e['source_company']=='가상배전')
    n=entry['recent']['note'];eligible=relation=='SAME_PROJECT_EXPLICIT';positive=stage=='DELIVERY_COMPLETED'
    n['evidence_kind']=entry['evidence_kind']='REPORTED_DELIVERY' if positive else 'CANCELLATION'
    old=(datetime.fromisoformat(n['reported_date'])-timedelta(days=1)).date().isoformat()
    n['execution']={'anchor_note_id':'d'*64,'project_relation':relation,'matching_basis':'합성 동일 프로젝트 명시',
                    'evidence_stage':stage,'period_end':None,'counter_reference':None}
    entry['execution_context']={'anchor_note_id':'d'*64,'anchor_reported_date':old,
        'anchor_available_at':entry['baseline']['available_at'],'project_relation':relation,
        'matching_basis':n['execution']['matching_basis'],'reported_execution_progress':eligible and positive,
        'reported_execution_setback':eligible and not positive,'project_identity_independently_verified':False}
    seal(entry)
    result=selector.attach(priority,document=doc,source=value)
    decision=next(r for r in result['news_material']['candidate_decisions'] if r['security_id']=='000660')
    assert decision['action']==expected
    assert result['news_material']['new_score_model'] is False
    if expected=='STRENGTHEN':assert result['priority_candidates'][0]['security_id']=='000660'
    selector.validate_order(result)
