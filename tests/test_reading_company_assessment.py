"""Bound reading links must reach completed company assessments even without a title event."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.recent_theme_followups import publish_followups,metadata_resolver
from newscatalystos.era_daily_assessment import import_daily,canonical
from test_recent_theme_followups import scenario
from test_era_daily_assessment import source
from test_federated_news_search import fingerprint

def producer(tmp_path,name,at):
    def rename(doc):
        doc['candidates'][0]['name']=name
        view={'source_watch_sha256':doc['source']['source_watch_sha256'],
              'rows':[{'id':doc['candidates'][0]['security_id'],'name':name}]}
        raw=canonical(view)+b'\n';pin=sha256(raw).hexdigest()
        folder=tmp_path/'producer/output/candidate_browser'/pin
        folder.mkdir(parents=True);(folder/'view.json').write_bytes(raw)
        doc['source']['source_browser_file_sha256']=pin
        doc['links']['original_candidate_browser']='../../candidate_browser/'+pin+'/index.html'
    return source(tmp_path,change=rename,at=at)

def setup(tmp_path,monkeypatch,mode):
    from scripts.open_research_dashboard import DashboardServer
    root,w,documents,workspace,baselines,doc,_=scenario(tmp_path,monkeypatch)
    publish_followups(root,doc,baselines,metadata_resolver((workspace,),now=datetime.now(timezone.utc)))
    before=datetime.now(timezone.utc)
    if mode!='missing':
        era,path,pin,_=producer(tmp_path/'era','가상배전',before-timedelta(seconds=1))
        cache=documents/'era_daily_assessments'
        import_daily(era,path,pin,cache,now=before+timedelta(seconds=1))
        if mode=='corrupt':
            p=next(cache.glob('era_daily_*.json'));p.write_bytes(p.read_bytes()+b' ')
    now=before+timedelta(seconds=2)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return now
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,
        news_search_workspaces=(workspace,),additional_source_roots=(('other',w),))
    return server,doc,before

@pytest.mark.parametrize('mode',['available','missing','corrupt'])
def test_exact_recent_article_company_snapshot_pit_and_local_failure(tmp_path,monkeypatch,mode):
    server,doc,before=setup(tmp_path,monkeypatch,mode)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    pins=fingerprint(tmp_path)
    def get(n,**extra):
        r=n['recent_source'];query=dict(q=r['headline'],provider_id=r['provider_id'],
            event_id=r['event_id'],title_sha256=r['title_sha256'],discovery='1',**extra)
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/news-evidence?'+urlencode(query)) as response:
            return json.load(response)
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/economic-discovery?common_causes=1&since='+before.isoformat().replace('+','%2B')) as response:
            comparison=json.load(response)
        group=next(g['recent_news_comparison'] for g in comparison['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
        assert group['period_comparison']['company_results']
        entries=group['company_assessment_comparison']['company_results']
        bound=next(r for r in entries if r['source_company']=='가상배전')
        assert bound['status']==('NEWLY_AVAILABLE_ASSESSMENT' if mode=='available' else 'ASSESSMENT_UNAVAILABLE')
        for n in doc['notes']:
            detail=get(n);row,=detail['recent_theme_followup_analysis']
            assert row['company_connection_basis']=='SOURCE_BOUND_READING_ANALYSIS'
            assessment=row['era_daily_assessment']
            if mode=='available' and row['source_company']=='가상배전':
                assert detail['article_company_context']['themes']==[]
                assert assessment['status']=='AVAILABLE'
                assert assessment['entity_id']=='DART_CORP:00164779'
                assert assessment['value']['dart_annual_cfs']['revenue_krw']==1000
                assert assessment['value']['krx_completed_close']['close_krw']==100
                assert not assessment['verified_real_benefit'] and not assessment['orders_enabled']
            elif mode=='available':assert assessment['status']=='COMPANY_NOT_IN_SNAPSHOT'
            else:assert assessment['status']=='NOT_AVAILABLE_AS_OF'
            past,=get(n,as_of=before.isoformat())['recent_theme_followup_analysis']
            assert past['era_daily_assessment']['status']=='NOT_AVAILABLE_AS_OF'
            assert row['note']==past['note']  # optional corporate evidence never replaces source analysis
    finally:server.shutdown();server.server_close();worker.join(2)
    assert fingerprint(tmp_path)==pins

def test_recent_reading_renderer_reuses_financial_price_risk_panel(tmp_path):
    code=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(t,c,text){return {textContent:text||'',children:[],append(...x){this.children.push(...x)},addEventListener(){}}}
const ctx={node},place=node('div');
for(const [a,b] of [['function renderEraDailyAssessment(','function renderThemes('],
['function renderRecentThemeComparison(','function renderPublicDemandNotes(']])
vm.runInNewContext(src.slice(src.indexOf(a),src.indexOf(b)),ctx);
ctx.renderRecentThemeComparison(place,{period_comparison:{since:'2026-10-18',company_results:[{
source_company:'합성 배전',status_label:'기존 발표·시점 미확정 사업 근거 추가',execution_status:'NO_NEW_EXECUTION_PROOF'}]},
company_assessment_comparison:{company_results:[{source_company:'합성 배전',status_label:'기존 기업 평가 근거 유지',
current:{status:'NOT_AVAILABLE_AS_OF'}}]},notes:[{source_company:'합성 배전',recent_available_at:'2026-10-18',
available_at:'2026-10-18',baseline_headline:'이전 근거',baseline_analysis:'기존 수요 분석',baseline_source_url:'https://example.org/old',
note:{evidence_kind:'REPORTED_CONTRACT',recent_source:{headline:'공급 제목',source_url:'https://example.org/new'},
reported_date:'2026-10-13',analysis_text:'읽기 분석 <img src=x>',product_scope:'배전',limitation:'납품 예정',source_location:'공식 자료'},
era_daily_assessment:{status:'AVAILABLE',source_name:'합성 배전',security_id:'000660',entity_id:'DART_CORP:00164779',
source_sha256:'a'.repeat(64),imported_at:'2026-10-18',producer_evaluated_at:'2026-10-17',
value:{formal_selection_state:'WATCH',dart_annual_cfs:{status:'DART_VERIFIED_ANNUAL_CFS',fiscal_year:2025,
revenue_krw:1000,operating_income_krw:200,operating_margin_pct:20,operating_cashflow_krw:150},
krx_completed_close:{status:'OBSERVED_COMPLETED_KRX_CLOSE',source_market_session:'2026-10-16',close_krw:100},
evidence_brief:{supporting_evidence:[{reason:'양수 현금흐름'}],weakening_evidence:[{reason:'관측 위험'}]}}}}]});
function all(n){return [n,...n.children.flatMap(all)]}
const text=all(place).map(n=>n.textContent).join(' ');
for(const s of ['읽기 분석 <img src=x>','읽기 분석을 사용합니다','EraLeader 기업 평가 연결','연결재무 FY2025',
'보관 종가','관측 위험','기간 시작과 비교한 근거 변화','기존 기업 평가 근거 유지','같은 계약의 새 이행 근거 미확보'])assert(text.includes(s),s);
assert(all(place).some(n=>n.href==='https://example.org/new'));
"""
    subprocess.run(['node','-e',code],cwd=Path(__file__).resolve().parent.parent,capture_output=True,text=True,check=True)
