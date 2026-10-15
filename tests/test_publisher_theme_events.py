"""Synthetic licensed document -> named bindings -> theme/supply links."""
from dataclasses import replace
from datetime import timedelta
from copy import deepcopy
import json

import pytest

from newscatalystos.publisher_theme_events import mentions_name,read_publisher_theme_events
from newscatalystos.provider_registry import ProviderRegistry,SCHEMA
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.standard_delivery import build_theme_bundle
from test_publisher_beneficiary_delivery import prepare,publisher_argv
import test_publisher_relation_intake as inputs


def case(tmp_path,monkeypatch,*,line=None,plan=False):
    sentence=line or 'Alpha Devices는 Beta Systems와 HBM 공급 계약을 체결했다.'
    monkeypatch.setattr(inputs,'SENTENCE',sentence)
    monkeypatch.setattr(inputs,'BODY',('SYNTHETIC ONLY\n'+sentence).encode())
    info=list(inputs.fixture(tmp_path,relation_kind='ANNOUNCED_SUPPLY_PLAN' if plan else 'REPORTED_DIRECT_TRANSACTION'))
    provider=replace(info[3].providers[0],method='DOCUMENT',kind='GOVERNMENT_POLICY',grant='PUBLIC_LICENSE_KOGL_1',hourly_limit=1,rights_reference='https://www.motir.go.kr/kor/article/ATCL3f49a5a8c',endpoint='https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/171178/view')
    info[3]=ProviderRegistry((provider,))
    info[4].write_text(json.dumps({'schema':SCHEMA,'providers':[inputs.plain(provider)]}))
    return info


def events(info,**kwargs):
    return read_publisher_theme_events(info[0],info[1].version_id,info[1].receipt_sha256,
        info[2],info[1].payload_sha256,info[3],now=kwargs.get('now',info[-1]))


def test_source_names_and_ids_reach_search_and_json_without_raw_text(tmp_path,monkeypatch):
    from scripts.publish_reviewed_beneficiaries import parser,evaluate
    info=case(tmp_path/'source',monkeypatch)
    rows=events(info);assert len(rows)==1
    assert rows[0]['change']['entity_ids']==['Alpha Devices','Beta Systems']
    assert {m['entity_id'] for m in rows[0]['company_mappings']}=={'SEC_CIK:111111','SEC_CIK:222222'}
    root=tmp_path/'themes'
    args=parser().parse_args(publisher_argv(info,tmp_path/'out')+['--theme-root',str(root)])
    code,result=evaluate(args)
    assert code==0 and result['theme_economic_events']==1 and result['theme_versions_created']==1
    theme=ThemeStore(root).search(query='Alpha Devices')[0]
    assert theme['entity_ids']==['SEC_CIK:111111','SEC_CIK:222222']
    assert theme['scores']['distinct_economic_events']==1
    assert all(x['supply_chain_links'] for x in theme['company_links'])
    assert ThemeStore(root).search(query='111111')==[theme]
    from datetime import datetime,timezone
    raw=build_theme_bundle([theme],decision_at=datetime.now(timezone.utc))
    assert inputs.SENTENCE.encode() not in raw and b'111111' in raw


def test_mapping_enriches_existing_event_without_counting_twice_or_rewriting_past(tmp_path,monkeypatch):
    info=case(tmp_path/'source',monkeypatch);resolved=events(info)[0]
    raw=deepcopy(resolved);raw.pop('company_mappings')
    store=ThemeStore(tmp_path/'themes');first=store.ingest([raw],now=info[-1])[0]
    later=info[-1]+timedelta(seconds=1)
    second=store.ingest([resolved],now=later)[0]
    assert first['event_ids']==second['event_ids'] and second['scores']['distinct_economic_events']==1
    assert second['entity_ids']==['SEC_CIK:111111','SEC_CIK:222222']
    assert store.search(as_of=info[-1],now=later)==[first]
    assert store.ingest([resolved],now=later)==[]
    build_theme_bundle([second],decision_at=later,now=later)


@pytest.mark.parametrize('text,name,expected',[
    ('삼성전자는 계약했다.','삼성전자',True),('삼성전자서비스는 계약했다.','삼성전자',False),
    ('가상삼성전자와 계약했다.','삼성전자',False),('ASML은 공급한다.','ASML',True),
    ('ASMLAB supplies','ASML',False),('Alpha  Devices와 계약했다.','Alpha Devices',True),
    ('ALPHA DEVICES와 계약했다.','Alpha Devices',True),('SK하이닉스에 공급','SK하이닉스',True),
])
def test_only_source_scoped_whole_names_match(text,name,expected):
    assert mentions_name(text,name)==expected


def test_plan_and_historical_non_event_are_not_promoted(tmp_path,monkeypatch):
    info=case(tmp_path/'plan',monkeypatch,plan=True)
    assert events(info)[0]['change']['phase']=='PLANNED'
    info=case(tmp_path/'old',monkeypatch,line='지난해 Alpha Devices는 Beta Systems와 HBM 공급 계약을 체결했다.')
    assert events(info)==[]


def test_unrelated_paragraph_has_no_inherited_companies(tmp_path,monkeypatch):
    info=case(tmp_path/'source',monkeypatch,line='Alpha Devices는 Beta Systems에 장비를 공급한다.\nHBM 생산을 시작했다.')
    row=events(info)[0]
    assert row['company_mappings']==[] and row['change']['entity_ids']==[]


def test_revoked_future_or_different_document_cannot_supply_names(tmp_path,monkeypatch):
    info=case(tmp_path/'source',monkeypatch)
    with pytest.raises(SourceShareError):events(info,now=info[-1]-timedelta(days=1))
    bad=list(info);bad[3]=ProviderRegistry((replace(info[3].providers[0],approved=False),))
    with pytest.raises(SourceShareError):events(bad)
    data=json.loads(info[2].read_bytes());data['supplier']['source_document_id']='different-document'
    info[2].write_text(json.dumps(data))
    with pytest.raises(SourceShareError):events(info)


def test_ambiguous_mapping_is_not_silently_selected(tmp_path,monkeypatch):
    info=case(tmp_path/'source',monkeypatch);row=events(info)[0]
    row['company_mappings'].append(dict(row['company_mappings'][0],entity_id='SEC_CIK:999999'))
    with pytest.raises(SourceShareError,match='ambiguous'):
        economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'change','event_id'}})


def test_feed_endpoint_is_not_presented_as_article_source(tmp_path):
    info=inputs.fixture(tmp_path)
    assert events(info)==[]


def test_unrelated_sentence_in_same_paragraph_cannot_supply_bound_companies(tmp_path,monkeypatch):
    info=case(tmp_path/'source',monkeypatch,line='Alpha Devices는 Beta Systems에 장비를 공급한다. HBM 생산을 시작했다.')
    row=events(info)[0]
    assert row['change']['entity_ids']==[] and row['company_mappings']==[]


def test_publisher_names_preserve_prior_event_identity(tmp_path,monkeypatch):
    from hashlib import sha256
    info=case(tmp_path/'source',monkeypatch)
    row=events(info)[0]
    expected=[row['origin_reference'],'hbm','UNKNOWN','CONTRACT',['Alpha Devices','Beta Systems']]
    raw=(json.dumps(expected,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    assert row['event_id']==sha256(raw).hexdigest()
