"""Same economic event -> literal recipient/purpose -> user-visible connection.

No new industry detector or company lookup. Older event IDs/claims remain
unchanged; newly interpreted source links are available only after analysis.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode

import pytest
from newscatalystos.economic_discovery import discover_economic_events as discover,connect_discovered_source_context as connect
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.feed_analysis_delivery import _validate_report
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore
from scripts.run_feed_analysis import evaluate
from test_economic_discovery import flags,T
from test_new_source_adapter import registry
from test_federated_news_search import setup_workspace,collect,fingerprint

SUB='Department of Commerce Awards CHIPS Incentives to a Subsidiary of Alpha Mining (Beta Metals) to Support a State-of-the-Art Smelter and Critical Minerals Processing Facility in the United States'
PURPOSE='Department of Commerce Announces Finalization of CHIPS Incentives with Sample Works to Enhance Domestic Production Capacity of Key Components for U.S. Semiconductor Manufacturing'
UNKNOWN='Department of Commerce Announces Finalization of CHIPS R&D Award with SampleQuantum'


def test_recipient_parent_and_industry_are_exact_source_spans_not_new_events():
    events=discover(SUB);original=deepcopy(events)
    links=connect(SUB,events);value,=links;child,=value['company_links']
    assert child['source_name']=='Beta Metals' and child['source_parent_name']=='Alpha Mining'
    assert child['parent_is_direct_recipient'] is False and child['ownership_verified'] is False
    assert child['official_entity_id'] is None and not child['verified_real_benefit']
    for span in (child['name_evidence'],child['relation_evidence'],child['parent_name_evidence'],value['purpose_evidence']):
        assert SUB[span['start']:span['end']]==span['text']
        assert sha256(span['text'].encode()).hexdigest()==span['sha256']
    assert events==original and value['new_economic_event'] is False
    assert value['event_index']==0 and value['event_identity_changed'] is False
    assert value['industry_links'][0]['industry']=='CRITICAL_MINERALS'
    assert connect(SUB,[])==[]  # context never admits an economic event


def test_industry_uses_same_action_purpose_instead_of_company_or_program_name(monkeypatch):
    events=discover(PURPOSE);assert events[0]['change']['industry_tags']==[]
    proof,=connect(PURPOSE,events)
    assert proof['company_links']==[]
    tag,=proof['industry_links'];assert tag['industry']=='SEMICONDUCTOR'
    assert tag['source_phrase']=='Semiconductor' and tag['source_phrase'] in proof['purpose_evidence']['text']
    assert tag['status']=='SOURCE_WORD_HINT_NOT_SUPPLY_CHAIN_VALIDATION'
    assert connect(UNKNOWN,discover(UNKNOWN))==[]
    monkeypatch.setattr('newscatalystos.economic_discovery.HINTS',())
    assert len(discover(PURPOSE))==1 and connect(PURPOSE,discover(PURPOSE))==[]
    # Recipient binding is independent of an industry dictionary.
    c,=connect(SUB,discover(SUB));assert c['company_links'][0]['source_name']=='Beta Metals'
    assert c['industry_links']==[]


@pytest.mark.parametrize('title',[
    'NIST Awards Grants to a Subsidiary of Alpha Mining (NYSE: ALP) to Support Factory Equipment',
    'NIST Awards Grants to a Subsidiary of Alpha Mining to Support Factory Equipment',
    'NIST Awards Grants to a Subsidiary of Alpha Mining (Beta Metals) and Other Works to Support Factory Equipment',
    'NIST Awards Grants to a Subsidiary of Alpha Mining (Beta and Delta Metals) to Support Factory Equipment',
    'NIST Awards Grants with Other Works to a Subsidiary of Alpha Mining (Beta Metals) to Support Factory Equipment',
    'NIST Awards Grants to a Subsidiary of Alpha Mining (Beta Metals); Other Works to Support Semiconductors',
    'NIST Awards Grants to a Subsidiary of Alpha Mining (Beta Metals). Another company plans expansion',
    'Department of Commerce Announces Finalization of CHIPS Incentives with Sample Works; Another Company to Enhance Semiconductor Manufacturing',
])
def test_missing_or_ambiguous_parentheses_do_not_create_recipient(title):
    values=connect(title,discover(title))
    assert all(not v['company_links'] for v in values)


def test_short_purpose_not_treated_as_company_when_named_subsidiary_is_explicit():
    title='NIST Awards Grants to a Subsidiary of Alpha Mining (Beta Metals) to Support New Unknown Materials'
    records=discover(title)
    linked,=connect(title,records)
    assert linked['company_links'][0]['source_name']=='Beta Metals'
    assert linked['industry_links']==[]
    assert all(p['source_name']!='Support New Unknown Materials' for p in linked['company_links'])


def data_source(tmp_path):
    reg=registry();provider=reg.providers[0].provider_id
    w=setup_workspace(tmp_path,'core',reg)
    collect(w,reg,provider,[(str(i),text,'https://gov.example.org/context/'+str(i))
        for i,text in enumerate((SUB,PURPOSE,UNKNOWN))],at=T)
    return w,reg,provider


def test_old_reports_readable_new_links_have_separate_PIT_without_theme_duplication(tmp_path,monkeypatch):
    import scripts.run_feed_analysis as runner
    w,reg,provider=data_source(tmp_path);root=tmp_path/'discovery'
    opts=flags(w,provider,root)
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    publish=runner.publish_feed_analysis
    def old_format(report,*args,**kwargs):
        for r in report['results']:r.pop('discovery_source_connections',None)
        return publish(report,*args,**kwargs)
    monkeypatch.setattr(runner,'publish_feed_analysis',old_format)
    code,old=evaluate(opts,now=at);assert code==0
    assert _validate_report(old,at)==at
    old_view=read_discovery(root,as_of=at,now=at)
    old_export=json.loads(export_discovery(root,as_of=at,now=at))
    old_themes=ThemeStore(root/'theme_history').search(now=at)
    assert 'Beta Metals' not in {n for c in old_view['candidates'] for n in c['source_companies']}
    parent=next(c for c in old_view['candidates'] if c['source_companies']==['Sample Works'])
    assert parent['industry_tags']==[]
    monkeypatch.setattr(runner,'publish_feed_analysis',publish)
    later=at+timedelta(minutes=1);pins=fingerprint(w.registry_path.parent.parent)
    code,current=evaluate(opts,now=later)
    assert code==0 and current['theme_versions_created']==0
    assert _validate_report(current,later)==later
    assert ThemeStore(root/'theme_history').search(now=later)==old_themes
    before=fingerprint(root)
    live=read_discovery(root,as_of=later,now=later)
    prior=read_discovery(root,as_of=at,now=later)
    assert prior['counts']==old_view['counts']
    assert live['counts']['events']==prior['counts']['events']==3
    assert live['counts']['topics']==prior['counts']['topics']==3
    recipient=next(c for c in live['candidates'] if 'Beta Metals' in c['source_companies'])
    assert recipient['source_companies']==['Beta Metals'] and 'Alpha Mining' not in recipient['source_companies']
    assert recipient['original_source_companies']==[]
    assert recipient['context_connected_at']==later.isoformat()
    assert recipient['first_observed_at']==at.isoformat()
    refined=next(c for c in live['candidates'] if c['source_companies']==['Sample Works'])
    assert refined['industry_tags']==['SEMICONDUCTOR'] and refined['original_industry_tags']==[]
    assert live['counts']['unclassified_topics']==prior['counts']['unclassified_topics']-1
    assert any(c['source_companies']==['SampleQuantum'] and c['industry_tags']==[] for c in live['candidates'])
    new_export=json.loads(export_discovery(root,as_of=later,now=later))
    assert {t['theme_id'] for t in new_export['ThemeCandidates']}=={t['theme_id'] for t in old_export['ThemeCandidates']}
    for theme in new_export['ThemeCandidates']:
        original=next(t for t in old_export['ThemeCandidates'] if t['theme_id']==theme['theme_id'])
        for k in ('event_ids','entity_ids','company_links','industry_tags','scores','source_refs'):
            assert theme[k]==original[k]
        ctx=theme.get('discovery_source_context')
        if ctx:
            assert theme['decision_at']==ctx['available_at']==later.isoformat()
            assert ctx['original_theme_decision_at']==at.isoformat()
            assert not ctx['new_economic_event'] and not ctx['ownership_or_benefit_verified']
    assert not any('discovery_source_context' in t for t in json.loads(export_discovery(root,as_of=at,now=later))['ThemeCandidates'])
    assert fingerprint(root)==before and fingerprint(w.registry_path.parent.parent)==pins
    bad=deepcopy(current)
    row=next(r for r in bad['results'] if r['discovery_source_connections'] and r['discovery_source_connections'][0]['company_links'])
    row['discovery_source_connections'][0]['company_links'][0]['source_name']='Wrong Company'
    with pytest.raises(SourceShareError):_validate_report(bad,later)
    code,repeat=evaluate(opts,now=later+timedelta(minutes=1))
    assert code==0 and repeat['theme_versions_created']==0
    same=read_discovery(root,as_of=later+timedelta(minutes=1),now=later+timedelta(minutes=1))
    child=next(c for c in same['candidates'] if c['source_companies']==['Beta Metals'])
    assert child['context_connected_at']==later.isoformat()
    assert child['source_context_connections']==recipient['source_context_connections']


def test_http_discovery_and_export_show_roles_not_inferred_parent_benefit(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    w,reg,provider=data_source(tmp_path);docs=tmp_path/'documents';root=docs/'economic_discovery'
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    assert evaluate(flags(w,provider,root),now=at)[0]==0
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs,news_search_workspaces=(w,))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    pins=fingerprint(root)
    try:
        for params in ({},{'export':'1'}):
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/economic-discovery?'+urlencode(params),timeout=20) as response:
                assert response.status==200;data=json.load(response)
            if not params:
                linked=next(c for c in data['candidates'] if 'Beta Metals' in c['source_companies'])
                assert linked['source_context_connections'][0]['company_links'][0]['source_parent_name']=='Alpha Mining'
                assert linked['source_companies']==['Beta Metals']
            else:
                assert any(t.get('discovery_source_context',{}).get('source_named_companies')==['Beta Metals'] for t in data['ThemeCandidates'])
    finally:server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(root)==pins


def test_display_shows_recipient_relation_purpose_and_new_interpretation_time():
    js=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(t,c,s){return {textContent:s||'',children:[],append(...a){this.children.push(...a)},replaceChildren(...a){this.children=a}}}
const els={};for(const k of ['economic-discovery','discovery-panel','discovery-summary'])els[k]=node();
const ctx={node,$:k=>els[k],economicActionLabels:{POLICY_CHANGE:'정책지원'},renderCatalystMaterial:()=>{}};
vm.runInNewContext(src.slice(src.indexOf('function renderEconomicDiscovery(')),ctx);
ctx.renderEconomicDiscovery({status:'READY',counts:{topics:1,events:1,unclassified_topics:0},candidates:[{watch_topic:'Unknown new product',industry_links:[],source_companies:['Beta Metals'],economic_actions:['POLICY_CHANGE'],first_observed_at:'earlier',source_evidence:[],source_context_connections:[{available_at:'later',company_links:[{source_name:'Beta Metals',source_parent_name:'Alpha Mining',relation_evidence:{text:'a subsidiary of Alpha Mining (Beta Metals)'}}],purpose_evidence:{text:'critical minerals'}}]}]});
function text(n){return [n.textContent,...n.children.flatMap(text)].join(' ')}
const s=text(els['economic-discovery']);for(const item of ['Beta Metals','Alpha Mining','later','새 발표 아님','수혜주로 승격하지 않음','critical minerals'])assert(s.includes(item));
console.log('EXACT_SOURCE_ROLE_CONTEXT_UI');
'''
    subprocess.run(['node','-e',js],cwd=Path(__file__).resolve().parent.parent,capture_output=True,text=True,check=True)
