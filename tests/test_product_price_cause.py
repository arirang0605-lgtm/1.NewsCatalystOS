"""Synthetic product-price causes, never stock-price or profit confirmation."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
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

CAUSE='HBM 제품 가격 상승으로'
TITLE='가상전자, '+CAUSE+' 생산 시작'

@pytest.mark.parametrize('tail,action,phase',[
 ('생산 시작','PRODUCTION_START','SOURCE_REPORTED'),
 ('생산능력 확대','CAPACITY_ADDITION','SOURCE_REPORTED'),
 ('신규 공장 투자 결정','INVESTMENT','SOURCE_REPORTED'),
 ('투자 집행','INVESTMENT_EXECUTION','SOURCE_REPORTED'),
 ('공급계약 체결','CONTRACT','SOURCE_REPORTED'),
 ('신규 고객 확보','CUSTOMER_ACQUISITION','SOURCE_REPORTED'),
 ('기존 고객에 납품 시작','DELIVERY_START','SOURCE_REPORTED'),
 ('일본 시장 진출','MARKET_ENTRY','SOURCE_REPORTED'),
 ('생산 시작 계획','PRODUCTION_START','PLANNED'),
 ('신규 공장 투자 결정 예정','INVESTMENT','PLANNED'),
 ('생산 시작 목표','PRODUCTION_START','PLANNED'),
 ('생산 시작한다','PRODUCTION_START','PLANNED'),
])
def test_explicit_price_action_phase_actor_proof(tail,action,phase):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['economic_driver'],c['action'],c['phase'],c['entity_ids'])==('PRODUCT_PRICE_INCREASE',action,phase,['가상전자'])
 assert c['product_price_cause']==dict(product='HBM',change='INCREASE',source_expression=CAUSE,expression_sha256=sha256(CAUSE.encode()).hexdigest())
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']

@pytest.mark.parametrize('cause',[
 'HBM 가격 상승으로','HBM 가격이 상승에 따라','HBM 가격 인상에 대응해',
 '고대역폭 메모리 가격 급등으로','AI 서버용 HBM 가격 상승으로',
])
def test_price_spelling_scope_and_cause_first(cause):
 c,=extract_economic_changes(cause+' 가상전자는 생산 시작');validate_change(c)
 assert c['economic_driver']=='PRODUCT_PRICE_INCREASE' and c['topic']=='HBM'
 if cause.startswith('AI 서버용'):assert c['demand_scope']['destination']=='AI 서버'

@pytest.mark.parametrize('text',[
 TITLE.replace(CAUSE,'HBM 주가 상승으로'),TITLE.replace(CAUSE,'HBM ETF 가격 상승으로'),
 TITLE.replace(CAUSE,'삼성전자 주식 가격 상승으로'),TITLE.replace(CAUSE,'HBM 수요 증가로'),
 TITLE.replace(CAUSE,'HBM 가격 상승 예상으로'),TITLE.replace(CAUSE,'지난해 HBM 가격 상승으로'),
 TITLE+'하지 않았다',TITLE+'하지 못했다',TITLE+' 보도를 부인했다',TITLE+' 취소',
 TITLE+' 여부 확인',TITLE+'을 위한 기술 소개',TITLE+' 설명회',TITLE+' 전망',
 TITLE.replace('생산 시작','새빛소재는 생산 시작'),TITLE.replace('생산 시작','DRAM 생산 시작'),
 TITLE.replace('가상전자, ','그 회사는 '),TITLE.replace('가상전자, ',''),
 TITLE.replace(CAUSE,'HBM 및 DRAM 가격 상승으로'),
 TITLE.replace(CAUSE,'HBM 가격 상승과 DRAM 가격 상승으로'),
 TITLE.replace(CAUSE,'HBM 가격 상승으로 HBM 수요 증가로'),
 TITLE.replace(CAUSE,'HBM 가격 상승으로 미국 ‘첨단칩통제법’ HBM 수출 규제 완화로'),
 '가상전자, HBM 제품 가격 상승',
])
def test_no_forecast_denial_stock_price_or_borrowed_cause(text):
 assert not any(c['economic_driver']=='PRODUCT_PRICE_INCREASE' for c in extract_economic_changes(text))


def case(tmp_path):
 return source_case(tmp_path,titles=[TITLE,'새빛소재, HBM 가격 상승으로 신규 공장 투자 결정',
  '미래장비, '+CAUSE+' 일본 시장 진출'])


def test_price_cause_to_theme_sources_search_period_and_bundle(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['economic_driver']=='PRODUCT_PRICE_INCREASE'
 assert '제품 가격 상승' in theme['provisional_name'] and theme['scores']['distinct_economic_events']==3
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 for c in data['CompanyCandidates']:
  basis,=c['inclusion_basis'];assert basis['product_price_cause']['product']=='HBM' and '보도된 제품 가격 원인' in basis['reason']
  assert not c['verified_real_transaction'] and not c['verified_real_benefit']
  assert any('판매량·이익·실제 수혜' in u for u in c['uncertainties'])
  item,=company_evidence(theme,c['entity_id'],**args)['items']
  assert item['status']=='READY' and '가격 상승' in item['excerpt']
 assert store.search(query='제품 가격 상승',as_of=args['as_of'],now=args['now'])==[theme]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert all(r['supporting_source']['product_price_cause']['product']=='HBM' for r in diff['events']['added'])
 assert store.search(as_of=at,now=args['now'])==[first]
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def mixed_titles():
 return [TITLE,'새빛소재, HBM 가격 상승으로 신규 공장 투자 결정','미래장비, '+CAUSE+' 생산능력 확대',
 '수요전자, HBM 수요 증가로 생산 시작','기타소재, HBM 생산 시작',
 '정책장비, 미국 ‘첨단칩통제법’ HBM 수출 규제 완화로 생산 시작',
 '별도전자, AI 서버용 HBM 가격 상승으로 생산 시작','다른소재, 스마트폰용 HBM 가격 상승으로 생산 시작']


def test_demand_policy_unspecified_and_end_use_scopes_separate(tmp_path):
 rows=[claim(t,i) for i,t in enumerate(mixed_titles())];at=T+timedelta(hours=9)
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=at)
 assert len(themes)==6 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,1,3]
 assert next(t for t in themes if len(t['entity_ids'])==3)['economic_driver']=='PRODUCT_PRICE_INCREASE'


def test_price_parallel_and_distinct_company_clauses():
 rows=extract_economic_changes(TITLE+' 및 생산능력 확대')
 assert [c['action'] for c in rows]==['PRODUCTION_START','CAPACITY_ADDITION']
 rows=extract_economic_changes(TITLE.replace('가상전자,','가상전자는')+'했고 새빛소재는 DRAM 가격 상승으로 신규 공장 투자 결정')
 assert [(c['topic'],c['entity_ids']) for c in rows]==[('HBM',['가상전자']),('DRAM',['새빛소재'])]


def test_saved_price_proof_cannot_be_forged(tmp_path):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=case(tmp_path)
 forged=deepcopy(report);c=forged['results'][0]['economic_changes'][0]
 c['product_price_cause']['expression_sha256']='0'*64
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])
 forged=deepcopy(report);c=forged['results'][0]['economic_changes'][0]
 c['product_price_cause']=extract_economic_changes(TITLE.replace('상승','급등'))[0]['product_price_cause']
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])
 c=extract_economic_changes(TITLE)[0];del c['product_price_cause']
 with pytest.raises(SourceShareError):validate_change(c)


def test_old_price_title_keeps_original_event_snapshot_source_and_bytes(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 info=setup(tmp_path,TITLE);at=datetime.now(timezone.utc);report=run(info,now=at);row=report['results'][0]
 current=deepcopy(row['economic_changes']);old,=extract_economic_changes(TITLE,include_product_prices=False)
 old['evidence_level']='REPORTED';row['economic_changes']=[old];assert old['economic_driver']=='CAPACITY_EXPANSION'
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');theme,=store.ingest([observation(row,old)],now=at)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 item,=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
  feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
 assert item['status']=='READY' and item['excerpt']==TITLE
 later=at+timedelta(seconds=1);store.ingest([observation(row,c) for c in current],now=later)
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)
 assert theme in store.search(as_of=later,now=later)


def test_product_price_search_keeps_snapshot_unchanged():
 c=extract_economic_changes(TITLE)[0]
 result=present(dict(headline='합성 자료',economic_changes=[c]),['가격 상승','주가 상승'])
 assert result['matches']==result['themes']==[True,False] and result['unchanged']


def test_licensed_body_price_cause(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 이익은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args)
 assert report['economic_changes'][0]['product_price_cause']['product']=='HBM'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


@pytest.mark.parametrize('source_topic',['HBM','고대역폭 메모리'])
def test_semantic_price_claim_retains_literal_proof_without_live_ai(source_topic):
 from types import SimpleNamespace
 from newscatalystos.news_semantics import parse_events,changes_from_events
 event=dict(actors=['가상전자'],action='PRODUCTION_START',phase='SOURCE_REPORTED',topic='HBM',driver='PRODUCT_PRICE_INCREASE',quote=TITLE,cause_quote=CAUSE)
 event['quote']=event['quote'].replace('HBM',source_topic);event['cause_quote']=event['cause_quote'].replace('HBM',source_topic);event['topic']=source_topic
 parsed=parse_events(SimpleNamespace(claims=[json.dumps(event)]),event['quote'])
 change,=changes_from_events(parsed,sha256(TITLE.encode()).hexdigest());validate_change(change)
 assert change['product_price_cause']['source_expression']==CAUSE.replace('HBM',source_topic)
 event['quote']=TITLE.replace(CAUSE,'HBM 주가 상승으로');event['cause_quote']='HBM 주가 상승으로'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),event['quote'])

import threading
from urllib.request import urlopen
from urllib.parse import urlencode

def test_period_http_price_cause_and_company_source(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,*_=source_case(tmp_path,titles=mixed_titles())
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
  assert len(data['company_candidates'])==8 and len(data['themes'])==6
  assert next(t for t in data['themes'] if t['theme_id']==theme['theme_id'])['status']=='EMERGING'
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']==TITLE
  with urlopen(url+'/api/themes?'+urlencode({'q':'PRODUCT_PRICE_INCREASE'})) as response:found=json.load(response)
  assert len(found['ThemeCandidates'])==3 and theme in found['ThemeCandidates']
 finally:
  server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before


def test_pre_driver_source_refs_keep_standard_bytes_readable(tmp_path):
 row=claim('가상전자, HBM 생산 시작',0)
 theme,=ThemeStore(tmp_path/'themes').ingest([row],now=T)
 for ref in theme['source_refs']:ref.pop('economic_driver',None)
 raw=build_theme_bundle([theme],decision_at=T,now=T,include_company_candidates=True)
 assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=T,now=T)['ThemeCandidates']==[theme]
 assert 'economic_driver' not in theme['source_refs'][0]
