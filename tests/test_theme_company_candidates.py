"""Synthetic company evidence; never a real investment discovery claim."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.standard_delivery import build_theme_bundle, read_theme_bundle
from newscatalystos.source_share import SourceShareError
from test_theme_emergence import event, T
from test_theme_supply_chain import setup, attach


def bundle(themes, at=T):
    raw=build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True)
    return read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)


def test_saved_event_to_company_reason_and_pinned_delivery(tmp_path):
    store=ThemeStore(tmp_path/'themes')
    original=event()
    rows=store.ingest([original],now=T)
    before=(store.root/'themes.sqlite3').read_bytes()
    result=bundle(store.search(as_of=T,now=T))
    candidate=result['CompanyCandidates'][0]
    assert result['schema']=='newscatalyst.theme_delivery.v3'
    assert candidate['display_name']=='가상기업1'
    assert candidate['inclusion_basis'][0]['kind']=='SOURCE_REPORTED_PARTICIPANT'
    assert candidate['inclusion_basis'][0]['source_url']==original['source_url']
    assert candidate['business_context']['source_topics']==['액침냉각']
    assert candidate['business_context']['verified_company_business'] is None
    assert candidate['benefit_path_status']=='UNKNOWN'
    assert candidate['financial_assessment']['value'] is None
    assert candidate['price_assessment']['status']=='NOT_CONNECTED'
    assert candidate['investment_merit']=='NOT_ASSESSED'
    assert candidate['verified_real_transaction'] is candidate['verified_real_benefit'] is False
    assert (store.root/'themes.sqlite3').read_bytes()==before
    assert bundle(rows)==result
    assert store.ingest([original],now=T+timedelta(seconds=1))==[]


def test_resolved_name_keeps_filing_identity_evidence(tmp_path):
    original=event(company='가상전자')
    row=economic_observation(original['change'],**{k:v for k,v in original.items() if k not in {'event_id','change'}},
        source_binding={'source_event_sha256':'a'*64,'document_sha256':'b'*64},
        company_mappings=[{'source_name':'가상전자','entity_id':'DART_CORP:12345678','evidence_sha256':'c'*64}])
    candidate=bundle(ThemeStore(tmp_path/'themes').ingest([row],now=T))['CompanyCandidates'][0]
    assert candidate['entity_id']=='DART_CORP:12345678' and candidate['display_name']=='가상전자'
    assert candidate['inclusion_basis'][0]['identity_evidence'][0]['evidence_sha256']=='c'*64
    assert candidate['verified_real_transaction'] is False


@pytest.mark.parametrize('quality,kind',[('REPORTED','SOURCE_REPORTED_PARTICIPANT'),('INFERRED','INFERRED_ASSOCIATION')])
def test_reported_party_is_distinct_from_inference(tmp_path,quality,kind):
    row=event();row['change']['evidence_level']=quality;row['change']['phase']='PLANNED'
    if quality=='REPORTED':row['content_scope']='RSS_TITLE_METADATA'
    row=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'event_id','change'}})
    c=bundle(ThemeStore(tmp_path/'themes').ingest([row],now=T))['CompanyCandidates'][0]
    assert c['inclusion_basis'][0]['kind']==kind
    assert any('계획' in u for u in c['uncertainties'])
    assert any('제목' in u for u in c['uncertainties'])==(quality=='REPORTED')


@pytest.mark.parametrize('relation',['REPORTED_DIRECT_TRANSACTION','ANNOUNCED_SUPPLY_PLAN'])
def test_supplier_and_customer_paths_are_separate_from_realized_benefit(tmp_path,relation):
    info,out,pub,store,_,first=setup(tmp_path,relation_kind=relation)
    later=info[-1]+timedelta(seconds=1)
    linked=attach(store,out,pub,later)
    result=bundle(linked,later)
    supplier=next(c for c in result['CompanyCandidates'] if c['entity_id']=='SEC_CIK:111111')
    customer=next(c for c in result['CompanyCandidates'] if c['entity_id']=='SEC_CIK:222222')
    assert supplier['inclusion_basis'][0]['kind']=='SOURCE_REPORTED_SUPPLY_RELATION'
    assert supplier['benefit_paths'][0]['category']==('POTENTIAL_BENEFICIARY_UNVERIFIED'
        if relation=='REPORTED_DIRECT_TRANSACTION' else 'ANNOUNCED_SUPPLY_PLAN_UNVERIFIED')
    assert customer['benefit_paths'][0]['category']=='EFFECT_DIRECTION_UNKNOWN'
    assert supplier['revenue_contribution'] is None
    assert bundle(store.search(as_of=info[-1],now=later),info[-1])['CompanyCandidates'][0]['entity_id']=='SEC_CIK:222222'
    assert linked[0]['scores']==first['scores']


def test_retraction_removes_candidate_but_preserves_asof_and_conflicts(tmp_path):
    store=ThemeStore(tmp_path/'themes');row=event();store.ingest([row],now=T)
    conflict=event(2,polarity='CONTRADICT',target=row['event_id'])
    store.ingest([conflict],now=T+timedelta(seconds=1))
    at=T+timedelta(seconds=2)
    c=bundle(store.search(now=at),at)['CompanyCandidates'][0]
    assert c['conflicting_event_ids']==[row['event_id']]
    store.ingest([event(3,polarity='RETRACT',target=row['event_id'])],now=at)
    assert bundle(store.search(now=at),at)['CompanyCandidates']==[]
    assert len(bundle(store.search(as_of=T,now=at))['CompanyCandidates'])==1


def test_company_free_policy_never_invents_a_beneficiary(tmp_path):
    row=event();row['change']['entity_ids']=[]
    row=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'event_id','change'}})
    assert bundle(ThemeStore(tmp_path/'themes').ingest([row],now=T))['CompanyCandidates']==[]


@pytest.mark.parametrize('field,value',[('verified_real_benefit',True),('display_name','fabricated'),
                                      ('decision_at','2099-01-01T00:00:00+00:00'),('revenue_contribution',99)])
def test_rehashed_tampered_company_projection_rejected(tmp_path,field,value):
    result=bundle(ThemeStore(tmp_path/'themes').ingest([event()],now=T))
    result['CompanyCandidates'][0][field]=value
    from newscatalystos.standard_delivery import _json_bytes
    raw=_json_bytes(result)
    with pytest.raises(SourceShareError,match='noncanonical'):
        read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=T,now=T)


def test_same_company_and_reprints_do_not_multiply_candidates(tmp_path):
    first=event();copy=deepcopy(first);copy['source_url']='https://press.example/reprint'
    result=bundle(ThemeStore(tmp_path/'themes').ingest([first,copy],now=T))
    assert len(result['CompanyCandidates'])==1
    assert len(result['CompanyCandidates'][0]['event_ids'])==1
    assert result['ThemeCandidates'][0]['scores']['distinct_economic_events']==1


def test_cli_persists_v3_and_dashboard_reads_company_reasons(tmp_path,capsys):
    from scripts.search_themes import main
    from scripts.open_research_dashboard import DashboardServer
    from datetime import datetime,timezone
    import threading
    from urllib.request import urlopen
    docs=tmp_path/'documents';store=ThemeStore(docs/'theme_history');store.ingest([event()])
    assert main(['--root',str(store.root),'--company-candidates','--query','가상기업1',
                 '--export-root',str(tmp_path/'exports')])==0
    saved=json.loads(capsys.readouterr().out)
    from pathlib import Path
    raw=Path(saved['path']).read_bytes()
    result=read_theme_bundle(raw,saved['sha256'],decision_at=datetime.now(timezone.utc))
    assert len(result['CompanyCandidates'])==1
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        with urlopen(base+'/api/themes?company_candidates=1') as response: data=json.load(response)
        assert data['CompanyCandidates'][0]['candidate_id']==result['CompanyCandidates'][0]['candidate_id']
        with urlopen(base+'/api/themes') as response: legacy=json.load(response)
        assert legacy['schema']=='newscatalyst.theme_delivery.v1' and 'CompanyCandidates' not in legacy
        with urlopen(base+'/api/period?view=day') as response: period=json.load(response)
        assert period['company_candidates'][0]['inclusion_basis']
        with urlopen(base+'/app.js') as response: assert '기업 포함 이유'.encode() in response.read()
    finally:
        server.shutdown();server.server_close();worker.join(2)
