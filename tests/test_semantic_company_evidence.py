"""Stored AI quotes must match original rights, bytes, actor, event and PIT."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import pytest
from newscatalystos.company_evidence import company_evidence,_semantic_clause,_clause
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.standard_delivery import build_theme_bundle
from test_feed_analysis import setup,run
from test_ai_provider import config
from test_ai_gemini_transport import key,LocalOpener
from test_news_semantics import response
from test_order_growth import observation
from test_federated_news_search import fingerprint

QUOTE='가상소자, 시리즈 B 투자 유치'
TITLE=QUOTE+'... 기존 누적 투자 안내'
EVENT=dict(actors=['가상소자'],action='INVESTMENT',phase='SOURCE_REPORTED',topic='시리즈 B 투자 유치',driver='UNKNOWN',quote=QUOTE,cause_quote='')


def case(tmp_path,key):
 info=setup(tmp_path,TITLE);opener=LocalOpener(response(EVENT))
 report=run(info,semantic_ai=True,model=config('GEMINI'),allow_paid=True,opener=opener)
 assert opener.calls==1  # Synthetic transport, never a live request.
 row,=report['results'];c,=row['economic_changes'];assert c['extraction_method']=='AI_SOURCE_SPAN_MATCHED'
 reports=tmp_path/'reports';docs=tmp_path/'documents';path,pin=publish_feed_analysis(report,reports/'core/reports')
 at=datetime.now(timezone.utc)+timedelta(seconds=1);obs=observation(row,c)
 theme,=ThemeStore(docs/'theme_history').ingest([obs],now=at)
 args=dict(reports_root=reports,document_root=docs,feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)],as_of=at,now=at+timedelta(seconds=1))
 return theme,args,path,report,info


def test_saved_quote_returns_only_original_span_with_ai_limitation(tmp_path,key):
 theme,args,_,report,_=case(tmp_path,key);before=fingerprint(tmp_path)
 row,=report['results'];ref,=theme['source_refs'];change,=row['economic_changes']
 assert _clause(TITLE,change,'가상소자',ref) is None
 bundle=build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 item,=company_evidence(theme,'가상소자',**args)['items']
 assert item['status']=='READY' and item['excerpt']==QUOTE and item['excerpt']!=TITLE
 assert item['extraction_method']=='AI_SOURCE_SPAN_MATCHED' and '독립 사실 확인은 아닙니다' in item['reason']
 assert item['excerpt_sha256']==sha256(QUOTE.encode()).hexdigest()
 assert item['evidence_sha256']==sha256(TITLE.encode()).hexdigest()
 assert bundle==build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
 assert fingerprint(tmp_path)==before

@pytest.mark.parametrize('fault',['report_bytes','source_sha','missing_source','revoked','future','actor','event'])
def test_invalid_source_report_or_actor_never_exposes_quote(tmp_path,key,fault):
 theme,args,path,report,info=case(tmp_path,key)
 if fault=='report_bytes':path.write_bytes(path.read_bytes().replace(QUOTE.encode(),'조작된 원문'.encode()))
 if fault=='source_sha':theme['source_refs'][0]['evidence_sha256']='e'*64
 if fault=='missing_source':args['feeds']=[]
 if fault=='revoked':
  p=info[0].registry_path;data=json.loads(p.read_bytes())
  for provider in data['providers']:provider['approved']=False
  p.write_text(json.dumps(data))
 if fault=='future':args['as_of']=datetime.fromisoformat(report['results'][0]['analysis_available_at'])-timedelta(microseconds=1)
 if fault=='actor':
  theme['source_refs'][0]['entity_ids']=['다른기업'];theme['entity_ids']=['다른기업']
 if fault=='event':
  theme['source_refs'][0]['event_id']='f'*64;theme['event_ids']=['f'*64]
 entity='다른기업' if fault=='actor' else '가상소자'
 if fault=='future':
  # Keep a valid historical snapshot for the query; future report remains unavailable.
  theme['decision_at']=args['as_of'].isoformat();theme['first_detected_at']=args['as_of'].isoformat()
 items=company_evidence(theme,entity,**args)['items']
 assert all(i['status']!='READY' and i['excerpt'] is None for i in items)

@pytest.mark.parametrize('fault',['quote','actor','status','method','wrong_original'])
def test_semantic_fallback_requires_exact_validated_claim(tmp_path,key,fault):
 theme,_,_,report,_=case(tmp_path,key);row=deepcopy(report['results'][0]);c=deepcopy(row['economic_changes'][0]);text=TITLE
 if fault=='quote':row['semantic_analysis']['events'][0]['quote']='불일치 인용'
 if fault=='actor':row['semantic_analysis']['events'][0]['actors']=['다른기업']
 if fault=='status':row['semantic_analysis']['status']='UNSUPPORTED_PROPOSAL'
 if fault=='method':c.pop('extraction_method')
 if fault=='wrong_original':text='다른 저장 원문'
 assert _semantic_clause(text,row,c,'가상소자',theme['source_refs'][0],False) is None


def licensed_case(tmp_path,key):
 from test_motir_document_analysis import case as source_case
 from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis
 from newscatalystos.motir_article_binding import consume_motir_article_binding
 from newscatalystos.motir_document_collection import _registry_bytes
 paragraph=QUOTE+'. 세부 조건은 미확인이다.'
 source,opts=source_case(tmp_path,paragraph+'\n다른 기업의 무관한 사업 설명입니다.')
 report=analyze_motir_document(**opts,semantic_ai=True,analyze_existing=True,allow_paid=True,opener=LocalOpener(response(EVENT)))
 c,=report['economic_changes'];assert c['extraction_method']=='AI_SOURCE_SPAN_MATCHED'
 at=datetime.now(timezone.utc)+timedelta(seconds=1);docs=tmp_path/'documents'
 publish_motir_document_analysis(report,docs/('a'*64)/'reports')
 binding=consume_motir_article_binding(opts['binding_path'],opts['binding_sha256'],now=at)
 obs=economic_observation(c,origin_reference=report['source_url'],source_url=report['source_url'],source_id='motir-official-press',source_available_at=report['source_available_at'],source_binding={'source_event_sha256':binding['archive_version'],'document_sha256':report['document_sha256']})
 theme,=ThemeStore(docs/'theme_history').ingest([obs],now=at)
 registry=tmp_path/'article-registry.json';registry.write_bytes(_registry_bytes(source[1].providers[0]));registry.chmod(0o600)
 jobs=[{k:opts[k] for k in ('binding_path','binding_sha256','archive_root')}|{'article_registry':registry}]
 args=dict(reports_root=tmp_path/'absent',document_root=docs,jobs=jobs,as_of=at,now=at+timedelta(seconds=1))
 return theme,args,binding,paragraph


def test_licensed_semantic_quote_is_exact_and_not_whole_article(tmp_path,key):
 theme,args,_,paragraph=licensed_case(tmp_path,key);before=fingerprint(tmp_path)
 item,=company_evidence(theme,'가상소자',**args)['items']
 assert item['status']=='READY' and item['excerpt']==QUOTE and item['extraction_method']=='AI_SOURCE_SPAN_MATCHED'
 assert item['evidence_sha256']==sha256(paragraph.encode()).hexdigest()
 assert fingerprint(tmp_path)==before

@pytest.mark.parametrize('fault',['body_tamper','revoked','binding'])
def test_licensed_ai_quote_keeps_original_rights_and_integrity_gates(tmp_path,key,fault):
 theme,args,binding,_=licensed_case(tmp_path,key);job=args['jobs'][0]
 if fault=='body_tamper':
  p=job['archive_root']/binding['archive_version']/'payload.bin';p.write_bytes(p.read_bytes()+b'x')
 if fault=='revoked':
  p=job['article_registry'];data=json.loads(p.read_bytes());data['providers'][0]['approved']=False;p.write_text(json.dumps(data))
 if fault=='binding':theme['source_refs'][0]['source_binding']['document_sha256']='f'*64
 item,=company_evidence(theme,'가상소자',**args)['items']
 assert item['status']!='READY' and item['excerpt'] is None


def test_http_company_evidence_returns_labelled_stored_ai_quote(tmp_path,key,monkeypatch):
 import threading
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 from scripts.open_research_dashboard import DashboardServer
 from newscatalystos import company_evidence as module
 theme,args,*_=case(tmp_path,key)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return args['now'].astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 monkeypatch.setattr(module,'installed_sources',lambda base:(args['feeds'],[]))
 server=DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root']);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  query=urlencode({'theme_id':theme['theme_id'],'entity_id':'가상소자','as_of':args['as_of'].isoformat()})
  with urlopen(f'http://127.0.0.1:{server.server_port}/api/company-evidence?'+query) as response:data=json.load(response)
  item,=data['items'];assert item['status']=='READY' and item['excerpt']==QUOTE and item['extraction_method']=='AI_SOURCE_SPAN_MATCHED'
 finally:server.shutdown();server.server_close();thread.join(timeout=2)


def test_distinct_matching_quotes_are_not_arbitrarily_chosen(tmp_path,key):
 from test_ai_gemini_transport import packet
 text=QUOTE+'; '+QUOTE+' 확정 보도'
 other={**EVENT,'quote':QUOTE+' 확정 보도'}
 payload=packet(result={'summary':'합성 AI 해석','claims':[json.dumps(EVENT),json.dumps(other)],'uncertainties':['독립 확인 없음']})
 info=setup(tmp_path,text)
 row=run(info,semantic_ai=True,model=config('GEMINI'),allow_paid=True,opener=LocalOpener(payload))['results'][0]
 c=row['economic_changes'][0]
 assert c['extraction_method']=='AI_SOURCE_SPAN_MATCHED'
 assert _semantic_clause(text,row,c,'가상소자',{},False) is None
