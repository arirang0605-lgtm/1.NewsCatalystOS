"""Single-company existing Era assessment -> News, without WATCH insertion."""
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from copy import deepcopy
import json,subprocess
import pytest
from newscatalystos.era_individual_assessment import import_individual,validate_document,SOURCE,METHOD
from newscatalystos.era_daily_assessment import read_latest,assessment_for,project_themes
from newscatalystos.era_company_assessment import canonical
from newscatalystos.source_share import SourceShareError

NOW=datetime(2026,10,19,tzinfo=timezone.utc)
def private(p,value):
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    p.write_bytes(canonical(value)+b'\n');p.chmod(0o600);return p

def fixture(tmp_path):
    e=tmp_path/'era';root=tmp_path/'news';root.mkdir(mode=0o700)
    company={'security_id':'001234','name':'가상전기','issuer_corp_code':'00000001'}
    stamp=(NOW-timedelta(hours=2)).isoformat()
    market={'securities':[{'security_id':'001234','name':'가상전기','current_dart_directory_matched':True}],
            'market_session':'2026-10-16','built_at_utc':stamp,'content_sha256':'b'*64}
    marketfile=private(e/'output/market/marketwide_kr.json',market);sources=[]
    f={'dart_latest_cfs_business_year':2025,'dart_previous_cfs_business_year':2024,
       'dart_cfs_issuer_corp_code':'00000001','dart_cfs_revenue_krw':100,
       'dart_cfs_operating_income_krw':20,'dart_cfs_operating_margin_pct':20,
       'dart_cfs_operating_cashflow_krw':12}
    for year in [2024,2025]:
        folder=e/'output/official_api_capture'/('dart_fin_'+str(year))
        raw=private(folder/'raw_response.json',{'synthetic':True,'year':year})
        meta={'stock_code':'001234','corp_code':'00000001','bsns_year':year,'statement':'CFS','reprt_code':'11011',
              'raw_length':len(raw.read_bytes()),'raw_sha256':sha256(raw.read_bytes()).hexdigest(),
              'report_accessions':[str(year+1)+'0316000001'],'first_local_received_at_utc':stamp}
        receipt=private(folder/'first_receipt.json',meta);pin=sha256(receipt.read_bytes()).hexdigest()
        sources.append({'security_id':'001234','issuer_corp_code':'00000001','fiscal_year':year,'folder':str(folder),
            'first_receipt_sha256':pin,'raw_sha256':meta['raw_sha256'],'report_accession':meta['report_accessions'][0],
            'available_at':stamp,'statement':'CFS','report_code':'11011','currency':'KRW'})
        prefix='dart_cfs_' if year==2025 else 'dart_cfs_previous_'
        f[prefix+'first_receipt_sha256']=pin;f[prefix+'first_received_at_utc']=stamp
    a={'method':METHOD,'security_id':'001234','issuer_corp_code':'00000001','annual_fiscal_year':2025,
       'inputs':{**f,'security_id':'001234'},'source_market_session':'2026-10-16',
       'orders_enabled':False,'leader_score_unchanged':True,'valuation':{'status':'N/A'},
       'competitiveness':{'score_20':None,'supporting':[{'reason':'합성: 기존 평가기의 양수 수익성 관측'}],'weakening':[]},
       'financial_risk':{'signals':[]},'missing':[],'limitations':['합성: 사업 경쟁우위 미확인'],
       'sources':{('annual' if s['fiscal_year']==2025 else 'previous_annual'):{
           'first_receipt_sha256':s['first_receipt_sha256'],'issuer_corp_code':'00000001','fiscal_year':s['fiscal_year']}
           for s in sources}}
    d={'schema':SOURCE,'producer':'EraLeader','published_at':(NOW-timedelta(hours=1)).isoformat(),
       'producer_code_sha':'a'*40,'research_only':True,'orders':0,'watch_membership_changed':False,
       'investment_rank_created':False,'company':company,'financial':f,'assessment':a,'method':METHOD,
       'market_source':{'file':str(marketfile),'file_sha256':sha256(marketfile.read_bytes()).hexdigest(),
          'content_sha256':'b'*64,'market_session':'2026-10-16','available_at':stamp},'annual_sources':sources}
    def publish(doc):
        d=deepcopy(doc);d.pop('content_sha256',None);d['content_sha256']=sha256(canonical(d)).hexdigest()
        p=private(e/'output/news_company_assessment'/d['content_sha256']/'report.json',d)
        p.with_name('index.html').write_text('<h1>합성 개별 평가</h1>');p.with_name('index.html').chmod(0o600)
        return p,sha256(p.read_bytes()).hexdigest()
    p,pin=publish(d);return e,root,d,p,pin,publish

