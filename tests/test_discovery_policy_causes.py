"""Literal policy modifier -> one corporate action -> optional causal view."""
from copy import deepcopy
from datetime import timedelta, datetime
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import threading
from urllib.request import urlopen

import pytest

from newscatalystos.economic_discovery import discover_economic_events as discover
from newscatalystos.economic_changes import policy_cause_key
from newscatalystos.feed_analysis_delivery import _validate_report
from newscatalystos.discovery_watch import read_discovery, export_discovery
from newscatalystos.discovery_cause_links import build_discovery_causes
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_analysis import evaluate
from test_discovery_launch_comparison import analyzed, source
from test_discovery_cause_links import view
from test_economic_discovery import flags, SAMPLES
from test_federated_news_search import fingerprint
from test_policy_investment_comparison import text

A=text()
B=text(product='DRAM',actor='새빛소재',tail='생산을 시작했다')


@pytest.mark.parametrize('tail,action',[
    ('신규 공장 투자를 집행했다','INVESTMENT_EXECUTION'),
    ('생산을 시작했다','PRODUCTION_START'),
    ('생산능력 확대','CAPACITY_ADDITION'),
    ('공급 계약을 체결했다','CONTRACT'),
    ('신규 공장 투자 결정','INVESTMENT'),
])
def test_policy_modifier_is_one_corporate_action_with_exact_offsets_and_old_rules(tail,action):
    title=text(tail=tail)
    row,=discover(title)
    assert row['change']['action']==action and row['change']['entity_ids']==['가상전자']
    proof=row['discovery']['action_evidence']
    assert title[proof['start']:proof['end']]==proof['text']
    assert proof['sha256']==sha256(proof['text'].encode()).hexdigest()
    assert discover(title,rule_version='rss-event-first-v1')==[]
    assert discover(title,rule_version='rss-event-first-v2')==[]


def test_boundary_is_industry_independent_and_never_adds_an_industry_gate(monkeypatch):
    title=text(product='초격자센서',restriction='생산 규제',tail='생산을 시작했다')
    row,=discover(title)
    assert row['change']['action']=='PRODUCTION_START'
    assert row['change']['industry_tags']==[]
    monkeypatch.setattr('newscatalystos.economic_discovery.HINTS',())
    assert discover(title)==[row]
    for sample,*_ in SAMPLES:
        assert discover(sample)==discover(sample,rule_version='rss-event-first-v2')


def test_input_store_optional_export_preserves_originals_and_repeated_event_identity(tmp_path):
    root,w,opts,at,report=analyzed(tmp_path,(A,B))
    assert report['economic_changes_count']==2 and report['semantic_ai_attempts']==0
    assert _validate_report(report,at)==at
    before=fingerprint(tmp_path)
    raw=export_discovery(root,as_of=at,now=at)
    old=read_discovery(root,as_of=at,now=at)
    data=view(root,at);g,=data['common_cause_connections']['groups']
    assert g['cause_basis']=='POLICY' and g['subject']=='미국 · 첨단칩통제법'
    assert g['products']==['DRAM','HBM']
    assert g['economic_actions']==['INVESTMENT_EXECUTION','PRODUCTION_START']
    assert len(g['event_ids'])==2 and g['reported_action_count']==2
    assert not g['verified_real_benefit'] and not g['supply_chain_transaction_verified']
    for row in g['source_evidence']:
        proof=row['policy_cause']
        assert policy_cause_key(proof)==g['policy_cause_key']
        assert row['headline'][slice(row['cause_evidence']['start'],row['cause_evidence']['end'])]==proof['source_expression']
        assert row['report_sha256'] and row['source_theme_snapshots']
    assert data['theme_outlook']==old['theme_outlook']
    optional=json.loads(export_discovery(root,as_of=at,now=at,include_common_causes=True))
    for new,prior in zip(optional['ThemeCandidates'],json.loads(raw)['ThemeCandidates']):
        assert new.pop('discovery_common_causes')['groups']==[g]
        assert new==prior
    assert export_discovery(root,as_of=at,now=at)==raw and fingerprint(tmp_path)==before
    code,again=evaluate(opts,now=at+timedelta(minutes=1))
    assert code==0 and again['theme_versions_created']==0
    assert view(root,at+timedelta(minutes=1))['counts']['events']==2


@pytest.mark.parametrize('other',[
    B.replace('미국','일본'), B.replace('첨단칩통제법','별도통제법'),
    B.replace('수출 규제','수입 규제'), B.replace('완화로','폐지로'),
    B.replace('미국 ',''), B.replace('‘첨단칩통제법’ ',''),
    B.replace('DRAM','HBM'), B.replace('DRAM','NAND DRAM'),
    B.replace('DRAM','중국향 DRAM'),
    B.replace('완화로','완화 전망으로'),
    B.replace('시작했다','시작하지 않았다'),
    'Department of Commerce Awards CHIPS Incentives with 새빛소재',
    '새빛소재, DRAM 생산을 시작했다',
    B.replace('완화로','완화로 다른전자는'),
])
def test_different_missing_ambiguous_or_denied_cause_cannot_join(tmp_path,other):
    root,*_,at,_=analyzed(tmp_path,(A,other))
    assert view(root,at)['common_cause_connections']['groups']==[]


