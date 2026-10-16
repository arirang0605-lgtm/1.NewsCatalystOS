"""Synthetic pinned issuer metadata -> names for already identified candidates."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
from hashlib import sha256
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.theme_company_identity import ensure_identities,resolve_candidates,filter_research
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.article_company_identity import encoded
from newscatalystos.era_company_assessment import enrich_candidates
from test_event_supply_impact import case
from test_article_company_identity import context


def sec(at,name,code):
 return replace(context(at,name,code),source_id='sec-submissions',issuer_namespace_observed='SEC_CIK',document_id='0000000000-26-000001')


def directory(at,name='합성공급전자'):
 return {'a':sec(at,name,'111111'),'b':sec(at,'합성고객전자','222222')}


def resolved(cs,root,at):return resolve_candidates(cs,root,as_of=at,now=at)[0]


def test_known_id_name_search_retains_relation_role_and_first_availability(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path);root=tmp_path/'names';db=(store.root/'themes.sqlite3').read_bytes();original=deepcopy(cs)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 later=at+timedelta(seconds=2)
 assert ensure_identities(cs,directory(at),root,at=later)=={'created':2,'cache_hits':0}
 files={p.name:p.read_bytes() for p in root.glob('*.json')}
 assert ensure_identities(cs,directory(at),root,at=later+timedelta(seconds=1))=={'created':0,'cache_hits':2}
 assert files=={p.name:p.read_bytes() for p in root.glob('*.json')}
 old=resolve_candidates(cs,root,as_of=at,now=later)[0]
 assert all(c['official_name_context']['status']=='NOT_AVAILABLE_AS_OF' for c in old)
 new=resolved(cs,root,later)
 result=filter_research({'CompanyCandidates':new},[theme],'합성공급전자')
 assert len(result['CompanyCandidates'])==2
 supplier=next(c for c in result['CompanyCandidates'] if c['entity_id']=='SEC_CIK:111111')
 assert supplier['display_name']=='SEC_CIK:111111' and supplier['identity_context']['status']=='ALREADY_IDENTIFIED'
 name=supplier['official_name_context'];assert name['status']=='MATCHED' and name['decision_at']==later.isoformat()
 assert name['proof']['available_at']==at.isoformat() and name['proof']['issuer_name']=='합성공급전자'
 view=result['company_search']['candidates'][supplier['candidate_id']]
 assert view['match_kind']=='DIRECT_COMPANY'
 assert any(k['kind']=='OFFICIAL_DIRECTORY_NAME' for k in view['keys'])
 assert view['sources'][0]['company_participation']=='SUPPLY_CHAIN_CONTEXT'
 assert cs==original and (store.root/'themes.sqlite3').read_bytes()==db
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)

@pytest.mark.parametrize('fault',['missing','namespace','conflicting_names','homonym'])
def test_unavailable_or_ambiguous_directory_names_are_not_guessed(tmp_path,fault):
 theme,cs,store,first,at,info=case(tmp_path);root=tmp_path/'names';rows=directory(at)
 if fault=='missing':rows.pop('a')
 if fault=='namespace':rows['a']=context(at,'합성공급전자','11111111')
 if fault=='conflicting_names':rows['c']=sec(at,'다른명칭전자','111111')
 if fault=='homonym':rows['c']=sec(at,'합성공급전자','999999')
 ensure_identities(cs,rows,root,at=at);new=resolved(cs,root,at)
 supplier=next(c for c in new if c['entity_id']=='SEC_CIK:111111')
 name=supplier['official_name_context']
 assert name['status']==('AMBIGUOUS_NAMES' if fault=='conflicting_names' else 'MATCHED' if fault=='homonym' else 'NOT_IN_SNAPSHOT')
 r=filter_research({'CompanyCandidates':new},[theme],'合成不存在' if fault!='homonym' else '합성공급전자')
 if fault=='homonym':assert r['company_search']['candidates'][supplier['candidate_id']]['match_kind']=='AMBIGUOUS_NAME'
 exact=filter_research({'CompanyCandidates':new},[theme],'SEC_CIK:111111')
 assert exact['company_search']['candidates'][supplier['candidate_id']]['match_kind']=='DIRECT_COMPANY'


def test_changed_name_directory_does_not_rewrite_past_or_other_snapshot(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path);root=tmp_path/'names'
 ensure_identities(cs,directory(at),root,at=at)
 later=at+timedelta(hours=1);ensure_identities(cs,directory(later,'새명칭전자'),root,at=later)
 assert next(c for c in resolve_candidates(cs,root,as_of=at,now=later)[0] if c['entity_id']=='SEC_CIK:111111')['official_name_context']['proof']['issuer_name']=='합성공급전자'
 assert next(c for c in resolved(cs,root,later) if c['entity_id']=='SEC_CIK:111111')['official_name_context']['proof']['issuer_name']=='새명칭전자'
 stale=deepcopy(cs)
 for c in stale:c['theme_snapshot_sha256']='f'*64
 assert all(c['official_name_context']['status']=='NOT_AVAILABLE_AS_OF' for c in resolved(stale,root,later))

@pytest.mark.parametrize('fault',['json','proof','future'])
def test_tampered_or_future_name_receipt_stays_local_unavailable(tmp_path,fault):
 theme,cs,store,first,at,info=case(tmp_path);root=tmp_path/'names';ensure_identities(cs,directory(at),root,at=at)
 for p in root.glob('theme_official_name_*.json'):
  if fault=='json':p.write_text('{}');continue
  saved=json.loads(p.read_bytes());r=saved['report']
  if fault=='proof':r['proof']['original_sha256']='f'*64
  else:r['decision_at']='2099-01-01T00:00:00+00:00'
  saved['sha256']=sha256(encoded(r)).hexdigest();p.write_bytes(encoded(saved))
 new,skipped=resolve_candidates(cs,root,as_of=at,now=at)
 assert skipped==2 and all(c['official_name_context']['status']=='NOT_AVAILABLE_AS_OF' for c in new)


def test_browser_distinguishes_directory_name_from_article_name(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path);root=tmp_path/'names';ensure_identities(cs,directory(at),root,at=at)
 cs=resolved(cs,root,at);r=filter_research({'CompanyCandidates':cs},[theme],'합성공급전자')
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}replaceChildren(...a){this.children=a}addEventListener(){}}
const elements={},document={createElement:t=>new Element(t),getElementById:id=>elements[id]||(elements[id]=new Element('root'))};
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');vm.runInNewContext(code.split('function renderItems(){')[0]+code.slice(code.indexOf('function renderThemes(term){'))+';currentData=input;renderThemes("합성공급전자");',{input,document});process.stdout.write(JSON.stringify(elements.themes));'''
 data=dict(themes=[theme],company_candidates=cs,company_search=r['company_search'])
 text=subprocess.check_output(['node','-e',code],input=json.dumps(data).encode()).decode()
 assert '공식 명부 이름: 합성공급전자 · 기사 명시 이름 아님' in text
 assert '공급망 관계 기업 · 직접 행동 주체 아님' in text and '명부 가용:' in text


def test_http_name_search_only_after_receipt_and_standard_v3_unchanged(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 theme,cs,store,first,at,info=case(tmp_path);docs=tmp_path/'docs';docs.mkdir();store.root.rename(docs/'theme_history')
 later=at+timedelta(seconds=2);ensure_identities(cs,directory(at),docs/'theme_company_identity',at=later)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return later.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  r=json.loads(fetch('/api/company-research',q='합성공급전자',as_of=later.isoformat()))
  assert len(r['CompanyCandidates'])==2
  before=json.loads(fetch('/api/company-research',q='합성공급전자',as_of=at.isoformat()))
  assert before['CompanyCandidates']==[]
  p=json.loads(fetch('/api/period',q='합성공급전자',date=later.astimezone(dashboard.KST).date().isoformat()))
  assert p['company_search']['candidates']==r['company_search']['candidates']
  assert fetch('/api/themes',as_of=later.isoformat(),company_candidates='1')==build_theme_bundle([theme],decision_at=later,now=later,include_company_candidates=True)
 finally:server.shutdown();server.server_close();worker.join(2)


def test_existing_resolve_cli_loads_configured_directory_for_known_ids(tmp_path,monkeypatch,capsys):
 from scripts.resolve_theme_companies import main
 from test_feed_company_identity import directory as config_fixture
 from datetime import timezone
 theme,cs,store,first,at,info=case(tmp_path);root=tmp_path/'names';db=(store.root/'themes.sqlite3').read_bytes()
 config=config_fixture(tmp_path,monkeypatch,directory(at))
 assert main(['--theme-root',str(store.root),'--identity-config',str(config),'--output-root',str(root)])==0
 assert json.loads(capsys.readouterr().out)=={'created':2,'cache_hits':0}
 current=resolve_candidates(cs,root,as_of=datetime.now(timezone.utc),now=datetime.now(timezone.utc))[0]
 assert all(c['official_name_context']['status']=='MATCHED' for c in current)
 assert (store.root/'themes.sqlite3').read_bytes()==db


def test_future_directory_is_not_recorded_as_available(tmp_path):
 from newscatalystos.source_share import SourceShareError
 theme,cs,store,first,at,info=case(tmp_path);root=tmp_path/'names'
 with pytest.raises(SourceShareError):ensure_identities(cs,directory(at+timedelta(days=1)),root,at=at)
 assert not list(root.glob('*.json'))