def test_import_exact_company_past_pit_replay_and_originals_preserved(tmp_path):
    e,root,d,p,pin,_=fixture(tmp_path)
    originals={f:sha256(f.read_bytes()).hexdigest() for f in e.rglob('*') if f.is_file()}
    result=import_individual(e,p,pin,root,now=NOW)
    assert result['status']=='IMPORTED'
    assert import_individual(e,p,pin,root,now=NOW+timedelta(hours=1))['imported_at']==NOW.isoformat()
    assert read_latest(root,as_of=NOW-timedelta(seconds=1),now=NOW)[0] is None
    snap,skipped=read_latest(root,as_of=NOW,now=NOW);assert skipped==0 and snap[1]['candidates']==[]
    for entity in ['가상전기','KRX_STOCK:001234','DART_CORP:00000001']:
        a=assessment_for(entity,snap);assert a['status']=='AVAILABLE'
        assert a['assessment_scope']=='INDIVIDUAL_COMPANY_RESEARCH' and not a['orders_enabled']
        assert a['value']['dart_annual_cfs']['operating_cashflow_krw']==12
    assert assessment_for('다른 회사',snap)['status']!='AVAILABLE'
    assert assessment_for('KRX_STOCK:001235',snap)['status']!='AVAILABLE'
    assert all(sha256(f.read_bytes()).hexdigest()==h for f,h in originals.items())
    from newscatalystos.company_economic_changes import _identity
    assert _identity('가상전기',snap,None)['status']=='INDIVIDUAL_ASSESSMENT_OUTSIDE_WATCH'
    theme={'theme_id':'c'*64,'entity_ids':['가상전기'],'event_ids':[],'decision_at':NOW.isoformat(),
           'company_links':[],'source_refs':[]}
    projected,=project_themes([theme],'discovery',snap)
    assert projected['entity_ids']==['가상전기'] and projected['export_origin']['identity_receipt_sha256'] is None

@pytest.mark.parametrize('fault',['company','issuer','future','statement','orders','raw','market','input','hash'])
def test_invalid_individual_does_not_create_receipt(tmp_path,fault):
    e,root,d,p,pin,publish=fixture(tmp_path)
    if fault=='company':d['company']['name']='다른 회사'
    if fault=='issuer':d['company']['issuer_corp_code']='00000002'
    if fault=='future':d['published_at']=(NOW+timedelta(seconds=1)).isoformat()
    if fault=='statement':d['annual_sources'][0]['statement']='OFS'
    if fault=='orders':d['orders']=1
    if fault=='input':d['assessment']['inputs']['dart_cfs_operating_margin_pct']=99
    if fault=='market':d['market_source']['file_sha256']='f'*64
    if fault=='raw':Path(d['annual_sources'][0]['folder'],'raw_response.json').write_text('changed')
    if fault!='hash':p,pin=publish(d)
    else:p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises((SourceShareError,ValueError)):
        import_individual(e,p,pin,root,now=NOW)
    assert not list(root.rglob('individual_*.json'))

def test_corrupt_receipt_skips_only_that_company(tmp_path):
    e,root,_,p,pin,_=fixture(tmp_path);import_individual(e,p,pin,root,now=NOW)
    f,=(root/'individual').glob('*.json');f.write_bytes(f.read_bytes()+b' ')
    snap,skipped=read_latest(root,as_of=NOW,now=NOW)
    assert snap is None and skipped==1

def test_individual_UI_displays_existing_evaluation_and_official_annual_links(tmp_path):
    e,root,_,p,pin,_=fixture(tmp_path);import_individual(e,p,pin,root,now=NOW)
    value=assessment_for('가상전기',read_latest(root,as_of=NOW,now=NOW)[0])
    script=r"""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8'),data=JSON.parse(fs.readFileSync(0,'utf8'));
function node(t,c,text){return {textContent:text||'',children:[],append(...x){this.children.push(...x)}}}
const p=node('div'),ctx={node,Intl};vm.runInNewContext(src.slice(src.indexOf('function renderEraDailyAssessment('),src.indexOf('function renderThemes(')),ctx);
ctx.renderEraDailyAssessment(p,data);function all(n){return [n,...n.children.flatMap(all)]}
const text=all(p).map(n=>n.textContent).join(' ');
for(const x of ['개별 기업 평가 · WATCH 선정과 별개','연결재무 FY2025','기존 평가기의 양수 수익성 관측','FY2024 공식 연간공시 원문','FY2025 공식 연간공시 원문'])assert(text.includes(x),x);
assert(all(p).some(n=>n.href==='https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260316000001'));
assert(!text.includes('undefined'));
"""
    subprocess.run(['node','-e',script],input=json.dumps(value),text=True,capture_output=True,check=True,
                   cwd=Path(__file__).resolve().parent.parent)
