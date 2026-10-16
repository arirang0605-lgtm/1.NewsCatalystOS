"""Synthetic query attribution: company name equality is not a transaction proof."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.theme_company_candidates import company_candidates
from newscatalystos.theme_company_identity import filter_research,ensure_identities,resolve_candidates
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle
from test_service_realization import claim,T
from test_article_company_identity import context as identity_context
from test_theme_emergence import event
from test_federated_news_search import fingerprint


def case(tmp_path):
 store=ThemeStore(tmp_path/'theme_history')
 first,=store.ingest([claim('가상전자, HBM 수요 증가로 공급계약 체결',0)],now=T)
 at=T+timedelta(hours=2)
 theme,=store.ingest([claim('새빛소재, HBM 수요 증가로 생산 시작',1)],now=at)
 return theme,company_candidates(theme),store,first,at


def result(theme,cs,q):
 return filter_research({'CompanyCandidates':deepcopy(cs)},[theme],q)


def test_exact_company_with_separate_related_sources_preserves_canonical_and_storage(tmp_path):
 theme,cs,store,first,at=case(tmp_path);before=deepcopy((theme,cs));disk=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 research=result(theme,cs,'가상전자');views=research['company_search']['candidates']
 assert len(research['CompanyCandidates'])==2
 for c in cs:
  row=views[c['candidate_id']];direct=c['entity_id']=='가상전자'
  assert row['match_kind']==('DIRECT_COMPANY' if direct else 'RELATED_THEME')
  assert row['identity_status']=='SOURCE_NAME_ONLY'
  assert {s['event_id'] for s in row['sources']}==set(c['event_ids'])
  assert {s['source_url'] for s in row['sources']}==({'https://example.org/0'} if direct else {'https://example.org/1'})
  assert not c['verified_real_transaction'] and not c['verified_real_benefit']
 assert (theme,cs)==before and fingerprint(tmp_path)==disk
 assert raw==build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 old_cs=company_candidates(first);old=result(first,old_cs,'가상전자')
 assert len(old['CompanyCandidates'])==1
 assert {s['event_id'] for v in old['company_search']['candidates'].values() for s in v['sources']}==set(first['event_ids'])
 assert store.search(as_of=T,now=at)==[first]
 stale=company_search_context([first],cs)
 assert all(not r['keys'] and not r['sources'] for r in stale.values())

@pytest.mark.parametrize('q',['가상','전자','가상전자서비스','HBM','공급계약',''])
def test_partial_name_and_topic_search_do_not_claim_direct_company(tmp_path,q):
 theme,cs,*_=case(tmp_path);r=result(theme,cs,q)
 assert all(v['match_kind'] in {'TEXT_CONTEXT','UNFILTERED'} for v in r['company_search']['candidates'].values())
 if q=='HBM':assert len(r['CompanyCandidates'])==2
 if q=='가상전자서비스':assert r['CompanyCandidates']==[]


def test_exact_official_id_with_same_name_is_unambiguous_but_name_is_not(tmp_path):
 store=ThemeStore(tmp_path/'themes');theme,=store.ingest([event(1,company='DART_CORP:11111111'),event(2,company='DART_CORP:22222222')],now=T)
 cs=company_candidates(theme)
 for c in cs:c['display_name']='동명전자'  # Synthetic exact display names for two known distinct IDs.
 views=result(theme,cs,'동명전자')['company_search']['candidates']
 assert {v['match_kind'] for v in views.values()}=={'AMBIGUOUS_NAME'}
 assert len({tuple(s['event_id'] for s in v['sources']) for v in views.values()})==2
 r=result(theme,cs,'dart_corp:11111111')
 assert len(r['CompanyCandidates'])==2
 assert sorted(v['match_kind'] for v in r['company_search']['candidates'].values())==['DIRECT_COMPANY','RELATED_THEME']


def test_official_resolution_is_available_only_as_of_receipt(tmp_path):
 theme,cs,store,first,at=case(tmp_path);root=tmp_path/'identities'
 ensure_identities(cs,{'a':identity_context(at,'가상전자','12345678')},root,at=at)
 old,_=resolve_candidates(cs,root,as_of=T,now=at)
 assert result(theme,old,'DART_CORP:12345678')['CompanyCandidates']==[]
 new,_=resolve_candidates(cs,root,as_of=at,now=at)
 r=result(theme,new,'DART_CORP:12345678')
 assert len(r['CompanyCandidates'])==2
 assert sorted(v['match_kind'] for v in r['company_search']['candidates'].values())==['DIRECT_COMPANY','RELATED_THEME']
 # An unresolved homonym is never upgraded by exact text alone.
 for c in new:
  if c['entity_id']=='가상전자':c['identity_context']={'status':'AMBIGUOUS'};c.pop('resolved_entity_id',None)
 assert 'AMBIGUOUS_NAME' in {v['match_kind'] for v in result(theme,new,'가상전자')['company_search']['candidates'].values()}



def test_inactive_or_other_company_sources_are_not_search_proof(tmp_path):
 theme,cs,*_=case(tmp_path)
 old=next(r for r in theme['source_refs'] if r['entity_ids']==['가상전자'])
 theme['invalidated_event_ids'].append(old['event_id'])
 # Query snapshots remain authoritative even when an old company still has context.
 from newscatalystos.theme_emergence import _bytes
 from hashlib import sha256
 for c in cs:c['theme_snapshot_sha256']=sha256(_bytes(theme)).hexdigest()
 views=company_search_context([theme],cs)
 target=next(c for c in cs if c['entity_id']=='가상전자')
 assert views[target['candidate_id']]['sources']==[]
 assert all(old['event_id']!=s['event_id'] for v in views.values() for s in v['sources'])


def js_matches(context,q):
 script='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
process.stdout.write(JSON.stringify(vm.runInNewContext(code+';companySearchResults(input.context,input.q)',{input})));'''
 return json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(dict(context=context,q=q)).encode()))


def test_browser_matching_equals_json_and_renders_company_specific_links(tmp_path):
 theme,cs,*_=case(tmp_path);context=company_search_context([theme],cs)
 for q in ['가상전자','가상','HBM','','  가상전자  ']:assert js_matches(context,q)==match_company_search(context,q)
 script='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}replaceChildren(...a){this.children=a}addEventListener(){}}
const elements={};const document={createElement:t=>new Element(t),getElementById:id=>elements[id]||(elements[id]=new Element('root'))};
let code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');code=code.split('function renderItems(){')[0]+code.slice(code.indexOf('function renderThemes(term){'));
vm.runInNewContext(code+';currentData=input;renderThemes("가상전자");',{input,document});
process.stdout.write(JSON.stringify(elements.themes));'''
 data=dict(themes=[theme],company_candidates=cs,company_search={'candidates':context})
 dom=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(data).encode()))
 def nodes(node):
  yield node
  for child in node.get('children',[]):yield from nodes(child)
 texts=[n.get('textContent','') for n in nodes(dom)]
 assert '검색 기업명·식별자와 정확히 일치 · 거래·수혜 확인 아님' in texts
 assert '같은 테마의 연관 기업 · 검색 기업과 직접 관계 미확인' in texts
 details=[n for n in nodes(dom) if n['tag']=='details' and n.get('children',[{}])[0].get('textContent')=='이 기업의 사건·출처 근거']
 assert [{n['href'] for n in nodes(d) if n.get('href')} for d in details]==[{'https://example.org/0'},{'https://example.org/1'}]


def test_http_company_period_and_old_v3(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 theme,cs,store,first,at=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(path,params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{path}?'+urlencode(params)) as r:return r.read()
 try:
  r=json.loads(fetch('/api/company-research',dict(q='가상전자',as_of=at.isoformat())))
  kinds={k:v['match_kind'] for k,v in r['company_search']['candidates'].items()}
  assert sorted(kinds.values())==['DIRECT_COMPANY','RELATED_THEME']
  p=json.loads(fetch('/api/period',dict(q='가상전자',date=at.astimezone(dashboard.KST).date().isoformat())))
  assert {k:v['match_kind'] for k,v in p['company_search']['candidates'].items()}==kinds
  old=json.loads(fetch('/api/company-research',dict(q='가상전자',as_of=T.isoformat())))
  assert len(old['CompanyCandidates'])==1
  for t,when in [(first,T),(theme,at)]:
   raw=fetch('/api/themes',dict(as_of=when.isoformat(),company_candidates='1'))
   assert raw==build_theme_bundle([t],decision_at=when,now=at,include_company_candidates=True)
 finally:server.shutdown();server.server_close();worker.join(2)