def test_plans_keep_their_phase_and_literal_policy_variants_reuse_existing_key(tmp_path):
    second=B.replace('미국 ‘첨단칩통제법’','미국의 「첨단칩통제법」')
    root,*_,at,_=analyzed(tmp_path,(A+' 계획',second))
    group,=view(root,at)['common_cause_connections']['groups']
    assert group['planned_action_count']==1 and group['reported_action_count']==1
    assert len({r['policy_cause']['source_expression'] for r in group['source_evidence']})==2


def test_old_v2_report_and_past_default_bytes_remain_valid_after_v3(tmp_path,monkeypatch):
    import newscatalystos.economic_discovery as engine
    w,reg,provider,at=source(tmp_path,(SAMPLES[0][0],A,B))
    root=tmp_path/'watch';opts=flags(w,provider,root)
    current=engine.RULE_VERSION
    monkeypatch.setattr(engine,'discover_economic_events',lambda value,**kw:discover(value,rule_version='rss-event-first-v2'))
    monkeypatch.setattr(engine,'RULE_VERSION','rss-event-first-v2')
    code,old=evaluate(opts,now=at)
    assert code==0 and old['economic_changes_count']==1
    saved=Path(old['private_report_file']);pin=sha256(saved.read_bytes()).hexdigest()
    standard=export_discovery(root,as_of=at,now=at)
    monkeypatch.setattr(engine,'discover_economic_events',discover)
    monkeypatch.setattr(engine,'RULE_VERSION',current)
    later=at+timedelta(minutes=1)
    code,new=evaluate(opts,now=later)
    assert code==0 and new['economic_changes_count']==3 and new['theme_versions_created']==2
    assert _validate_report(old,later)==at
    assert sha256(saved.read_bytes()).hexdigest()==pin
    assert export_discovery(root,as_of=at,now=later)==standard
    assert read_discovery(root,as_of=at,now=later,include_common_causes=True)['common_cause_connections']['groups']==[]
    assert view(root,later)['common_cause_connections']['groups']
    bad=deepcopy(new);bad['rule_version']='rss-event-first-v2'
    with pytest.raises(SourceShareError):_validate_report(bad,later)
    bad=deepcopy(new)
    row=next(r for r in bad['results'] if r['headline']==A)
    row['economic_discovery'][0]['discovery']['action_evidence']['start']=0
    with pytest.raises(SourceShareError):_validate_report(bad,later)


def test_conflicting_future_missing_sources_and_wrong_actor_cannot_supply_policy(tmp_path):
    root,*_,at,_=analyzed(tmp_path,(A,B))
    themes=ThemeStore(root/'theme_history').search(now=at)
    parents=tuple((p.name,p) for p in (root/'feed_analysis').glob('d_*'))
    reports,_=scan_saved_analysis(root/'none',as_of=at,now=at,additional_roots=parents)
    titles={(r['provider'],r['source_event_sha256'],r['source_title_sha256']):r for r in reports}
    candidates=read_discovery(root,as_of=at,now=at)['candidates']
    before=deepcopy((themes,titles,candidates))
    def build(ts=themes,rs=titles):
        return build_discovery_causes(ts,rs,candidates,as_of=at,since=at,now=at)['groups']
    assert build()
    for field in ('invalidated_event_ids','conflicting_event_ids'):
        bad=deepcopy(themes);bad[0][field]=bad[0]['event_ids']
        assert build(bad)==[]
    future=deepcopy(titles)
    for r in future.values():r['available_at']=(at+timedelta(seconds=1)).isoformat()
    assert build(rs=future)==[] and build(rs={})==[]
    assert (themes,titles,candidates)==before


def test_http_and_screen_show_policy_action_sources_and_counterconditions(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    w,reg,provider,at=source(tmp_path,(A+' 계획',B))
    documents=tmp_path/'documents';root=documents/'economic_discovery'
    assert evaluate(flags(w,provider,root),now=at)[0]==0
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,news_search_workspaces=(w,))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def get(query):
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/economic-discovery?'+query) as r:return json.load(r)
    try:
        assert 'common_cause_connections' not in get('')
        data=get('common_causes=1')['common_cause_connections'];g,=data['groups']
        for t in get('common_causes=1&export=1')['ThemeCandidates']:
            assert t['discovery_common_causes']['groups']==[g]
    finally:server.shutdown();server.server_close();thread.join(2)
    script=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,txt){return {textContent:txt||'',children:[],append(...x){this.children.push(...x)}}}
const place=node('div'),ctx={node,economicActionLabels:{INVESTMENT_EXECUTION:'투자 집행',PRODUCTION_START:'생산 개시'}};
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
vm.runInNewContext(code.slice(code.indexOf('function renderDiscoveryCauses(')),ctx);
ctx.renderDiscoveryCauses(place,data);
function text(n){return [n.textContent,...n.children.flatMap(text)].join(' ')}
for(const s of ['첨단칩통제법','미국','정책','HBM','DRAM','투자 집행','계획','반증','원문'])assert(text(place).includes(s));
"""
    subprocess.run(['node','-e',script],input=json.dumps(data),text=True,capture_output=True,
                   cwd=Path(__file__).resolve().parent.parent,check=True)


@pytest.mark.parametrize('tail',[
    '다른전자는 생산을 시작했다',
    'DRAM 수입 규제 폐지 및 생산을 시작했다',
    '공급 계약을 체결하고 생산을 시작했다',
])
def test_distinct_subject_or_second_action_is_not_collapsed_to_one_event(tail):
    assert discover(text(tail=tail))==[]
