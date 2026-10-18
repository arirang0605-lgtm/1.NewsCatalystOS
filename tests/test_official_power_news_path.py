"""Synthetic official-list fixtures exercise the existing full input/output path."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import subprocess
import threading
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

import pytest
from newscatalystos.official_news_metadata import parse_listing, BASE
from newscatalystos.provider_registry import parse_provider_registry, SCHEMA
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.economic_discovery import discover_economic_events as discover
from newscatalystos.feed_analysis_delivery import _validate_report
from newscatalystos.discovery_watch import read_discovery, export_discovery
from newscatalystos.federated_news_search import TitleSearchWorkspace
from newscatalystos.source_share import SourceShareError
from scripts.run_official_power_news_once import execute, ENDPOINT, SOURCE
from test_feed_transport import _Opener, _Response
from test_federated_news_search import fingerprint

TITLE='가상전기, 해외 765kV 초고압 변압기 수주'
HTML=('<html><script>PRIVATE SCRIPT</script><p>PRIVATE BODY</p>'
      '<a href="javascript:;" onclick="javascript:goDetail(\'123\');">'
      '<p><img src="unused"></p><p>'+TITLE+'</p></a>'
      '<a href="https://other.example.org/">변압기 제품 설명</a></html>').encode()


def registry(at, **changes):
    provider=dict(provider_id=SOURCE,kind='COMPANY_IR',method='HTML_METADATA',
        endpoint=ENDPOINT,grant='OFFICIAL_TERMS_REVIEWED',rights_reference=BASE+'newsList.jsp',
        reviewed_at=at.isoformat(),expires_at=None,approved=True,
        allow_full_text_storage=False,hourly_limit=1)
    provider.update(changes)
    return parse_provider_registry(json.dumps(dict(schema=SCHEMA,providers=[provider])).encode(),now=at)


def test_official_list_stores_only_literal_metadata_and_document_identity():
    at=datetime.now(timezone.utc)
    row,=parse_authorized_feed(registry(at),SOURCE,HTML,observed_at=at)
    assert row.headline==TITLE and row.document_id=='123'
    assert row.source_url==BASE+'newsView.jsp?commBoardSeq=123'
    assert row.reported_published_at is None and row.first_seen_at==at
    assert 'PRIVATE' not in str(row) and 'unused' not in str(row)
    assert len(parse_listing(HTML+HTML))==1


@pytest.mark.parametrize('change',[
    {'endpoint':'https://other.example.org/news'},
    {'endpoint':BASE+'newsList.jsp?paging.pageNo=999'},
    {'kind':'GOVERNMENT_POLICY'}, {'allow_full_text_storage':True},
    {'grant':'WRITTEN_LICENSE'}, {'method':'DOCUMENT'},
])
def test_html_adapter_cannot_expand_approved_endpoint_kind_or_fulltext(change):
    with pytest.raises(SourceShareError):registry(datetime.now(timezone.utc),**change)


@pytest.mark.parametrize('payload',[
    b'<script>goDetail(123)</script>',
    HTML.replace(TITLE.encode(),b''),
    HTML+HTML.replace(TITLE.encode(),'다른 제목'.encode()),
    b'\xff',
])
def test_missing_layout_conflicting_document_and_bad_encoding_fail_locally(payload):
    with pytest.raises(SourceShareError):parse_listing(payload)


@pytest.mark.parametrize('title',[
    '가상전기, 올해 수주 42억 달러 목표 세워',
    '가상전기, 초고압 변압기 수주 전망',
    '가상전기, 초고압 변압기 수주 취소',
    '가상전기, 초고압 변압기 수주 가능성',
    '가상전기, 변압기 수주잔고 증가',
    '변압기 수주',
    '가상전기, 변압기 수주한 지 10년',
    '가상전기, 변압기 수주 실패',
])
def test_order_targets_reprints_and_uncertain_claims_are_not_awards(title):
    assert discover(title)==[]


def test_awards_are_detected_before_industry_and_old_editions_stay_exact(monkeypatch):
    row,=discover(TITLE)
    assert row['change']['action']=='CONTRACT'
    assert row['change']['entity_ids']==['가상전기']
    assert row['change']['industry_tags']==['POWER_EQUIPMENT']
    assert discover(TITLE,rule_version='rss-event-first-v3')==[]
    unknown=TITLE.replace('765kV 초고압 변압기','초격자센서')
    assert discover(unknown)[0]['change']['industry_tags']==[]
    monkeypatch.setattr('newscatalystos.economic_discovery.HINTS',())
    assert discover(TITLE)[0]['change']['action']=='CONTRACT'


def collect(tmp_path,monkeypatch):
    opener=_Opener(_Response(ENDPOINT,body=HTML,media='text/html'))
    monkeypatch.setattr('newscatalystos.feed_transport._default_opener',lambda:opener)
    workspace=tmp_path/'power';documents=tmp_path/'documents'
    code,result=execute(workspace,documents/'economic_discovery')
    assert code==0 and result['discovery']['economic_events']==1
    assert opener.calls==1 and result['stored_article_bodies']==result['paid_ai_calls']==0
    return workspace,documents,opener


def test_exact_news_analysis_industry_company_excerpt_and_export_over_http(tmp_path,monkeypatch):
    from scripts.open_research_dashboard import DashboardServer
    workspace,documents,opener=collect(tmp_path,monkeypatch)
    root=documents/'economic_discovery';at=datetime.now(timezone.utc)
    plain=export_discovery(root,as_of=at,now=at)
    observed=read_discovery(root,as_of=at,now=at)
    candidate,=observed['candidates']
    assert candidate['industry_tags']==['POWER_EQUIPMENT']
    assert candidate['source_companies']==['가상전기']
    w=TitleSearchWorkspace('power',workspace/'providers/authorized_sources.json',
        workspace/'state/incremental_feeds.sqlite3',workspace/'inbox/feed_triage')
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,
        news_search_workspaces=(w,),additional_source_roots=(('power',workspace),),
        additional_reports=(('power',workspace/'feed_analysis'),))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    pins=fingerprint(tmp_path)
    def get(route,args):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(args)) as r:return json.load(r)
    try:
        item,=get('/api/news-search',{'q':'변압기'})['results']
        query={'q':'변압기','discovery':'1',**{k:item[k] for k in ('provider_id','event_id','title_sha256')}}
        detail=get('/api/news-evidence',query)
        assert detail['saved_title_analysis']['status']=='READY'
        assert detail['analysis_scope']=='ECONOMIC_DISCOVERY'
        group,=detail['article_company_context']['themes']
        party,=group['direct_parties']
        assert party['source_name']=='가상전기' and party['inclusion_status']=='READY'
        excerpt=get('/api/news-evidence',{**query,'excerpt_theme_id':group['theme_id'],
            'excerpt_entity_id':party['entity_id'],'excerpt_claim_event_id':party['event_id'],
            'excerpt_evidence_sha256':party['evidence_sha256']})['article_company_excerpt']
        assert excerpt['status']=='READY' and excerpt['excerpt']==TITLE
        assert not excerpt['verified_real_benefit'] and not excerpt['verified_real_transaction']
        ordinary=get('/api/news-evidence',{**query,'discovery':'0'})
        assert ordinary['status']=='N/A'
        bad={**query,'title_sha256':'f'*64}
        with pytest.raises(HTTPError):get('/api/news-evidence',bad)
        with pytest.raises(HTTPError):get('/api/news-evidence',{**query,'discovery':'invalid'})
        past=get('/api/news-evidence',{**query,'as_of':(at-timedelta(days=1)).isoformat()})
        assert past['article_company_context']['themes']==[]
    finally:server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path)==pins
    assert export_discovery(root,as_of=at,now=at)==plain
    code,repeat=execute(workspace,root)
    assert code==0 and repeat['discovery']['sources'][0]['theme_versions_created']==0
    assert opener.calls==1
    assert read_discovery(root)['counts']['events']==1
