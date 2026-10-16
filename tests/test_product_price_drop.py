"""Price decline and reported/planned curtailment, with literal source evidence."""
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

CAUSE='HBM 제품 가격 하락으로'
TITLE='가상전자, '+CAUSE+' 생산 축소'

@pytest.mark.parametrize('tail,phase',[
 ('생산 축소','SOURCE_REPORTED'),('생산을 축소했다','SOURCE_REPORTED'),
 ('공급을 중단했다','SOURCE_REPORTED'),('감산을 실시했다','SOURCE_REPORTED'),
 ('감산에 착수했다','SOURCE_REPORTED'),('감산했다','SOURCE_REPORTED'),
 ('감산 결정','PLANNED'),('감산을 결정했다','PLANNED'),
 ('생산 축소 결정','PLANNED'),('생산 축소 계획','PLANNED'),
 ('생산 축소 예정','PLANNED'),('생산 축소 목표','PLANNED'),
 ('생산을 축소할 계획','PLANNED'),('감산한다','PLANNED'),
 ('감산을 추진했다','PLANNED'),('HBM 생산을 축소했다','SOURCE_REPORTED'),
])
def test_price_drop_action_phase_and_literal_proof(tail,phase):
 text='가상전자, '+CAUSE+' '+tail;c,=extract_economic_changes(text);validate_change(c)
 assert (c['economic_driver'],c['action'],c['phase'],c['entity_ids'])==('PRODUCT_PRICE_DECREASE','SUPPLY_REDUCTION',phase,['가상전자'])
 assert c['product_price_cause']==dict(product='HBM',change='DECREASE',source_expression=CAUSE,expression_sha256=sha256(CAUSE.encode()).hexdigest())
 assert c['source_paragraph_sha256']==sha256(text.encode()).hexdigest() and not c['verified_economic_effect']

@pytest.mark.parametrize('cause',[
 'HBM 가격 하락으로','HBM 가격 인하에 대응해','고대역폭 메모리 가격 급락으로',
 'AI 서버용 HBM 가격 하락으로',
])
def test_cause_first_and_explicit_end_use(cause):
 c,=extract_economic_changes(cause+' 가상전자는 생산을 축소했다');validate_change(c)
 assert c['economic_driver']=='PRODUCT_PRICE_DECREASE' and c['topic']=='HBM'
 if cause.startswith('AI 서버용'):assert c['demand_scope']['destination']=='AI 서버'

@pytest.mark.parametrize('text',[
 TITLE.replace(CAUSE,'HBM 주가 하락으로'),TITLE.replace(CAUSE,'HBM ETF 가격 하락으로'),
 TITLE.replace(CAUSE,'삼성전자 주식 가격 하락으로'),TITLE.replace(CAUSE,'HBM 수요 감소로'),
 TITLE.replace(CAUSE,'HBM 주문 감소로'),TITLE.replace(CAUSE,'HBM 가격 하락 예상으로'),
 TITLE.replace(CAUSE,'지난해 HBM 가격 하락으로'),TITLE+'하지 않았다',TITLE+'하지 못했다',
 TITLE+' 보도를 부인했다',TITLE+' 취소',TITLE+' 여부 확인',TITLE+'를 위한 기술 소개',
 TITLE+' 설명회',TITLE+' 전망',TITLE.replace('생산 축소','새빛소재는 생산 축소'),
 TITLE.replace('생산 축소','DRAM 생산 축소'),TITLE.replace('가상전자, ','그 회사는 '),
 TITLE.replace('가상전자, ',''),TITLE.replace(CAUSE,'HBM 및 DRAM 가격 하락으로'),
 TITLE.replace(CAUSE,'HBM 가격 하락과 DRAM 가격 하락으로'),
 TITLE.replace(CAUSE,'HBM 가격 하락으로 HBM 수요 감소로'),
 TITLE.replace(CAUSE,'HBM 가격 하락으로 미국 ‘첨단칩통제법’ HBM 수출 규제 완화로'),
 TITLE.replace('생산 축소','생산 시작'),TITLE.replace('생산 축소','감산 가능성'),
 '가상전자, HBM 제품 가격 하락',
])
def test_confusion_and_unrealized_claims_do_not_borrow_price_cause(text):
 assert not any(c['economic_driver']=='PRODUCT_PRICE_DECREASE' for c in extract_economic_changes(text))


