"""Synthetic explicit-target reports, separate from transaction cancellation."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.timeline_counterevidence import targeted_counterevidence
from newscatalystos.company_timeline import select_timelines
from newscatalystos.company_search import match_company_search
from newscatalystos.standard_delivery import build_theme_bundle
from test_company_timeline import build
from test_theme_emergence import event,T
from test_federated_news_search import fingerprint

ID='DART_CORP:00000001'


def case(tmp_path,polarity='RETRACT',company=ID):
 store=ThemeStore(tmp_path/'theme_history');original=event(1,topic='HBM',company=ID)
 original['source_binding']={'source_event_sha256':'a'*64,'document_sha256':'b'*64}
 first,=store.ingest([original],now=T)
 report=event(2,topic='HBM',company=company,polarity=polarity,target=original['event_id'])
 report['source_binding']={'source_event_sha256':'c'*64,'document_sha256':'d'*64}
 at=T+timedelta(hours=1);latest,=store.ingest([report],now=at)
 return latest,store,first,at,original,report


def enriched(themes,store,at):
 timeline,cs,ctx,comparisons=build(themes,at)
 return targeted_counterevidence(store,themes,timeline,ctx,as_of=at,now=at),cs

@pytest.mark.parametrize('polarity',['CONTRADICT','RETRACT'])
def test_exact_target_restores_history_and_attaches_separate_document_proof(tmp_path,polarity):
 latest,store,first,at,original,report=case(tmp_path,polarity)
 before=fingerprint(tmp_path);raw=build_theme_bundle([latest],decision_at=at,now=at,include_company_candidates=True)
 (timeline,ctx),cs=enriched([latest],store,at)
 selected=select_timelines(timeline,match_company_search(ctx,ID),ID)
 company,=selected['companies'];entry,=company['entries'];proof,=entry['counterevidence']
 assert entry['event_id']==original['event_id'] and entry['observed_at']==T.isoformat()
 assert entry['current_activity']==('EXCLUDED_BY_STORED_RETRACTION' if polarity=='RETRACT' else 'CONFLICTING_ACTIVE')
 assert proof['event_id']==report['event_id'] and proof['source_url']==report['source_url']
 assert proof['target_event_id']==entry['event_id'] and proof['target_entity_id']==ID
 assert proof['target_source_binding']==original['source_binding'] and proof['source_binding']==report['source_binding']
 assert proof['document_binding_status']=='PINNED_SEPARATE_SOURCE_DOCUMENTS' and not proof['verified_transaction_cancellation']
 assert proof['recorded_at']==at.isoformat() and company['distinct_economic_actions']==(0 if polarity=='RETRACT' else 1)
 assert company['historical_target_actions']==(1 if polarity=='RETRACT' else 0)
 assert not timeline['counterevidence_unresolved']
 assert before==fingerprint(tmp_path) and raw==build_theme_bundle([latest],decision_at=at,now=at,include_company_candidates=True)
 # Old PIT cannot reveal a later report or invalidate an observed action.
 old,oldctx=targeted_counterevidence(store,[first],build([first],T)[0],build([first],T)[2],as_of=T,now=at)
 assert old['companies'][0]['entries'][0]['counterevidence']==[]
 assert old['companies'][0]['entries'][0]['current_activity']=='ACTIVE'

@pytest.mark.parametrize('fault,reason',[
 ('missing','TARGET_NOT_SPECIFIED'),('unknown_event','TARGET_NOT_FOUND'),
 ('company','COMPANY_BINDING_MISMATCH'),('substring','COMPANY_BINDING_MISMATCH'),
 ('document','TARGET_SOURCE_VERSION_MISMATCH'),
])
def test_uncertain_target_does_not_borrow_another_company_or_source(tmp_path,fault,reason):
 latest,store,first,at,original,report=case(tmp_path,'CONTRADICT')
 selected=deepcopy(latest);negative=next(r for r in selected['source_refs'] if r['polarity']=='CONTRADICT')
 if fault=='missing':negative['supersedes_event_id']=None
 if fault=='unknown_event':negative['supersedes_event_id']='f'*64
 if fault=='company':negative['entity_ids']=['DART_CORP:00000002']
 if fault=='substring':negative['entity_ids']=[ID+'1']
 if fault=='document':
  next(r for r in selected['source_refs'] if r['polarity']=='SUPPORT')['source_binding']['document_sha256']='e'*64
 base,cs,ctx,comparisons=build([latest],at)
 timeline,extra=targeted_counterevidence(store,[selected],base,ctx,as_of=at,now=at)
 assert all(not e['counterevidence'] for c in timeline['companies'] for e in c['entries'])
 assert timeline['counterevidence_unresolved'][0]['reason']==reason
 if fault in {'company','substring'}:
  own=select_timelines(timeline,match_company_search(extra,ID),ID)
  assert own['counterevidence_unresolved']==[]



def test_two_actions_only_explicit_target_receives_counterevidence(tmp_path):
 store=ThemeStore(tmp_path/'theme_history');a=event(1,topic='HBM',company=ID);b=event(2,topic='HBM',company=ID)
 store.ingest([a,b],now=T);at=T+timedelta(hours=1)
 latest,=store.ingest([event(3,topic='HBM',company=ID,polarity='RETRACT',target=a['event_id'])],now=at)
 (timeline,ctx),cs=enriched([latest],store,at)
 entries=timeline['companies'][0]['entries']
 assert len(entries)==2
 assert next(e for e in entries if e['event_id']==a['event_id'])['counterevidence']
 assert next(e for e in entries if e['event_id']==b['event_id'])['counterevidence']==[]
 assert timeline['companies'][0]['distinct_economic_actions']==1

@pytest.mark.parametrize('same_document',[False,True])
def test_unidentified_same_name_requires_same_pinned_document(tmp_path,same_document):
 store=ThemeStore(tmp_path/'theme_history');a=event(1,topic='HBM',company='동명전자')
 a['source_binding']={'source_event_sha256':'a'*64,'document_sha256':'b'*64}
 store.ingest([a],now=T);at=T+timedelta(hours=1)
 negative=event(2,topic='HBM',company='동명전자',polarity='CONTRADICT',target=a['event_id'])
 negative['source_binding']=a['source_binding'] if same_document else {'source_event_sha256':'c'*64,'document_sha256':'d'*64}
 latest,=store.ingest([negative],now=at)
 (timeline,ctx),cs=enriched([latest],store,at)
 attached=timeline['companies'][0]['entries'][0]['counterevidence']
 assert bool(attached)==same_document
 if not same_document:assert timeline['counterevidence_unresolved'][0]['reason']=='COMPANY_ID_UNRESOLVED'


def test_future_report_and_future_versions_never_enter_old_query(tmp_path):
 latest,store,first,at,original,report=case(tmp_path)
 timeline,cs,ctx,comparisons=build([first],T)
 # A caller passing newer refs still cannot leak their future observation.
 result,_=targeted_counterevidence(store,[latest],timeline,ctx,as_of=T,now=at)
 assert result==timeline


def test_target_missing_from_prior_version_is_local_unavailable(tmp_path):
 latest,store,first,at,original,report=case(tmp_path)
 class MissingHistory:
  def period_versions(self,**kw):return {}
 base,cs,ctx,comparisons=build([latest],at)
 result,extra=targeted_counterevidence(MissingHistory(),[latest],base,ctx,as_of=at,now=at)
 assert result['companies']==[] and result['counterevidence_unresolved'][0]['reason']=='TARGET_NOT_AVAILABLE_BEFORE_REPORT'
 selected=select_timelines(result,{},ID)
 assert selected['status']=='TARGET_UNRESOLVED' and len(selected['counterevidence_unresolved'])==1



def test_unreadable_history_preserves_current_timeline_and_only_holds_target_join(tmp_path):
 latest,store,first,at,original,report=case(tmp_path,'CONTRADICT')
 class UnavailableHistory:
  def period_versions(self,**kw):raise OSError('synthetic unavailable history')
 base,cs,ctx,comparisons=build([latest],at)
 result,extra=targeted_counterevidence(UnavailableHistory(),[latest],base,ctx,as_of=at,now=at)
 assert all(result['companies'][0][k]==v for k,v in base['companies'][0].items()) and extra==ctx
 assert result['counterevidence_unresolved'][0]['reason']=='HISTORICAL_VERSION_UNAVAILABLE'


def test_missing_document_id_uses_hash_only_without_fabricated_binding(tmp_path):
 latest,store,first,at,original,report=case(tmp_path,'CONTRADICT')
 selected=deepcopy(latest)
 for r in selected['source_refs']:
  if r['polarity']=='CONTRADICT':r.pop('source_binding')
 base,cs,ctx,comparisons=build([latest],at)
 result,_=targeted_counterevidence(store,[selected],base,ctx,as_of=at,now=at)
 proof=result['companies'][0]['entries'][0]['counterevidence'][0]
 assert proof['document_binding_status']=='SOURCE_HASH_ONLY' and proof['reason']=='DOCUMENT_ID_UNAVAILABLE'


def test_browser_renders_historical_action_and_separate_counter_source(tmp_path):
 latest,store,first,at,original,report=case(tmp_path)
 (timeline,ctx),cs=enriched([latest],store,at)
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCompanyTimelines(parent,input.timeline,input.q,companySearchResults(input.context,input.q));',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 text=subprocess.check_output(['node','-e',code],input=json.dumps(dict(timeline=timeline,context=ctx,q=ID)).encode()).decode()
 assert '당시 관측 사실은 보존' in text and '실거래 취소 확정 아님' in text
 assert original['source_url'] in text and report['source_url'] in text


def test_http_retired_company_search_and_pit_do_not_change_standard_v3(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 latest,store,first,at,original,report=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  r=json.loads(fetch('/api/company-research',q=ID,as_of=at.isoformat()))
  assert r['CompanyCandidates']==[]  # No new active candidate fabricated.
  assert len(r['company_timelines']['companies'])==1
  p=json.loads(fetch('/api/period',q=ID,date=at.astimezone(dashboard.KST).date().isoformat()))
  assert p['company_timelines']['companies'][0]['entries'][0]['counterevidence']
  old=json.loads(fetch('/api/company-research',q=ID,as_of=T.isoformat()))
  assert old['company_timelines']['companies'][0]['entries'][0]['counterevidence']==[]
  for snapshot,when in [(first,T),(latest,at)]:
   assert fetch('/api/themes',as_of=when.isoformat(),company_candidates='1')==build_theme_bundle([snapshot],decision_at=when,now=at,include_company_candidates=True)
 finally:server.shutdown();server.server_close();worker.join(2)
