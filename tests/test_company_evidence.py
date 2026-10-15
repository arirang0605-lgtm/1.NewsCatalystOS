"""Private synthetic title/body evidence, exact versions, no operating writes."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
from pathlib import Path
import threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.company_evidence import company_evidence
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from test_feed_analysis import setup,run
from test_federated_news_search import fingerprint

TITLE='가상전자는 HBM 수요 감소로 감산을 결정했고 새빛소재는 DRAM 수요 증가로 공급계약을 체결했다'

def rss(tmp_path,title=TITLE):
    info=setup(tmp_path,title);at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=run(info,now=at);row=report['results'][0]
    reports=tmp_path/'reports';path,pin=publish_feed_analysis(report,reports/'core/reports')
    obs=[economic_observation(c,origin_reference=row['source_url'],source_url=row['source_url'],
         source_id=row['provider_id'],source_available_at=row['source_available_at'],content_scope='RSS_TITLE_METADATA',
         source_binding={'source_event_sha256':row['source_event_sha256'],'document_sha256':row['source_title_sha256']}) for c in row['economic_changes']]
    docs=tmp_path/'documents';store=ThemeStore(docs/'theme_history');themes=store.ingest(obs,now=at)
    theme=next(t for t in themes if t['economic_driver']=='DEMAND_CONTRACTION')
    spec={'registry':info[0].registry_path,'inbox':info[0].inbox_root,'state':info[0].poll_state}
    args=dict(reports_root=reports,document_root=docs,feeds=[spec],now=at+timedelta(seconds=5),as_of=at)
    return theme,args,path,report,info,store


def test_exact_rss_clause_original_sha_and_no_writes(tmp_path):
    theme,args,path,report,info,store=rss(tmp_path,TITLE.replace(' HBM','  HBM'))
    before=fingerprint(tmp_path)
    result=company_evidence(theme,'가상전자',**args)
    item=result['items'][0]
    assert item['status']=='READY' and item['content_scope']=='RSS_TITLE_METADATA'
    assert '가상전자' in item['excerpt'] and '새빛소재' not in item['excerpt'] and 'DRAM' not in item['excerpt']
    assert item['evidence_sha256']==sha256(TITLE.replace(' HBM','  HBM').encode()).hexdigest()
    assert item['excerpt_sha256']==sha256(item['excerpt'].encode()).hexdigest()
    assert fingerprint(tmp_path)==before
    assert company_evidence(theme,'다른전자',**args)['items']==[]


@pytest.mark.parametrize('fault',['tampered_report','wrong_sha','wrong_event','wrong_time','wrong_url','missing_source','revoked'])
def test_mismatch_never_returns_excerpt(tmp_path,fault):
    theme,args,path,report,info,store=rss(tmp_path)
    if fault=='tampered_report':path.write_bytes(path.read_bytes().replace('HBM'.encode(),b'XYZ'))
    elif fault=='wrong_sha':theme['source_refs'][0]['evidence_sha256']='f'*64
    elif fault=='wrong_event':
        old=theme['source_refs'][0]['event_id'];theme['source_refs'][0]['event_id']='e'*64
        theme['event_ids']=['e'*64 if x==old else x for x in theme['event_ids']]
    elif fault=='wrong_time':theme['source_refs'][0]['source_available_at']=(args['as_of']-timedelta(seconds=1)).isoformat()
    elif fault=='wrong_url':theme['source_refs'][0]['source_url']='https://example.org/other'
    elif fault=='missing_source':args['feeds']=[]
    elif fault=='revoked':
        p=args['feeds'][0]['registry'];data=json.loads(p.read_bytes())
        for provider in data['providers']:provider['approved']=False
        p.write_text(json.dumps(data))
    result=company_evidence(theme,'가상전자',**args)
    assert all(r['status']!='READY' and r['excerpt'] is None for r in result['items'])


def test_future_report_is_not_backdated_and_historical_query_keeps_old_version(tmp_path):
    theme,args,path,report,info,store=rss(tmp_path)
    later=args['as_of']+timedelta(seconds=2)
    report['checked_at']=later.isoformat()
    for row in report['results']:row['analysis_available_at']=later.isoformat()
    other=Path(args['reports_root'])/'future';publish_feed_analysis(report,other/'core/reports')
    args['reports_root']=other
    item=company_evidence(theme,'가상전자',**args)['items'][0]
    assert item['status']=='NOT_AVAILABLE_AS_OF' and item['excerpt'] is None
    args['as_of']=later
    assert company_evidence(theme,'가상전자',**args)['items'][0]['status']=='READY'


def body(tmp_path):
    from test_motir_document_analysis import case
    from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis
    from newscatalystos.motir_article_binding import consume_motir_article_binding
    from newscatalystos.motir_document_collection import _registry_bytes
    source,opts=case(tmp_path,body=TITLE+'. 추가 근거는 미확인이다.')
    at=datetime.now(timezone.utc)+timedelta(seconds=1)
    report=analyze_motir_document(**opts,now=at)
    documents=tmp_path/'documents';folder=documents/('a'*64)
    publish_motir_document_analysis(report,folder/'reports')
    binding=consume_motir_article_binding(opts['binding_path'],opts['binding_sha256'],now=at)
    change=next(c for c in report['economic_changes'] if c['entity_ids']==['가상전자'])
    obs=economic_observation(change,origin_reference=report['source_url'],source_url=report['source_url'],
        source_id='motir-official-press',source_available_at=report['source_available_at'],
        source_binding={'source_event_sha256':binding['archive_version'],'document_sha256':report['document_sha256']})
    theme=ThemeStore(documents/'theme_history').ingest([obs],now=at)[0]
    registry=tmp_path/'article-registry.json';registry.write_bytes(_registry_bytes(source[1].providers[0]));registry.chmod(0o600)
    jobs=[{k:opts[k] for k in ('binding_path','binding_sha256','archive_root')}|{'article_registry':registry}]
    args=dict(reports_root=tmp_path/'no-reports',document_root=documents,jobs=jobs,as_of=at,now=at+timedelta(seconds=1))
    return theme,args,binding


def test_licensed_paragraph_exact_binding_rights_and_company_clause(tmp_path):
    theme,args,binding=body(tmp_path);before=fingerprint(tmp_path)
    item=company_evidence(theme,'가상전자',**args)['items'][0]
    assert item['status']=='READY' and item['content_scope']=='LICENSED_ARTICLE_TEXT'
    assert '감산' in item['excerpt'] and '새빛소재' not in item['excerpt']
    assert item['evidence_sha256']==theme['source_refs'][0]['evidence_sha256']
    assert fingerprint(tmp_path)==before


@pytest.mark.parametrize('fault',['revoked','body_tamper','binding','paragraph'])
def test_licensed_mismatch_never_exposes_body(tmp_path,fault):
    theme,args,binding=body(tmp_path);job=args['jobs'][0]
    if fault=='revoked':
        p=job['article_registry'];data=json.loads(p.read_bytes());data['providers'][0]['approved']=False;p.write_text(json.dumps(data))
    elif fault=='body_tamper':
        p=job['archive_root']/binding['archive_version']/'payload.bin';p.write_bytes(p.read_bytes()+b'x')
    elif fault=='binding':theme['source_refs'][0]['source_binding']['document_sha256']='e'*64
    else:theme['source_refs'][0]['evidence_sha256']='e'*64
    item=company_evidence(theme,'가상전자',**args)['items'][0]
    assert item['status']!='READY' and item['excerpt'] is None


def test_dashboard_company_evidence_endpoint(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    from newscatalystos import company_evidence as module
    theme,args,path,report,info,store=rss(tmp_path)
    # Endpoint runs after the synthetic source and theme timestamps.
    monkeypatch.setattr(module,'installed_sources',lambda base:(args['feeds'],[]))
    from datetime import datetime as RealDatetime
    class Clock(RealDatetime):
        @classmethod
        def now(cls,tz=None):return args['now']
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        query=urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':args['as_of'].isoformat()})
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/company-evidence?'+query) as response:result=json.load(response)
        assert result['items'][0]['status']=='READY'
        assert '새빛소재' not in result['items'][0]['excerpt']
    finally:server.shutdown();server.server_close();worker.join(2)