def case(tmp_path):
 return source_case(tmp_path,titles=[TITLE,'새빛소재, HBM 가격 하락으로 감산 결정',
  '미래장비, HBM 가격 급락으로 공급을 중단했다'])


def mixed_titles():
 return [TITLE,'새빛소재, HBM 가격 하락으로 감산 결정','미래장비, HBM 가격 급락으로 공급을 중단했다',
 '수요전자, HBM 수요 감소로 생산 축소','기타소재, HBM 생산 축소',
 '상승장비, HBM 가격 상승으로 생산 시작','주문전자, HBM 주문 감소로 감산을 실시했다',
 '별도전자, AI 서버용 HBM 가격 하락으로 생산 축소','다른소재, 스마트폰용 HBM 가격 하락으로 생산 축소',
 '다른전자, DRAM 가격 하락으로 생산 축소']


def test_price_drop_to_theme_company_source_period_and_standard(tmp_path):
 theme,args,store,report,events,first,at=case(tmp_path)
 assert theme['status']=='EMERGING' and theme['economic_driver']=='PRODUCT_PRICE_DECREASE'
 assert '제품 가격 하락' in theme['provisional_name'] and theme['scores']['distinct_economic_events']==3
 before=fingerprint(tmp_path)
 raw=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
 for c in data['CompanyCandidates']:
  basis,=c['inclusion_basis'];assert basis['product_price_cause']['change']=='DECREASE' and '보도된 제품 가격 원인' in basis['reason']
  assert not c['verified_real_transaction'] and not c['verified_real_benefit']
  assert any('실제 감산 이행이나 매출·이익 감소 확인이 아님' in u for u in c['uncertainties'])
  item,=company_evidence(theme,c['entity_id'],**args)['items']
  assert item['status']=='READY' and '가격' in item['excerpt']
  if c['entity_id']=='새빛소재':assert basis['phase']=='PLANNED'
 assert store.search(query='제품 가격 하락',as_of=args['as_of'],now=args['now'])==[theme]
 diff,=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'])['ThemeChanges']
 assert all(r['supporting_source']['product_price_cause']['change']=='DECREASE' for r in diff['events']['added'])
 assert store.search(as_of=at,now=args['now'])==[first]
 assert report['source_fetch_calls']==report['new_ai_results']==0 and fingerprint(tmp_path)==before
 assert store.ingest(events,now=args['now'])==[]


def test_rise_demand_unspecified_and_other_products_scopes_separate(tmp_path):
 rows=[claim(t,i) for i,t in enumerate(mixed_titles())];at=T+timedelta(hours=11)
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=at)
 assert len(themes)==7 and sorted(t['scores']['company_breadth'] for t in themes)==[1,1,1,1,1,2,3]
 assert next(t for t in themes if len(t['entity_ids'])==3)['economic_driver']=='PRODUCT_PRICE_DECREASE'


def test_distinct_company_clauses_preserve_decision_phase():
 rows=extract_economic_changes('가상전자는 HBM 가격 하락으로 생산을 축소했고 새빛소재는 DRAM 가격 하락으로 감산 결정')
 assert [(c['topic'],c['entity_ids'],c['phase']) for c in rows]==[('HBM',['가상전자'],'SOURCE_REPORTED'),('DRAM',['새빛소재'],'PLANNED')]


@pytest.mark.parametrize('forgery',['direction','expression','driver','missing'])
def test_saved_price_drop_proof_is_bound_to_source(tmp_path,forgery):
 from newscatalystos.feed_analysis_delivery import _validate_report
 _,args,_,report,*_=case(tmp_path);forged=deepcopy(report);c=forged['results'][0]['economic_changes'][0]
 if forgery=='direction':c['product_price_cause']['change']='INCREASE'
 elif forgery=='expression':c['product_price_cause']=extract_economic_changes(TITLE.replace('하락','급락'))[0]['product_price_cause']
 elif forgery=='driver':c['economic_driver']='PRODUCT_PRICE_INCREASE'
 else:del c['product_price_cause']
 with pytest.raises(SourceShareError):_validate_report(forged,args['now'])


