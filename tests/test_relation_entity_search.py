"""Exact role-aware search sources from synthetic pinned supply relations."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.theme_company_identity import filter_research
from newscatalystos.theme_company_candidates import company_candidates
from newscatalystos.standard_delivery import build_theme_bundle
from test_event_supply_impact import case
from test_theme_supply_chain import observation
from test_federated_news_search import fingerprint


def search(theme,cs,q):return filter_research({'CompanyCandidates':deepcopy(cs)},[theme],q)


def test_relation_company_id_has_own_role_document_and_graph_bound_source(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path);disk=fingerprint(tmp_path);original=deepcopy((theme,cs))
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 result=search(theme,cs,'SEC_CIK:111111');views=result['company_search']['candidates']
 for c in result['CompanyCandidates']:
  v=views[c['candidate_id']];s,=v['sources'];path,=s['impact_paths']
  supplier=c['entity_id']=='SEC_CIK:111111'
  assert v['match_kind']==('DIRECT_COMPANY' if supplier else 'RELATED_THEME')
  assert v['source_status']=='AVAILABLE' and s['company_participation']==('SUPPLY_CHAIN_CONTEXT' if supplier else 'SOURCE_EVENT_ACTOR')
  assert s['event_entity_ids']==['SEC_CIK:222222'] and s['entity_id']==c['entity_id']
  assert path['role']==('supplier' if supplier else 'customer')
  assert path['document_id']=='press-1' and path['document_sha256']==info[1].payload_sha256
  assert path['source_event_sha256']==info[1].version_id
  assert path['event_id']==s['event_id'] and path['entity_id']==c['entity_id']
  assert path['source_urls']==[s['source_url']] and len(path['graph_sha256'])==64
  assert s['evidence_level']=='OFFICIAL_SOURCE' and s['source_available_at']==info[-1].isoformat()
  assert not path['verified_real_transaction'] and not path['verified_real_benefit']
 assert original==(theme,cs) and disk==fingerprint(tmp_path)
 assert raw==build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 # Relationship evidence cannot travel back to the pre-link snapshot.
 old=search(first,company_candidates(first),'SEC_CIK:111111')
 assert old['CompanyCandidates']==[]
 assert store.search(as_of=info[-1],now=at)==[first]


def test_saved_display_name_and_partial_or_ambiguous_query_do_not_change_source_role(tmp_path):
 theme,cs,*_=case(tmp_path)
 for c in cs:c['display_name']='합성동명전자'  # Two known distinct IDs, a synthetic ambiguous display name.
 r=search(theme,cs,'합성동명전자');assert {v['match_kind'] for v in r['company_search']['candidates'].values()}=={'AMBIGUOUS_NAME'}
 for q in ['111','합성동명','관련없는기업']:
  r=search(theme,cs,q)
  assert all(v['match_kind']=='TEXT_CONTEXT' for v in r['company_search']['candidates'].values())
  assert all(s['entity_id']==v['entity_id'] for v in r['company_search']['candidates'].values() for s in v['sources'])

@pytest.mark.parametrize('fault',['snapshot','decision','missing_basis','missing_path'])
def test_stale_or_unsupported_candidate_has_no_borrowed_relationship_source(tmp_path,fault):
 theme,cs,*_=case(tmp_path)
 supplier=next(c for c in cs if c['entity_id']=='SEC_CIK:111111')
 if fault=='snapshot':supplier['theme_snapshot_sha256']='f'*64
 if fault=='decision':supplier['decision_at']='2099-01-01T00:00:00+00:00'
 if fault=='missing_basis':supplier['inclusion_basis']=[]
 if fault=='missing_path':supplier['benefit_paths']=[]
 v=company_search_context([theme],cs)[supplier['candidate_id']]
 assert v['sources']==[]


def test_other_event_and_same_url_other_document_never_lend_relationship(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path)
 wrong=observation(info);wrong['source_binding']={'source_event_sha256':'f'*64,'document_sha256':'e'*64}
 other=observation(info,number=2,company='SEC_CIK:333333',binding=wrong['source_binding'])
 latest,=store.ingest([wrong,other],now=at+timedelta(seconds=1))
 cs=company_candidates(latest);views=company_search_context([latest],cs)
 supplier=next(c for c in cs if c['entity_id']=='SEC_CIK:111111')
 assert len(views[supplier['candidate_id']]['sources'])==1
 for v in views.values():
  for source in v['sources']:
   if source.get('source_binding')==wrong['source_binding']:assert source['impact_paths']==[]
   assert source['entity_id']==v['entity_id']


def test_retracted_relation_does_not_supply_a_current_search_result(tmp_path):
 theme,cs,store,first,at,info=case(tmp_path)
 target=theme['event_ids'][0]
 retracted,=store.ingest([observation(info,number=2,polarity='RETRACT',target=target)],now=at+timedelta(seconds=1))
 assert search(retracted,company_candidates(retracted),'SEC_CIK:111111')['CompanyCandidates']==[]
 assert search(theme,cs,'SEC_CIK:111111')['CompanyCandidates']



def test_future_graph_availability_is_not_usable_for_search(tmp_path):
 from newscatalystos.source_share import SourceShareError
 theme,cs,*_=case(tmp_path)
 theme['supply_chain_evidence'][0]['available_at']='2099-01-01T00:00:00+00:00'
 with pytest.raises(SourceShareError):company_search_context([theme],cs)


def test_browser_search_renders_context_role_and_exact_provenance(tmp_path):
 theme,cs,*_=case(tmp_path);views=company_search_context([theme],cs)
 script='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}replaceChildren(...a){this.children=a}addEventListener(){}}
const elements={},document={createElement:t=>new Element(t),getElementById:id=>elements[id]||(elements[id]=new Element('root'))};
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
vm.runInNewContext(code.split('function renderItems(){')[0]+code.slice(code.indexOf('function renderThemes(term){'))+';currentData=input;renderThemes("SEC_CIK:111111".toLowerCase());',{input,document});process.stdout.write(JSON.stringify(elements.themes));'''
 data=dict(themes=[theme],company_candidates=cs,company_search={'candidates':views})
 dom=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(data).encode()))
 def nodes(n):
  yield n
  for child in n.get('children',[]):yield from nodes(child)
 details=[n for n in nodes(dom) if n['tag']=='details' and n.get('children',[{}])[0].get('textContent')=='이 기업의 사건·출처 근거']
 assert len(details)==2
 supplier_text=json.dumps(details[0],ensure_ascii=False)
 assert '공급망 관계 기업 · 직접 행동 주체 아님' in supplier_text
 assert '공식 출처 보도' in supplier_text and '출처 가용:' in supplier_text
 assert '문서 ID: press-1' in supplier_text and '원본 문서 SHA:' in supplier_text
 assert '출처의 사건 당사자' in json.dumps(details[1],ensure_ascii=False)


def test_http_search_period_and_pit_preserve_standard_bytes(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 theme,cs,store,first,at,info=case(tmp_path)
 docs=tmp_path/'documents';docs.mkdir();store.root.rename(docs/'theme_history')
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  r=json.loads(fetch('/api/company-research',q='SEC_CIK:111111',as_of=at.isoformat()))
  p=json.loads(fetch('/api/period',q='SEC_CIK:111111',date=at.astimezone(dashboard.KST).date().isoformat()))
  assert r['company_search']['candidates']==p['company_search']['candidates']
  old=json.loads(fetch('/api/company-research',q='SEC_CIK:111111',as_of=info[-1].isoformat()))
  assert old['CompanyCandidates']==[]
  for snapshot,when in [(first,info[-1]),(theme,at)]:
   assert fetch('/api/themes',as_of=when.isoformat(),company_candidates='1')==build_theme_bundle([snapshot],decision_at=when,now=at,include_company_candidates=True)
 finally:server.shutdown();server.server_close();worker.join(2)
