"""Synthetic article/snapshots for directory -> companies -> existing theme flow."""
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from copy import deepcopy
from argparse import Namespace
import json

import pytest

from newscatalystos.article_company_identity import prepare_article_identity,publish_article_identity,search_article_identities,resolve_names,validate_report
from newscatalystos.official_filing_context import FilingContext
from newscatalystos.source_share import SourceShareError
from newscatalystos.motir_article_binding import consume_motir_article_binding
from newscatalystos.theme_emergence import ThemeStore
from test_motir_document_analysis import case
from newscatalystos.motir_document_collection import _registry_bytes


def context(at,name='가상반도체',code='00000001'):
    return FilingContext('dart-disclosures','20261008000001','a'*64,'b'*64,name,
                         'DART_CORP',code,None,'DART_REPORT','Synthetic only',at)


def setup(tmp_path):
    _,args=case(tmp_path/'source',body='가상반도체는 HBM 수요 확대에 대응해 공급 계약을 체결했다. '*3)
    at=datetime.now(timezone.utc)
    binding=consume_motir_article_binding(args['binding_path'],args['binding_sha256'],now=at)
    ctx={('dart-disclosures','1'):context(at)}
    report=prepare_article_identity(args['archive_root'],binding['archive_version'],binding['archive_receipt_sha256'],binding['document_sha256'],args['article_registry'],ctx,now=at)
    return at,args,binding,ctx,report


def test_exact_names_deduplicate_filings_and_leave_unknown_ambiguous(tmp_path):
    at=datetime.now(timezone.utc);a=context(at)
    rows={'1':a,'2':replace(a,document_id='20261008000002'),'3':context(at,'동명반도체','00000002'),'4':context(at,'동명반도체','00000003')}
    found,unknown=resolve_names(['가상반도체','동명반도체','없는반도체'],rows,at=at)
    assert len(found)==1 and found[0]['entity_id']=='DART_CORP:00000001'
    assert {x['status'] for x in unknown}=={'AMBIGUOUS','NOT_IN_SNAPSHOT'}
    with pytest.raises(SourceShareError):resolve_names(['가상반도체'],{'x':context(at+timedelta(seconds=1))},at=at)


def test_licensed_article_to_saved_search_is_readonly_and_has_no_original_text(tmp_path):
    at,args,binding,ctx,report=setup(tmp_path)
    before={str(p):sha256(p.read_bytes()).hexdigest() for p in args['archive_root'].rglob('*') if p.is_file()}
    assert report['matches'][0]['entity_id']=='DART_CORP:00000001'
    root=tmp_path/'identities';path,digest=publish_article_identity(report,root)
    assert search_article_identities(root,query='00000001',as_of=at)==[report]
    assert search_article_identities(root,query='가상반도체',as_of=at)==[report]
    assert search_article_identities(root,as_of=at-timedelta(seconds=1))==[]
    assert '공급 계약을 체결' not in path.read_text()
    assert before=={str(p):sha256(p.read_bytes()).hexdigest() for p in args['archive_root'].rglob('*') if p.is_file()}
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(SourceShareError,match='SHA'):search_article_identities(root)


@pytest.mark.parametrize('fault',['pin','future','identity','revenue','extra'])
def test_invalid_identity_cannot_enter_saved_results(tmp_path,fault):
    at,args,binding,ctx,report=setup(tmp_path)
    if fault=='pin':report['matches'][0]['original_sha256']='f'*64
    if fault=='future':report['matches'][0]['available_at']=(at+timedelta(days=1)).isoformat()
    if fault=='identity':report['matches'][0]['entity_id']='SEC_CIK:123'
    if fault=='revenue':report['verified_real_benefit']=True
    if fault=='extra':report['private_article_text']='Synthetic forbidden body'
    with pytest.raises(SourceShareError):validate_report(report,at)


def test_article_pin_and_revoked_rights(tmp_path):
    from newscatalystos.provider_registry import ProviderRegistry
    at,args,binding,ctx,_=setup(tmp_path)
    with pytest.raises(SourceShareError,match='pin'):
        prepare_article_identity(args['archive_root'],binding['archive_version'],binding['archive_receipt_sha256'],'0'*64,args['article_registry'],ctx,now=at)
    revoked=ProviderRegistry(tuple(replace(p,approved=False) for p in args['article_registry'].providers))
    with pytest.raises(SourceShareError):
        prepare_article_identity(args['archive_root'],binding['archive_version'],binding['archive_receipt_sha256'],binding['document_sha256'],revoked,ctx,now=at)


