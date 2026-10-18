"""Synthetic title input -> demand context -> company evidence, with PIT."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest

from newscatalystos.economic_discovery import discover_economic_events as discover
from newscatalystos.business_demand_context import stated_demand,demand_coverage
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.federated_news_search import TitleSearchWorkspace
from test_discovery_launch_comparison import analyzed
from test_federated_news_search import fingerprint
from test_official_power_news_path import collect
from test_manual_company_theme_path import manual,private_json,SOURCE,LIST,PAYLOAD
from scripts.run_manual_company_news_once import execute

TITLE='가상중공업, 글로벌 전력 인프라 수요 폭증에 초고압변압기 공장 증설'


def observation(title=TITLE):
    record,=discover(title)
    verb=record['discovery']['action_evidence']
    return dict(headline=title,source_companies=record['change']['entity_ids'],
        action=record['change']['action'],phase=record['change']['phase'],action_evidence=verb,
        source_event_sha256='e'*64,source_title_sha256=sha256(title.encode()).hexdigest(),
        provider_id='synthetic',source_url=LIST+'/8',basis_available_at=datetime.now(timezone.utc).isoformat())


def test_nominal_expansion_is_planned_and_older_editions_stay_exact(monkeypatch):
    row,=discover(TITLE)
    assert row['change']['action']=='CAPACITY_ADDITION' and row['change']['phase']=='PLANNED'
    assert row['discovery']['phase_basis']=='NOMINAL_FACILITY_EXPANSION_COMPLETION_UNCONFIRMED'
    for version in ('v1','v2','v3','v4'):
        assert discover(TITLE,rule_version='rss-event-first-'+version)==[]
    old='가상전기, 초고압 변압기 수주'
    assert discover(old,rule_version='rss-event-first-v4')==discover(old)
    monkeypatch.setattr('newscatalystos.economic_discovery.HINTS',())
    assert discover(TITLE)[0]['change']['industry_tags']==[]
    assert discover(TITLE)[0]['change']['entity_ids']==['가상중공업']


@pytest.mark.parametrize('title',[
    TITLE+' 전망',TITLE+' 취소',TITLE+' 가능성',TITLE+' 실패',TITLE+' 기념',
    '글로벌 전력 인프라 수요 폭증에 공장 증설',
    '가상중공업, 공장 증설 여부', '가상중공업, 공장 증설하지 않았다',
])
def test_uncertain_cancelled_incidental_or_unattributed_expansion_not_awarded(title):
    assert discover(title)==[]


@pytest.mark.parametrize('title',[
    '가상중공업, 초고압변압기 공장 증설',
    TITLE.replace('수요 폭증에','수요 폭증 전망에'),
    TITLE.replace('글로벌 전력 인프라','글로벌 시장'),
    TITLE.replace('폭증에','폭증…'),
    TITLE.replace('폭증에','폭증에 다른회사는'),
])
def test_missing_generic_forecast_separate_subject_or_no_connector_cause_rejected(title):
    rows=discover(title)
    if rows:assert stated_demand(observation(title)) is None


def test_exact_cause_spans_and_normal_cross_company_match_without_taxonomy():
    first=observation(TITLE.replace('초고압변압기','초격자센서'))
    second=observation(first['headline'].replace('가상중공업','다른소재'))
    claim=stated_demand(first)
    assert claim['scope']=='글로벌 전력 인프라'
    e=claim['cause_evidence']
    assert first['headline'][e['start']:e['end']]==e['text']=='글로벌 전력 인프라 수요 폭증'
    assert sha256(e['text'].encode()).hexdigest()==e['sha256']
    result=demand_coverage([first,second])
    assert result['status']=='CROSS_COMPANY_SOURCE_MATCH'
    assert result['cross_company_source_cause_match'] and not result['common_market_shock_verified']
    assert not result['verified_real_benefit']


@pytest.mark.parametrize('change',[
    {'headline':TITLE.replace('전력 인프라','전기차 인프라')},
    {'headline':TITLE.replace('수요','주문')},
    {'headline':TITLE.replace('폭증','감소')},
])
def test_different_scope_basis_or_direction_does_not_prove_common_cause(change):
    a=observation();b=observation(change['headline'].replace('가상중공업','다른소재'))
    assert not demand_coverage([a,b])['cross_company_source_cause_match']
    assert not demand_coverage([a,deepcopy(a)])['cross_company_source_cause_match']


def test_three_company_title_import_group_http_and_no_past_or_source_mutation(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    hd,documents,opener=collect(tmp_path,monkeypatch)
    workspace,path,metadata=manual(tmp_path,monkeypatch)
    data=deepcopy(PAYLOAD);url=LIST+'/8'
    data['items'].append({'id':url,'title':TITLE,'url':url});private_json(metadata,data)
    root=documents/'economic_discovery';before=datetime.now(timezone.utc)
    old=export_discovery(root,as_of=before,now=before)
    args=dict(provider_id=SOURCE,official_list_url=LIST,metadata_file=metadata,scope='other')
    code,receipt=execute(workspace,root,**args);assert code==0
    pins=fingerprint(tmp_path);at=datetime.now(timezone.utc)
    plain=export_discovery(root,as_of=at,now=at)
    current=read_discovery(root,as_of=at,now=at,include_common_causes=True)
    group,=[g for g in current['theme_outlook']['candidates'] if g['subject']=='변압기']
    assert group['source_company_name_count']==3 and group['attention_tier']=='MULTI_ACTIVITY'
    coverage=group['source_demand_context']
    assert coverage['companies_with_explicit_cause']==['가상중공업']
    assert coverage['companies_without_explicit_cause']==['가상배전','가상전기']
    assert coverage['status']=='PARTIAL_SOURCE_COVERAGE' and not coverage['cross_company_source_cause_match']
    assert not group['common_demand_cause_verified']
    hyo,=[s for s in group['source_evidence'] if s['source_companies']==['가상중공업']]
    assert hyo['phase']=='PLANNED'
    shared=hyo['shared_object_evidence']
    assert TITLE[shared['start']:shared['end']]=='변압기'
    assert export_discovery(root,as_of=at,now=at)==plain
    assert fingerprint(tmp_path)==pins
    assert export_discovery(root,as_of=before,now=at)==old
    w=TitleSearchWorkspace('other',path,workspace/'state/incremental_feeds.sqlite3',workspace/'inbox/feed_triage')
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,
        news_search_workspaces=(w,),additional_source_roots=(('other',workspace),))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def get(route,**args):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(args)) as r:return json.load(r)
    try:
        api=get('/api/economic-discovery',common_causes='1')
        assert any(g.get('source_demand_context',{}).get('status')=='PARTIAL_SOURCE_COVERAGE' for g in api['theme_outlook']['candidates'])
        query=dict(q=TITLE,provider_id=SOURCE,event_id=hyo['source_event_sha256'],
                   title_sha256=hyo['source_title_sha256'],discovery='1')
        detail=get('/api/news-evidence',**query)
        theme,=detail['article_company_context']['themes'];party,=theme['direct_parties']
        assert party['source_name']=='가상중공업' and party['phase']=='PLANNED'
        excerpt=get('/api/news-evidence',**query,excerpt_theme_id=theme['theme_id'],excerpt_entity_id=party['entity_id'],
            excerpt_claim_event_id=party['event_id'],excerpt_evidence_sha256=party['evidence_sha256'])
        assert excerpt['article_company_excerpt']['excerpt']==TITLE
    finally:server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path)==pins
    code,again=execute(workspace,root,**args)
    assert code==0 and again['discovery']['sources'][0]['theme_versions_created']==0 and opener.calls==1


def test_demand_context_UI_preserves_source_claim_and_missing_companies(tmp_path):
    root,*_,at,_=analyzed(tmp_path,('가상전기, 초고압 변압기 수주',
        '가상배전, HVDC 변압기 수주',TITLE))
    data=read_discovery(root,as_of=at,now=at,include_common_causes=True)['theme_outlook']
    script=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8'),data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,txt){return {textContent:txt||'',children:[],append(...x){this.children.push(...x)},addEventListener(){}}}
const p=node('div'),ctx={node,economicActionLabels:{CONTRACT:'계약',CAPACITY_ADDITION:'생산능력 확대'}};
vm.runInNewContext(s.slice(s.indexOf('function renderThemeOutlook('),s.indexOf('function renderLaunchComparisons(')),ctx);
ctx.renderThemeOutlook(p,data);
function text(n){return [n.textContent,...n.children.flatMap(text)].join(' ')}
for(const x of ['일부 기업 원문만 명시','가상중공업 → 글로벌 전력 인프라 수요 폭증','완료 미확인','같은 수요 원인인지 미확인: 가상배전 · 가상전기','이 테마의 기업·분석 근거 보기'])assert(text(p).includes(x),x);
assert(!s.slice(s.indexOf('function renderThemeOutlook(')).includes('innerHTML'));
"""
    subprocess.run(['node','-e',script],input=json.dumps(data),text=True,capture_output=True,check=True,
                   cwd=Path(__file__).resolve().parent.parent)
