"""Economic action first, optional industry second; keep the unclassified watch.

Tests run only source-bound metadata and existing derived state. No source poll,
new AI or changes to original sector-specific outputs.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
import pytest

from newscatalystos.economic_discovery import discover_economic_events as discover
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.feed_analysis import analyze_completed_feed
from newscatalystos.feed_analysis_delivery import _validate_report
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_analysis import parser,evaluate
from test_new_source_adapter import registry
from test_federated_news_search import setup_workspace,collect,fingerprint

T=datetime.now(timezone.utc)
SAMPLES=(
    ('가상소재는 리튬황소재 생산을 시작했다','PRODUCTION_START','리튬황소재',['가상소재'],[]),
    ('가상전기는 초고압 변압기 공급계약을 체결했다','CONTRACT','초고압 변압기',['가상전기'],['POWER_EQUIPMENT']),
    ('가상테크, 신규 공장 투자를 결정했다','INVESTMENT','신규 공장',['가상테크'],[]),
    ('새물질 생산을 시작했다','PRODUCTION_START','새물질',[],[]),
    ('미래소재, 초격자센서 생산능력을 확대했다','CAPACITY_ADDITION','초격자센서',['미래소재'],[]),
    ('미래물류, 배송로봇 서비스 개시','BUSINESS_START','배송로봇',['미래물류'],['ROBOTICS']),
    ('가상전자, HBM 생산을 시작할 계획이다','PRODUCTION_START','HBM',['가상전자'],['SEMICONDUCTOR']),
    ('Department of Commerce Announces Finalization of CHIPS R&D Award with D-Wave','POLICY_CHANGE','CHIPS R&D Award',['D-Wave'],[]),
    ('NIST Awards More Than $30 Million for MEP Centers in 11 States and Puerto Rico','POLICY_CHANGE','More Than $30 Million for MEP Centers in 11 States and Puerto Rico',[],[]),
)


@pytest.mark.parametrize('title,action,topic,entities,tags',SAMPLES)
def test_event_appears_without_industry_prerequisite(title,action,topic,entities,tags):
    record,=discover(title)
    change=record['change'];meta=record['discovery']
    assert change['action']==action and change['topic']==topic
    assert change['entity_ids']==entities and change['industry_tags']==tags
    assert change['source_paragraph_sha256']==sha256(title.encode()).hexdigest()
    assert change['verified_economic_effect'] is False
    assert meta['event_first'] and not meta['industry_required_for_detection']
    span=meta['action_evidence']
    assert title[span['start']:span['end']]==span['text']
    assert sha256(span['text'].encode()).hexdigest()==span['sha256']
    assert not meta['deep_industry_validation'] and meta['market_newness']=='UNKNOWN'
    if not tags:assert meta['industry_status']=='UNCLASSIFIED_OBSERVATION'
    if not entities:assert meta['company_status']=='COMPANY_UNSPECIFIED'


def test_removing_every_industry_label_does_not_remove_a_single_event(monkeypatch):
    import newscatalystos.economic_discovery as module
    initial=[discover(t[0]) for t in SAMPLES]
    monkeypatch.setattr(module,'HINTS',())
    after=[discover(t[0]) for t in SAMPLES]
    assert [len(x) for x in initial]==[len(x) for x in after]
    for before,new in zip(initial,after):
        for a,b in zip(before,new):
            assert {k:v for k,v in a['change'].items() if k!='industry_tags'}=={k:v for k,v in b['change'].items() if k!='industry_tags'}
            assert b['change']['industry_tags']==[]
    assert all(after) # industrial dictionaries are not admission filters


@pytest.mark.parametrize('text',(
    '가상테크, 리튬황소재 생산을 시작하지 않았다',
    '가상전기는 변압기 공급계약을 체결했다는 루머를 부인했다',
    '가상전기는 변압기 공급계약 취소를 알렸다',
    '가상제약, 신약 생산 개시 기념행사 개최',
    '가상제약, 신약 생산 개시 전망',
    'NIST Announces Funding Opportunity for 14 MEP Centers',
    'Example Company may begin production',
    '가상기업, 인공지능 시장 동향',
    '가상기업, 자사주 투자를 결정했다',
))
def test_incidental_unsupported_or_denied_action_not_a_new_economic_claim(text):
    assert discover(text)==[]


def test_company_name_does_not_supply_missing_sector_or_wrong_actor():
    record,=discover('Department of Commerce Announces Finalization of CHIPS R&D Award with PsiQuantum')
    assert record['change']['entity_ids']==['PsiQuantum'] and record['change']['industry_tags']==[]
    assert record['discovery']['industry_status']=='UNCLASSIFIED_OBSERVATION'
    row,=discover('가상전자, 다른제약은 신약 생산을 시작했다')
    assert row['change']['entity_ids']==[]
    plan,=discover('가상테크, 신규 공장 투자를 결정했다')
    assert plan['change']['phase']=='PLANNED'


def setup(tmp_path):
    providers=registry();provider=providers.providers[0].provider_id
    w=setup_workspace(tmp_path,'core',providers)
    collect(w,providers,provider,[(str(i),s[0],f'https://gov.example.org/observation/{i}') for i,s in enumerate(SAMPLES)],at=T)
    return w,providers,provider


def flags(w,provider,root):
    return parser().parse_args(['--registry',str(w.registry_path),'--state',str(w.poll_state),'--inbox-root',str(w.inbox_root),
        '--provider-id',provider,'--discover-economy','--limit','100',
        '--analysis-root',str(root/'feed_analysis/d_test/core'),'--theme-root',str(root/'theme_history')])


def test_shared_input_storage_unclassified_watch_and_standard_output(tmp_path):
    w,providers,provider=setup(tmp_path);root=tmp_path/'discovery';at=datetime.now(timezone.utc)+timedelta(seconds=1)
    before=fingerprint(w.registry_path.parent.parent)
    code,result=evaluate(flags(w,provider,root),now=at)
    assert code==0 and result['economic_changes_count']==len(SAMPLES)
    from newscatalystos.economic_discovery import RULE_VERSION
    assert result['rule_version']==RULE_VERSION and result['analysis_industry']=='ECONOMIC_DISCOVERY'
    assert result['source_fetch_calls']==result['semantic_ai_attempts']==0
    assert all(not r['ai_eligible'] and not r['ai_adapter_attempted'] for r in result['results'])
    assert _validate_report(result,at)==at
    view=read_discovery(root,as_of=at,now=at)
    assert view['status']=='READY' and view['counts']['events']==len(SAMPLES)
    assert view['counts']['unclassified_topics']>=4
    unmapped=next(c for c in view['candidates'] if c['watch_topic']=='리튬황소재')
    assert unmapped['source_companies']==['가상소재'] and unmapped['industry_tags']==[]
    assert unmapped['source_evidence'][0]['headline']==SAMPLES[0][0]
    assert unmapped['material']['selection_owner']=='EraLeader'
    unknown=next(c for c in view['candidates'] if c['watch_topic']=='새물질')
    assert unknown['source_companies']==[] and unknown['company_status']=='COMPANY_UNSPECIFIED'
    raw=export_discovery(root,as_of=at,now=at)
    doc=json.loads(raw)
    assert len(doc['ThemeCandidates'])==len(view['candidates'])
    assert any(t['industry_tags']==[] for t in doc['ThemeCandidates'])
    assert all('catalyst_material' in t for t in doc['ThemeCandidates'])
    assert read_discovery(root,as_of=T,now=at)['candidates']==[]
    code,again=evaluate(flags(w,provider,root),now=at+timedelta(minutes=2))
    assert code==0 and again['theme_versions_created']==0
    assert read_discovery(root,as_of=at+timedelta(minutes=2),now=at+timedelta(minutes=2))['counts']['events']==len(SAMPLES)
    assert fingerprint(w.registry_path.parent.parent)==before


def test_event_metadata_tamper_and_cross_profile_state_blocked(tmp_path):
    w,providers,provider=setup(tmp_path);root=tmp_path/'discovery';at=datetime.now(timezone.utc)+timedelta(seconds=1)
    opts=flags(w,provider,root);code,result=evaluate(opts,now=at);assert code==0
    bad=deepcopy(result);bad['results'][0]['economic_discovery'][0]['discovery']['industry_required_for_detection']=True
    with pytest.raises(SourceShareError):_validate_report(bad,at)
    changed=deepcopy(result);changed['results'][0]['economic_changes'][0]['entity_ids']=['다른기업']
    with pytest.raises(SourceShareError):_validate_report(changed,at)
    with pytest.raises(SourceShareError,match='industry root differs'):
        analyze_completed_feed(providers,w.inbox_root,w.poll_state,opts.analysis_root,provider_id=provider,now=at)
    opts.industry='POWER_EQUIPMENT';assert evaluate(opts,now=at)[0]==4
    opts=flags(w,provider,tmp_path/'second');opts.allow_paid=True
    assert evaluate(opts,now=at)[0]==4 and not opts.analysis_root.exists()


def test_existing_semiconductor_and_optional_power_are_not_reinterpreted(tmp_path):
    w,providers,provider=setup(tmp_path);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    a=analyze_completed_feed(providers,w.inbox_root,w.poll_state,tmp_path/'a',provider_id=provider,now=at)
    b=analyze_completed_feed(providers,w.inbox_root,w.poll_state,tmp_path/'b',provider_id=provider,now=at,industry='SEMICONDUCTOR')
    assert a==b and a['rule_version']=='rss-title-economic-v13'
    assert 'economic_discovery' not in a['results'][0]
    assert evaluate(flags(w,provider,tmp_path/'new'),now=at)[0]==0
    assert ThemeStore(tmp_path/'new/theme_history').search(now=at)


def test_current_http_view_and_export_show_unclassified_economy(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    w,providers,provider=setup(tmp_path);documents=tmp_path/'documents';root=documents/'economic_discovery';at=datetime.now(timezone.utc)+timedelta(seconds=1)
    assert evaluate(flags(w,provider,root),now=at)[0]==0
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,tmp_path/'legacy-reports',tmp_path/'notes',documents,news_search_workspaces=(w,))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    before=fingerprint(tmp_path)
    def get(route,query=None):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+('?' + urlencode(query) if query else ''),timeout=20) as r:
            assert r.status==200;return json.load(r)
    try:
        found=get('/api/economic-discovery')
        assert found['counts']['unclassified_topics']>=4
        assert any(c['watch_topic']=='리튬황소재' for c in found['candidates'])
        exported=get('/api/economic-discovery',{'export':'1'})
        assert any(t['industry_tags']==[] for t in exported['ThemeCandidates'])
        day=get('/api/period',{'view':'day','date':at.astimezone().date().isoformat()})
        assert day['economic_discovery']['counts']['events']==len(SAMPLES)
        assert get('/api/economic-discovery',{'as_of':T.isoformat()})['candidates']==[]
        with pytest.raises(HTTPError) as e:get('/api/economic-discovery',{'as_of':(at+timedelta(days=1)).isoformat()})
        assert e.value.code==400
    finally:server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(tmp_path)==before


def test_existing_runner_new_mode_does_not_poll_or_require_industry(tmp_path):
    from scripts.run_economic_discovery import execute
    w,providers,provider=setup(tmp_path);root=tmp_path/'observe'
    source=[('core',w.registry_path,w.poll_state,w.inbox_root)]
    before=fingerprint(w.registry_path.parent.parent)
    dry=execute(root,source,now=datetime.now(timezone.utc)+timedelta(seconds=1),dry_run=True)
    assert dry['status']=='READY' and not root.exists()
    out=execute(root,source,now=datetime.now(timezone.utc)+timedelta(seconds=1))
    assert out['status']=='READY' and out['industry_selected'] is None
    assert out['economic_events']==len(SAMPLES) and out['unclassified_events']>=4
    assert out['source_fetch_calls']==out['paid_ai_calls']==0
    assert fingerprint(w.registry_path.parent.parent)==before


def test_ui_preserves_unknown_industry_and_unknown_company_without_rejecting():
    script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(tag,cls,text){return {tag,textContent:text||'',children:[],append(...x){this.children.push(...x)},replaceChildren(...x){this.children=x}}}
const els={};for(const k of ['economic-discovery','discovery-panel','discovery-summary'])els[k]=node('div');
const context={node,$:id=>els[id],economicActionLabels:{PRODUCTION_START:'생산개시'},renderCatalystMaterial:()=>{}};
vm.runInNewContext(code.slice(code.indexOf('function renderEconomicDiscovery(')),context);
context.renderEconomicDiscovery({status:'READY',counts:{topics:1,events:1,unclassified_topics:1},candidates:[{watch_topic:'새소재<script>',industry_links:[],source_companies:[],economic_actions:['PRODUCTION_START'],first_observed_at:'2026-10-18',source_evidence:[],material:null}]});
function text(n){return [n.textContent,...n.children.flatMap(text)].join(' ')}
const displayed=text(els['economic-discovery']);assert(displayed.includes('새소재<script>'));assert(displayed.includes('산업 미분류'));assert(displayed.includes('미확보'));assert(displayed.includes('생산개시'));assert(els['discovery-panel'].hidden===false);
console.log('EVENT_FIRST_UNCLASSIFIED_UI_PASS');
'''
    root=Path(__file__).resolve().parent.parent
    subprocess.run(['node','-e',script],cwd=root,check=True,capture_output=True,text=True)


def test_raw_title_digest_and_normalized_display_text_are_separate(tmp_path):
    providers=registry();provider=providers.providers[0].provider_id
    w=setup_workspace(tmp_path,'core',providers)
    raw='Department of Commerce Announces Finalization of CHIPS R&amp;D Award with D-Wave'
    collect(w,providers,provider,[('raw-html',raw,'https://gov.example.org/award')],at=T)
    at=datetime.now(timezone.utc)+timedelta(seconds=1);root=tmp_path/'discovery'
    code,result=evaluate(flags(w,provider,root),now=at)
    assert code==0 and result['economic_changes_count']==1
    row=result['results'][0]
    assert row['source_title_sha256']==sha256(raw.encode()).hexdigest()
    assert row['source_title_sha256']!=sha256(row['headline'].encode()).hexdigest()
    assert _validate_report(result,at)==at
    view=read_discovery(root,as_of=at,now=at)
    candidate,=view['candidates']
    assert candidate['source_companies']==['D-Wave']
    assert candidate['source_evidence'][0]['title_sha256']==row['source_title_sha256']
    assert candidate['source_evidence'][0]['headline']==row['headline']


def test_long_unknown_object_observed_without_exceeding_existing_topic_contract():
    from newscatalystos.theme_emergence import validate_change
    title='Department of Commerce Awards CHIPS Incentives to a Subsidiary of Korea Zinc (Crucible Metals) to Support a State-of-the-Art Smelter and Critical Minerals Processing Facility in the United States'
    record,=discover(title)
    validate_change(record['change'])
    assert len(record['change']['topic'])<=80
    assert record['change']['industry_tags']==['CRITICAL_MINERALS']
    assert record['discovery']['topic_label_truncated']
    assert record['change']['entity_ids']==[] # don't invent a subsidiary issuer


@pytest.mark.parametrize('title',(
 '중소기업자 우선조달 계약 범위를 확대하는 「판로지원법」 개정안 국무회의 의결',
 '국가 인공지능 데이터의 체계적 관리를 위한 「인공지능 기본법」 개정안 국무회의 통과',
 'AI에 맛집 묻는 손님 늘자... 동네 가게 AI 검색 노출 서비스 ‘로컬블록’ 출시',
 '동네 심부름, 이웃에게 맡긴다... 근거리 매칭 서비스 ‘심부름’ 전국 출시',
))
def test_rhetorical_titles_kept_as_events_not_invented_company_names(title):
    row,=discover(title)
    assert row['change']['entity_ids']==[]
    assert row['discovery']['company_status']=='COMPANY_UNSPECIFIED'
    assert row['change']['action'] in ('POLICY_CHANGE','BUSINESS_START')


def test_announced_business_start_is_planned_not_completed_operation():
    row,=discover('클루닉스, 네오에이아이클라우드와 손잡고 포항 AI 데이터센터 AI·HPC 통합 운영 나선다')
    assert row['change']['entity_ids']==['클루닉스']
    assert row['change']['phase']=='PLANNED'


def test_existing_market_entry_evidence_contract_reused_for_unknown_industry():
    from newscatalystos.theme_emergence import validate_change
    row,=discover('가상테크, 우주 데이터 시장에 진출했다')
    validate_change(row['change'])
    assert row['change']['action']=='MARKET_ENTRY'
    assert row['change']['market_entry']['market_name']=='우주 데이터'
    assert row['change']['industry_tags']==[]
