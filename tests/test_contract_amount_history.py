"""Synthetic saved versions through the existing theme/company HTTP query."""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import json
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from newscatalystos.company_evidence import company_evidence
from newscatalystos.contract_amount_history import compare_amounts
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from test_feed_analysis import setup, run, URL
from test_federated_news_search import collect, GOV, fingerprint
from test_new_source_adapter import NOW

BEFORE='가상전자는 HBM 수요 증가로 공급계약 금액 3000억원 체결'
AFTER='가상전자는 HBM 공급계약 금액 2000억원으로 감액'


def case(tmp_path,after=AFTER,doc='contract-1'):
    info=setup(tmp_path,BEFORE)
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    first=run(info,now=at)
    row=first['results'][0]
    root=tmp_path/'reports';docs=tmp_path/'documents'
    publish_feed_analysis(first,root/'core/reports')
    change=row['economic_changes'][0]
    obs=economic_observation(change,origin_reference=row['source_url'],source_url=row['source_url'],
        source_id=row['provider_id'],source_available_at=row['source_available_at'],content_scope='RSS_TITLE_METADATA',
        source_binding={'source_event_sha256':row['source_event_sha256'],'document_sha256':row['source_title_sha256']})
    store=ThemeStore(docs/'theme_history');theme=store.ingest([obs],now=at)[0]
    collect(info[0],info[1],GOV,[(doc,after,URL)],at=NOW+timedelta(hours=1))
    later=at+timedelta(seconds=2)
    revised=run(info,now=later);path,pin=publish_feed_analysis(revised,root/'core/reports')
    args=dict(reports_root=root,document_root=docs,feeds=[dict(registry=info[0].registry_path,
        inbox=info[0].inbox_root,state=info[0].poll_state)],now=later+timedelta(seconds=5),as_of=later)
    return theme,args,path,revised,at,info


def history(theme,args):
    item=company_evidence(theme,'가상전자',**args)['items'][0]
    assert item['status']=='READY'
    return item['contract_amount_history']


def test_two_saved_versions_to_theme_company_and_readonly(tmp_path):
    theme,args,path,report,at,info=case(tmp_path)
    before=fingerprint(tmp_path)
    value=history(theme,args);change=value['changes'][0]
    assert value['status']=='AVAILABLE' and len(value['changes'])==1
    assert change['status']=='READY'
    assert change['before_value']=='300000000000' and change['after_value']=='200000000000'
    assert change['difference']=='-100000000000' and change['percent_change']=='-33.33'
    assert change['before_source']['source_event_sha256']==change['after_source']['source_event_sha256']
    assert change['before_source']['source_title_sha256']!=change['after_source']['source_title_sha256']
    assert change['before_source']['report_sha256']!=change['after_source']['report_sha256']
    assert fingerprint(tmp_path)==before
    store=ThemeStore(args['document_root']/'theme_history')
    assert store.search(query='가상전자',as_of=args['as_of'],now=args['now'])


def test_future_correction_not_disclosed_and_reanalysis_deduplicated(tmp_path):
    theme,args,path,report,at,info=case(tmp_path)
    args['as_of']=at
    assert history(theme,args)['changes']==[]
    args['as_of']=args['now']
    duplicate=deepcopy(report);duplicate['checked_at']=args['now'].isoformat()
    publish_feed_analysis(duplicate,args['reports_root']/'core/reports')
    assert len(history(theme,args)['changes'])==1


@pytest.mark.parametrize('fault',['other_document','wrong_prior_sha','wrong_prior_time','wrong_provider',
                                  'wrong_event','wrong_scope','missing_link','future_link','bad_time','tampered'])
