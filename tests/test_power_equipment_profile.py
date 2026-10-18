"""Optional V1.1 input -> stored action/theme -> material delivery -> exact quote.

Synthetic headlines are never presented as real market observations. Existing
RSS rights/ACK/PIT are reused and semiconductor remains the untouched default.
"""
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from newscatalystos.power_equipment import extract_power_equipment_changes as extract,matched_equipment
from newscatalystos.feed_analysis import analyze_completed_feed
from newscatalystos.feed_analysis_delivery import _validate_report
from newscatalystos.catalyst_material import materials_for_store
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_analysis import parser,evaluate
from test_new_source_adapter import registry
from test_federated_news_search import setup_workspace,collect,fingerprint

CASES=(
 ('가상전기는 초고압 변압기 공급계약을 체결했다','변압기','CONTRACT','SOURCE_REPORTED'),
 ('합성중공업, 변압기 신규 생산공장에 200억원 투자 결정','변압기','INVESTMENT','PLANNED'),
 ('합성전기는 차단기 생산능력을 2배 확대했다','차단기','CAPACITY_ADDITION','SOURCE_REPORTED'),
 ('가상일렉트릭, 배전반 양산을 시작했다','배전설비','PRODUCTION_START','SOURCE_REPORTED'),
 ('가상전기는 변압기 납품을 개시할 계획이다','변압기','DELIVERY_START','PLANNED'),
 ('합성전기는 수배전 설비 납품을 시작했다','배전설비','DELIVERY_START','SOURCE_REPORTED'),
 ('합성중공업, 변압기 생산공장 투자를 집행했다','변압기','INVESTMENT_EXECUTION','SOURCE_REPORTED'),
)


@pytest.mark.parametrize('title,topic,action,phase',CASES)
def test_source_explicit_power_equipment_action(title,topic,action,phase):
    row,=extract(title)
    assert row['topic']==topic and row['action']==action and row['phase']==phase
    assert row['industry_tags']==['POWER_EQUIPMENT'] and row['entity_ids']
    assert row['source_paragraph_sha256']==sha256(title.encode()).hexdigest()
    assert row['evidence_level']=='REPORTED' and row['verified_economic_effect'] is False
    assert matched_equipment(title)


@pytest.mark.parametrize('title',(
 '가상전기는 데이터센터를 건설했다',
 '가상전기는 전력망 확대로 수혜가 기대된다',
 '가상전자, 전력반도체 생산을 시작했다',
 '가상전자, Transformer AI 모델을 출시했다',
 '가상전기는 변압기 공장 투자를 검토한다',
 '가상전기는 변압기 공급계약 체결을 부인했다',
 '가상전기는 변압기 공급계약을 체결하지 않았다',
 '가상전기는 변압기 공급계약을 취소했다',
 '가상전기는 차단기 생산 개시 기념행사를 열었다',
 '가상전기는 변압기 자사주 투자를 결정했다',
 '가상전기는 변압기와 차단기 공급계약을 체결했다',
 '정부는 변압기 공급계약을 체결했다',
 '가상전기는 변압기 수요를 언급했고 다른전기는 HBM 양산을 시작했다',
 '가상전기는 HBM 양산 개시 후 변압기 시장을 살핀다',
 '변압기 공급계약 체결',
))
def test_no_inferred_supplier_or_market_beneficiary(title):
    assert extract(title)==[]


def setup(tmp_path):
    reg=registry();provider=reg.providers[0].provider_id
    from newscatalystos.federated_news_search import TitleSearchWorkspace
    from test_federated_news_search import write_registry
    base=tmp_path/'source'
    w=TitleSearchWorkspace('core',base/'providers/authorized_sources.json',
        base/'state/incremental_feeds.sqlite3',base/'inbox/feed_triage')
    write_registry(w.registry_path,reg)
    at=datetime.now(timezone.utc)
    titles=[c[0] for c in CASES]+['가상전자, HBM 생산을 시작했다','초고압 변압기 시장 동향']
    collect(w,reg,provider,[(str(i),text,f'https://gov.example.org/equipment/{i}') for i,text in enumerate(titles)],at=at)
    later=datetime.now(timezone.utc)+timedelta(seconds=1)
    return w,reg,provider,later


