"""Previously missed, industry-independent product/solution introductions.

A launch statement is not a factory, customer order, achieved sales, or a stock
signal. Source announcer may be a distributor; missing company stays missing.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode

import pytest
from newscatalystos.economic_discovery import discover_economic_events as discover,RULE_VERSION
from newscatalystos.feed_analysis_delivery import _validate_report
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_analysis import evaluate
from test_economic_discovery import flags,T,SAMPLES
from test_new_source_adapter import registry
from test_federated_news_search import setup_workspace,collect,fingerprint

CASES=(
 ('가상테크, 새로운 측정장치 ‘NovaSensor’ 정식 출시','NovaSensor',['가상테크']),
 ('예시유통, Future PC 국내 출시','Future PC',['예시유통']),
 ('가상소프트웨어, 고객 응답 자동화하는 플랫폼 ‘UnknownFlow’ 출시','UnknownFlow',['가상소프트웨어']),
 ('예시헬스, 혈당 확인 ‘UnknownCare’ 앱 국내 출시','UnknownCare',['예시헬스']),
 ('가상물질, ‘UnknownGel’ 출시 계획','UnknownGel',['가상물질']),
 ('‘업무용 AI’... 가상테크, ‘SafeInput’ 출시','SafeInput',['가상테크']),
 ('‘새 측정도구’ 국내 출시','새 측정도구',[]),
 ('Example Labs Launches UnknownCell','UnknownCell',['Example Labs']),
 ('Sample Tech Launches Small-Package Test IC Supporting Low-Voltage Operation','Small-Package Test IC Supporting Low-Voltage Operation',['Sample Tech']),
 ('Example Launches UnknownJet, First Commercial System on New Platform','UnknownJet',['Example']),
 ('Example Plans to Launch UnknownScope','UnknownScope',['Example']),
 ('Unknown Client 11 Launches Across Asia: Expanded Software Support','Unknown Client 11',[]),
)


@pytest.mark.parametrize('text,topic,companies',CASES)
def test_literal_product_launch_without_industry_dictionary(text,topic,companies):
    value,=discover(text)
    c=value['change'];meta=value['discovery'];validate_change(c)
    assert c['action']=='PRODUCT_LAUNCH' and c['topic']==topic and c['entity_ids']==companies
    assert c['economic_driver']=='UNKNOWN' and not c['verified_economic_effect']
    assert not meta['industry_required_for_detection'] and meta['market_newness']=='UNKNOWN'
    assert meta['commercial_success_verified'] is False
    for span in (meta['action_evidence'],meta['object_evidence']):
        assert text[span['start']:span['end']]==span['text']
        assert sha256(span['text'].encode()).hexdigest()==span['sha256']
    assert c['phase']==('PLANNED' if '계획' in text or 'Plans' in text else 'SOURCE_REPORTED')
    assert discover(text,rule_version='rss-event-first-v1')==[]


@pytest.mark.parametrize('text',(
 'Example Launches a Consultation on Reclassifying a Market',
 'NIST Launches Center to Drive the Manufacture of Quantum Technologies',
 'Example Launches New AI Industrial Accelerator',
 'Example Launches Annual Research Report',
 'Example may Launch UnknownProduct',
 'Example did not launch UnknownProduct',
 '가상테크, ‘새제품’ 출시를 부인했다',
 '가상테크, ‘새제품’ 출시 취소',
 '가상테크, ‘새제품’ 출시 기념행사 개최',
 '가상테크, ‘새제품’ 출시 경쟁 본격화',
 '가상테크, 다른회사는 ‘새제품’ 출시',
 'Example Launches Product A and Launches Product B',
 '가상테크, ‘제품A’와 ‘제품B’ 출시',
 'Unknown market investment news',
 'Unknown product launch roadmap',
 'Product Launch Event Announcement',
))
def test_nonproduct_unconfirmed_or_ambiguous_launch_is_not_positive_event(text):
    assert discover(text)==[]


def test_existing_event_versions_are_identical_and_removing_hints_does_not_gate(monkeypatch):
    for title,*_ in SAMPLES:
        assert discover(title)==discover(title,rule_version='rss-event-first-v1')
    baseline=[discover(text) for text,*_ in CASES]
    monkeypatch.setattr('newscatalystos.economic_discovery.HINTS',())
    current=[discover(text) for text,*_ in CASES]
    assert len(baseline)==len(current)
    for a,b in zip(baseline,current):
        assert a and b
        assert {k:v for k,v in a[0]['change'].items() if k!='industry_tags'}=={k:v for k,v in b[0]['change'].items() if k!='industry_tags'}
    with pytest.raises(ValueError):discover(CASES[0][0],rule_version='invented-version')


def source(tmp_path):
    reg=registry();provider=reg.providers[0].provider_id
    w=setup_workspace(tmp_path,'core',reg)
    items=[(str(i),title,'https://gov.example.org/launch/'+str(i)) for i,(title,*_) in enumerate(CASES[:6])]
    items.append(('prior',SAMPLES[0][0],'https://gov.example.org/old'))
    collect(w,reg,provider,items,at=T)
    return w,reg,provider


def test_immutable_v1_reports_PIT_and_old_themes_preserved_after_v2_interpretation(tmp_path,monkeypatch):
    import newscatalystos.economic_discovery as engine
    w,reg,provider=source(tmp_path);root=tmp_path/'watch';opts=flags(w,provider,root)
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    real=engine.discover_economic_events
    monkeypatch.setattr(engine,'discover_economic_events',lambda text,**kw:real(text,rule_version='rss-event-first-v1'))
    monkeypatch.setattr(engine,'RULE_VERSION','rss-event-first-v1')
    code,old=evaluate(opts,now=at)
    assert code==0 and old['economic_changes_count']==1 and old['rule_version']=='rss-event-first-v1'
    oldfile=Path(old['private_report_file']);oldsha=sha256(oldfile.read_bytes()).hexdigest()
    originals=ThemeStore(root/'theme_history').search(now=at)
    old_view=read_discovery(root,as_of=at,now=at)
    monkeypatch.setattr(engine,'discover_economic_events',real)
    monkeypatch.setattr(engine,'RULE_VERSION',RULE_VERSION)
    assert _validate_report(old,at)==at  # v1 replay despite newer extraction
    later=at+timedelta(minutes=1);sourcepins=fingerprint(w.registry_path.parent.parent)
    code,new=evaluate(opts,now=later)
    assert code==0 and new['rule_version']==RULE_VERSION and new['economic_changes_count']==7
    assert new['theme_versions_created']==6
    assert _validate_report(new,later)==later
    current=ThemeStore(root/'theme_history').search(now=later)
    assert all(o in current for o in originals)
    before=fingerprint(root)
    watch=read_discovery(root,as_of=later,now=later)
    assert watch['counts']['events']==7 and watch['source_coverage']['saved_reports_skipped']==0
    past=read_discovery(root,as_of=at,now=later)
    assert past['counts']==old_view['counts'] and past['counts']['events']==1
    product=next(c for c in watch['candidates'] if c['watch_topic']=='NovaSensor')
    assert product['industry_tags']==[] and product['source_companies']==['가상테크']
    m,=product['material']['materials'];h,=m['company_impacts'][0]['hypotheses']
    assert m['is_new_market_catalyst'] is None and not m['verified_economic_effect']
    assert h['path']=='EARNINGS' and h['direction']=='UNKNOWN'
    assert '매출' in h['counter_argument'] and '제조사' in h['counter_argument']
    payload=json.loads(export_discovery(root,as_of=later,now=later))
    assert any(r['action']=='PRODUCT_LAUNCH' for t in payload['ThemeCandidates'] for r in t['source_refs'])
    assert fingerprint(root)==before and fingerprint(w.registry_path.parent.parent)==sourcepins
    assert sha256(oldfile.read_bytes()).hexdigest()==oldsha
    bad=deepcopy(new);bad['rule_version']='rss-event-first-v1'
    with pytest.raises(SourceShareError):_validate_report(bad,later)
    bad=deepcopy(new);product_row=next(r for r in bad['results'] if any(c['action']=='PRODUCT_LAUNCH' for c in r['economic_changes']))
    product_row['economic_discovery'][0]['discovery']['object_evidence']['text']='made up'
    with pytest.raises(SourceShareError):_validate_report(bad,later)
    code,repeated=evaluate(opts,now=later+timedelta(minutes=1))
    assert code==0 and repeated['theme_versions_created']==0
    assert read_discovery(root,as_of=later+timedelta(minutes=1),now=later+timedelta(minutes=1))['counts']['events']==7


def test_http_watch_and_export_include_new_product_and_keep_old_claims(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    w,reg,provider=source(tmp_path);docs=tmp_path/'documents';root=docs/'economic_discovery'
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    assert evaluate(flags(w,provider,root),now=at)[0]==0
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs,news_search_workspaces=(w,))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();pins=fingerprint(root)
    try:
        for query in ({},{'export':'1'}):
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/economic-discovery?'+urlencode(query),timeout=20) as h:
                assert h.status==200;result=json.load(h)
            if query:
                assert len(result['ThemeCandidates'])==7
                assert any(t['industry_tags']==[] for t in result['ThemeCandidates'])
            else:
                assert result['counts']['events']==7
                assert any(c['watch_topic']=='UnknownCare' and c['economic_actions']==['PRODUCT_LAUNCH'] for c in result['candidates'])
    finally:server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(root)==pins


def test_source_claim_label_does_not_assert_manufacture_or_sales():
    text=(Path(__file__).resolve().parent.parent/'scripts/dashboard_assets/app.js').read_text()
    assert 'PRODUCT_LAUNCH:"제품·솔루션 출시 발표"' in text
    assert '판매·매출·수혜를 확정하지 않습니다' in text
    assert '번역·재배포 제목은 독립 시장사건으로 인증하지 않습니다' in text
