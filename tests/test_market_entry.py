"""Synthetic market entry claims; no independent sales/benefit certification."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import threading
from urllib.request import urlopen
from urllib.parse import urlencode
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,validate_change,economic_observation
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from newscatalystos.theme_changes import compare_themes
from newscatalystos.source_share import SourceShareError
from test_policy_company_actions import case as source_case
from test_service_realization import claim
from test_theme_emergence import T
from test_federated_news_search import fingerprint
from test_research_action_labels import present

CAUSE='AI 서버용 HBM 수요 증가로'
TITLE='가상전자, '+CAUSE+' 일본 시장 진출'
POLICY='미국 ‘첨단칩통제법’ HBM 수출 규제 완화로'

@pytest.mark.parametrize('tail,market,phase',[
 ('일본 시장 진출','일본','SOURCE_REPORTED'),
 ('일본 시장에 진출했다','일본','SOURCE_REPORTED'),
 ('유럽 시장으로 본격 진출','유럽','SOURCE_REPORTED'),
 ('일본 반도체 시장 신규 진출','일본 반도체','SOURCE_REPORTED'),
 ('「일본 HBM」 시장에 진출','일본 HBM','SOURCE_REPORTED'),
 ('일본 시장 진출에 성공했다','일본','SOURCE_REPORTED'),
 ('일본 시장 진출 계획','일본','PLANNED'),
 ('일본 시장 진출 목표','일본','PLANNED'),
 ('일본 시장 진출 예정이다','일본','PLANNED'),
 ('일본 시장에 진출한다','일본','PLANNED'),
 ('일본 시장에 진출할 계획이다','일본','PLANNED'),
])
def test_source_named_market_stage_actor_and_hash(tail,market,phase):
 text='가상전자, '+CAUSE+' '+tail
 c,=extract_economic_changes(text);validate_change(c)
 assert (c['action'],c['phase'],c['entity_ids'])==('MARKET_ENTRY',phase,['가상전자'])
 assert c['demand_scope']['destination']=='AI 서버' and c['topic']=='HBM'
 proof=c['market_entry'];assert proof['market_name']==market and proof['source_expression'] in text
 assert proof['expression_sha256']==sha256(proof['source_expression'].encode()).hexdigest()
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']

@pytest.mark.parametrize('text',[
 TITLE.replace('수요','주문'),TITLE.replace(CAUSE,POLICY),
 CAUSE+' 가상전자는 일본 시장 진출',POLICY+' 가상전자는 일본 시장 진출',
])
def test_demand_order_policy_cause_first(text):
 c,=extract_economic_changes(text);validate_change(c)
 assert c['action']=='MARKET_ENTRY' and c['entity_ids']==['가상전자']
 assert c['market_entry']['market_name']=='일본'

@pytest.mark.parametrize('text',[
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 취소',TITLE+' 철회',TITLE+' 실패',
 TITLE+' 보도를 부인했다',TITLE+' 여부 확인',TITLE+'을 위한 기술 소개',TITLE+' 설명회',TITLE+' 전망',
 TITLE.replace('일본 시장 진출','일본 시장 진출 준비 시작'),
 TITLE.replace('일본 시장 진출','새빛소재는 일본 시장 진출'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 기술 소개로'),TITLE.replace(CAUSE,'HBM 주가 상승으로'),
 TITLE.replace(CAUSE,'HBM 수요 감소로'),TITLE.replace(CAUSE,'지난해 HBM 수요 증가로'),
 TITLE.replace('일본 시장','지난달 일본 시장'),TITLE+'했고 그 회사는 생산 시작',
 TITLE.replace('일본 시장','DRAM 시장'),TITLE.replace('일본 시장','새빛소재 시장'),
 TITLE.replace('일본 시장','신규 시장'),TITLE.replace('일본 시장','일본 및 미국 시장'),
 TITLE.replace('일본 시장','일본과 미국 시장'),
 TITLE.replace('일본 시장 진출','일본 시장의 기술 소개'),
])
def test_no_unanchored_negative_historical_or_other_actor_entry(text):
 assert not any(c['action']=='MARKET_ENTRY' for c in extract_economic_changes(text))


def test_custom_issuer_directory_and_separate_company_clauses():
 c,=extract_economic_changes('알파시스템은 '+CAUSE+' 일본 시장 진출',company_names=['알파시스템'])
 assert c['entity_ids']==['알파시스템']
 rows=extract_economic_changes('가상전자는 '+CAUSE+' 일본 시장 진출했고 새빛소재는 스마트폰용 HBM 수요 증가로 미국 시장 진출')
 assert [(c['entity_ids'],c['market_entry']['market_name'],c['demand_scope']['destination']) for c in rows]==[
  (['가상전자'],'일본','AI 서버'),(['새빛소재'],'미국','스마트폰')]
 assert not extract_economic_changes(TITLE,include_market_entry=False)


def case(tmp_path):
 return source_case(tmp_path,titles=[TITLE,'새빛소재, '+CAUSE+' 미국 시장 진출',
   '미래장비, '+CAUSE+' 생산 시작'])


def test_source_to_theme_company_evidence_search_period_and_standard_output(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['scores']['distinct_economic_events']==3
 assert theme['entity_ids']==['가상전자','미래장비','새빛소재']
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 for actor,market in [('가상전자','일본'),('새빛소재','미국')]:
  c=next(c for c in data['CompanyCandidates'] if c['entity_id']==actor)
  basis,=c['inclusion_basis'];assert basis['market_entry']['market_name']==market and market+' 시장 진출' in basis['reason']
  assert not c['verified_real_transaction'] and not c['verified_real_benefit'] and not c['benefit_paths']
  assert any('실제 판매·매출·수혜' in s for s in c['uncertainties'])
  item,=company_evidence(theme,actor,**args)['items']
  assert item['status']=='READY' and market+' 시장 진출' in item['excerpt']
 assert store.search(query='일본',as_of=args['as_of'],now=args['now'])==[theme]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert {r['supporting_source']['market_entry']['market_name'] for r in diff['events']['added'] if r['supporting_source']['action']=='MARKET_ENTRY'}=={'일본','미국'}
 assert store.search(as_of=at,now=args['now'])==[first]
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_other_causes_scopes_do_not_merge_despite_same_market(tmp_path):
 titles=[TITLE,'새빛소재, '+CAUSE+' 미국 시장 진출','미래장비, '+CAUSE+' 생산 시작',
  TITLE.replace('가상전자','다른전자').replace('AI 서버용','스마트폰용'),
  TITLE.replace('가상전자','기타소재').replace(CAUSE,POLICY)]
 rows=[claim(t,i) for i,t in enumerate(titles)];at=T+timedelta(hours=6)
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=at)
 assert len(themes)==3 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,3]
 assert next(t for t in themes if len(t['entity_ids'])==3)['status']=='EMERGING'
 raw=build_theme_bundle(themes,decision_at=at,now=at,include_company_candidates=True)
 assert len(read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=at,now=at)['CompanyCandidates'])==5


def test_same_document_two_markets_preserve_two_new_action_ids():
 text=TITLE+'. '+TITLE.replace('일본','미국')
 changes=extract_economic_changes(text);assert len(changes)==2
 events=[economic_observation(c,origin_reference='https://example.org/1',source_url='https://example.org/1',source_id='synthetic',source_available_at=T.isoformat()) for c in changes]
 assert len({e['event_id'] for e in events})==2
 assert {e['change']['market_entry']['market_name'] for e in events}=={'일본','미국'}


@pytest.mark.parametrize('phase,label',[('SOURCE_REPORTED','시장 진출 · 출처 보도'),('PLANNED','시장 진출 · 계획 단계')])
def test_js_market_label_and_search(phase,label):
 c=extract_economic_changes(TITLE)[0];c['phase']=phase
 result=present(dict(headline='합성 자료',economic_changes=[c]),['시장 진출','일본','신규 고객 확보'])
 assert result['label']==label and result['matches']==result['themes']==[True,True,False] and result['unchanged']


def test_saved_title_cannot_promote_plan_replace_market_or_actor(tmp_path):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=source_case(tmp_path,titles=[TITLE+' 계획','새빛소재, '+CAUSE+' 생산 시작'])
 for field,value in [('phase','SOURCE_REPORTED'),('entity_ids',['없는전자']),
   ('market_entry',extract_economic_changes(TITLE.replace('일본','미국'))[0]['market_entry'])]:
  forged=deepcopy(report);row=next(r for r in forged['results'] if '계획' in r['headline']);row['economic_changes'][0][field]=value
  with pytest.raises(SourceShareError):_validate_report(forged,args['now'])
 c=extract_economic_changes(TITLE)[0];del c['market_entry']
 with pytest.raises(SourceShareError):validate_change(c)


def test_period_http_and_company_source(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,*_=source_case(tmp_path,titles=[TITLE,'새빛소재, '+CAUSE+' 미국 시장 진출',
  '미래장비, '+CAUSE+' 생산 시작','다른전자, 스마트폰용 HBM 수요 증가로 일본 시장 진출',
  '기타소재, '+POLICY+' 일본 시장 진출'])
 themes=store.search(as_of=args['as_of'],now=args['now'])
 theme=next(t for t in themes if len(t['entity_ids'])==3)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
 server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 before=fingerprint(args['document_root']);url=f'http://127.0.0.1:{server.server_port}'
 try:
  day=args['now'].astimezone(dashboard.KST).date().isoformat()
  with urlopen(url+'/api/period?'+urlencode({'date':day})) as response:data=json.load(response)
  assert len(data['company_candidates'])==5 and len(data['themes'])==3
  assert next(t for t in data['themes'] if t['theme_id']==theme['theme_id'])['status']=='EMERGING'
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']==TITLE
  with urlopen(url+'/api/themes?'+urlencode({'q':'AI 서버'})) as response:found=json.load(response)
  assert found['ThemeCandidates']==[theme]
 finally:
  server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_licensed_body_market_entry(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 판매·매출은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args)
 assert report['economic_changes'][0]['market_entry']['market_name']=='일본'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_old_unsplit_scoped_investment_keeps_source_and_v3_bytes(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 text='가상전자는 '+CAUSE+' 일본 시장 진출했고 새빛소재는 HBM 신규 공장 투자 결정'
 info=setup(tmp_path,text);at=datetime.now(timezone.utc);report=run(info,now=at);row=report['results'][0]
 current=deepcopy(row['economic_changes']);old,=extract_economic_changes(text,include_market_entry=False)
 old['evidence_level']='REPORTED';row['economic_changes']=[old]
 assert old['entity_ids']==['가상전자','새빛소재'] and old['action']=='INVESTMENT' and old['demand_scope']['destination']=='AI 서버'
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');theme=store.ingest([observation(row,old)],now=at)[0]
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 for actor in old['entity_ids']:
  item,=company_evidence(theme,actor,reports_root=root,document_root=docs,as_of=at,now=at,
   feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
  assert item['status']=='READY' and item['excerpt']==text
 later=at+timedelta(seconds=1);store.ingest([observation(row,c) for c in current],now=later)
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)
