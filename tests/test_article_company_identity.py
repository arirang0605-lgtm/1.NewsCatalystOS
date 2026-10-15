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


def test_automatic_identity_cache_refresh_and_current_rights(tmp_path,monkeypatch):
    from newscatalystos.article_company_identity import ensure_article_identity
    from newscatalystos import official_filing_context as filing
    from newscatalystos.provider_registry import ProviderRegistry
    at,args,binding,ctx,_=setup(tmp_path)
    rows=dict(ctx)
    monkeypatch.setattr(filing,'read_pinned_filing_context',lambda *a,**k:rows)
    root=tmp_path/'auto'
    def run(registry=None):
        return ensure_article_identity(args['archive_root'],binding,registry or args['article_registry'],
            root,tmp_path,tmp_path/'report',tmp_path/'anchor')
    first,status=run();assert status=='CREATED'
    before={p.name:p.read_bytes() for p in root.glob('*.json')}
    rows={k:replace(v,local_context_verified_at=datetime.now(timezone.utc)) for k,v in rows.items()}
    cached,status=run();assert status=='CACHE_HIT' and cached==first
    assert before=={p.name:p.read_bytes() for p in root.glob('*.json')}
    rows={k:replace(v,issuer_code_observed='00000002',original_sha256='c'*64) for k,v in rows.items()}
    revised,status=run();assert status=='CREATED'
    assert revised['directory_sha256']!=first['directory_sha256']
    assert revised['matches'][0]['entity_id']=='DART_CORP:00000002'
    assert len(list(root.glob('*.json')))==2
    assert search_article_identities(root,as_of=datetime.fromisoformat(first['decision_at']))==[first]
    revoked=ProviderRegistry(tuple(replace(p,approved=False) for p in args['article_registry'].providers))
    with pytest.raises(SourceShareError):run(revoked)
    monkeypatch.setattr(filing,'read_pinned_filing_context',lambda *a,**k:(_ for _ in ()).throw(SourceShareError('bad pin')))
    with pytest.raises(SourceShareError):run()


def test_scheduler_generates_identity_before_analysis_and_recovers(tmp_path,monkeypatch):
    from scripts import run_motir_policy_once as scheduler
    from scripts.run_motir_document_analysis import evaluate
    from newscatalystos import official_filing_context as filing
    at,args,binding,ctx,_=setup(tmp_path)
    monkeypatch.setattr(filing,'read_pinned_filing_context',lambda *a,**k:ctx)
    root=tmp_path/'documents';registry=tmp_path/'registry.json'
    registry.write_bytes(_registry_bytes(args['article_registry'].providers[0]));registry.chmod(0o600)
    config=tmp_path/'company_identity.json'
    config.write_text(json.dumps({k:str(tmp_path/k) for k in ('era_root','era_report','independent_anchor')}));config.chmod(0o600)
    opts=Namespace(document_analysis_root=root,company_identity_config=config,
        output_root=tmp_path/'output',replay_only=True,allow_paid_ai=True)
    job={'binding_path':str(args['binding_path']),'binding_sha256':args['binding_sha256'],
         'archive_root':str(args['archive_root']),'article_registry':str(registry)}
    def tick():return scheduler._analyze_documents(opts,evaluate,[job])[1]['results'][0]
    first=tick();assert first['exit_code']==0 and first['company_identity_generation']=='CREATED'
    report=json.loads(Path(first['private_report_file']).read_text())
    assert report['company_identity']['decision_at']<=report['analysis_available_at']
    assert ThemeStore(root/'theme_history').search()[0]['entity_ids']==['DART_CORP:00000001']
    second=tick();assert second['company_identity_generation']=='CACHE_HIT'
    assert second['new_ai_results']==0 and second['theme_versions_created']==0
    config.write_text('{}')
    failed=tick();assert failed['exit_code']==0 and failed['company_identity_status']=='UNAVAILABLE'
    assert 'company_identity' not in json.loads(Path(failed['private_report_file']).read_text())
    config.write_text(json.dumps({k:str(tmp_path/k) for k in ('era_root','era_report','independent_anchor')}))
    assert tick()['company_identity_generation']=='CACHE_HIT'


def test_article_revision_gets_separate_automatic_identity(tmp_path,monkeypatch):
    from newscatalystos.article_company_identity import ensure_article_identity
    from newscatalystos import official_filing_context as filing
    _,first,binding,ctx,_=setup(tmp_path/'first')
    monkeypatch.setattr(filing,'read_pinned_filing_context',lambda *a,**k:ctx)
    root=tmp_path/'identities'
    original,_=ensure_article_identity(first['archive_root'],binding,first['article_registry'],root,tmp_path,tmp_path,tmp_path)
    _,second=case(tmp_path/'second',body='가상반도체는 HBM 공급 계약을 취소했다. '*3)
    other=consume_motir_article_binding(second['binding_path'],second['binding_sha256'])
    revised,status=ensure_article_identity(second['archive_root'],other,second['article_registry'],root,tmp_path,tmp_path,tmp_path)
    assert status=='CREATED' and revised['archive_version']!=original['archive_version']
    assert len(search_article_identities(root))==2


def test_directory_name_without_company_suffix_reaches_actual_document_pipeline(tmp_path,monkeypatch):
    from scripts.run_motir_document_analysis import evaluate
    from newscatalystos import official_filing_context as filing
    _,args=case(tmp_path/'source',body='별빛공업은 EUV 수요 증가에 대응해 공급 계약을 체결했다. '*3)
    at=datetime.now(timezone.utc)
    monkeypatch.setattr(filing,'read_pinned_filing_context',lambda *a,**k:{'one':context(at,'별빛공업')})
    registry=tmp_path/'registry.json'
    registry.write_bytes(_registry_bytes(args['article_registry'].providers[0]));registry.chmod(0o600)
    opts=opts_for(args,tmp_path/'documents',registry)
    code,old=evaluate(opts)
    assert code==0
    config=tmp_path/'identity.json'
    config.write_text(json.dumps({k:str(tmp_path/k) for k in ('era_root','era_report','independent_anchor')}));config.chmod(0o600)
    opts.company_identity_config=config
    code,result=evaluate(opts)
    assert code==0 and result['company_identity_generation']=='CREATED'
    report=json.loads(Path(result['private_report_file']).read_text())
    assert report['economic_changes'][0]['entity_ids']==['별빛공업']
    theme=ThemeStore(tmp_path/'documents/theme_history').search()[0]
    assert theme['entity_ids']==['DART_CORP:00000001']
    assert theme['scores']['distinct_economic_events']==1
    assert evaluate(opts)[1]['theme_versions_created']==0
