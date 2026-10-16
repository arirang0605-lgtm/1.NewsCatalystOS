"""Named investment siblings preserve legacy first IDs and separate project facts."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import pytest
from newscatalystos.economic_changes import extract_economic_changes,normalized
from newscatalystos.theme_emergence import ThemeStore,economic_observation,validate_change
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from newscatalystos.source_share import SourceShareError
from test_federated_news_search import fingerprint
from test_service_realization import T
from test_research_action_labels import present

A='가상전자, HBM 수요 회복으로 「청해공장」 투자 결정'
B=A.replace('청해공장','남해공장')
BODY=A+'\n'+B
TITLE=A+'. '+B


def observations(changes,url='https://example.org/article',at=T):
 return [economic_observation(c,origin_reference=url,source_url=url,source_id='synthetic',source_available_at=at.isoformat(),content_scope='LICENSED_ARTICLE_TEXT') for c in changes]

@pytest.mark.parametrize('separator',['\n','. '])
def test_two_names_extract_and_store_as_two_same_source_events(tmp_path,separator):
 text=separator.join((A,B));changes=extract_economic_changes(text)
 assert [c['investment_project']['project_name'] for c in changes]==['청해공장','남해공장']
 for c in changes:validate_change(c)
 first,=extract_economic_changes(A)
 if separator!='\n':first['source_paragraph_sha256']=sha256(text.encode()).hexdigest()
 assert changes[0]==first and 'investment_event_key' not in first
 assert changes[1]['investment_event_key']==sha256(normalized('남해공장').encode()).hexdigest()
 rows=observations(changes);assert len({r['event_id'] for r in rows})==2
 assert rows[0]['event_id']==observations([first])[0]['event_id']
 theme,=ThemeStore(tmp_path/'themes').ingest(rows,now=T)
 assert theme['scores']['distinct_economic_events']==2 and theme['scores']['company_breadth']==1
 assert {r['investment_project']['project_name'] for r in theme['source_refs']}=={'청해공장','남해공장'}

@pytest.mark.parametrize('text',[A+'\n'+A,BODY+'\n'+A+'\n'+B,A+'. '+A])
def test_repeated_literal_projects_do_not_multiply(text):
 changes=extract_economic_changes(text)
 assert len(changes)==len({c['investment_project']['project_name'] for c in changes})==(2 if B in text else 1)


def test_unnamed_factories_do_not_get_project_identities():
 text=A.replace('「청해공장」','신규 공장')+'\n'+B.replace('「남해공장」','시설')
 changes=extract_economic_changes(text)
 assert all('investment_project' not in c and 'investment_event_key' not in c for c in changes)


def case(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc)+timedelta(seconds=1)
 report=run(info,now=at);root=tmp_path/'reports';docs=tmp_path/'documents'
 publish_feed_analysis(report,root/'core/reports')
 events=[observation(r,c) for r in report['results'] for c in r['economic_changes']]
 store=ThemeStore(docs/'theme_history');first,=store.ingest(events[:1],now=at)
 later=at+timedelta(seconds=1);theme,=store.ingest(events[1:],now=later)
 args=dict(reports_root=root,document_root=docs,feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)],as_of=later,now=later+timedelta(seconds=1))
 return theme,args,store,report,events,first,at


def test_rss_saved_report_company_excerpts_search_pit_and_standard(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert len(events)==2 and theme['scores']['distinct_economic_events']==2
 row,=report['results'];assert len(row['economic_changes'])==2
 assert len({c['source_paragraph_sha256'] for c in row['economic_changes']})==1
 assert store.search(as_of=at,now=args['now'])==[first]
 before=fingerprint(tmp_path);detail=company_evidence(theme,'가상전자',**args)
 assert {i['excerpt'] for i in detail['items'] if i['status']=='READY'}=={A+'.',B}
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 c,=data['CompanyCandidates'];assert {b['investment_project']['project_name'] for b in c['inclusion_basis']}=={'청해공장','남해공장'}
 assert not c['verified_real_transaction'] and not c['verified_real_benefit']
 assert store.search(query='청해공장',as_of=args['as_of'],now=args['now'])==[theme]
 assert store.search(query='남해공장',as_of=args['as_of'],now=args['now'])==[theme]
 screen=present(dict(headline='합성 자료',category=None,economic_changes=row['economic_changes']),['청해공장','남해공장'])
 assert screen['matches']==screen['themes']==[True,True]
 assert store.ingest(events,now=args['now'])==[] and fingerprint(tmp_path)==before


def test_licensed_body_same_article_old_first_id_snapshot_and_bytes(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,BODY)
 report=analyze_motir_document(**args);changes=report['economic_changes'];assert len(changes)==2
 old=deepcopy(report);old['economic_changes']=changes[:1]
 root=tmp_path/'reports';oldpath,oldpin=publish_motir_document_analysis(old,root)
 path,pin=publish_motir_document_analysis(report,root)
 assert path!=oldpath and consume_motir_document_analysis(oldpath,oldpin)['economic_changes']==changes[:1]
 assert consume_motir_document_analysis(path,pin)['economic_changes']==changes
 rows=observations(changes);store=ThemeStore(tmp_path/'themes');first,=store.ingest(rows[:1],now=T)
 raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 later=T+timedelta(seconds=1);latest,=store.ingest(rows,now=later)
 assert latest['theme_id']==first['theme_id'] and latest['first_detected_at']==first['first_detected_at']
 assert latest['scores']['distinct_economic_events']==2 and rows[0]['event_id'] in first['event_ids']
 assert store.search(as_of=T,now=later)==[first]
 assert raw==build_theme_bundle([first],decision_at=T,now=later,include_company_candidates=True)
 assert sha256(oldpath.read_bytes()).hexdigest()==oldpin


def test_two_projects_have_separate_decision_execution_followups(tmp_path):
 plans=extract_economic_changes(BODY)
 starts=extract_economic_changes(BODY.replace('투자 결정','투자 집행'))
 p=observations(plans,'https://example.org/plan',T)
 at=T+timedelta(hours=1);s=observations(starts,'https://example.org/start',at)
 store=ThemeStore(tmp_path/'themes');first,=store.ingest(p,now=T);latest,=store.ingest(s,now=at)
 assert first['scores']['distinct_economic_events']==2 and latest['scores']['distinct_economic_events']==2
 assert len(latest['event_ids'])==4 and len(latest['investment_stage_links'])==2
 assert {link['project_name'] for link in latest['investment_stage_links']}=={'청해공장','남해공장'}
 for link in latest['investment_stage_links']:
  plan=next(r for r in p if r['event_id']==link['decision_event_id'])
  start=next(r for r in s if r['event_id']==link['execution_event_id'])
  assert plan['change']['investment_project']['project_name']==start['change']['investment_project']['project_name']==link['project_name']
  assert not link['is_execution_confirmed']
 raw=build_theme_bundle([latest],decision_at=at,now=at,include_company_candidates=True)
 assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)['ThemeCandidates']==[latest]

@pytest.mark.parametrize('fault',['name','actor','scope','product','future'])
def test_other_project_actor_scope_or_time_cannot_borrow_followup(tmp_path,fault):
 p=observations(extract_economic_changes(BODY),'https://example.org/plan',T)
 text=B.replace('투자 결정','투자 집행')
 if fault=='name':text=text.replace('남해공장','정암공장')
 if fault=='actor':text=text.replace('가상전자','새빛소재')
 if fault=='product':text=text.replace('HBM','DRAM')
 if fault=='scope':text=text.replace('HBM 수요','AI 서버용 HBM 수요')
 at=T+timedelta(hours=1);s=observations(extract_economic_changes(text),'https://example.org/start',T if fault=='future' else at)
 themes=ThemeStore(tmp_path/'themes').ingest(p+s,now=at)
 assert not any(t.get('investment_stage_links') for t in themes)

@pytest.mark.parametrize('fault',['name','key','null','actor'])
def test_saved_rss_project_discriminator_cannot_be_forged(tmp_path,fault):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=case(tmp_path);forged=deepcopy(report);c=forged['results'][0]['economic_changes'][1]
 if fault=='name':c['investment_project']={**c['investment_project'],'project_name':'정암공장'}
 if fault=='key':c['investment_event_key']='f'*64
 if fault=='null':c['investment_event_key']=None
 if fault=='actor':c['entity_ids']=['새빛소재']
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_standard_export_rejects_invalid_sibling_key(tmp_path):
 theme,args,*_=case(tmp_path);ref=next(r for r in theme['source_refs'] if 'investment_event_key' in r)
 ref['investment_event_key']='f'*64
 with pytest.raises(SourceShareError):build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)


def test_period_http_shows_both_projects_and_originals(tmp_path,monkeypatch):
 import threading
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 theme,args,*_=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock);monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();before=fingerprint(args['document_root']);url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert len(data['items'])==1 and len(data['items'][0]['economic_changes'])==2
  assert len(data['themes'])==len(data['company_candidates'])==1
  assert {b['investment_project']['project_name'] for b in data['company_candidates'][0]['inclusion_basis']}=={'청해공장','남해공장'}
  for name in ('청해공장','남해공장'):
   with urlopen(url+'/api/themes?'+urlencode({'q':name})) as response:found=json.load(response)
   assert found['ThemeCandidates']==[theme]
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert {i['excerpt'] for i in detail['items'] if i['status']=='READY'}=={A+'.',B}
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def licensed_case(tmp_path,monkeypatch):
 import test_company_evidence as fixture
 from newscatalystos.motir_document_analysis import consume_motir_document_analysis
 monkeypatch.setattr(fixture,'TITLE',BODY)
 _,args,binding=fixture.body(tmp_path)
 path,=args['document_root'].glob('*/reports/motir_document_analysis_*.json')
 report=consume_motir_document_analysis(path,path.stem.split('_')[-1],now=args['now'])
 rows=[economic_observation(c,origin_reference=report['source_url'],source_url=report['source_url'],
  source_id='motir-official-press',source_available_at=report['source_available_at'],
  source_binding={'source_event_sha256':binding['archive_version'],'document_sha256':report['document_sha256']}) for c in report['economic_changes']]
 theme,=ThemeStore(args['document_root']/'theme_history').ingest(rows,now=args['as_of'])
 return theme,args,binding


def test_licensed_body_both_original_paragraphs_are_ready(tmp_path,monkeypatch):
 theme,args,_=licensed_case(tmp_path,monkeypatch);before=fingerprint(tmp_path)
 items=company_evidence(theme,'가상전자',**args)['items']
 assert len(items)==2 and all(i['status']=='READY' for i in items)
 assert {i['excerpt'] for i in items}=={A,B+'.'}
 assert theme['scores']['distinct_economic_events']==2 and fingerprint(tmp_path)==before

@pytest.mark.parametrize('fault',['body_tamper','key','service'])
def test_licensed_body_or_sibling_reference_tamper_never_exposes_source(tmp_path,monkeypatch,fault):
 theme,args,binding=licensed_case(tmp_path,monkeypatch)
 if fault=='body_tamper':
  p=args['jobs'][0]['archive_root']/binding['archive_version']/'payload.bin';p.write_bytes(p.read_bytes()+b'x')
 else:
  ref=next(r for r in theme['source_refs'] if 'investment_event_key' in r)
  ref['investment_event_key' if fault=='key' else 'investment_project']='f'*64 if fault=='key' else {**ref['investment_project'],'project_name':'정암공장'}
 items=company_evidence(theme,'가상전자',**args)['items']
 if fault=='body_tamper':assert all(i['status']!='READY' for i in items)
 else:
  sibling=next(r for r in theme['source_refs'] if 'investment_event_key' in r)
  assert all(i['status']!='READY' for i in items if i['event_id']==sibling['event_id'])


@pytest.mark.parametrize('suffix',[' 예정',' 계획',' 목표'])
def test_planned_execution_does_not_borrow_reported_stage(tmp_path,suffix):
 decisions=observations(extract_economic_changes(BODY),'https://example.org/decision',T)
 text=BODY.replace('투자 결정','투자 집행'+suffix)
 changes=extract_economic_changes(text)
 assert len(changes)==2 and all(c['phase']=='PLANNED' for c in changes)
 at=T+timedelta(hours=1);executions=observations(changes,'https://example.org/execution',at)
 theme,=ThemeStore(tmp_path/'themes').ingest(decisions+executions,now=at)
 assert not theme.get('investment_stage_links') and theme['scores']['distinct_economic_events']==4


def test_two_project_decisions_can_both_be_planned():
 changes=extract_economic_changes(BODY.replace('투자 결정','투자 결정 계획'))
 assert len(changes)==2 and all(c['phase']=='PLANNED' and c['action']=='INVESTMENT' for c in changes)
 assert {c['investment_project']['project_name'] for c in changes}=={'청해공장','남해공장'}
