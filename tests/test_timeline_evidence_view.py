"""Synthetic period projections over validated timelines; no storage changes."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,subprocess,threading
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
import pytest
from newscatalystos.company_timeline import timeline_evidence_view,select_timelines
from newscatalystos.timeline_counterevidence import targeted_counterevidence
from newscatalystos.company_search import match_company_search
from newscatalystos.standard_delivery import build_theme_bundle
from test_company_timeline import case,build,T
from test_timeline_counterevidence import case as direct_case,ID
from test_relation_timeline_counterevidence import SUPPLIER,observation


def test_new_sources_do_not_relabel_old_action_or_mutate_context(tmp_path):
 themes,store,first,at=case(tmp_path)
 timeline,*_=build(themes,at,T+timedelta(hours=1));before=deepcopy(timeline)
 result=timeline_evidence_view(timeline,'observed');company,=result['companies']
 assert len(company['entries'])==3
 assert company['period_evidence_counts']=={'ADDITIONAL_SOURCE':1,'SOURCE_REPORTED_FOLLOWUP':1,'ECONOMIC_ACTION_FIRST_OBSERVED':1}
 assert company['new_actions_in_period']==1 and company['distinct_economic_actions']==2
 assert timeline==before and len(timeline_evidence_view(timeline)['companies'][0]['entries'])==4


@pytest.mark.parametrize('polarity',['CONTRADICT','RETRACT'])
def test_old_action_survives_new_direct_report_and_old_reports_are_hidden(tmp_path,polarity):
 latest,store,first,at,*_=direct_case(tmp_path,polarity)
 since=at-timedelta(minutes=1)
 base,cs,ctx,*_=build([latest],at,since)
 timeline,_=targeted_counterevidence(store,[latest],base,ctx,as_of=at,now=at,since=since)
 company,=timeline_evidence_view(timeline,'observed')['companies'];entry,=company['entries']
 assert not entry['in_period'] and entry['recorded_at']==T.isoformat()
 assert company['period_evidence_counts']=={'DIRECT_RETRACTION' if polarity=='RETRACT' else 'DIRECT_CONTRADICTION':1}
 assert entry['counterevidence'][0]['recorded_at']==at.isoformat()
 assert company['new_actions_in_period']==0
 later=at+timedelta(hours=1)
 base,cs,ctx,*_=build([latest],later,later)
 old,_=targeted_counterevidence(store,[latest],base,ctx,as_of=later,now=later,since=later)
 empty=timeline_evidence_view(old,'observed')['companies'][0]
 assert empty['entries']==[] and empty['period_evidence_status']=='NO_NEW_EVIDENCE'
 assert len(timeline_evidence_view(old)['companies'][0]['entries'])==1


def test_late_relation_uses_context_time_not_counter_report_time(tmp_path):
 from test_theme_supply_chain import setup,attach
 info,out,pub,store,original,first=setup(tmp_path)
 at=info[-1]+timedelta(seconds=1)
 negative=observation(info,number=2,polarity='CONTRADICT',target=original['event_id'])
 negative['source_binding']={'source_event_sha256':'e'*64,'document_sha256':'f'*64}
 store.ingest([negative],now=at)
 linked=at+timedelta(seconds=1);latest,=attach(store,out,pub,linked)
 since=at+timedelta(milliseconds=500)
 base,cs,ctx,*_=build([latest],linked,since)
 timeline,ctx=targeted_counterevidence(store,[latest],base,ctx,as_of=linked,now=linked,since=since)
 selected=select_timelines(timeline,match_company_search(ctx,SUPPLIER),SUPPLIER)
 company,=timeline_evidence_view(selected,'observed')['companies'];entry,=company['entries']
 proof,=entry['relation_counterevidence']
 assert proof['context_in_period'] and not proof['in_period']
 assert company['period_evidence_counts']['RELATION_EVENT_CONTEXT']==1
 assert not entry['counterevidence'] and company['new_actions_in_period']==0
 past=store.search(as_of=at,now=linked);old,*_=build(past,at)
 assert not any(c['entity_id']==SUPPLIER for c in timeline_evidence_view(old,'observed')['companies'])


def test_only_new_counter_report_is_shown_while_original_target_is_retained(tmp_path):
 from test_theme_emergence import event
 latest,store,first,at,original,report=direct_case(tmp_path,'CONTRADICT')
 later=at+timedelta(hours=1)
 report2=event(3,topic='HBM',company=ID,polarity='RETRACT',target=original['event_id'])
 report2['source_binding']={'source_event_sha256':'e'*64,'document_sha256':'f'*64}
 latest,=store.ingest([report2],now=later)
 since=at+timedelta(minutes=1);base,cs,ctx,*_=build([latest],later,since)
 timeline,_=targeted_counterevidence(store,[latest],base,ctx,as_of=later,now=later,since=since)
 all_entry,=timeline_evidence_view(timeline)['companies'][0]['entries']
 assert len(all_entry['counterevidence'])==2
 entry,=timeline_evidence_view(timeline,'observed')['companies'][0]['entries']
 assert [p['polarity'] for p in entry['counterevidence']]==['RETRACT']
 assert entry['recorded_at']==T.isoformat() and entry['source_url']==original['source_url']


def test_identity_metadata_and_empty_days_are_not_new_actions(tmp_path):
 themes,store,first,at=case(tmp_path);later=at+timedelta(days=1)
 timeline,*_=build(themes,later,later)
 for e in timeline['companies'][0]['entries']:e['identity_available_at']=later.isoformat()
 company,=timeline_evidence_view(timeline,'observed')['companies']
 assert company['entries']==[] and company['period_evidence_counts']=={}
 assert company['period_evidence_status']=='NO_NEW_EVIDENCE' and company['new_actions_in_period']==0


def test_unresolved_reports_stay_unresolved_and_obey_period(tmp_path):
 themes,store,first,at=case(tmp_path);timeline,*_=build(themes,at,at)
 timeline['counterevidence_unresolved']=[{'recorded_at':T.isoformat(),'reason':'TARGET_NOT_FOUND'}, {'recorded_at':at.isoformat(),'reason':'COMPANY_BINDING_MISMATCH'}]
 view=timeline_evidence_view(timeline,'observed')
 assert view['counterevidence_unresolved']==[timeline['counterevidence_unresolved'][1]]
 assert len(timeline_evidence_view(timeline)['counterevidence_unresolved'])==2
 with pytest.raises(ValueError):timeline_evidence_view(timeline,'invalid')


def test_ui_empty_and_new_counterevidence_show_original_and_new_times(tmp_path):
 latest,store,first,at,*_=direct_case(tmp_path)
 since=at-timedelta(minutes=1);base,cs,ctx,*_=build([latest],at,since)
 timeline,ctx=targeted_counterevidence(store,[latest],base,ctx,as_of=at,now=at,since=since)
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCompanyTimelines(parent,input.timeline,input.query,companySearchResults(input.context,input.query));',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 def render(t):return subprocess.check_output(['node','-e',code],input=json.dumps(dict(timeline=t,context=ctx,query=ID)).encode()).decode()
 text=render(timeline_evidence_view(timeline,'observed'))
 assert '기간 이전 대상 사건' in text and '기간 내 새 직접 반대 근거' in text
 assert T.isoformat() in text and at.isoformat() in text
 for c in timeline['companies']:
  for e in c['entries']:
   for p in e['counterevidence']:p['in_period']=False
 text=render(timeline_evidence_view(timeline,'observed'))
 assert '선택 기간 새 근거 없음' in text and '약화·무효를 뜻하지 않습니다.' in text


def test_http_filter_both_routes_preserves_candidates_pit_and_v3(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 themes,store,first,at=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return at.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  for route,params,key in [('/api/company-research',{'as_of':at.isoformat(),'since':(T+timedelta(hours=1)).isoformat()},'CompanyCandidates'),('/api/period',{'date':'2026-10-15'},'company_candidates')]:
   all_data=json.loads(fetch(route,q=ID,**params));view=json.loads(fetch(route,q=ID,timeline_activity='observed',**params))
   assert view[key]==all_data[key]
   assert view['company_timelines']['evidence_filter']=='observed'
   assert view['company_timelines']['companies'][0]['period_evidence_status']=='NEW_EVIDENCE'
   assert json.loads(fetch(route,q='가상',timeline_activity='observed',**params))['company_timelines']['companies']==[]
   with pytest.raises(HTTPError) as exc:fetch(route,timeline_activity='invalid',**params)
   assert exc.value.code==400
  current=json.loads(fetch('/api/company-research',q=ID,as_of=at.isoformat(),timeline_activity='observed'))
  assert len(current['company_timelines']['companies'][0]['entries'])==4 # No since: all available history.
  old=json.loads(fetch('/api/company-research',q=ID,as_of=T.isoformat(),timeline_activity='observed'))
  assert len(old['company_timelines']['companies'][0]['entries'])==1
  assert fetch('/api/themes',as_of=at.isoformat(),company_candidates='1',timeline_activity='observed')==build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True)
 finally:server.shutdown();server.server_close();worker.join(2)
