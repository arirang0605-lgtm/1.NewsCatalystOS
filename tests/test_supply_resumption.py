"""Explicit demand-driven resumption; no inferred shutdown, sales or benefit."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from types import SimpleNamespace
import json
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,validate_change
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_policy_company_actions import case as source_case
from test_service_realization import claim
from test_theme_emergence import T
from test_federated_news_search import fingerprint
from test_research_action_labels import present

CAUSE='HBM 수요 증가로'
TITLE='가상전자, '+CAUSE+' 생산 재개'

@pytest.mark.parametrize('tail,phase',[
 ('생산 재개','SOURCE_REPORTED'),('공급을 재개했다','SOURCE_REPORTED'),
 ('HBM 생산을 재개했다','SOURCE_REPORTED'),('고대역폭 메모리를 공급 재개','SOURCE_REPORTED'),
 ('생산 재개 예정','PLANNED'),('생산 재개 계획','PLANNED'),('공급 재개 목표','PLANNED'),
 ('생산 재개한다','PLANNED'),('공급을 재개할 계획','PLANNED'),('생산 재개 결정','PLANNED'),
])
def test_literal_resumption_actor_phase_and_sha(tail,phase):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['economic_driver'],c['phase'],c['entity_ids'])==('SUPPLY_RESUMPTION','DEMAND_EXPANSION',phase,['가상전자'])
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']
 assert not any('shutdown' in k or 'revenue' in k for k in c)

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 취소',TITLE+' 보도를 부인했다',
 TITLE+' 전망',TITLE+' 여부 확인',TITLE+'를 위한 기술 소개',TITLE+' 가능성',
 TITLE.replace(CAUSE,'지난해 '+CAUSE),TITLE.replace('생산 재개','지난달 공급 재개'),
 TITLE.replace('생산 재개','DRAM 생산 재개'),TITLE.replace('생산 재개','새빛소재는 생산 재개'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 수요 증가. 새빛소재는'),TITLE.replace(CAUSE,'HBM 가격 상승으로'),
 TITLE.replace(CAUSE,'HBM 수요 감소로'),TITLE.replace(CAUSE,''),
 TITLE.replace(CAUSE,'HBM 수요 증가로 DRAM 주문 증가로'),
 TITLE.replace('생산 재개','생산 시작'),TITLE.replace('생산 재개','납품 시작'),TITLE.replace('생산 재개','공급계약 체결'),
 '가상전자, AI 서버용 HBM 수요 증가로 스마트폰용 HBM 생산 재개',
])
def test_denials_history_other_causes_and_borrowed_subject_product_scope(text):
 assert not any(c['action']=='SUPPLY_RESUMPTION' for c in extract_economic_changes(text))


def mixed_titles():
 return [TITLE,'새빛소재, HBM 주문 증가로 공급 재개','미래장비, HBM 수요 증가로 생산 재개 계획',
  '별도전자, AI 서버용 HBM 수요 증가로 생산 재개','다른소재, 스마트폰용 HBM 수요 증가로 공급 재개',
  '다른전자, DRAM 수요 증가로 생산 재개']


def case(tmp_path):return source_case(tmp_path,titles=mixed_titles()[:3])


def test_resumption_theme_sources_company_period_and_standard(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==3
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 for c in data['CompanyCandidates']:
  basis,=c['inclusion_basis'];assert basis['action']=='SUPPLY_RESUMPTION' and '생산·공급 재개' in basis['reason']
  assert not c['verified_real_transaction'] and not c['verified_real_benefit'] and c['benefit_paths']==[]
  assert any('이전 중단 이력·실제 판매·매출·수혜' in u for u in c['uncertainties'])
  item,=company_evidence(theme,c['entity_id'],**args)['items'];assert item['status']=='READY' and '재개' in item['excerpt']
  if c['entity_id']=='미래장비':assert basis['phase']=='PLANNED'
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert {r['supporting_source']['action'] for r in diff['events']['added']}=={'SUPPLY_RESUMPTION'}
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_causes_scopes_products_and_explicit_company_clauses(tmp_path):
 rows=[claim(t,i) for i,t in enumerate(mixed_titles())];at=T+timedelta(hours=7)
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=at)
 assert len(themes)==4 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,3]
 text='가상전자는 HBM 수요 증가로 생산을 재개했고 새빛소재는 DRAM 주문 증가로 공급 재개'
 assert [(c['topic'],c['entity_ids']) for c in extract_economic_changes(text)]==[('HBM',['가상전자']),('DRAM',['새빛소재'])]
 assert extract_economic_changes(TITLE,include_resumption=False)==[]


@pytest.mark.parametrize('field,value',[('phase','SOURCE_REPORTED'),('entity_ids',['다른전자'])])
def test_saved_report_cannot_replace_planned_action_actor_or_phase(tmp_path,field,value):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=case(tmp_path);forged=deepcopy(report)
 row=next(r for r in forged['results'] if '계획' in r['headline']);row['economic_changes'][0][field]=value
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_old_action_source_snapshot_id_and_bytes_remain_readable(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 title='가상전자, HBM 수요 증가로 생산 시작 및 공급 재개'
 info=setup(tmp_path,title);at=datetime.now(timezone.utc);report=run(info,now=at);row=report['results'][0]
 old,=extract_economic_changes(title,include_resumption=False);old['evidence_level']='REPORTED';row['economic_changes']=[old]
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');theme,=store.ingest([observation(row,old)],now=at)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 item,=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
  feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
 assert item['status']=='READY' and item['excerpt']==title
 later=at+timedelta(seconds=1);store.ingest([claim('새빛소재, HBM 수요 증가로 공급 재개',1,at=at)],now=later)
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)


def test_js_resumption_label_and_search_are_readonly():
 item=dict(headline='합성 자료',category=None,economic_changes=[dict(action='SUPPLY_RESUMPTION',phase='PLANNED')])
 r=present(item,['생산 재개','공급 재개','생산 시작','납품 시작'])
 assert r['label']=='생산·공급 재개 · 계획 단계' and r['matches']==r['themes']==[True,True,False,False] and r['unchanged']


def test_licensed_body_resumption(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 판매·매출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args);assert report['economic_changes'][0]['action']=='SUPPLY_RESUMPTION'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_semantic_resumption_is_literal_and_keeps_scope_without_live_ai():
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title=TITLE.replace('HBM','AI 서버용 HBM')
 event=dict(actors=['가상전자'],action='SUPPLY_RESUMPTION',phase='SOURCE_REPORTED',topic='HBM',driver='DEMAND_EXPANSION',quote=title,cause_quote='AI 서버용 '+CAUSE)
 parsed=parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)
 c,=changes_from_events(parsed,sha256(title.encode()).hexdigest());assert c['demand_scope']['destination']=='AI 서버'
 event['quote']=title+' 계획';event['phase']='SOURCE_REPORTED'
 assert parse_events(SimpleNamespace(claims=[json.dumps(event)]),event['quote'])[0]['phase']=='PLANNED'
 event['actors']=['다른전자']
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),event['quote'])


def test_period_http_resumption_company_source_and_search(tmp_path,monkeypatch):
 import threading
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,*_=source_case(tmp_path,titles=mixed_titles())
 theme=next(t for t in store.search(as_of=args['as_of'],now=args['now']) if len(t['entity_ids'])==3)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock);monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();before=fingerprint(args['document_root']);url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert len(data['company_candidates'])==6 and len(data['themes'])==4
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']==TITLE
  with urlopen(url+'/api/themes?'+urlencode({'q':'SUPPLY_RESUMPTION'})) as response:found=json.load(response)
  assert len(found['ThemeCandidates'])==4
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before