def options(w,provider,work,theme):
    return parser().parse_args(['--registry',str(w.registry_path),'--inbox-root',str(w.inbox_root),
        '--state',str(w.poll_state),'--provider-id',provider,'--industry','POWER_EQUIPMENT',
        '--analysis-root',str(work),'--theme-root',str(theme),'--limit','100'])


def test_shared_pipeline_persists_report_themes_repeat_and_original_titles(tmp_path):
    w,reg,provider,at=setup(tmp_path)
    source_pins=fingerprint(w.registry_path.parent.parent)
    work=tmp_path/'power/feed_analysis/core';themes=tmp_path/'power/document_analysis/theme_history'
    opts=options(w,provider,work,themes)
    code,out=evaluate(opts,now=at)
    assert code==0 and out['economic_changes_count']==7
    assert len(out['results'])==9 and out['rule_version']=='rss-power-equipment-v1'
    assert out['source_fetch_calls']==0 and out['semantic_ai_attempts']==0
    assert all(not r['ai_eligible'] and not r['verified_beneficiary'] for r in out['results'])
    assert sum(bool(r['economic_changes']) for r in out['results'])==7
    assert _validate_report(json.loads(Path(out['private_report_file']).read_bytes()),at)==at
    stored=ThemeStore(themes).search(now=at)
    assert len(stored)>=3 and all(t['industry_tags']==['POWER_EQUIPMENT'] for t in stored)
    # No automatic V1 material expansion: the profile must be requested.
    assert materials_for_store(ThemeStore(themes),since=at-timedelta(days=1),as_of=at,now=at)=={}
    materials=materials_for_store(ThemeStore(themes),since=at-timedelta(days=1),as_of=at,now=at,industry='POWER_EQUIPMENT')
    assert len(materials)==len(stored)
    assert all(m['selection_owner']=='EraLeader' and m['investment_rank'] is None for m in materials.values())
    again,result=evaluate(opts,now=at+timedelta(minutes=1))
    assert again==0 and result['economic_changes_count']==7 and result['theme_versions_created']==0
    assert fingerprint(w.registry_path.parent.parent)==source_pins
    from newscatalystos.company_evidence import company_evidence
    t=next(t for t in stored if '가상전기' in t['entity_ids'] and t['economic_driver']=='UNKNOWN' and any(r['action']=='CONTRACT' for r in t['source_refs']))
    evidence=company_evidence(t,'가상전기',reports_root=work.parent,document_root=themes.parent,
        feeds=[{'registry':w.registry_path,'state':w.poll_state,'inbox':w.inbox_root}],jobs=[],now=at,as_of=at)
    assert evidence['items'] and all(r['status']=='READY' for r in evidence['items'])
    assert any(CASES[0][0]==r['excerpt'] for r in evidence['items'])
    assert all('FULL ARTICLE BODY NOT FOR STORAGE' not in (r['excerpt'] or '') for r in evidence['items'])


def test_default_semiconductor_unchanged_and_profiles_do_not_share_derived_states(tmp_path):
    w,reg,provider,at=setup(tmp_path)
    a=analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'original',provider_id=provider,now=at,limit=100)
    b=analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'explicit',provider_id=provider,now=at,limit=100,industry='SEMICONDUCTOR')
    assert a==b and 'analysis_industry' not in a and a['rule_version']=='rss-title-economic-v13'
    with pytest.raises(SourceShareError,match='separate empty'):
        analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'original',provider_id=provider,now=at,industry='POWER_EQUIPMENT')
    opts=options(w,provider,tmp_path/'power-analysis',tmp_path/'power-themes')
    assert evaluate(opts,now=at)[0]==0
    with pytest.raises(SourceShareError,match='industry root differs'):
        analyze_completed_feed(reg,w.inbox_root,w.poll_state,opts.analysis_root,provider_id=provider,now=at)
    opts.industry='SEMICONDUCTOR'
    assert evaluate(opts,now=at)[0]==4
    missing=options(w,provider,tmp_path/'missing',tmp_path/'no-theme');missing.analysis_root=None
    assert evaluate(missing,now=at)[0]==4 and not (tmp_path/'no-theme').exists()
    with pytest.raises(SourceShareError,match='source rules only'):
        analyze_completed_feed(reg,w.inbox_root,w.poll_state,tmp_path/'paid',now=at,industry='POWER_EQUIPMENT',allow_paid=True)
    assert not (tmp_path/'paid').exists()


