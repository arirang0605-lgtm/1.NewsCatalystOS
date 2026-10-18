"""Existing news -> exact product/party -> repeat/revision/phase comparisons.

No fuzzy company aliases, translations, event merging, market novelty score or
new producer writes. Sources keep their original IDs and historical visibility.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode

import pytest
from scripts.run_feed_analysis import evaluate
from newscatalystos.feed_analysis import _sources
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.discovery_launch_comparison import compare_launch_observations
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore,_bytes
from test_new_source_adapter import registry
from test_federated_news_search import setup_workspace,collect,fingerprint
from test_economic_discovery import flags

KO='ACME, 새로운 장치 플랫폼 기반 ‘NovaProbe’ 출시'
EN='ACME Launches NovaProbe, First System on New Platform'


def source(tmp_path,titles=(KO,EN),*,same_doc=False):
    reg=registry();provider=reg.providers[0].provider_id
    w=setup_workspace(tmp_path,'core',reg)
    first=datetime.now(timezone.utc)-timedelta(hours=2)
    if same_doc:
        for i,title in enumerate(titles):
            collect(w,reg,provider,[('fixed',title,'https://gov.example.org/release/fixed')],at=first+timedelta(minutes=i*30))
    else:
        collect(w,reg,provider,[(str(i),title,'https://gov.example.org/release/'+str(i)) for i,title in enumerate(titles)],at=first)
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    return w,reg,provider,at


def analyzed(tmp_path,titles=(KO,EN)):
    w,reg,provider,at=source(tmp_path,titles)
    root=tmp_path/'discovery';opts=flags(w,provider,root)
    code,result=evaluate(opts,now=at);assert code==0
    return root,w,opts,at,result


def test_exact_company_and_product_cross_language_titles_are_compared_not_merged(tmp_path):
    root,w,opts,at,report=analyzed(tmp_path)
    allpins=fingerprint(tmp_path)
    view=read_discovery(root,as_of=at,now=at)
    group,=view['launch_comparisons'];pair,=group['pairs']
    assert group['source_company_name']=='ACME' and group['source_product_name']=='NovaProbe'
    assert group['source_observation_count']==2 and view['counts']['events']==2
    assert pair['status']=='SAME_COMPANY_PRODUCT_ONLY' and pair['scripts_differ']
    assert not pair['same_market_announcement_verified'] and not pair['translation_verified']
    assert pair['independent_market_event_count'] is None and pair['additional_new_material_supported'] is None
    assert pair['observed_title_time_gap_seconds']==0 and not pair['observed_times_are_release_dates']
    assert group['source_rows_merged'] is False and group['leader_score_adjustment'] is None
    assert group['selection_owner']=='EraLeader' and group['orders_enabled'] is False
    for row in group['observations']:
        for key in ('company_evidence','product_evidence'):
            proof=row[key]
            assert row['headline'][proof['start']:proof['end']]==proof['text']
            assert sha256(proof['text'].encode()).hexdigest()==proof['sha256']
        assert row['official_entity_id'] is None and row['reported_published_at'] is None
    assert all(group['comparison_group_id'] in c['launch_comparison_group_ids'] for c in view['candidates'])
    assert read_discovery(root,as_of=at,now=at)['launch_comparisons']==[group]
    assert read_discovery(root,as_of=at,now=at+timedelta(days=20))['launch_comparisons']==[group]
    assert fingerprint(tmp_path)==allpins
    original=ThemeStore(root/'theme_history').search(now=at)
    exported=json.loads(export_discovery(root,as_of=at,now=at))
    for t in exported['ThemeCandidates']:
        old=next(x for x in original if x['theme_id']==t['theme_id'])
        for field in ('event_ids','entity_ids','industry_tags','source_refs','company_links','scores'):
            assert t[field]==old[field]
        added=t['discovery_launch_comparison']
        assert added['comparison_groups']==[group] and added['new_economic_event'] is False
        assert added['source_theme_sha256']==sha256(_bytes(old)).hexdigest()
    assert fingerprint(tmp_path)==allpins
    _,again=evaluate(opts,now=at+timedelta(minutes=1));assert again['theme_versions_created']==0
    repeated=read_discovery(root,as_of=at+timedelta(minutes=1),now=at+timedelta(minutes=1))
    assert repeated['counts']==view['counts']
    assert repeated['launch_comparisons'][0]['comparison_group_id']==group['comparison_group_id']
    assert repeated['launch_comparisons'][0]['pairs'][0]['comparison_id']==pair['comparison_id']


@pytest.mark.parametrize('left,right',[
    (KO,'OTHER Launches NovaProbe'),
    (KO,'ACME Launches NovaProbe 2'),
    ('ACME, ‘NovaProbe 11’ 출시','ACME Launches NovaProbe 12'),
    ('ACME, ‘Nova-Probe’ 출시','ACME Launches NovaProbe'),
    (KO,'애크미, ‘NovaProbe’ 출시'),
    ('‘NovaProbe’ 출시',EN),
    ('가상테크, ‘NovaProbe’ 출시',EN),
    ('ACME, ‘Probe’ 출시',EN),
])
def test_missing_company_alias_similar_product_and_versions_are_not_assumed_same(tmp_path,left,right):
    root,w,opts,at,_=analyzed(tmp_path,(left,right))
    view=read_discovery(root,as_of=at,now=at)
    assert view['launch_comparisons']==[] and view['counts']['launch_comparison_groups']==0


def test_case_and_fullwidth_normalization_preserves_literal_matching_evidence(tmp_path):
    root,w,opts,at,_=analyzed(tmp_path,('ACME, ‘ＮｏｖａＰｒｏｂｅ’ 출시','acme Launches novaprobe'))
    group,=read_discovery(root,as_of=at,now=at)['launch_comparisons']
    assert group['pairs'][0]['same_market_announcement_verified'] is False
    # The existing source adapter normalizes display text, while retaining
    # the raw source-title SHA separately. Comparison quotes that display.
    assert {x['product_evidence']['text'] for x in group['observations']}=={'NovaProbe','novaprobe'}
    row=next(x for x in group['observations'] if x['product_evidence']['text']=='NovaProbe')
    assert row['source_title_sha256']==sha256('ACME, ‘ＮｏｖａＰｒｏｂｅ’ 출시'.encode()).hexdigest()
    assert row['headline_sha256']==sha256(row['headline'].encode()).hexdigest()
    assert row['source_title_sha256']!=row['headline_sha256']


def test_identical_title_content_does_not_count_as_independent_new_evidence(tmp_path):
    root,w,opts,at,_=analyzed(tmp_path,(EN,EN))
    view=read_discovery(root,as_of=at,now=at);group,=view['launch_comparisons'];pair,=group['pairs']
    assert pair['status']=='IDENTICAL_TITLE_CONTENT' and pair['title_content_same']
    assert pair['additional_new_material_supported'] is False and pair['news_use']=='NO_NEW_TITLE_CONTENT'
    assert pair['independent_market_event_count'] is None and not pair['same_market_announcement_verified']
    assert len(group['observations'])==2 and not group['source_rows_merged']


def test_phase_difference_preserved_not_certified_realization_or_new_rank(tmp_path):
    root,w,opts,at,_=analyzed(tmp_path,('ACME, ‘NovaProbe’ 출시 계획',EN))
    group,=read_discovery(root,as_of=at,now=at)['launch_comparisons'];pair,=group['pairs']
    assert pair['status']=='REPORTED_PHASE_DIFFERENCE' and pair['source_phase_differs']
    assert {x['phase'] for x in group['observations']}=={'PLANNED','SOURCE_REPORTED'}
    assert not pair['economic_change_confirmed'] and group['leader_score_adjustment'] is None


def test_same_source_title_revision_PIT_and_older_export_do_not_borrow_later_news(tmp_path):
    w,reg,provider,at=source(tmp_path,(KO,EN),same_doc=True)
    root=tmp_path/'discovery';opts=flags(w,provider,root)
    rows=_sources(w.inbox_root,w.poll_state,reg,at)
    first=next(r for r in rows if r['headline']==KO);last=next(r for r in rows if r['headline']==EN)
    assert first['event_id']==last['event_id']
    opts.event_id=first['event_id'];opts.title_sha256=first['title_sha256']
    assert evaluate(opts,now=at)[0]==0
    before=read_discovery(root,as_of=at,now=at);old_export=json.loads(export_discovery(root,as_of=at,now=at))
    assert before['launch_comparisons']==[]
    later=at+timedelta(minutes=2);opts.title_sha256=last['title_sha256']
    assert evaluate(opts,now=later)[0]==0
    pins=fingerprint(tmp_path)
    view=read_discovery(root,as_of=later,now=later);group,=view['launch_comparisons'];pair,=group['pairs']
    assert pair['source_document_same'] and pair['status']=='SAME_SOURCE_TITLE_REVISION'
    assert group['basis_available_at']==later.isoformat()
    assert read_discovery(root,as_of=at,now=later)['launch_comparisons']==[]
    assert read_discovery(root,as_of=at,now=later)['counts']==before['counts']
    historic=json.loads(export_discovery(root,as_of=at,now=later))
    assert historic==old_export
    now=json.loads(export_discovery(root,as_of=later,now=later))
    assert all(t['decision_at']>=later.isoformat() for t in now['ThemeCandidates'])
    assert all(t['discovery_launch_comparison']['original_theme_decision_at']<=t['decision_at'] for t in now['ThemeCandidates'])
    assert fingerprint(tmp_path)==pins


def test_distant_local_observation_dates_do_not_prove_one_launch_or_product_identity(tmp_path):
    root,w,opts,at,_=analyzed(tmp_path)
    themes=ThemeStore(root/'theme_history').search(now=at)
    parents=tuple((p.name,p) for p in (root/'feed_analysis').glob('d_*'))
    reports,_=scan_saved_analysis(root/'none',as_of=at,now=at,additional_roots=parents)
    titles={(r['provider'],r['source_event_sha256'],r['source_title_sha256']):r for r in reports}
    original=deepcopy(themes)
    first=themes[0]['source_refs'][0];first['source_available_at']=(at-timedelta(days=90)).isoformat()
    group,=compare_launch_observations(themes,titles,as_of=at,now=at)
    assert group['pairs'][0]['observed_title_time_gap_seconds']>80*86400
    assert group['pairs'][0]['status']=='SAME_COMPANY_PRODUCT_ONLY'
    assert not group['pairs'][0]['same_market_announcement_verified']
    with pytest.raises(SourceShareError):compare_launch_observations(themes,titles,as_of=at+timedelta(seconds=1),now=at)
    # Duplicating a stored reference or theme does not duplicate the comparison.
    group2,=compare_launch_observations(original+deepcopy(original),titles,as_of=at,now=at)
    assert group2['source_observation_count']==2 and group2['comparison_pair_count']==1


def test_current_http_comparison_and_standard_export_are_read_only(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    w,reg,provider,at=source(tmp_path);docs=tmp_path/'docs';root=docs/'economic_discovery'
    assert evaluate(flags(w,provider,root),now=at)[0]==0
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs,news_search_workspaces=(w,))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();pins=fingerprint(tmp_path)
    try:
        for query in ({},{'export':'1'}):
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/economic-discovery?'+urlencode(query),timeout=20) as r:
                assert r.status==200;data=json.load(r)
            if query:assert all(t['discovery_launch_comparison']['comparison_groups'] for t in data['ThemeCandidates'])
            else:
                assert len(data['launch_comparisons'])==1
                assert data['counts']['compared_launch_source_observations']==2
                assert data['launch_comparisons'][0]['pairs'][0]['status']=='SAME_COMPANY_PRODUCT_ONLY'
    finally:server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(tmp_path)==pins


def test_comparison_UI_shows_two_originals_exact_evidence_and_uncertainty():
    js=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(t,c,txt){return {textContent:txt||'',children:[],append(...x){this.children.push(...x)}}}
const ctx={node,economicPhaseLabels:{PLANNED:'계획',SOURCE_REPORTED:'출시보도'}};
vm.runInNewContext(s.slice(s.indexOf('function renderLaunchComparisons(')),ctx);
const place=node();
ctx.renderLaunchComparisons(place,[{source_company_name:'ACME',source_product_name:'NovaProbe<script>',source_observation_count:2,pairs:[{reason:'같은 회사와 제품이지만 별도 발표인지 미확인',scripts_differ:true,source_phase_differs:true}],observations:[{headline:'원문 A',company_evidence:{text:'ACME'},product_evidence:{text:'NovaProbe'},source_available_at:'earlier',phase:'PLANNED',source_title_sha256:'a'.repeat(64),source_url:'https://example.org/1'},{headline:'Original B',company_evidence:{text:'ACME'},product_evidence:{text:'NovaProbe'},source_available_at:'later',phase:'SOURCE_REPORTED',source_title_sha256:'b'.repeat(64),source_url:'https://example.org/2'}]}]);
function text(n){return [n.textContent,...n.children.flatMap(text)].join(' ')}
const all=text(place);for(const phrase of ['원문 A','Original B','별도 발표인지 미확인','계획·발표 단계가 다름','번역·재배포 여부는 미확인','NovaProbe<script>','점수를 변경하지 않았습니다'])assert(all.includes(phrase));
console.log('SIDE_BY_SIDE_SOURCE_COMPARISON_NO_EVENT_MERGE_UI');
'''
    subprocess.run(['node','-e',js],cwd=Path(__file__).resolve().parent.parent,check=True,capture_output=True,text=True)
