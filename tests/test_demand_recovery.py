"""Literal recovery causes, distinct from growth and price changes."""
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

CAUSE='HBM 수요 회복으로'
TITLE='가상전자, '+CAUSE+' 생산 재개'

@pytest.mark.parametrize('cause,tail,phase,basis',[
 (CAUSE,'생산 재개','SOURCE_REPORTED','DEMAND'),
 ('HBM 주문 회복으로','공급을 재개했다','SOURCE_REPORTED','ORDER'),
 ('HBM 수요가 회복에 따라','생산을 재개했다','SOURCE_REPORTED','DEMAND'),
 ('고대역폭 메모리 주문 회복에 대응해','공급 재개','SOURCE_REPORTED','ORDER'),
 (CAUSE,'생산 재개 계획','PLANNED','DEMAND'),(CAUSE,'생산 재개 결정','PLANNED','DEMAND'),
 (CAUSE,'공급 재개 목표','PLANNED','DEMAND'),(CAUSE,'생산 재개한다','PLANNED','DEMAND'),
 ('HBM 수요 회복에 대비해','생산 재개','PLANNED','DEMAND'),
])
def test_literal_recovery_phase_actor_and_proof(cause,tail,phase,basis):
 text='가상전자, '+cause+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['economic_driver'],c['action'],c['phase'],c['entity_ids'])==('DEMAND_RECOVERY','SUPPLY_RESUMPTION',phase,['가상전자'])
 assert c['demand_recovery_cause']==dict(product='HBM',basis=basis,change='RECOVERY',source_expression=cause,expression_sha256=sha256(cause.encode()).hexdigest())
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 취소',TITLE+' 보도를 부인했다',
 TITLE+' 전망',TITLE+' 가능성',TITLE+'를 위한 기술 소개',TITLE.replace('회복으로','회복 예상으로'),
 TITLE.replace(CAUSE,'지난해 '+CAUSE),TITLE.replace('생산 재개','지난달 공급 재개'),
 TITLE.replace('생산 재개','새빛소재는 생산 재개'),TITLE.replace('생산 재개','DRAM 생산 재개'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 수요 증가로'),TITLE.replace(CAUSE,'HBM 가격 상승으로'),
 TITLE.replace(CAUSE,'HBM 주가 회복으로'),TITLE.replace(CAUSE,''),
 TITLE.replace(CAUSE,'HBM 및 DRAM 수요 회복으로'),TITLE.replace(CAUSE,'HBM 수요 회복으로 DRAM 주문 증가로'),
 TITLE.replace('생산 재개','생산 시작'),
 '가상전자, AI 서버용 HBM 수요 회복으로 스마트폰용 HBM 생산 재개',
])
def test_unrealized_unrelated_or_borrowed_recovery_is_not_a_recovery_event(text):
 assert not any(c['economic_driver']=='DEMAND_RECOVERY' for c in extract_economic_changes(text))


def mixed_titles():
 return [TITLE,'새빛소재, HBM 주문 회복으로 공급 재개','미래장비, HBM 수요 회복으로 생산 재개 계획',
  '별도전자, AI 서버용 HBM 수요 회복으로 생산 재개','다른소재, 스마트폰용 HBM 수요 회복으로 공급 재개',
  '다른전자, DRAM 수요 회복으로 생산 재개','증가전자, HBM 수요 증가로 생산 재개',
  '가격소재, HBM 가격 상승으로 생산 시작','미명시장비, HBM 생산 시작']


def case(tmp_path):return source_case(tmp_path,titles=mixed_titles()[:3])


def test_recovery_theme_company_sources_period_and_standard(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['economic_driver']=='DEMAND_RECOVERY' and '회복' in theme['provisional_name']
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 for c in data['CompanyCandidates']:
  basis,=c['inclusion_basis'];assert basis['demand_recovery_cause']['change']=='RECOVERY' and '보도된 회복 원인' in basis['reason']
  assert not c['verified_real_transaction'] and not c['verified_real_benefit']
  assert any('기준 수요량·이전 중단' in u for u in c['uncertainties'])
  item,=company_evidence(theme,c['entity_id'],**args)['items'];assert item['status']=='READY' and '회복' in item['excerpt']
 assert store.search(query='수요·주문 회복',as_of=args['as_of'],now=args['now'])==[theme]
 assert store.search(as_of=at,now=args['now'])==[first]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert all(r['supporting_source']['demand_recovery_cause']['change']=='RECOVERY' for r in diff['events']['added'])
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_growth_price_unknown_product_and_end_use_are_separate(tmp_path):
 rows=[claim(t,i) for i,t in enumerate(mixed_titles())];at=T+timedelta(hours=10)
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=at)
 assert len(themes)==7 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,1,1,3]
 assert next(t for t in themes if len(t['entity_ids'])==3)['economic_driver']=='DEMAND_RECOVERY'
 text='가상전자는 HBM 수요 회복으로 생산을 재개했고 새빛소재는 DRAM 주문 회복으로 공급 재개'
 assert [(c['topic'],c['entity_ids']) for c in extract_economic_changes(text)]==[('HBM',['가상전자']),('DRAM',['새빛소재'])]
 assert extract_economic_changes(TITLE,include_demand_recovery=False)==[]


