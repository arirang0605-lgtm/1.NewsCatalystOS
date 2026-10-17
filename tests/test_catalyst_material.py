"""Core role: new/repeat/change -> source-company impacts -> Era input.

No stock ranking, invented supplier, pricing signal or write to the producer.
"""
from copy import deepcopy
from datetime import timedelta,datetime
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
import json
import threading
import subprocess

import pytest
from newscatalystos.catalyst_material import materials_for_store,attach_material
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.source_share import SourceShareError
from test_theme_emergence import T,event
from test_federated_news_search import fingerprint
from test_service_realization import pair

L=T+timedelta(hours=1)


def view(store,since=T,end=L):
    return list(materials_for_store(store,since=since,as_of=end,now=end,scope='company').values())


def test_first_local_observation_is_not_new_market_fact_or_recommendation(tmp_path):
    store=ThemeStore(tmp_path/'themes');store.ingest([event()],now=T)
    before=fingerprint(tmp_path);summary,=view(store)
    material,=summary['materials']
    assert material['material_status']=='FIRST_RECORDED_CLAIM'
    assert material['market_novelty']=='UNCONFIRMED' and material['is_new_market_catalyst'] is None
    assert material['source_published_at'] is None
    assert material['news_input_for_era']=='CONTEXT_ONLY_MARKET_NOVELTY_UNKNOWN'
    assert summary['selection_owner']=='EraLeader' and summary['investment_rank'] is None
    company,=material['company_impacts']
    assert company['entity_id']=='가상기업1'
    assert company['role']=='DIRECT_SOURCE_ACTION_PARTY'
    hypothesis,=company['hypotheses']
    assert hypothesis['path']=='EARNINGS' and hypothesis['direction']=='UNKNOWN'
    assert hypothesis['counter_argument'] and hypothesis['claim_type']=='HYPOTHESIS'
    assert not company['verified_real_benefit'] and not material['orders_enabled']
    again,=view(store,end=L+timedelta(hours=1))
    assert again==summary # a clock tick never mints new semantic content
    assert fingerprint(tmp_path)==before


def test_old_source_discovered_today_is_reference_not_new_catalyst(tmp_path):
    store=ThemeStore(tmp_path/'themes');store.ingest([event()],now=L)
    summary,=view(store,since=T+timedelta(minutes=30))
    m,=summary['materials']
    assert m['material_status']=='EXISTING_SOURCE_NEWLY_ANALYZED'
    assert m['first_source_observed_at']==T.isoformat()
    assert m['first_event_recorded_at']==L.isoformat()
    assert m['news_input_for_era']=='CONTEXT_ONLY_MARKET_NOVELTY_UNKNOWN'


def test_reprints_same_economic_event_do_not_strengthen_or_multiply(tmp_path):
    store=ThemeStore(tmp_path/'themes');original=event();store.ingest([original],now=T)
    copies=[]
    for n in range(6):
        r=deepcopy(original);r['source_id']='press-'+str(n);r['source_url']='https://press.example/'+str(n);copies.append(r)
    store.ingest(copies,now=L)
    m,=view(store,since=L)[0]['materials']
    assert m['material_status']=='REPEATED_CLAIM' and m['source_document_count']==7
    assert m['locally_added_action_count']==0
    assert m['news_input_for_era']=='NO_NEW_CATALYST'
    assert len(m['company_impacts'])==1
    assert store.search(now=L)[0]['scores']['distinct_economic_events']==1


def test_absence_of_news_never_invalidates_previous_event(tmp_path):
    store=ThemeStore(tmp_path/'themes');store.ingest([event()],now=T)
    m,=view(store,since=L,end=L+timedelta(days=50))[0]['materials']
    assert m['material_status']=='NO_NEW_MATERIAL' and m['active']
    assert m['news_input_for_era']=='NO_NEW_CATALYST'


def test_official_identity_update_does_not_become_new_material(tmp_path):
    store=ThemeStore(tmp_path/'themes');original=event(company='가상기업')
    kw={k:v for k,v in original.items() if k not in ('event_id','change')}
    binding={'source_event_sha256':'a'*64,'document_sha256':'b'*64}
    plain=economic_observation(original['change'],**kw,source_binding=binding)
    store.ingest([plain],now=T)
    mapped=economic_observation(original['change'],**kw,source_binding=binding,
        company_mappings=[{'source_name':'가상기업','entity_id':'DART_CORP:12345678','evidence_sha256':'c'*64}])
    store.ingest([mapped],now=L)
    summary,=view(store,since=L)
    m,=summary['materials']
    assert m['material_status']=='IDENTITY_OR_CONTEXT_ONLY' and m['news_input_for_era']=='NO_NEW_CATALYST'
    projected=attach_material(store.search(now=L),{summary['theme_id']:summary})
    assert projected[0]['catalyst_material']['materials'][0]['company_impacts'][0]['entity_id']=='DART_CORP:12345678'


