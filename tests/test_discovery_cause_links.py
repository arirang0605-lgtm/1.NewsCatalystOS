"""Optional causal view reuses existing input/store/output, with synthetic news."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import json
import subprocess
import threading
from urllib.request import urlopen
from urllib.error import HTTPError

import pytest

from newscatalystos.discovery_watch import read_discovery, export_discovery
from newscatalystos.discovery_cause_links import build_discovery_causes
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.theme_emergence import ThemeStore
from test_discovery_launch_comparison import analyzed, source
from test_economic_discovery import flags
from test_federated_news_search import fingerprint
from scripts.run_feed_analysis import evaluate

A='가상전자, AI 서버용 HBM 수요 회복으로 신규 공장 투자 집행'
B='새빛소재, AI 서버용 DRAM 수요 회복으로 생산능력 확대'


def view(root, at, **kw):
    return read_discovery(root,as_of=at,now=at,include_common_causes=True,**kw)


def test_input_store_view_and_optional_export_keep_original_bytes_and_bind_sources(tmp_path):
    root,w,opts,at,report=analyzed(tmp_path,(A,B))
    before=fingerprint(tmp_path)
    original=export_discovery(root,as_of=at,now=at)
    old=read_discovery(root,as_of=at,now=at)
    result=view(root,at);group,=result['common_cause_connections']['groups']
    assert group['products']==['DRAM','HBM'] and group['subject']=='AI 서버'
    assert group['economic_actions']==['CAPACITY_ADDITION','INVESTMENT_EXECUTION']
    assert group['reported_action_count']==2 and group['planned_action_count']==0
    assert group['conditional_paths'] and group['source_cause_link_explicit']
    assert not group['supply_chain_transaction_verified'] and not group['verified_real_benefit']
    assert result['theme_outlook']==old['theme_outlook']
    for s in group['source_evidence']:
        e=s['cause_evidence'];assert s['headline'][e['start']:e['end']]==e['text']
        assert s['report_sha256'] and s['source_theme_snapshots']
    exported=json.loads(export_discovery(root,as_of=at,now=at,include_common_causes=True))
    plain=json.loads(original)
    for new,prev in zip(exported['ThemeCandidates'],plain['ThemeCandidates']):
        extension=new.pop('discovery_common_causes')
        assert extension['groups']==[group] and not extension['interpretation_is_historical_record']
        assert new==prev
    assert export_discovery(root,as_of=at,now=at)==original
    assert fingerprint(tmp_path)==before and report['semantic_ai_attempts']==0


@pytest.mark.parametrize('other',[
    B.replace('AI 서버용','스마트폰용'),
    B.replace('DRAM','HBM'),
    B.replace('수요 회복으로','수요 증가에 따라'),
    B.replace('수요 회복으로','주문 회복으로'),
    B.replace('AI 서버용 ',''),
    B.replace('생산능력 확대','NAND 생산능력 확대'),
    B.replace('회복으로','회복 전망으로'),
    B.replace('생산능력 확대','생산능력을 확대하지 않았다'),
    '새빛소재, DRAM 생산능력 확대',
])
def test_different_scope_driver_basis_product_or_missing_denied_cause_cannot_join(tmp_path,other):
    root,*_,at,report=analyzed(tmp_path,(A,other))
    assert view(root,at)['common_cause_connections']['groups']==[]


def test_plan_is_not_execution(tmp_path):
    root,*_,at,_=analyzed(tmp_path/'planned',(A+' 계획',B))
    g,=view(root,at)['common_cause_connections']['groups']
    assert g['planned_action_count']==1 and g['reported_action_count']==1


def test_historical_sources_do_not_borrow_later_actor_and_default_export_stays_exact(tmp_path):
    w,reg,provider,at=source(tmp_path,(A,B))
    root=tmp_path/'discovery';opts=flags(w,provider,root)
    from newscatalystos.feed_analysis import _sources
    first=next(r for r in _sources(w.inbox_root,w.poll_state,reg,at) if r['headline']==A)
    opts.event_id=first['event_id'];opts.title_sha256=first['title_sha256']
    assert evaluate(opts,now=at)[0]==0
    original=export_discovery(root,as_of=at,now=at)
    assert view(root,at)['common_cause_connections']['groups']==[]
    later=at+timedelta(minutes=1)
    opts.event_id=None;opts.title_sha256=None
    assert evaluate(opts,now=later+timedelta(seconds=1))[0]==0
    end=later+timedelta(seconds=2)
    assert view(root,end)['common_cause_connections']['groups']
    assert read_discovery(root,as_of=at,now=end,include_common_causes=True)['common_cause_connections']['groups']==[]
    assert export_discovery(root,as_of=at,now=end)==original


def test_conflicting_invalidated_future_and_missing_report_cannot_supply_cause(tmp_path):
    root,*_,at,_=analyzed(tmp_path,(A,B))
    themes=ThemeStore(root/'theme_history').search(now=at)
    parents=tuple((p.name,p) for p in (root/'feed_analysis').glob('d_*'))
    reports,_=scan_saved_analysis(root/'none',as_of=at,now=at,additional_roots=parents)
    titles={(r['provider'],r['source_event_sha256'],r['source_title_sha256']):r for r in reports}
    candidates=read_discovery(root,as_of=at,now=at)['candidates']
    before=deepcopy((themes,titles,candidates))
    assert build_discovery_causes(themes,titles,candidates,as_of=at,since=at,now=at)['groups']
    for field in ('invalidated_event_ids','conflicting_event_ids'):
        ts=deepcopy(themes)
        ts[0][field]=ts[0]['event_ids']
        assert build_discovery_causes(ts,titles,candidates,as_of=at,since=at,now=at)['groups']==[]
    future=deepcopy(titles)
    for r in future.values():r['available_at']=(at+timedelta(seconds=1)).isoformat()
    assert build_discovery_causes(themes,future,candidates,as_of=at,since=at,now=at)['groups']==[]
    assert build_discovery_causes(themes,{},candidates,as_of=at,since=at,now=at)['groups']==[]
    assert (themes,titles,candidates)==before


def test_http_optional_view_export_and_UI_show_same_cause_plan_and_counterconditions(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    from datetime import datetime
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
        with pytest.raises(HTTPError):get('common_causes=invalid')
    finally:server.shutdown();server.server_close();thread.join(2)
    script=r'''const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,txt){return {textContent:txt||'',children:[],append(...x){this.children.push(...x)}}}
const place=node('div'),ctx={node,economicActionLabels:{INVESTMENT_EXECUTION:'투자 집행',CAPACITY_ADDITION:'생산능력 확대'}};
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
vm.runInNewContext(code.slice(code.indexOf('function renderDiscoveryCauses(')),ctx);
ctx.renderDiscoveryCauses(place,data);
function text(n){return [n.textContent,...n.children.flatMap(text)].join(' ')}
for(const s of ['AI 서버','HBM','DRAM','투자 집행','계획','반증','원문'])assert(text(place).includes(s));
'''
    subprocess.run(['node','-e',script],input=json.dumps(data),text=True,capture_output=True,
        cwd=Path(__file__).resolve().parent.parent,check=True)
