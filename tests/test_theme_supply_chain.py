"""Synthetic source-backed graphs; no real contract/benefit assertions."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.standard_delivery import build_theme_bundle, read_theme_bundle
from newscatalystos.source_share import SourceShareError
from test_publisher_beneficiary_delivery import fixture, publish, fingerprint


def observation(info, *, company='SEC_CIK:222222', binding=None, number=1, polarity='SUPPORT', target=None):
    change={'topic':'HBM','economic_driver':'CAPACITY_EXPANSION','action':'CAPACITY_ADDITION',
            'phase':'SOURCE_REPORTED','entity_ids':[company],'industry_tags':['SEMICONDUCTOR'],
            'source_paragraph_sha256':sha256(str(number).encode()).hexdigest(),
            'evidence_level':'OFFICIAL_SOURCE','verified_economic_effect':False}
    return economic_observation(change,origin_reference=f'https://example.org/release/{number}',
        source_url=f'https://example.org/release/{number}',source_id='synthetic-publisher',
        source_available_at=info[-1].isoformat(),polarity=polarity,supersedes_event_id=target,
        source_binding=binding or {'source_event_sha256':info[1].version_id,'document_sha256':info[1].payload_sha256})


def setup(tmp_path, **kwargs):
    info=fixture(tmp_path/'source',**kwargs)
    _,out,pub=publish(info,tmp_path)
    store=ThemeStore(tmp_path/'themes')
    original=observation(info)
    first=store.ingest([original],now=info[-1])[0]
    return info,out,pub,store,original,first


def attach(store,out,pub,at):
    return store.ingest_supply_graph(pub.folder,out,pub.payload_sha256,now=at)


@pytest.mark.parametrize('relation', ['REPORTED_DIRECT_TRANSACTION','ANNOUNCED_SUPPLY_PLAN'])
def test_source_graph_to_theme_search_export_and_history(tmp_path,relation):
    info,out,pub,store,original,first=setup(tmp_path,relation_kind=relation)
    before=fingerprint(out);later=info[-1]+timedelta(seconds=5)
    row=attach(store,out,pub,later)[0]
    assert fingerprint(out)==before
    assert row['schema_version']=='newscatalyst.theme_candidate.v2'
    assert row['scores']==first['scores']  # contextual firms are not independent events
    assert row['verified_beneficiary_count']==0
    supplier=next(c for c in row['company_links'] if c['entity_id']=='SEC_CIK:111111')
    link=supplier['supply_chain_links'][0]
    assert link['relation_kind']==relation and link['product_stage']=='ADVANCED_PACKAGING'
    assert link['impact_category']==('POTENTIAL_BENEFICIARY_UNVERIFIED' if relation=='REPORTED_DIRECT_TRANSACTION' else 'ANNOUNCED_SUPPLY_PLAN_UNVERIFIED')
    assert link['linked_at']==later.isoformat()
    assert link['verified_real_transaction'] is False and link['revenue_contribution'] is None
    assert store.search(query='SEC_CIK:111111',now=later)==[row]
    assert store.search(as_of=info[-1],now=later)==[first]
    assert not store.search(as_of=info[-1],query='111111',now=later)
    raw=build_theme_bundle([row],decision_at=later,now=later)
    value=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=later,now=later)
    assert value['schema']=='newscatalyst.theme_delivery.v2'
    assert attach(store,out,pub,later+timedelta(seconds=1))==[]
    # Ordinary subsequent ingestion keeps the already linked relationship.
    newer=store.ingest([observation(info,number=2)],now=later+timedelta(seconds=2))[0]
    assert len(newer['supply_chain_evidence'])==1
    assert len(newer['company_links'][0]['supply_chain_links'][0]['event_ids'])==2
    build_theme_bundle([newer],decision_at=later+timedelta(seconds=2),now=later+timedelta(seconds=2))


@pytest.mark.parametrize('mismatch',['source','document','company','industry','missing'])
def test_unrelated_or_ambiguous_input_never_gains_a_relationship(tmp_path,mismatch):
    info=fixture(tmp_path/'source');_,out,pub=publish(info,tmp_path)
    row=observation(info)
    if mismatch=='source':row['source_binding']['source_event_sha256']='f'*64
    if mismatch=='document':row['source_binding']['document_sha256']='f'*64
    if mismatch=='missing':row.pop('source_binding')
    if mismatch in {'company','industry'}:
        row['change']['entity_ids']=['Unresolved company name'] if mismatch=='company' else row['change']['entity_ids']
        row['change']['industry_tags']=[] if mismatch=='industry' else row['change']['industry_tags']
        row=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'change','event_id'}})
    store=ThemeStore(tmp_path/'themes');first=store.ingest([row],now=info[-1])[0]
    assert attach(store,out,pub,info[-1]+timedelta(seconds=1))==[]
    assert store.search(now=info[-1]+timedelta(seconds=1))==[first]


def test_graph_before_event_connects_automatically_and_retraction_removes_current_link(tmp_path):
    info=fixture(tmp_path/'source');_,out,pub=publish(info,tmp_path)
    store=ThemeStore(tmp_path/'themes');at=info[-1]
    assert attach(store,out,pub,at)==[]
    original=observation(info)
    linked=store.ingest([original],now=at+timedelta(seconds=1))[0]
    assert linked['company_links'][0]['supply_chain_links'][0]['linked_at']==(at+timedelta(seconds=1)).isoformat()
    retracted=store.ingest([observation(info,number=2,polarity='RETRACT',target=original['event_id'])],now=at+timedelta(seconds=2))[0]
    assert retracted['status']=='INVALIDATED' and retracted['company_links']==[]
    assert 'supply_chain_evidence' not in retracted
    assert store.search(as_of=at+timedelta(seconds=1),now=at+timedelta(seconds=2))==[linked]


def test_conflicting_claim_is_visible_without_certifying_supplier(tmp_path):
    info,out,pub,store,original,_=setup(tmp_path);at=info[-1]+timedelta(seconds=1)
    attach(store,out,pub,at)
    row=store.ingest([observation(info,number=2,polarity='CONTRADICT',target=original['event_id'])],now=at+timedelta(seconds=1))[0]
    assert row['status']=='WEAKENING'
    assert row['company_links'][0]['supply_chain_links'][0]['conflicting_event_ids']==[original['event_id']]


@pytest.mark.parametrize('tamper',['revenue','relation','time','pin','counterparty','unmatched','version'])
def test_export_rejects_fabricated_projection_and_future_evidence(tmp_path,tamper):
    info,out,pub,store,_,_=setup(tmp_path);at=info[-1]+timedelta(seconds=1)
    row=deepcopy(attach(store,out,pub,at)[0]);link=row['company_links'][0]['supply_chain_links'][0]
    if tamper=='revenue':link['revenue_contribution']=100
    if tamper=='relation':link['relation_kind']='VERIFIED_DIRECT_TRANSACTION'
    if tamper=='time':row['supply_chain_evidence'][0]['available_at']=(at+timedelta(days=1)).isoformat()
    if tamper=='pin':row['supply_chain_evidence'][0]['payload_sha256']='0'*64
    if tamper=='counterparty':link['counterparty_id']='SEC_CIK:999999'
    if tamper=='unmatched':row['source_refs'][0]['source_binding']['document_sha256']='f'*64
    if tamper=='version':row['schema_version']='newscatalyst.theme_candidate.v1'
    with pytest.raises(SourceShareError):build_theme_bundle([row],decision_at=at,now=at)


def test_cli_pinned_ingest_and_existing_dashboard_delivery(tmp_path,capsys):
    from scripts.connect_theme_supply_chain import main
    from scripts.search_themes import main as export
    from scripts.open_research_dashboard import DashboardServer
    import threading
    from urllib.request import urlopen
    info,out,pub,_,original,_=setup(tmp_path)
    docs=tmp_path/'documents';store=ThemeStore(docs/'theme_history');store.ingest([original])
    args=['--folder',str(pub.folder),'--out-root',str(out),'--expected-sha256',pub.payload_sha256,'--root',str(store.root)]
    assert main(args)==0
    result=json.loads(capsys.readouterr().out)
    assert result['theme_versions_created']==1 and result['ai_calls']==0
    assert main(args)==0
    assert json.loads(capsys.readouterr().out)['theme_versions_created']==0
    assert export(['--root',str(store.root),'--query','111111','--export-root',str(tmp_path/'exports')])==0
    server=DashboardServer(0,tmp_path/'empty',tmp_path/'notes',docs)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/themes?q=111111') as r: data=json.load(r)
        assert data['schema']=='newscatalyst.theme_delivery.v2'
        assert data['ThemeCandidates'][0]['company_links'][0]['supply_chain_links']
    finally:server.shutdown();server.server_close();thread.join(2)


@pytest.mark.parametrize('source',['dart-disclosures','sec-submissions'])
def test_existing_official_graph_v1_still_connects_readonly(tmp_path,source):
    from test_reviewed_beneficiary_delivery import fixture as official_fixture, prepare
    from newscatalystos.reviewed_beneficiary_delivery import publish_reviewed_beneficiary_graph
    info=official_fixture(tmp_path/'source',source)
    report=prepare(info);graph=json.loads(report.graph.JSON_bytes);edge=graph['edges'][0]
    out=tmp_path/'out';pub=publish_reviewed_beneficiary_graph(report,out,now=info[-1])
    change={'topic':'HBM','economic_driver':'CAPACITY_EXPANSION','action':'CAPACITY_ADDITION',
        'phase':'SOURCE_REPORTED','entity_ids':[edge['customer_namespace']+':'+edge['customer_id']],
        'industry_tags':['SEMICONDUCTOR'],'source_paragraph_sha256':'a'*64,
        'evidence_level':'OFFICIAL_SOURCE','verified_economic_effect':False}
    original=economic_observation(change,origin_reference='https://example.org/filing',source_url='https://example.org/filing',
        source_id=source,source_available_at=info[-1].isoformat(),source_binding={
            'source_event_sha256':graph['event_sha256'],'document_sha256':edge['document_sha256']})
    store=ThemeStore(tmp_path/'themes');store.ingest([original],now=info[-1]);before=fingerprint(out)
    rows=store.ingest_supply_graph(pub.folder,out,pub.payload_sha256,graph_version='v1',now=info[-1])
    assert rows[0]['company_links'][0]['supply_chain_links']
    assert fingerprint(out)==before
    build_theme_bundle(rows,decision_at=info[-1],now=info[-1])


def test_publication_automatically_registers_for_future_events(tmp_path):
    from scripts.publish_reviewed_beneficiaries import evaluate,parser
    from test_publisher_beneficiary_delivery import publisher_argv
    from datetime import datetime,timezone
    info=fixture(tmp_path/'source');root=tmp_path/'themes'
    args=parser().parse_args(publisher_argv(info,tmp_path/'out')+['--theme-root',str(root)])
    code,result=evaluate(args)
    assert code==0 and result['theme_link_status']=='REGISTERED'
    assert result['theme_versions_created']==0
    rows=ThemeStore(root).ingest([observation(info)])
    assert rows[0]['supply_chain_evidence'][0]['payload_sha256']==result['payload_sha256']
    build_theme_bundle(rows,decision_at=datetime.now(timezone.utc))


def test_source_after_snapshot_cannot_leak_through_later_export(tmp_path):
    info,out,pub,store,_,_=setup(tmp_path);at=info[-1]+timedelta(seconds=1)
    row=attach(store,out,pub,at)[0]
    row['source_refs'][0]['recorded_at']=(at+timedelta(seconds=1)).isoformat()
    with pytest.raises(SourceShareError,match='future'):
        build_theme_bundle([row],decision_at=at+timedelta(seconds=2),now=at+timedelta(seconds=2))