def test_plan_to_start_uses_existing_followup_as_progress_not_second_fact(tmp_path):
    store=ThemeStore(tmp_path/'themes');plan,start=pair()
    plan['change']['industry_tags']=start['change']['industry_tags']=['SEMICONDUCTOR']
    store.ingest([plan],now=T);store.ingest([start],now=L)
    summary,=view(store,since=L);m,=summary['materials']
    assert m['material_status']=='REPORTED_STAGE_PROGRESS'
    assert m['news_input_for_era']=='REASSESS_REPORTED_PROGRESS'
    assert len(m['event_ids'])==2 and m['locally_added_action_count']==0
    assert not m['source_reported_progress'][0]['is_realization_confirmed']
    assert not m['verified_economic_effect'] and summary['leader_score'] is None


@pytest.mark.parametrize('polarity,kind,hint',[('RETRACT','SOURCE_WITHDRAWAL','REASSESS_WITHDRAWAL'),('CONTRADICT','SOURCE_CONFLICT','REASSESS_CONFLICT')])
def test_targeted_counterevidence_reaches_era_and_only_that_company(tmp_path,polarity,kind,hint):
    store=ThemeStore(tmp_path/'themes');first=event(1);second=event(2)
    store.ingest([first,second],now=T)
    store.ingest([event(3,polarity=polarity,target=first['event_id'])],now=L)
    summary,=view(store,since=L)
    a=next(m for m in summary['materials'] if first['event_id'] in m['event_ids'])
    b=next(m for m in summary['materials'] if second['event_id'] in m['event_ids'])
    assert a['material_status']==kind and a['news_input_for_era']==hint
    assert a['company_impacts']==[]
    assert b['material_status']=='NO_NEW_MATERIAL' and b['active']
    assert b['company_impacts'][0]['entity_id']=='가상기업2'


def test_same_document_text_revision_is_not_automatically_new_contract(tmp_path):
    store=ThemeStore(tmp_path/'themes');old=event(company='가상기업')
    old['change']['evidence_level']='REPORTED'
    kw={k:v for k,v in old.items() if k not in ('event_id','change')}
    first=economic_observation(old['change'],**kw,content_scope='RSS_TITLE_METADATA',
        source_binding={'source_event_sha256':'a'*64,'document_sha256':old['change']['source_paragraph_sha256']})
    store.ingest([first],now=T)
    revised=deepcopy(old['change']);revised['source_paragraph_sha256']='b'*64
    changed=economic_observation(revised,**kw,content_scope='RSS_TITLE_METADATA',
        source_binding={'source_event_sha256':'a'*64,'document_sha256':'b'*64})
    store.ingest([changed],now=L)
    summary,=view(store,since=L)
    m=next(x for x in summary['materials'] if changed['event_id'] in x['event_ids'])
    assert m['material_status']=='SOURCE_TEXT_REVISION_UNRESOLVED'
    assert m['locally_added_action_count']==0
    assert m['previous_document_event_ids']==[first['event_id']]


def test_invalid_period_or_source_digest_is_not_silently_used(tmp_path):
    store=ThemeStore(tmp_path/'themes');store.ingest([event()],now=T)
    with pytest.raises(SourceShareError):materials_for_store(store,since=L,as_of=T,now=L)
    with pytest.raises(SourceShareError):materials_for_store(store,since=T,as_of=L,now=T)
    import sqlite3
    with sqlite3.connect(store.root/'themes.sqlite3') as db:db.execute('UPDATE versions SET digest=?',('f'*64,))
    with pytest.raises(SourceShareError):view(store)


def test_actual_http_contract_and_article_keep_news_to_era_direction(tmp_path,monkeypatch):
    from test_company_evidence import rss
    from scripts.open_research_dashboard import DashboardServer
    theme,args,report_path,report,info,store=rss(tmp_path/'news')
    at=args['now']
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'],news_search_workspaces=(info[0],))
    thr=threading.Thread(target=server.serve_forever,daemon=True);thr.start();before=fingerprint(tmp_path)
    def get(route,query):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(query),timeout=20) as r:
            assert r.status==200;return json.load(r)
    try:
        a=get('/api/themes',{});b=get('/api/themes',{})
        assert a==b
        row=next(t for t in a['ThemeCandidates'] if t['theme_id']==theme['theme_id'])
        assert row['catalyst_material']['selection_owner']=='EraLeader'
        assert row['theme_id']==theme['theme_id']
        assert row['event_ids']==theme['event_ids'] and row['scores']==theme['scores']
        assert row['catalyst_material']['materials']
        search=get('/api/news-search',{'q':'HBM'});source=search['results'][0]
        detail=get('/api/news-evidence',{'q':'HBM',**{k:source[k] for k in ('provider_id','event_id','title_sha256')}})
        for g in detail['article_company_context']['themes']:
            for party in g['direct_parties']:
                assert party['catalyst_materials']
                assert all(party['event_id'] in m['event_ids'] for m in party['catalyst_materials'])
        period=get('/api/period',{'view':'day','date':at.astimezone().date().isoformat()})
        assert period['catalyst_material'][theme['theme_id']]['materials']
    finally:
        server.shutdown();server.server_close();thr.join(3)
    assert fingerprint(tmp_path)==before