def test_no_similarity_join_or_invalid_link(tmp_path,fault):
    theme,args,path,report,at,info=case(tmp_path,doc='another-contract' if fault=='other_document' else 'contract-1')
    row=next(r for r in report['results'] if r['headline']==AFTER)
    if fault=='wrong_prior_sha':row['followup_change']['prior_title_sha256']='f'*64
    elif fault=='wrong_prior_time':row['followup_change']['prior_available_at']=at.isoformat()
    elif fault=='wrong_provider':row['provider_id']='other'
    elif fault=='wrong_event':row['source_event_sha256']='f'*64
    elif fault=='wrong_scope':row['followup_change']['scope']='SIMILAR_COMPANY'
    elif fault=='missing_link':row['followup_change']=None
    elif fault=='future_link':row['followup_change']['available_at']=(args['now']+timedelta(days=1)).isoformat()
    elif fault=='bad_time':row['followup_change']['available_at']='invalid'
    path.unlink()
    path,_=publish_feed_analysis(report,args['reports_root']/'core/reports')
    if fault=='tampered':path.write_bytes(path.read_bytes()+b' ')
    assert history(theme,args)['changes']==[]


@pytest.mark.parametrize(('a','b','status'),[
    ('3000억원','2000억원으로','READY'),('0.3조원','2000억원으로','READY'),
    ('0원','2000억원으로','ZERO_BASE'),('3000억원','0원으로','ZERO_BASE'),
    ('3000억원','2000억원','TARGET_AMOUNT_UNCLEAR'),
    ('3000억원','$2000 USD으로','CURRENCY_UNSUPPORTED'),
    ('3000억원','USD 2000억원으로','CURRENCY_UNSUPPORTED'),
    ('3000억원','4000억원으로','DIRECTION_MISMATCH'),
    ('3000억원','미확인으로','AMOUNT_UNKNOWN'),
    ('3000억원 및 투자 10억원','2000억원으로','MULTIPLE_AMOUNTS'),
    ('3000억원','2000억원으로, 매출 100억원','MULTIPLE_AMOUNTS'),
])
def test_amount_semantics(a,b,status):
    value=compare_amounts('HBM 공급계약 금액 '+a+' 체결','HBM 공급계약 금액 '+b+' 감액')
    assert value['status']==status
    if status!='READY':assert value['difference'] is value['percent_change'] is None


def test_ambiguous_amount_reaches_card_as_na(tmp_path):
    theme,args,*_=case(tmp_path,after=AFTER.replace('으로',''))
    value=history(theme,args)['changes'][0]
    assert value['status']=='TARGET_AMOUNT_UNCLEAR' and value['after_source']['headline']


@pytest.mark.parametrize('after',[
    '가상전자는 HBM 수요 증가로 공급계약 금액 2000억원 체결',
    '가상전자는 HBM 별도 공급계약 금액 2000억원으로 감액',
    '다른전자는 HBM 공급계약 금액 2000억원으로 감액',
])
def test_same_document_alone_is_not_explicit_same_contract_change(tmp_path,after):
    theme,args,*_=case(tmp_path,after=after)
    assert history(theme,args)['changes']==[]


def test_revision_source_missing_no_disclosure(tmp_path,monkeypatch):
    import newscatalystos.company_evidence as module
    theme,args,*_=case(tmp_path)
    original=module._rss_source
    def read(ref,row,*rest):
        return (None,'RIGHTS_UNAVAILABLE') if row['headline']==AFTER else original(ref,row,*rest)
    monkeypatch.setattr(module,'_rss_source',read)
    value=history(theme,args)
    assert value['changes']==[] and value['status']=='RIGHTS_UNAVAILABLE'


def test_existing_company_evidence_http(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    theme,args,*_=case(tmp_path)
    monkeypatch.setattr('newscatalystos.company_evidence.installed_sources',lambda base:(args['feeds'],[]))
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return args['now']
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        query=urlencode(dict(theme_id=theme['theme_id'],entity_id='가상전자',as_of=args['as_of'].isoformat()))
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/company-evidence?'+query) as response:result=json.load(response)
        assert result['items'][0]['contract_amount_history']['changes'][0]['difference']=='-100000000000'
    finally:server.shutdown();server.server_close();worker.join(2)