def opts_for(args,root,registry):
    return Namespace(binding_path=args['binding_path'],binding_sha256=args['binding_sha256'],
        archive_root=args['archive_root'],article_registry=registry,analysis_root=root/args['binding_sha256'],
        model_config=None,ai_ledger=None,allow_paid=False,analyze_existing=False)


def test_saved_identity_enters_existing_document_theme_and_search_with_failure_isolation(tmp_path):
    from scripts.run_motir_document_analysis import evaluate
    from scripts.search_news import _with_saved_analysis
    from newscatalystos.research_dashboard import scan_saved_documents
    at,args,binding,ctx,report=setup(tmp_path)
    root=tmp_path/'documents';registry=tmp_path/'registry.json'
    registry.write_bytes(_registry_bytes(args['article_registry'].providers[0]));registry.chmod(0o600)
    publish_article_identity(report,root/'company_identity')
    code,result=evaluate(opts_for(args,root,registry),now=at)
    assert code==0 and result['company_identity_status']=='READY'
    row=ThemeStore(root/'theme_history').search(now=at)[0]
    assert row['entity_ids']==['DART_CORP:00000001']
    assert row['verified_beneficiary_count']==0
    saved,_=scan_saved_documents(root,[],now=at)
    assert saved[0]['company_identity']['matches'][0]['source_name']=='가상반도체'
    assert _with_saved_analysis({},Namespace(company_identity_root=root/'company_identity',query='00000001'))['article_company_identities']==[report]
    next((root/'company_identity').glob('*.json')).write_bytes(b'bad')
    code,result=evaluate(opts_for(args,root,registry),now=at)
    assert code==0 and result['company_identity_status']=='UNAVAILABLE'


def test_directory_reader_uses_existing_pinned_capture_contract(tmp_path,monkeypatch):
    from test_official_filing_context import environments,NOW
    from newscatalystos.official_filing_context import read_pinned_filing_context
    era,*_=environments(tmp_path,monkeypatch)
    rows=read_pinned_filing_context(era,era/'report.json',tmp_path/'pin.json',now=NOW)
    matches,_=resolve_names(['가상반도체'],rows,at=NOW)
    assert matches[0]['entity_id']=='DART_CORP:00000001'
    assert matches[0]['original_sha256'] in {r.original_sha256 for r in rows.values()}


def test_generic_equipment_terms_are_not_company_candidates(tmp_path):
    _,args=case(tmp_path/'source',body='삼성전자는 ASML의 노광장비와 첨단장비를 설명했다. '*3)
    at=datetime.now(timezone.utc)
    binding=consume_motir_article_binding(args['binding_path'],args['binding_sha256'],now=at)
    report=prepare_article_identity(args['archive_root'],binding['archive_version'],binding['archive_receipt_sha256'],binding['document_sha256'],args['article_registry'],{},now=at)
    assert {r['source_name'] for r in report['unresolved']}=={'삼성전자','ASML'}


def test_identity_cards_http_and_bad_identity_do_not_block_news(tmp_path):
    import threading
    from urllib.request import urlopen
    from scripts.open_research_dashboard import DashboardServer
    at,args,binding,ctx,report=setup(tmp_path)
    docs=tmp_path/'documents';path,_=publish_article_identity(report,docs/'company_identity')
    server=DashboardServer(0,tmp_path/'empty',tmp_path/'notes',docs)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}/api/period?view=day&date='+at.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul')).date().isoformat()
    try:
        with urlopen(url) as response: data=json.load(response)
        assert data['company_identities'][0]['matches'][0]['entity_id']=='DART_CORP:00000001'
        path.write_bytes(b'bad')
        with urlopen(url) as response: data=json.load(response)
        assert data['company_identity_status']=='UNAVAILABLE' and 'items' in data
    finally:server.shutdown();server.server_close();thread.join(2)
