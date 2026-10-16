"""Pinned relation-event counterevidence is context, not a firm's own reversal."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,threading,subprocess
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.timeline_counterevidence import targeted_counterevidence,_relation_paths
from newscatalystos.company_timeline import select_timelines
from newscatalystos.company_search import match_company_search
from newscatalystos.standard_delivery import build_theme_bundle
from test_event_supply_impact import case as supply_case
from test_theme_supply_chain import observation
from test_company_timeline import build
from test_federated_news_search import fingerprint

SUPPLIER='SEC_CIK:111111';ACTOR='SEC_CIK:222222'


def case(tmp_path,polarity='RETRACT'):
 prior,cs,store,first,linked,info=supply_case(tmp_path)
 negative=observation(info,number=2,polarity=polarity,target=prior['event_ids'][0])
 negative['source_binding']={'source_event_sha256':'e'*64,'document_sha256':'f'*64}
 at=linked+timedelta(seconds=1);latest,=store.ingest([negative],now=at)
 report=next(r for r in latest['source_refs'] if r['polarity']==polarity)
 return latest,store,prior,at,report,linked


def enriched(latest,store,at):
 timeline,cs,ctx,comparisons=build([latest],at)
 result,extra=targeted_counterevidence(store,[latest],timeline,ctx,as_of=at,now=at)
 return result,extra

@pytest.mark.parametrize('polarity',['CONTRADICT','RETRACT'])
def test_verified_relation_gets_separate_context_without_own_action_reversal(tmp_path,polarity):
 latest,store,prior,at,report,linked=case(tmp_path,polarity);before=fingerprint(tmp_path)
 raw=build_theme_bundle([latest],decision_at=at,now=at,include_company_candidates=True)
 result,ctx=enriched(latest,store,at)
 selected=select_timelines(result,match_company_search(ctx,SUPPLIER),SUPPLIER)
 company,=selected['companies'];entry,=company['entries'];proof,=entry['relation_counterevidence']
 assert entry['counterevidence']==[] and entry['company_participation']=='SUPPLY_CHAIN_CONTEXT'
 assert entry['current_activity']==('RELATION_EVENT_CONTEXT_EXCLUDED' if polarity=='RETRACT' else 'RELATION_EVENT_CONTEXT_CONFLICTING')
 assert entry['observed_at']==linked.isoformat()
 assert proof['status']=='RELATION_EVENT_CONTEXT' and proof['relation_entity_id']==SUPPLIER
 assert proof['target_actor_ids']==[ACTOR] and proof['target_entity_id']==ACTOR
 assert proof['target_event_id']==entry['event_id'] and proof['relationship']['event_id']==entry['event_id']
 assert proof['relationship']['role']=='supplier' and proof['relationship']['counterparty_id']==ACTOR
 assert proof['relationship']['source_urls']==[entry['source_url']]
 assert proof['source_url']==report['source_url'] and proof['source_binding']!=entry['source_binding']
 assert not proof['affects_own_action'] and not proof['verified_transaction_cancellation'] and not proof['verified_benefit_loss']
 assert company['distinct_economic_actions']==0 and company['historical_target_actions']==0
 assert company['historical_relation_contexts']==(1 if polarity=='RETRACT' else 0)
 actor=next(c for c in result['companies'] if c['entity_id']==ACTOR)
 assert actor['entries'][0]['counterevidence'] and not actor['entries'][0]['relation_counterevidence']
 assert before==fingerprint(tmp_path) and raw==build_theme_bundle([latest],decision_at=at,now=at,include_company_candidates=True)

@pytest.mark.parametrize('fault',['company','actor','event','document','graph','relation','role','stage','future_link','future_graph','graph_bytes','missing'])
def test_other_party_event_document_graph_role_or_future_never_lends_context(tmp_path,fault):
 latest,store,prior,at,report,linked=case(tmp_path)
 historical,*_=build([prior],linked)
 entry=next(c for c in historical['companies'] if c['entity_id']==SUPPLIER)['entries'][0]
 p=deepcopy(prior);e=deepcopy(entry);r=deepcopy(report)
 if fault=='company':e['entity_id']='SEC_CIK:333333'
 if fault=='actor':r['entity_ids']=['SEC_CIK:333333']
 if fault=='event':r['supersedes_event_id']='f'*64
 if fault=='document':e['source_binding']['document_sha256']='c'*64
 if fault=='graph':e['impact_paths'][0]['graph_sha256']='c'*64
 if fault=='relation':e['impact_paths'][0]['relation_sha256']='d'*64
 if fault=='role':e['impact_paths'][0]['role']='customer'
 if fault=='stage':e['impact_paths'][0]['product_stage']='MEMORY_DRAM'
 if fault=='future_link':e['impact_paths'][0]['linked_at']=(at+timedelta(days=1)).isoformat()
 if fault=='future_graph':p['supply_chain_evidence'][0]['available_at']=(at+timedelta(days=1)).isoformat()
 if fault=='graph_bytes':p['supply_chain_evidence'][0]['graph_payload']+=' '
 if fault=='missing':e['impact_paths']=[]
 assert _relation_paths(p,e,r)==[]


def test_historical_query_does_not_see_later_counterevidence(tmp_path):
 latest,store,prior,at,report,linked=case(tmp_path)
 old,cs,ctx,comparisons=build([prior],linked)
 result,extra=targeted_counterevidence(store,[prior],old,ctx,as_of=linked,now=at)
 supplier=next(c for c in result['companies'] if c['entity_id']==SUPPLIER)
 assert supplier['entries'][0]['relation_counterevidence']==[]
 assert supplier['entries'][0]['relation_counterevidence_status']=='NO_VERIFIED_CONTEXT'



def test_later_known_relation_can_use_earlier_report_without_leaking_into_past(tmp_path):
 from test_theme_supply_chain import setup,attach
 info,out,pub,store,original,first=setup(tmp_path)
 at=info[-1]+timedelta(seconds=1)
 negative=observation(info,number=2,polarity='CONTRADICT',target=original['event_id'])
 negative['source_binding']={'source_event_sha256':'e'*64,'document_sha256':'f'*64}
 before,=store.ingest([negative],now=at)
 linked=at+timedelta(seconds=1);latest,=attach(store,out,pub,linked)
 result,ctx=enriched(latest,store,linked)
 supplier=next(c for c in result['companies'] if c['entity_id']==SUPPLIER)
 proof,=supplier['entries'][0]['relation_counterevidence']
 assert proof['recorded_at']==at.isoformat() and proof['context_observed_at']==linked.isoformat()
 assert proof['relationship']['linked_at']==linked.isoformat()
 base,cs,current_ctx,comparisons=build([latest],linked,at+timedelta(milliseconds=500))
 window,extra=targeted_counterevidence(store,[latest],base,current_ctx,as_of=linked,now=linked,since=at+timedelta(milliseconds=500))
 scoped=next(c for c in window['companies'] if c['entity_id']==SUPPLIER)['entries'][0]['relation_counterevidence'][0]
 assert scoped['context_in_period'] and not scoped['in_period']
 stale=deepcopy(base)
 for c in stale['companies']:
  if c['entity_id']==SUPPLIER:c['entries'][0]['theme_snapshot_sha256']='f'*64
 blocked,extra=targeted_counterevidence(store,[latest],stale,current_ctx,as_of=linked,now=linked)
 assert not next(c for c in blocked['companies'] if c['entity_id']==SUPPLIER)['entries'][0]['relation_counterevidence']
 old,oldctx=enriched(before,store,at)
 assert select_timelines(old,match_company_search(oldctx,SUPPLIER),SUPPLIER)['companies']==[]


def test_missing_relation_does_not_fabricate_a_related_company(tmp_path):
 from test_timeline_counterevidence import case as direct_case
 latest,store,prior,at,original,report=direct_case(tmp_path)
 result,ctx=enriched(latest,store,at)
 assert all(not e['relation_counterevidence'] for c in result['companies'] for e in c['entries'])
 assert select_timelines(result,match_company_search(ctx,SUPPLIER),SUPPLIER)['companies']==[]


def test_browser_separates_original_relation_source_and_counter_source(tmp_path):
 latest,store,prior,at,report,linked=case(tmp_path);timeline,ctx=enriched(latest,store,at)
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCompanyTimelines(parent,input.timeline,input.q,companySearchResults(input.ctx,input.q));',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 text=subprocess.check_output(['node','-e',code],input=json.dumps(dict(timeline=timeline,ctx=ctx,q=SUPPLIER)).encode()).decode()
 assert '관계 사건 맥락' in text and '직접 행동 철회·실거래 취소·수혜 소멸 확정 아님' in text
 assert '원래 공급망 관계 출처' in text and '연결 사건의 반대 근거 출처' in text
 assert '원래 당사자 SEC_CIK:222222' in text and '관계 출처 가용:' in text and '반대 근거 가용:' in text


def test_http_relation_company_context_preserves_pit_and_v3(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 latest,store,prior,at,report,linked=case(tmp_path)
 docs=tmp_path/'docs';docs.mkdir();store.root.rename(docs/'theme_history')
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  result=json.loads(fetch('/api/company-research',q=SUPPLIER,as_of=at.isoformat()))
  assert result['CompanyCandidates']==[]
  company,=result['company_timelines']['companies'];assert company['entity_id']==SUPPLIER
  assert company['entries'][0]['relation_counterevidence'] and not company['entries'][0]['counterevidence']
  period=json.loads(fetch('/api/period',q=SUPPLIER,date=at.astimezone(dashboard.KST).date().isoformat()))
  assert period['company_timelines']['companies'][0]['entries'][0]['relation_counterevidence']
  old=json.loads(fetch('/api/company-research',q=SUPPLIER,as_of=linked.isoformat()))
  assert old['company_timelines']['companies'][0]['entries'][0]['relation_counterevidence']==[]
  for snapshot,when in [(prior,linked),(latest,at)]:
   assert fetch('/api/themes',company_candidates='1',as_of=when.isoformat())==build_theme_bundle([snapshot],decision_at=when,now=at,include_company_candidates=True)
 finally:server.shutdown();server.server_close();worker.join(2)