def test_old_supply_reduction_keeps_source_event_snapshot_and_bytes(tmp_path):
 from test_feed_analysis import setup,run
 from test_order_growth import observation
 from newscatalystos.feed_analysis import publish_feed_analysis
 from newscatalystos.feed_analysis_delivery import consume_feed_analysis
 title='가상전자, HBM 가격 하락으로 감산 결정'
 info=setup(tmp_path,title);at=datetime.now(timezone.utc);report=run(info,now=at);row=report['results'][0]
 current=deepcopy(row['economic_changes']);old,=extract_economic_changes(title,include_product_prices=False)
 old['evidence_level']='REPORTED';row['economic_changes']=[old]
 assert (old['economic_driver'],old['phase'])==('SUPPLY_CONTRACTION','SOURCE_REPORTED')
 root=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,root/'core/reports')
 assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
 store=ThemeStore(docs/'theme_history');theme,=store.ingest([observation(row,old)],now=at)
 raw=build_theme_bundle([theme],decision_at=at,now=at,include_company_candidates=True)
 item,=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
  feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])['items']
 assert item['status']=='READY' and item['excerpt']==title
 later=at+timedelta(seconds=1);store.ingest([observation(row,c) for c in current],now=later)
 assert store.search(as_of=at,now=later)==[theme]
 assert raw==build_theme_bundle([theme],decision_at=at,now=later,include_company_candidates=True)
 assert theme in store.search(as_of=later,now=later)


def test_price_drop_search_keeps_snapshot_unchanged():
 c=extract_economic_changes(TITLE)[0]
 result=present(dict(headline='합성 자료',economic_changes=[c]),['가격 하락','감산','주가 하락','가격 상승'])
 assert result['matches']==result['themes']==[True,True,False,False] and result['unchanged']


def test_licensed_body_price_drop_cause(tmp_path):
 from test_motir_document_analysis import case as body_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
 _,args=body_case(tmp_path,(TITLE+'. 실제 이익은 독립 확인되지 않았다. ')*3)
 report=analyze_motir_document(**args)
 assert report['economic_changes'][0]['product_price_cause']['change']=='DECREASE'
 path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
 assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


@pytest.mark.parametrize('tail,phase',[('생산 축소','SOURCE_REPORTED'),('감산 결정','PLANNED')])
def test_semantic_price_drop_literal_cause_and_phase_without_ai(tail,phase):
 from newscatalystos.news_semantics import parse_events,changes_from_events
 title='가상전자, '+CAUSE+' '+tail
 event=dict(actors=['가상전자'],action='SUPPLY_REDUCTION',phase=phase,topic='HBM',driver='PRODUCT_PRICE_DECREASE',quote=title,cause_quote=CAUSE)
 parsed=parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)
 change,=changes_from_events(parsed,sha256(title.encode()).hexdigest());validate_change(change)
 assert change['product_price_cause']['source_expression']==CAUSE and change['phase']==phase
 event['phase']='PLANNED' if phase=='SOURCE_REPORTED' else 'SOURCE_REPORTED'
 with pytest.raises(SourceShareError):parse_events(SimpleNamespace(claims=[json.dumps(event)]),title)


def test_period_http_price_drop_and_company_source(tmp_path,monkeypatch):
 import threading
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 from newscatalystos import company_evidence as evidence
 _,args,store,*_=source_case(tmp_path,titles=mixed_titles())
 themes=store.search(as_of=args['as_of'],now=args['now']);theme=next(t for t in themes if len(t['entity_ids'])==3)
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
  assert len(data['company_candidates'])==10 and len(data['themes'])==7
  assert next(t for t in data['themes'] if t['theme_id']==theme['theme_id'])['status']=='EMERGING'
  with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'새빛소재','as_of':data['as_of']})) as response:detail=json.load(response)
  assert detail['items'][0]['status']=='READY' and detail['items'][0]['excerpt']=='새빛소재, HBM 가격 하락으로 감산 결정'
  with urlopen(url+'/api/themes?'+urlencode({'q':'PRODUCT_PRICE_DECREASE'})) as response:found=json.load(response)
  assert len(found['ThemeCandidates'])==4 and theme in found['ThemeCandidates']
 finally:server.shutdown();server.server_close();thread.join(2)
 assert fingerprint(args['document_root'])==before
