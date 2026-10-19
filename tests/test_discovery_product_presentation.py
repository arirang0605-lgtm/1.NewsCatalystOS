"""Source-stated public presentations remain distinct from commercial launches."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
import json
import pytest

from newscatalystos.economic_discovery import discover_economic_events as discover,RULE_VERSION
from newscatalystos.theme_emergence import validate_change
from newscatalystos.discovery_watch import read_discovery,export_discovery
from newscatalystos.feed_analysis_delivery import _validate_report
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_analysis import evaluate
from test_economic_discovery import flags,SAMPLES
from test_discovery_product_launch import CASES
from test_new_source_adapter import registry
from test_federated_news_search import setup_workspace,collect,fingerprint

PRESENTATIONS=(
 ('가상테크, ‘테크엑스포’서 ‘NovaScope’ 솔루션 공개','NovaScope',['가상테크']),
 ('가상전기, ‘GridScope’ 장치 공개 예정','GridScope',['가상전기']),
 ('가상기기, ‘Alpha Module’ 모듈 시연','Alpha Module',['가상기기']),
 ('가상기업, ‘UnknownFlow’ 플랫폼 선보여','UnknownFlow',['가상기업']),
 ('‘UnknownApp’ 앱 공개','UnknownApp',[]),
)

@pytest.mark.parametrize('title,topic,names',PRESENTATIONS)
def test_named_presentation_has_literal_evidence_but_no_launch_or_sales(title,topic,names):
    value,=discover(title);c=value['change'];m=value['discovery'];validate_change(c)
    assert c['action']=='PRODUCT_PRESENTATION' and c['topic']==topic and c['entity_ids']==names
    assert c['economic_driver']=='UNKNOWN' and not c['verified_economic_effect']
    assert c['phase']==('PLANNED' if '예정' in title else 'SOURCE_REPORTED')
    assert m['commercial_availability_verified'] is False and m['commercial_success_verified'] is False
    assert m['source_company_role']=='SOURCE_STATED_PRESENTER_NOT_ATTESTED_MANUFACTURER'
    for span in [m['action_evidence'],m['object_evidence']]:
        assert title[span['start']:span['end']]==span['text']
        assert sha256(span['text'].encode()).hexdigest()==span['sha256']
    assert discover(title,rule_version='rss-event-first-v5')==[]

@pytest.mark.parametrize('title',(
 '가상기업, 기업공개 추진',
 '가상기업, ‘직원명단’ 공개',
 '가상기업, ‘성과보고서’ 공개',
 '가상기업, ‘NovaScope’ 솔루션 공개 취소',
 '가상기업, ‘NovaScope’ 솔루션 공개 루머 부인',
 '가상기업, ‘NovaScope’ 솔루션 공개 기념행사 개최',
 '가상기업, ‘NovaScope’ 솔루션 공개채용',
 '가상기업, ‘ProductA’와 ‘ProductB’ 솔루션 공개',
 '가상기업, 다른기업은 ‘NovaScope’ 솔루션 공개',
 '정부, ‘NovaScope’ 솔루션 공개',
 '가상기업, ‘NovaScope’ 공개',
))
def test_public_disclosure_ambiguous_objects_and_denials_are_not_presentations(title):
    assert discover(title)==[]

def test_v5_events_identical_and_hints_not_required(monkeypatch):
    for title,*_ in (*SAMPLES,*CASES):
        assert discover(title)==discover(title,rule_version='rss-event-first-v5')
    monkeypatch.setattr('newscatalystos.economic_discovery.HINTS',())
    assert all(discover(title)[0]['change']['industry_tags']==[] for title,*_ in PRESENTATIONS)

def test_stored_v5_report_then_new_presentation_keeps_past_and_repeat(tmp_path,monkeypatch):
    import newscatalystos.economic_discovery as engine
    reg=registry();provider=reg.providers[0].provider_id;w=setup_workspace(tmp_path,'core',reg)
    at=datetime.now(timezone.utc);collect(w,reg,provider,[('public',PRESENTATIONS[0][0],'https://gov.example.org/public'),('launch',CASES[0][0],'https://gov.example.org/launch')],at=at)
    # Recovery acknowledgment is written after collection; query after it exists.
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    root=tmp_path/'watch';opts=flags(w,provider,root);real=engine.discover_economic_events
    monkeypatch.setattr(engine,'RULE_VERSION','rss-event-first-v5')
    monkeypatch.setattr(engine,'discover_economic_events',lambda text,**kw:real(text,rule_version='rss-event-first-v5'))
    code,old=evaluate(opts,now=at);assert code==0 and old['economic_changes_count']==1, old
    oldfile=Path(old['private_report_file']);oldraw=oldfile.read_bytes();past=read_discovery(root,as_of=at,now=at)
    monkeypatch.setattr(engine,'RULE_VERSION',RULE_VERSION);monkeypatch.setattr(engine,'discover_economic_events',real)
    later=at+timedelta(seconds=1);source_before=fingerprint(w.registry_path.parent.parent)
    code,new=evaluate(opts,now=later);assert code==0 and new['economic_changes_count']==2 and new['theme_versions_created']==1
    assert _validate_report(old,later)==at and _validate_report(new,later)==later
    historical=read_discovery(root,as_of=at,now=later)
    # Stored report count can grow; the historical events and user result cannot.
    assert {k:v for k,v in historical.items() if k!='source_coverage'}=={k:v for k,v in past.items() if k!='source_coverage'}
    assert historical['source_coverage']['saved_reports_skipped']==0 and oldfile.read_bytes()==oldraw
    view=read_discovery(root,as_of=later,now=later,include_common_causes=True)
    public=next(x for x in view['candidates'] if x['watch_topic']=='NovaScope')
    assert public['economic_actions']==['PRODUCT_PRESENTATION'] and public['source_companies']==['가상테크']
    material,=public['material']['materials'];hypothesis,=material['company_impacts'][0]['hypotheses']
    assert hypothesis['direction']=='UNKNOWN' and '출시' in hypothesis['counter_argument']
    assert any(ref['action']=='PRODUCT_PRESENTATION' for t in json.loads(export_discovery(root,as_of=later,now=later))['ThemeCandidates'] for ref in t['source_refs'])
    bad=deepcopy(new);row=next(r for r in bad['results'] if any(c['action']=='PRODUCT_PRESENTATION' for c in r['economic_changes']))
    row['economic_discovery'][0]['discovery']['commercial_availability_verified']=True
    with pytest.raises(SourceShareError):_validate_report(bad,later)
    code,repeated=evaluate(opts,now=later+timedelta(seconds=1));assert code==0 and repeated['theme_versions_created']==0
    assert fingerprint(w.registry_path.parent.parent)==source_before

def test_presentation_ui_does_not_call_it_a_launch():
    text=(Path(__file__).resolve().parent.parent/'scripts/dashboard_assets/app.js').read_text()
    assert 'PRODUCT_PRESENTATION:"제품·솔루션 공개·시연 발표"' in text
    assert '출시·판매 개시·고객 채택·매출·수혜는 미확인입니다' in text
