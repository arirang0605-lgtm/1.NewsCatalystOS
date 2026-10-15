"""Synthetic completed producer publications and actual NC consumption paths."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path

import pytest

from newscatalystos.era_company_assessment import canonical, import_watch, enrich_candidates, METHOD
from newscatalystos.source_share import SourceShareError
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.theme_emergence import ThemeStore
from test_theme_emergence import event, T


def source(tmp_path, change=None):
    inputs={'security_id':'123456','dart_cfs_issuer_corp_code':'12345678'}
    assessment={'method':METHOD,'security_id':'123456','issuer_corp_code':'12345678',
        'assessment_day':'2026-10-15','source_market_session':'2026-10-13','annual_fiscal_year':2025,
        'inputs':inputs,'sources':{
            'market_sample':{'content_sha256':'a'*64,'available_at_utc':T.isoformat(),'market_session':'2026-10-13'},
            'annual':{'issuer_corp_code':'12345678','fiscal_year':2025,'currency':'KRW','statement':'CFS',
                      'report_code':'11011','first_receipt_sha256':'b'*64,'available_at_utc':T.isoformat()}},
        'competitiveness':{'score_20':None,'supporting':[],'weakening':[]},
        'financial_risk':{'assessed_items':1,'possible_items':5,'signals':[]},
        'valuation':{'status':'N/A'},'orders_enabled':False,'leader_score_unchanged':True,
        'missing':['다른 재무 항목 부족'],'limitations':['안전 확정 아님']}
    row={**inputs,'company_assessment':assessment}
    doc={'schema':'eraleader.kr_early_watch_queue.v1','market':'KR','watch_only':True,
        'orders_enabled':False,'order_instruction':False,'execution_authority':False,'investment_priority_certified':False,
        'company_assessment_method':METHOD,'company_assessment_day':'2026-10-15',
        'watch_published_at_utc':T.isoformat(),'source_market_session':'2026-10-13',
        'source_marketwide_sha256':'a'*64,'review_queue':[row]}
    if change:change(doc)
    doc['source_company_assessment_sha256']=sha256(canonical([r['company_assessment'] for r in doc['review_queue']])).hexdigest()
    doc['content_sha256']=sha256(canonical(doc)).hexdigest()
    raw=canonical(doc)+b'\n';root=tmp_path/'producer'
    folder=root/'output/early_leader_watch_queue/KR_20261013_0123456789abcdef'
    folder.mkdir(parents=True)
    (folder/'index.html').write_text('<p>Synthetic published WATCH</p>')
    path=folder/'watch_queue.json';path.write_bytes(raw)
    return root,path,sha256(raw).hexdigest()


def candidates(tmp_path, company='DART_CORP:12345678'):
    themes=ThemeStore(tmp_path/'themes').ingest([event(company=company)],now=T)
    return json.loads(build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True))['CompanyCandidates']


def test_pinned_import_to_candidate_and_first_local_availability(tmp_path):
    root,path,pin=source(tmp_path);cache=tmp_path/'cache';at=T+timedelta(hours=1)
    before=path.read_bytes();first=import_watch(root,path,pin,cache,now=at)
    cs=candidates(tmp_path)
    result=enrich_candidates(cs,cache,as_of=at,now=at)
    a=result['CompanyCandidates'][0]['financial_assessment']
    assert first['status']=='IMPORTED' and a['status']=='AVAILABLE'
    assert a['value']['sources']['annual']['currency']=='KRW' and a['source_sha256']==pin
    assert a['imported_at']==at.isoformat()
    assert result['CompanyCandidates'][0]['investment_merit']=='NOT_ASSESSED'
    assert cs[0]['financial_assessment']['status']=='NOT_CONNECTED'
    assert enrich_candidates(cs,cache,as_of=T,now=at)['CompanyCandidates'][0]['financial_assessment']['status']=='NOT_AVAILABLE_AS_OF'
    second=import_watch(root,path,pin,cache,now=at+timedelta(hours=1))
    assert second['status']=='ALREADY_IMPORTED' and second['receipt_sha256']==first['receipt_sha256']
    assert len(list(cache.glob('*.json')))==1 and path.read_bytes()==before


@pytest.mark.parametrize('company,status',[('KRX_STOCK:123456','AVAILABLE'),('DART_CORP:99999999','COMPANY_NOT_IN_SNAPSHOT'),
                                         ('같은이름','IDENTITY_UNRESOLVED'),('SEC_CIK:123456','IDENTITY_UNRESOLVED')])
def test_exact_identity_only_no_name_or_namespace_guessing(tmp_path,company,status):
    root,path,pin=source(tmp_path);cache=tmp_path/'cache';import_watch(root,path,pin,cache,now=T)
    result=enrich_candidates(candidates(tmp_path,company),cache,as_of=T,now=T)
    assert result['CompanyCandidates'][0]['financial_assessment']['status']==status


@pytest.mark.parametrize('change',[
    lambda d:d['review_queue'][0]['company_assessment']['sources']['annual'].update(currency='USD'),
    lambda d:d['review_queue'][0]['company_assessment']['sources']['annual'].update(fiscal_year=2024),
    lambda d:d['review_queue'][0]['company_assessment']['sources']['annual'].update(issuer_corp_code='99999999'),
    lambda d:d['review_queue'][0]['company_assessment']['sources']['annual'].update(available_at_utc=(T+timedelta(days=1)).isoformat()),
    lambda d:d['review_queue'][0]['company_assessment'].update(security_id='999999'),
    lambda d:d.update(orders_enabled=True),
])
def test_reject_mismatched_company_period_currency_future_or_order_authority(tmp_path,change):
    root,path,pin=source(tmp_path,change)
    with pytest.raises(SourceShareError):import_watch(root,path,pin,tmp_path/'cache',now=T)
    assert not (tmp_path/'cache').exists()


def test_incomplete_symlink_and_wrong_pin_cannot_import(tmp_path):
    root,path,pin=source(tmp_path)
    with pytest.raises(SourceShareError):import_watch(root,path,'0'*64,tmp_path/'cache',now=T)
    (path.parent/'index.html').unlink()
    with pytest.raises(SourceShareError):import_watch(root,path,pin,tmp_path/'cache',now=T)
    (path.parent/'index.html').write_text('done')
    link=root/'output/early_leader_watch_queue/KR_20261013_ffffffffffffffff';link.symlink_to(path.parent)
    with pytest.raises(SourceShareError):import_watch(root,link/'watch_queue.json',pin,tmp_path/'cache',now=T)


def test_producer_write_and_future_candidate_are_rejected(tmp_path):
    root,path,pin=source(tmp_path)
    with pytest.raises(SourceShareError,match='producer'):
        import_watch(root,path,pin,root/'output/consumer-cache',now=T)
    assert not (root/'output/consumer-cache').exists()
    cache=tmp_path/'cache';import_watch(root,path,pin,cache,now=T)
    cs=candidates(tmp_path);cs[0]['decision_at']=(T+timedelta(days=1)).isoformat()
    with pytest.raises(SourceShareError,match='future'):enrich_candidates(cs,cache,as_of=T,now=T)


def test_duplicate_issuer_does_not_choose_one_stock_arbitrarily(tmp_path):
    def duplicate(d):
        row=deepcopy(d['review_queue'][0]);row['security_id']='654321'
        row['company_assessment']['security_id']='654321';row['company_assessment']['inputs']['security_id']='654321'
        d['review_queue'].append(row)
    root,path,pin=source(tmp_path,duplicate);cache=tmp_path/'cache';import_watch(root,path,pin,cache,now=T)
    assert enrich_candidates(candidates(tmp_path),cache,as_of=T,now=T)['CompanyCandidates'][0]['financial_assessment']['status']=='AMBIGUOUS_IDENTITY'


def test_corrupt_optional_assessment_does_not_remove_news_candidate(tmp_path):
    root,path,pin=source(tmp_path);cache=tmp_path/'cache';import_watch(root,path,pin,cache,now=T)
    receipt=next(cache.glob('*.json'));receipt.write_text('{}')
    result=enrich_candidates(candidates(tmp_path),cache,as_of=T,now=T)
    assert len(result['CompanyCandidates'])==1 and result['assessment_receipts_skipped']==1
    assert result['assessment_source_status']=='PARTIAL_UNAVAILABLE'


def test_cli_and_http_financial_research_keep_v3_unchanged(tmp_path,capsys):
    from scripts.search_themes import main
    from scripts.open_research_dashboard import DashboardServer
    from datetime import datetime,timezone
    import threading
    from urllib.request import urlopen
    root,path,pin=source(tmp_path);docs=tmp_path/'docs';cache=docs/'era_assessments'
    import_watch(root,path,pin,cache)
    store=ThemeStore(docs/'theme_history');store.ingest([event(company='DART_CORP:12345678')])
    assert main(['--root',str(store.root),'--with-financials','--assessment-root',str(cache)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['schema']=='newscatalyst.company_research.v1'
    assert result['CompanyCandidates'][0]['financial_assessment']['status']=='AVAILABLE'
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        with urlopen(base+'/api/company-research') as response: research=json.load(response)
        assert research['CompanyCandidates'][0]['financial_assessment']['value']['annual_fiscal_year']==2025
        with urlopen(base+'/api/themes?company_candidates=1') as response: legacy=json.load(response)
        assert legacy['schema']=='newscatalyst.theme_delivery.v3'
        assert legacy['CompanyCandidates'][0]['financial_assessment']['status']=='NOT_CONNECTED'
        with urlopen(base+'/api/period') as response: period=json.load(response)
        assert period['company_candidates'][0]['financial_assessment']['status']=='AVAILABLE'
    finally:
        server.shutdown();server.server_close();worker.join(2)
