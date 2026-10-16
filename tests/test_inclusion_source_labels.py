"""Query-only AI attribution preserves snapshots, candidates and v3 bytes."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
from pathlib import Path
import json,subprocess
import pytest
from newscatalystos.theme_emergence import ThemeStore,_bytes
from newscatalystos.theme_company_candidates import company_candidates,inclusion_presentations
from newscatalystos.standard_delivery import build_theme_bundle
from test_service_realization import claim,T
from test_federated_news_search import fingerprint

LABEL='AI 해석의 원문 근거 · 독립 사실 확인 아님'


def case(tmp_path):
 ai=claim('가상전자, HBM 수요 증가로 공급계약 체결',0)
 ai['change']['extraction_method']='AI_SOURCE_SPAN_MATCHED'  # Synthetic attribution fixture.
 rules=claim('가상전자, HBM 수요 증가로 생산 시작',1)
 at=T+timedelta(hours=2);store=ThemeStore(tmp_path/'theme_history')
 first,=store.ingest([ai],now=T);theme,=store.ingest([rules],now=at)
 return theme,company_candidates(theme),store,first,at


def test_mixed_reasons_receive_only_exact_ai_label_without_mutation(tmp_path):
 theme,candidates,store,first,at=case(tmp_path)
 old=deepcopy((theme,candidates));before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 presentations=inclusion_presentations([theme],candidates)
 c,=candidates;view=presentations[c['candidate_id']]
 assert view['status']=='READY' and view['theme_snapshot_sha256']==c['theme_snapshot_sha256']
 assert len(view['items'])==2 and [i['label'] for i in view['items']].count(LABEL)==1
 for item,basis in zip(view['items'],c['inclusion_basis']):
  assert item['event_id']==basis['event_id']
  assert (item['label']==LABEL)==(basis['action']=='CONTRACT')
 assert (theme,candidates)==old and fingerprint(tmp_path)==before
 assert raw==build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 assert store.search(as_of=T,now=at)==[first]
 old_candidates=company_candidates(first);old_c=old_candidates[0]
 old_view=inclusion_presentations([first],old_candidates)[old_c['candidate_id']]
 assert old_view['status']=='READY' and [i['label'] for i in old_view['items']]==[LABEL]
 assert inclusion_presentations([first],candidates)[c['candidate_id']]['status']=='SNAPSHOT_MISMATCH'

@pytest.mark.parametrize('field,value',[
 ('event_id','f'*64),('source_url','https://example.org/other'),('evidence_sha256','e'*64),
 ('source_available_at',(T+timedelta(days=1)).isoformat()),('phase','PLANNED'),('recorded_at',(T+timedelta(hours=9)).isoformat()),
 ('kind','INFERRED_ASSOCIATION'),('source_binding',{'source_event_sha256':'f'*64,'document_sha256':'e'*64}),
])
def test_other_event_source_or_stage_cannot_lend_method(tmp_path,field,value):
 theme,candidates,*_=case(tmp_path);c=candidates[0]
 basis=next(b for b in c['inclusion_basis'] if b['action']=='CONTRACT');basis[field]=value
 view=inclusion_presentations([theme],candidates)[c['candidate_id']]
 assert all(i['label'] is None for i in view['items'])

@pytest.mark.parametrize('fault',['snapshot','decision','theme','entity'])
def test_other_query_version_or_company_cannot_lend_method(tmp_path,fault):
 theme,candidates,*_=case(tmp_path);c=candidates[0]
 if fault=='snapshot':c['theme_snapshot_sha256']='f'*64
 if fault=='decision':c['decision_at']=(T+timedelta(days=1)).isoformat()
 if fault=='theme':c['theme_id']='e'*64
 if fault=='entity':c['entity_id']='다른전자'
 view=inclusion_presentations([theme],candidates)[c['candidate_id']]
 assert all(i['label'] is None for i in view['items'])


def test_ambiguous_same_binding_methods_are_not_cherry_picked(tmp_path):
 theme,*_=case(tmp_path);ai=next(r for r in theme['source_refs'] if r.get('extraction_method'))
 other=deepcopy(ai);other.pop('extraction_method');theme['source_refs'].append(other)
 c,=company_candidates(theme);view=inclusion_presentations([theme],[c])[c['candidate_id']]
 assert all(i['label'] is None for i in view['items'])


def js_label(candidate,basis,index,views):
 code='''const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
process.stdout.write(JSON.stringify(vm.runInNewContext(code+';inclusionBasisLabel(input.candidate,input.basis,input.index,input.views)',{input})));'''
 return json.loads(subprocess.check_output(['node','-e',code],input=json.dumps(dict(candidate=candidate,basis=basis,index=index,views=views)).encode()))


def test_js_displays_each_reason_label_and_rejects_stale_views(tmp_path):
 theme,candidates,*_=case(tmp_path);c=candidates[0];views=inclusion_presentations([theme],candidates)
 for i,basis in enumerate(c['inclusion_basis']):
  assert js_label(c,basis,i,views)==(LABEL if basis['action']=='CONTRACT' else '')
 index=next(i for i,b in enumerate(c['inclusion_basis']) if b['action']=='CONTRACT');basis=c['inclusion_basis'][index]
 for field,value in [('theme_snapshot_sha256','f'*64),('entity_id','다른전자'),('decision_at','old')]:
  stale=deepcopy(views);stale[c['candidate_id']][field]=value
  assert js_label(c,basis,index,stale)==''
 assert js_label(c,basis,index,{})==''


def test_period_json_has_reason_labels_but_canonical_theme_endpoint_is_unchanged(tmp_path,monkeypatch):
 import threading
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 theme,candidates,store,first,at=case(tmp_path)
 docs=tmp_path
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  day=at.astimezone(dashboard.KST).date().isoformat()
  with urlopen(f'http://127.0.0.1:{server.server_port}/api/period?'+urlencode({'date':day})) as r:data=json.load(r)
  c,=data['company_candidates'];items=data['company_inclusion_presentations'][c['candidate_id']]['items']
  assert sum(i['label']==LABEL for i in items)==1
  with urlopen(f'http://127.0.0.1:{server.server_port}/api/themes?'+urlencode({'as_of':at.isoformat(),'company_candidates':'1'})) as r:raw=r.read()
  expected=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
  assert raw==expected
  with urlopen(f'http://127.0.0.1:{server.server_port}/api/company-research?'+urlencode({'as_of':at.isoformat()})) as r:research=json.load(r)
  rc,=research['CompanyCandidates'];assert research['company_inclusion_presentations'][rc['candidate_id']]['items']==items
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
