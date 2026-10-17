"""Completed producer snapshot -> exact company -> current news + price/risks.

Synthetic data only. No EraLeader source modifications, official API or orders.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from newscatalystos.era_daily_assessment import (
    canonical,validate_daily,import_daily,read_latest,assessment_for,project_themes,refresh_daily)
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.source_share import SourceShareError
from test_federated_news_search import fingerprint

T=datetime(2026,10,17,1,tzinfo=timezone.utc)


def source(tmp_path,change=None,at=T):
    root=tmp_path/'producer'
    view={'source_watch_sha256':'a'*64,'rows':[{'id':'000660','name':'가상전자'}]}
    viewraw=canonical(view)+b'\n';viewid=sha256(viewraw).hexdigest()
    v=root/'output/candidate_browser'/viewid
    v.mkdir(parents=True);(v/'view.json').write_bytes(viewraw)
    row={'security_id':'000660','name':'가상전자','orders':0,'investment_rank':None,
         'formal_selection_state':'WATCH','facts':{},
         'dart_annual_cfs':{'security_id':'000660','status':'DART_VERIFIED_ANNUAL_CFS',
             'issuer_corp_code':'00164779','fiscal_year':2025,'orders':0,'valuation_score':None,
             'first_receipt_sha256':'f'*64,'first_local_received_at_utc':at.isoformat(),
             'revenue_krw':1000,'operating_income_krw':200,'operating_margin_pct':20,
             'operating_cashflow_krw':150,'current_valuation':{'status':'N/A'}},
         'krx_completed_close':{'security_id':'000660','status':'OBSERVED_COMPLETED_KRX_CLOSE',
             'source_market_session':'2026-10-16','first_receipt_sha256':'c'*64,
             'raw_sha256':'d'*64,'first_local_received_at_utc':at.isoformat(),
             'currency':'KRW','live_quote':False,'close_krw':100},
         'evidence_brief':{'security_id':'000660','market_session':'2026-10-16',
             'orders':0,'investment_rank':None,'formal_leader_promotion':False,
             'supporting_evidence':[{'basis':'DART_ANNUAL_CFS','first_receipt_sha256':'f'*64,
               'order_instruction':False,'formal_leader_change':False,'reason':'영업이익률 양수 관측'}],
             'weakening_evidence':[],'unavailable_or_limited':['정식 저평가 미확인']}}
    doc={'schema':'eraleader.kr_daily_candidate_explorer.v1','research_only':True,
         'receiver_neutral':True,'orders':0,'investment_rank_created':False,'candidate_count':1,
         'source':{'market_session':'2026-10-16','evaluated_at_utc':at.isoformat(),
           'source_watch_sha256':'a'*64,'source_evaluation_sha256':'b'*64,
           'source_browser_file_sha256':sha256(viewraw).hexdigest()},
         'links':{'original_candidate_browser':'../../candidate_browser/'+viewid+'/index.html'},
         'candidates':[row]}
    if change:change(doc)
    doc['content_sha256']=sha256(canonical(doc)).hexdigest()
    raw=canonical(doc)+b'\n';path=root/'output/kr_daily_candidate_explorer'/doc['content_sha256']/'report.json'
    path.parent.mkdir(parents=True);path.write_bytes(raw)
    path.with_name('index.html').write_text('<p>Completed synthetic producer report</p>')
    home=root/'output/operations/site';home.mkdir(parents=True,exist_ok=True)
    (home/'index.html').write_text('<a href="../../kr_daily_candidate_explorer/'+doc['content_sha256']+'/index.html">current</a>')
    return root,path,sha256(raw).hexdigest(),doc


def test_current_daily_import_exact_issuer_first_receipt_and_no_producer_writes(tmp_path):
    root,path,pin,doc=source(tmp_path);before=fingerprint(root)
    out=tmp_path/'news-cache';at=T+timedelta(hours=1)
    first=import_daily(root,path,pin,out,now=at)
    snap,skipped=read_latest(out,as_of=at,now=at)
    found=assessment_for('가상전자',snap)
    assert first['status']=='IMPORTED' and not skipped
    assert found['status']=='AVAILABLE' and found['entity_id']=='DART_CORP:00164779'
    assert found['value']==doc['candidates'][0] and found['security_id']=='000660'
    assert found['identity_evidence_sha256']=='f'*64 and not found['orders_enabled']
    assert found['imported_at']==at.isoformat() and not found['verified_real_benefit']
    assert read_latest(out,as_of=T,now=at)[0] is None
    assert assessment_for('DART_CORP:00164779',snap)['status']=='AVAILABLE'
    assert assessment_for('KRX_STOCK:000660',snap)['status']=='AVAILABLE'
    assert assessment_for('가상전',snap)['status']=='COMPANY_NOT_IN_SNAPSHOT'
    assert assessment_for('DART_CORP:99999999',snap)['status']=='COMPANY_NOT_IN_SNAPSHOT'
    assert assessment_for('SEC_CIK:123',snap)['status']=='US_ASSESSMENT_NOT_CONNECTED'
    second=import_daily(root,path,pin,out,now=at+timedelta(hours=1))
    assert second['status']=='ALREADY_IMPORTED' and second['imported_at']==first['imported_at']
    assert len(list(out.glob('*.json')))==1 and fingerprint(root)==before
    config=tmp_path/'private-config.json';config.write_bytes(canonical({'era_root':str(root),'source':'OPERATIONS_CURRENT_KR_DAILY'}));config.chmod(0o600)
    assert refresh_daily(config,out,now=at)['status']=='ALREADY_IMPORTED'
    assert refresh_daily(config,tmp_path/'no-copy',now=at,check_only=True)['status']=='VERIFIED_READ_ONLY'
    assert not (tmp_path/'no-copy').exists()


@pytest.mark.parametrize('change',[
    lambda d:d.update(orders=1),
    lambda d:d.update(research_only=False),
    lambda d:d['candidates'][0]['dart_annual_cfs'].update(security_id='999999'),
    lambda d:d['candidates'][0]['dart_annual_cfs'].update(first_receipt_sha256='bad'),
    lambda d:d['candidates'][0]['dart_annual_cfs'].update(first_local_received_at_utc=(T+timedelta(days=2)).isoformat()),
    lambda d:d['candidates'][0]['krx_completed_close'].update(live_quote=True),
    lambda d:d['candidates'][0]['krx_completed_close'].update(source_market_session='2026-10-15'),
    lambda d:d['candidates'][0]['evidence_brief']['supporting_evidence'][0].update(first_receipt_sha256='e'*64),
])
def test_unsafe_mismatched_or_future_producer_evidence_rejected(tmp_path,change):
    root,path,pin,_=source(tmp_path,change)
    with pytest.raises(SourceShareError):import_daily(root,path,pin,tmp_path/'out',now=T)
    assert not (tmp_path/'out').exists()


def test_missing_completed_marker_wrong_hash_and_ambiguous_issuer(tmp_path):
    root,path,pin,doc=source(tmp_path)
    with pytest.raises(SourceShareError):import_daily(root,path,'0'*64,tmp_path/'cache',now=T)
    with pytest.raises(SourceShareError):import_daily(root,path,pin,root/'output/invalid-write',now=T)
    path.with_name('index.html').unlink()
    with pytest.raises((SourceShareError,OSError)):import_daily(root,path,pin,tmp_path/'cache',now=T)
    assert not (tmp_path/'cache').exists()
    row=deepcopy(doc['candidates'][0]);row['security_id']='123456'
    row['dart_annual_cfs']['security_id']=row['krx_completed_close']['security_id']=row['evidence_brief']['security_id']='123456'
    doc['candidates'].append(row)
    receipt={'source_sha256':pin,'imported_at':T.isoformat()}
    assert assessment_for('가상전자',(receipt,doc))['status']=='AMBIGUOUS_IDENTITY'
    assert assessment_for('DART_CORP:00164779',(receipt,doc))['status']=='AMBIGUOUS_IDENTITY'


def test_actual_http_article_daily_and_backward_compatible_scoped_export(tmp_path,monkeypatch):
    from test_company_evidence import rss
    from scripts.open_research_dashboard import DashboardServer
    theme,args,report_path,report,info,store=rss(tmp_path/'news')
    at=args['now'];producer,path,pin,doc=source(tmp_path/'era',at=at-timedelta(seconds=1))
    cache=args['document_root']/'era_daily_assessments'
    import_daily(producer,path,pin,cache,now=at)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    import shutil
    separate=tmp_path/'separate-source'
    shutil.copytree(store.root,separate/'document_analysis/theme_history')
    server=DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'],
        news_search_workspaces=(info[0],),additional_source_roots=(("company",separate),))
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    before=fingerprint(tmp_path)
    def get(path,query=None):
        with urlopen(f'http://127.0.0.1:{server.server_port}'+path+('?' + urlencode(query) if query else ''),timeout=20) as r:
            assert r.status==200;return json.load(r)
    try:
        legacy=get('/api/themes',{'scope':'base'});assert 'export_origin' not in legacy['ThemeCandidates'][0]
        exported=get('/api/themes')  # existing receiver URL now includes new scopes
        assert exported==get('/api/themes',{'scope':'all'})
        assert all(t in exported['ThemeCandidates'] for t in legacy['ThemeCandidates'])
        found=next(t for t in exported['ThemeCandidates'] if 'DART_CORP:00164779' in t['entity_ids'])
        assert found['export_origin']['theme_id']==theme['theme_id']
        assert found['theme_id']!=theme['theme_id'] and found['event_ids']==theme['event_ids']
        assert found['decision_at']==at.isoformat()
        again=get('/api/themes',{'scope':'all'});assert again==exported
        past=get('/api/themes',{'scope':'all','as_of':(at-timedelta(seconds=1)).isoformat()})
        assert not any('DART_CORP:00164779' in t['entity_ids'] for t in past['ThemeCandidates'])
        a=get('/api/era-assessment',{'entity_id':'가상전자'})
        assert a['status']=='AVAILABLE' and a['value']['dart_annual_cfs']['revenue_krw']==1000
        rows=get('/api/news-search',{'q':'HBM'})
        original=rows['results'][0]
        detail=get('/api/news-evidence',{'q':'HBM',**{k:original[k] for k in ('provider_id','event_id','title_sha256')}})
        actor=next(p for t in detail['article_company_context']['themes'] for p in t['direct_parties'] if p['entity_id']=='가상전자')
        assert actor['era_daily_assessment']['status']=='AVAILABLE'
        assert actor['official_entity_id'] is None  # original source remains unchanged
        period=get('/api/period',{'view':'day','date':at.astimezone().date().isoformat()})
        assert any(c['era_daily_assessment']['status']=='AVAILABLE' for c in period['company_candidates'])
    finally:
        server.shutdown();server.server_close();worker.join(3)
    assert fingerprint(tmp_path)==before


def test_display_has_financial_price_risk_and_unconfirmed_status():
    import subprocess
    script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(tag,cls,text){return {tag,textContent:text||'',children:[],append(...xs){this.children.push(...xs)}}}
const ctx={node,Intl};vm.runInNewContext(src.slice(src.indexOf('function renderEraDailyAssessment('),src.indexOf('function renderThemes(')),ctx);
const box=node('div');
ctx.renderEraDailyAssessment(box,{status:'AVAILABLE',source_name:'합성기업<img>',security_id:'123456',entity_id:'DART_CORP:12345678',imported_at:'2026-10-17',producer_evaluated_at:'2026-10-16',source_sha256:'a'.repeat(64),value:{formal_selection_state:'WATCH',dart_annual_cfs:{status:'DART_VERIFIED_ANNUAL_CFS',fiscal_year:2025,revenue_krw:1000,operating_income_krw:200,operating_margin_pct:20,operating_cashflow_krw:100},krx_completed_close:{status:'OBSERVED_COMPLETED_KRX_CLOSE',source_market_session:'2026-10-16',close_krw:100},evidence_brief:{supporting_evidence:[{reason:'양수 현금흐름'}],weakening_evidence:[],unavailable_or_limited:['정식 PER 미확인']}}});
function text(x){return [x.textContent,...x.children.flatMap(text)]}
const s=text(box).join(' ');assert(s.includes('합성기업<img>'));assert(s.includes('양수 현금흐름'));assert(s.includes('보관 종가'));assert(s.includes('미확인'));assert(s.includes('FY2025'));
console.log('READONLY_ERA_FINANCIAL_AND_PRICE_UI_PASS');
'''
    subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parent.parent,check=True,capture_output=True,text=True)


def test_corrupt_optional_snapshot_keeps_source_news_unmodified(tmp_path):
    root,path,pin,doc=source(tmp_path);cache=tmp_path/'cache'
    import_daily(root,path,pin,cache,now=T)
    entry=next(cache.glob('era_daily_*.json'));entry.write_text('{}')
    snap,skipped=read_latest(cache,as_of=T,now=T)
    assert snap is None and skipped==1
    assert assessment_for('가상전자',snap)['status']=='NOT_AVAILABLE_AS_OF'
    assert sha256(path.read_bytes()).hexdigest()==pin


def test_optional_producer_refresh_failure_does_not_stop_news(tmp_path):
    from scripts.run_approved_research_feeds_once import parser,execute
    from test_approved_research_feeds_once import _setup
    root=_setup(tmp_path)
    opts=parser().parse_args(['--workspaces-root',str(root),'--dry-run',
        '--era-daily-config',str(tmp_path/'missing-config.json'),
        '--era-daily-root',str(tmp_path/'received')])
    code,report=execute(opts)
    assert code==0 and report['sources_failed']==0
    assert report['sources_checked']==5
    assert report['era_daily_connection']['status']=='UNAVAILABLE'
    assert not (tmp_path/'received').exists()


def test_tampering_import_time_cannot_backdate_exact_company(tmp_path):
    root,path,pin,doc=source(tmp_path);cache=tmp_path/'cache';at=T+timedelta(hours=1)
    import_daily(root,path,pin,cache,now=at)
    file=next(cache.glob('era_daily_*.json'));r=json.loads(file.read_bytes())
    r['imported_at']=T.isoformat();file.write_bytes(canonical(r)+b'\n')
    assert read_latest(cache,as_of=T,now=at)==(None,1)