@pytest.mark.parametrize('forgery',['expression','basis','missing'])
def test_saved_recovery_proof_cannot_be_forged(tmp_path,forgery):
 from newscatalystos.feed_analysis_delivery import _validate_report
 theme,args,_,report,*_=case(tmp_path);forged=deepcopy(report);c=next(r for r in forged['results'] if r['headline']==TITLE)['economic_changes'][0]
 if forgery=='expression':c['demand_recovery_cause']=extract_economic_changes(TITLE.replace('수요','주문'))[0]['demand_recovery_cause']
 elif forgery=='basis':c['demand_recovery_cause']['basis']='ORDER'
 else:del c['demand_recovery_cause']
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])
 # Standard delivery validates the same literal proof, including missing fields.
 forged_theme=deepcopy(theme);ref=forged_theme['source_refs'][0];ref.pop('demand_recovery_cause')
 with pytest.raises(SourceShareError):build_theme_bundle([forged_theme],decision_at=args['as_of'],now=args['now'])


def test_old_growth_report_id_source_pit_and_bytes_unchanged(tmp_path):
 theme,args,store,report,events,first,at=source_case(tmp_path,titles=[TITLE.replace('회복','증가'),'새빛소재, HBM 주문 증가로 공급 재개'])
 before=fingerprint(tmp_path);raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 item,=company_evidence(theme,'가상전자',**args)['items'];assert item['status']=='READY' and item['excerpt']==TITLE.replace('회복','증가')
 assert fingerprint(tmp_path)==before and 'demand_recovery_cause' not in theme['source_refs'][0]
 later=args['now']+timedelta(seconds=1);new=store.ingest([claim(TITLE,1,at=args['now'])],now=later)
 assert new[0]['theme_id']!=theme['theme_id'] and store.search(as_of=args['as_of'],now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=args['as_of'],now=later,include_company_candidates=True)


def test_js_recovery_search_is_readonly():
 c=extract_economic_changes(TITLE)[0]
 r=present(dict(headline='합성 자료',economic_changes=[c]),['수요 회복','주문 회복','가격 상승','DEMAND_RECOVERY'])
 assert r['matches']==r['themes']==[True,False,False,True] and r['unchanged']


def test_licensed_body_recovery_proof(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 판매·매출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args);assert report['economic_changes'][0]['demand_recovery_cause']['change']=='RECOVERY'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_semantic_recovery_preserves_proof_scope_and_phase_without_ai():
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title=TITLE.replace('HBM','AI 서버용 HBM');cause='AI 서버용 '+CAUSE
 event=dict(actors=['가상전자'],action='SUPPLY_RESUMPTION',phase='SOURCE_REPORTED',topic='HBM',driver='DEMAND_RECOVERY',quote=title,cause_quote=cause)
 parsed=parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)
 c,=changes_from_events(parsed,sha256(title.encode()).hexdigest());validate_change(c)
 assert c['demand_scope']['destination']=='AI 서버' and c['demand_recovery_cause']['basis']=='DEMAND'
 event['action']='PRODUCTION_START'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)
 event['action']='SUPPLY_RESUMPTION';event['driver']='DEMAND_EXPANSION'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)


def test_period_http_recovery_company_source_and_search(tmp_path,monkeypatch):
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
  assert len(data['company_candidates'])==9 and len(data['themes'])==7
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']==TITLE
  with urlopen(url+'/api/themes?'+urlencode({'q':'DEMAND_RECOVERY'})) as response:found=json.load(response)
  assert len(found['ThemeCandidates'])==4
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_pre_recovery_contract_source_id_and_snapshot_remain_readable(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 title=TITLE.replace('생산 재개','공급계약 체결');info=setup(tmp_path,title);at=datetime.now(timezone.utc)
 report=run(info,now=at);row=report['results'][0]
 old,=extract_economic_changes(title,include_demand_recovery=False);old['evidence_level']='REPORTED';row['economic_changes']=[old]
 assert old['economic_driver']=='UNKNOWN' and old['action']=='CONTRACT'
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');theme,=store.ingest([observation(row,old)],now=at)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 item,=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
  feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
 assert item['status']=='READY' and item['excerpt']==title
 later=at+timedelta(seconds=1);store.ingest([claim(TITLE,1,at=at)],now=later)
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)
