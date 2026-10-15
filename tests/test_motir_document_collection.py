"""Automatic official body collection uses offline HTTP and real receipt paths."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from newscatalystos.motir_document_collection import collect_motir_documents
from newscatalystos.motir_article_binding import consume_motir_article_binding
from newscatalystos.provider_registry import MOTIR_PRESS_RIGHTS
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.motir_document_analysis import publish_motir_document_analysis
from test_federated_news_search import collect, setup_workspace
from test_motir_rss_post import registry
from test_ai_gemini_transport import LocalResponse, LocalOpener, packet
from test_motir_document_analysis import case, analyze_motir_document, NEW

NOTICE = b'<img src="/images/contents/sub/mark_license01.png">' + '공공누리 1유형(출처표시)'.encode()


class Site:
    def __init__(self, notice=NOTICE, fail=None):
        self.calls=[];self.notice=notice;self.fail=fail
    def open(self, request, *, timeout):
        url=request.full_url;self.calls.append(url)
        if url==MOTIR_PRESS_RIGHTS:return LocalResponse(self.notice,url)
        if self.fail:raise TimeoutError('synthetic timeout')
        ident=url.split('/')[-2]
        body=('<input name="bbsSeqN" value="'+ident+'"><div class="detail-cont mViewerContents"><p>'+NEW+'</p></div>').encode()
        return LocalResponse(body,url)


def setup(tmp_path, count=1):
    feed=registry();work=setup_workspace(tmp_path,'motir',feed)
    items=[]
    for i in range(count):
        url=f'https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/{172295+i}/view'
        items.append((url,'반도체 공장 신규 투자 발표 '+str(i),url))
    collect(work,feed,'motir-official-press',items,at=datetime.now(timezone.utc))
    return dict(registry=feed,inbox_root=work.inbox_root,poll_state=work.poll_state,root=tmp_path/'collection')


def test_collect_bind_register_once_then_restart_without_http(tmp_path):
    args=setup(tmp_path);site=Site()
    first=collect_motir_documents(**args,opener=site)
    assert first['source_fetch_calls']==2 and first['registered_documents']==1
    job=first['jobs'][0]
    binding=consume_motir_article_binding(Path(job['binding_path']),job['binding_sha256'])
    assert binding['new_economic_event_verified'] is False
    assert collect_motir_documents(**args,opener=site)['jobs']==first['jobs']
    assert len(site.calls)==2
    assert collect_motir_documents(**args,replay_only=True,opener=site)['source_fetch_calls']==0


def test_replay_never_downloads_new_bodies(tmp_path):
    args=setup(tmp_path);site=Site()
    assert not collect_motir_documents(**args,replay_only=True,opener=site)['jobs']
    assert site.calls==[]


def test_board_permission_missing_blocks_body_and_has_hourly_budget(tmp_path):
    args=setup(tmp_path);site=Site(notice=b'<!--'+NOTICE+b'-->')
    for _ in range(5):
        result=collect_motir_documents(**args,opener=site)
        assert result['status']=='DOCUMENT_LICENSE_UNAVAILABLE'
    assert site.calls==[MOTIR_PRESS_RIGHTS]*3
    assert not list(args['root'].glob('*/archive'))


def test_timeout_has_persisted_cooldown_without_human_wait(tmp_path):
    args=setup(tmp_path);site=Site(fail=True)
    result=collect_motir_documents(**args,opener=site)
    assert result['status']=='DOCUMENT_COLLECTION_PARTIAL'
    assert result['outcomes'][0]['status']=='RETRY_PENDING'
    assert not collect_motir_documents(**args,opener=site)['jobs']
    assert len(site.calls)==2


def test_total_hourly_budget_shared_between_articles_and_ticks(tmp_path):
    args=setup(tmp_path,4);site=Site()
    first=collect_motir_documents(**args,opener=site)
    assert first['source_fetch_calls']==3 and first['registered_documents']==2
    second=collect_motir_documents(**args,opener=site)
    assert second['source_fetch_calls']==0 and len(site.calls)==3


def test_document_dashboard_keeps_ai_over_later_rules_only_report(tmp_path,monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','synthetic-gemini-key-only-for-offline-tests')
    _,args=case(tmp_path)
    result=analyze_motir_document(**args,analyze_existing=True,allow_paid=True,opener=LocalOpener(packet()))
    root=tmp_path/'display';folder=root/args['binding_sha256']/'reports'
    publish_motir_document_analysis(result,folder)
    later=analyze_motir_document(**args)
    publish_motir_document_analysis(later,folder)
    records,info=scan_saved_analysis(tmp_path/'empty',document_root=root)
    assert len(records)==1 and info['saved_reports_seen']==2
    assert records[0]['ai_summary']==result['ai_analysis']['summary']
    assert records[0]['content_scope']=='LICENSED_ARTICLE_TEXT'
    assert records[0]['analysis_purpose']=='EXISTING_ARTICLE'
    assert records[0]['source_url'].startswith('https://www.motir.go.kr/')
    result['source_url']='javascript:alert(1)'
    publish_motir_document_analysis(result,folder)
    records,info=scan_saved_analysis(tmp_path/'empty',document_root=root)
    assert info['saved_reports_skipped']==1 and len(records)==1


def test_partial_collection_still_analyzes_successful_jobs(tmp_path):
    from scripts import run_motir_policy_once as sector
    from test_motir_sector_pipeline import config
    args=setup(tmp_path/'source')
    collected=collect_motir_documents(**args,opener=Site())
    collected['status']='DOCUMENT_COLLECTION_PARTIAL'
    opts=config(tmp_path)
    opts.skip_analysis=False
    opts.document_collection_root=args['root']
    # Even an unreadable optional manifest must not stop the collected job.
    opts.document_jobs=tmp_path/'missing.json'
    calls=[]
    def run_document(args):
        calls.append(args.binding_sha256)
        return 0, {'status':'MOTIR_DOCUMENT_ANALYSIS_READY','new_ai_results':0}
    code,result=sector.run_once(opts, registry_reader=lambda _:registry(),
        feed_runner=lambda _:(0,{'status':'NOT_DUE'}),
        analysis_runner=lambda _:(0,{'status':'FEED_ECONOMIC_ANALYSIS_READY'}),
        document_collector=lambda *a,**kw:collected, document_runner=run_document)
    assert code==4 and calls==[collected['jobs'][0]['binding_sha256']]
    assert result['documents']['results'][0]['status']=='DOCUMENT_JOBS_UNAVAILABLE'
    assert result['document_collection']['status']=='DOCUMENT_COLLECTION_PARTIAL'
    assert 'jobs' not in result['document_collection']


def test_redirected_response_is_not_archived(tmp_path):
    args=setup(tmp_path)
    class Redirected(Site):
        def open(self, request, *, timeout):
            if request.full_url==MOTIR_PRESS_RIGHTS:
                return super().open(request,timeout=timeout)
            return LocalResponse(b'not an official article','https://example.invalid/article')
    result=collect_motir_documents(**args,opener=Redirected())
    assert result['status']=='DOCUMENT_COLLECTION_PARTIAL'
    assert result['registered_documents']==0
    assert not list(args['root'].glob('*/archive'))