def test_power_report_rejects_altered_company_action_or_phase(tmp_path):
    w,reg,provider,at=setup(tmp_path)
    code,out=evaluate(options(w,provider,tmp_path/'a',tmp_path/'t'),now=at)
    assert code==0
    for key,value in (('entity_ids',['다른전기']),('phase','PLANNED'),('topic','다른기기')):
        doc=deepcopy(out)
        row=next(r for r in doc['results'] if any(c['action']=='CONTRACT' for c in r['economic_changes']))
        row['economic_changes'][0][key]=value
        with pytest.raises(SourceShareError):_validate_report(doc,at)
    bad=options(w,provider,tmp_path/'later',tmp_path/'later-t')
    payload=json.loads(w.registry_path.read_bytes())
    for x in payload['providers']:x['approved']=False
    w.registry_path.write_text(json.dumps(payload))
    assert evaluate(bad,now=at)[0]==4 and not bad.analysis_root.exists()


def test_optional_industry_existing_cli_exports_materials(tmp_path,capsys,monkeypatch):
    from scripts.search_themes import main
    from newscatalystos.standard_delivery import read_theme_bundle
    w,reg,provider,at=setup(tmp_path);theme=tmp_path/'power-themes'
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.search_themes.datetime',Clock)
    assert evaluate(options(w,provider,tmp_path/'a',theme),now=at)[0]==0
    assert main(['--root',str(theme),'--materials','--material-industry','POWER_EQUIPMENT',
                '--since',(at-timedelta(days=1)).isoformat(),'--as-of',at.isoformat(),
                '--export-root',str(tmp_path/'separate-power-outbox')])==0
    stored=json.loads(capsys.readouterr().out)
    raw=Path(stored['path']).read_bytes()
    doc=read_theme_bundle(raw,stored['sha256'],decision_at=at,now=at)
    assert doc['ThemeCandidates']
    assert all(t['industry_tags']==['POWER_EQUIPMENT'] and 'catalyst_material' in t for t in doc['ThemeCandidates'])
    assert all(t['catalyst_material']['new_market_catalyst_count'] is None for t in doc['ThemeCandidates'])


def test_existing_dashboard_can_read_isolated_power_analysis_without_source_mutation(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    w,reg,provider,at=setup(tmp_path)
    work=tmp_path/'power/feed_analysis/core';documents=tmp_path/'power/document_analysis'
    assert evaluate(options(w,provider,work,documents/'theme_history'),now=at)[0]==0
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,work.parent,tmp_path/'notes',documents,news_search_workspaces=(w,),evidence_base=w.registry_path.parent.parent)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    before=fingerprint(tmp_path)
    def get(route,args):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(args),timeout=20) as r:
            assert r.status==200;return json.load(r)
    try:
        search=get('/api/news-search',{'q':'변압기'})
        assert search['coverage_complete']
        source=next(x for x in search['results'] if x['headline']==CASES[0][0])
        data=get('/api/news-evidence',{'q':'변압기',**{k:source[k] for k in ('provider_id','event_id','title_sha256')}})
        assert data['saved_title_analysis']['status']=='READY',data['saved_title_analysis']
        assert data['saved_title_analysis']['economic_changes'][0]['industry_tags']==['POWER_EQUIPMENT']
        group=next(g for g in data['article_company_context']['themes'] if g['direct_parties'])
        party=next(c for c in group['direct_parties'] if c['source_name']=='가상전기')
        exact=get('/api/news-evidence',{'q':'변압기',**{k:source[k] for k in ('provider_id','event_id','title_sha256')},
            'excerpt_theme_id':group['theme_id'],'excerpt_entity_id':party['entity_id'],
            'excerpt_claim_event_id':party['event_id'],'excerpt_evidence_sha256':party['evidence_sha256']})
        quote=exact['article_company_excerpt']
        assert quote['status']=='READY' and quote['excerpt']==CASES[0][0],quote
        assert quote['verified_real_benefit'] is False
    finally:server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(tmp_path)==before