def test_ui_presents_novelty_impacts_counterconditions_and_roles():
    root=Path(__file__).resolve().parent.parent
    js=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(t,c,text){return {tag:t,textContent:text||'',children:[],append(...xs){this.children.push(...xs)}}}
const ctx={node,economicActionLabels:{INVESTMENT:'투자'},economicPhaseLabels:{PLANNED:'계획'}};
vm.runInNewContext(s.slice(s.indexOf('function renderCatalystMaterial('),s.indexOf('function renderEraDailyAssessment(')),ctx);
const box=node('div');
ctx.renderCatalystMaterial(box,{materials:[{material_status:'NO_NEW_MATERIAL',reason:'기존 사건 반복',source_action:'INVESTMENT',source_phase:'PLANNED',topic:'HBM',news_input_for_era:'NO_NEW_CATALYST',first_source_observed_at:'2026-10-15',first_event_recorded_at:'2026-10-17',company_impacts:[{entity_id:'합성기업',source_entity_id:'합성기업',role:'DIRECT_SOURCE_ACTION_PARTY',hypotheses:[{path:'CAPEX',direction:'INCREASE',premise:'생산시설 투자 지출 가능성',counter_argument:'발주·가동 미확인'}]}]}]});
function text(x){return [x.textContent,...x.children.flatMap(text)].join(' ')}
const all=text(box);for(const expected of ['기존 사건 반복','새 재료 가산 근거 없음','합성기업','발주·가동 미확인','EraLeader','개별 전략'])assert(all.includes(expected));
assert(!all.includes('매수 추천'));console.log('NEWS_MATERIAL_NOT_STOCK_RANK_UI');
'''
    subprocess.run(['node','-e',js],cwd=root,check=True,capture_output=True,text=True)


def test_fully_withdrawn_semiconductor_theme_does_not_disappear_from_materials(tmp_path):
    store=ThemeStore(tmp_path/'themes');first=event()
    store.ingest([first],now=T)
    store.ingest([event(2,polarity='RETRACT',target=first['event_id'])],now=L)
    assert store.search(now=L)[0]['industry_tags']==[]
    newest,=view(store,since=L)[0]['materials']
    assert newest['material_status']=='SOURCE_WITHDRAWAL' and not newest['active']
    assert newest['company_impacts']==[]
    later=L+timedelta(hours=1)
    old,=view(store,since=later,end=later)[0]['materials']
    assert old['material_status']=='PREVIOUSLY_INVALIDATED'
    assert old['news_input_for_era']=='EXCLUDE_INVALIDATED_CATALYST'


def test_existing_delivery_cli_can_publish_immutable_material_input(tmp_path,capsys):
    from scripts.search_themes import main
    from newscatalystos.standard_delivery import read_theme_bundle
    store=ThemeStore(tmp_path/'themes');store.ingest([event()],now=T)
    flags=['--root',str(store.root),'--since',L.isoformat(),'--as-of',L.isoformat(),
           '--materials','--export-root',str(tmp_path/'news-outbox')]
    assert main(flags)==0
    record=json.loads(capsys.readouterr().out)
    raw=Path(record['path']).read_bytes()
    data=read_theme_bundle(raw,record['sha256'],decision_at=L,now=L)
    assert data['ThemeCandidates'][0]['catalyst_material']['materials'][0]['news_input_for_era']=='NO_NEW_CATALYST'
    before=fingerprint(tmp_path)
    assert main(flags)==0 and json.loads(capsys.readouterr().out)==record
    assert fingerprint(tmp_path)==before


def test_valid_legacy_source_without_topic_keeps_news_but_has_no_invented_impact(tmp_path):
    from newscatalystos.catalyst_material import assess_theme
    store=ThemeStore(tmp_path/'themes');theme=store.ingest([event()],now=T)[0]
    old=deepcopy(theme)
    for ref in old['source_refs']:ref.pop('topic',None)
    summary=assess_theme(None,old,since=T,scope='base',now=L)
    row,=summary['materials']
    assert row['topic'] is None and row['source_detail_status']=='LEGACY_DETAILS_UNAVAILABLE'
    assert row['company_impacts'][0]['hypotheses']==[]
    assert row['company_impacts'][0]['impact_status']=='N/A'
    assert row['is_new_market_catalyst'] is None
