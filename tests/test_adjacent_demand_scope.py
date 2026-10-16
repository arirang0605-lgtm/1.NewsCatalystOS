"""Synthetic literal end-use scopes across adjacent source sentences."""
from copy import deepcopy
from datetime import datetime,timedelta
from hashlib import sha256
import json,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.economic_changes import extract_economic_changes,parse_demand_scope
from newscatalystos.theme_emergence import ThemeStore,validate_change,economic_observation
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.company_timeline import company_timelines,select_timelines
from newscatalystos.feed_analysis_delivery import _source_changes
from newscatalystos.source_share import SourceShareError
from test_adjacent_demand import TEXT as UNSCOPED
from test_theme_emergence import T
from test_federated_news_search import fingerprint


def text(scope='AI 서버',actor='가상전자',product='HBM'):
 return f'{scope}용 {product} 수요가 증가했다. 이에 따라 {actor}는 {product} 생산능력을 확대했다.'


def observe(change,n):
 return economic_observation(change,origin_reference=f'https://example.org/{n}',source_url=f'https://example.org/{n}',source_id='synthetic',source_available_at=T.isoformat(),source_binding={'source_event_sha256':sha256(str(n).encode()).hexdigest(),'document_sha256':change['source_paragraph_sha256']})


@pytest.mark.parametrize('scope',['AI 서버','모바일','데이터센터','차량','AI  서버'])
def test_exact_scope_and_clause_spans_preserve_literal_source(scope):
 source=text(scope);row,=extract_economic_changes(source);validate_change(row)
 proof=row['adjacent_demand_cause'];scoped=row['demand_scope']
 assert row['economic_driver']=='DEMAND_EXPANSION'
 assert scoped['status']=='EXPLICIT' and scoped['destination']==scope
 assert scoped['source_expression']==source.split('. ')[0]+'.'
 assert scoped['expression_sha256']==sha256(scoped['source_expression'].encode()).hexdigest()
 assert parse_demand_scope(scoped['source_expression'])==('HBM','DEMAND_EXPANSION',scoped)
 start,end=proof['cause_span'];assert proof['source_expression'][start:end]==scoped['source_expression']
 assert row['source_paragraph_sha256']==sha256(source.encode()).hexdigest()


@pytest.mark.parametrize('scope',['AI 서버 및 모바일','AI 서버/모바일','복수 고객','관련 제품','서버와 모바일'])
def test_multiple_or_unclear_end_uses_are_unresolved_not_one_destination(tmp_path,scope):
 rows=[]
 for n,actor in enumerate(['가상전자','새빛소재']):
  row,=extract_economic_changes(text(scope,actor));validate_change(row)
  assert row['demand_scope']['status']=='UNRESOLVED' and row['demand_scope']['destination'] is None
  rows.append(observe(row,n))
 themes=ThemeStore(tmp_path/'themes').ingest(rows,now=T)
 assert len(themes)==2 and all(t['scores']['distinct_economic_events']==1 for t in themes)


def test_same_scope_groups_companies_other_scope_unspecified_and_unknown_stay_separate(tmp_path):
 store=ThemeStore(tmp_path/'theme_history');observations=[]
 inputs=[text(actor='가상전자'),text(actor='새빛소재'),text('모바일','빛결반도체'),UNSCOPED,text('AI 서버 및 모바일','달빛전자')]
 for n,source in enumerate(inputs):
  row,=extract_economic_changes(source);observations.append(observe(row,n))
 themes=store.ingest(observations,now=T)
 assert len(themes)==4
 shared=next(t for t in themes if len(t['entity_ids'])==2)
 assert shared['scores']['distinct_economic_events']==2 and shared['entity_ids']==['가상전자','새빛소재']
 disk=fingerprint(tmp_path);raw=build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True)
 cs=json.loads(raw)['CompanyCandidates'];ctx=company_search_context(themes,cs);comp=common_cause_comparisons(themes,cs)
 timeline=company_timelines(themes,cs,ctx,comp,as_of=T)
 selected=select_timelines(timeline,match_company_search(ctx,'가상전자'),'가상전자')['companies']
 assert len(selected)==2 # Same unresolved literal name across distinct theme contexts stays separate.
 company=next(c for c in selected if c['entries'][0]['cause'].get('demand_scope'))
 entry,=company['entries'];assert entry['cause']['demand_scope']['destination']=='AI 서버'
 assert entry['source_binding']==observations[0]['source_binding']
 assert all(not c['verified_real_benefit'] for c in timeline['companies'])
 assert raw==build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True) and fingerprint(tmp_path)==disk


@pytest.mark.parametrize('mutate',[
 lambda s:s.replace('. 이에','.\n이에'),lambda s:s.replace('HBM 생산','DRAM 생산'),
 lambda s:s.replace('가상전자','이회사'),lambda s:s.replace('가상전자','가상전자와 새빛소재'),
 lambda s:s.replace('증가했다','증가할 전망이다'),lambda s:s.replace('확대했다','확대할 계획이다'),
 lambda s:s.replace('AI 서버용','지난해 AI 서버용'),lambda s:s.replace('AI 서버용','수요 감소에 따른 AI 서버용'),
 lambda s:s.replace('AI 서버용','DRAM용'),lambda s:'"'+s,
])
def test_unrelated_future_negative_or_ambiguous_context_is_not_scoped_cause(mutate):
 rows=extract_economic_changes(mutate(text()))
 assert all('adjacent_demand_cause' not in r for r in rows)


@pytest.mark.parametrize('fault',['removed','borrowed','destination','hash'])
def test_scope_is_bound_to_exact_adjacent_cause_and_standard_output(tmp_path,fault):
 row,=extract_economic_changes(text())
 if fault=='removed':row.pop('demand_scope')
 elif fault=='borrowed':
  other,=extract_economic_changes(text('모바일'));row['demand_scope']=other['demand_scope']
 elif fault=='destination':row['demand_scope']['destination']='다른 수요처'
 else:row['demand_scope']['expression_sha256']='f'*64
 with pytest.raises(SourceShareError):validate_change(row)
 original,=extract_economic_changes(text());theme,=ThemeStore(tmp_path/'themes').ingest([observe(original,0)],now=T)
 ref=theme['source_refs'][0]
 if 'demand_scope' in row:ref['demand_scope']=row['demand_scope']
 else:ref.pop('demand_scope')
 with pytest.raises(SourceShareError):build_theme_bundle([theme],decision_at=T,now=T)


def test_pre_scope_and_unscoped_history_are_not_reclassified_or_counted_twice(tmp_path):
 new,=extract_economic_changes(text());old,=extract_economic_changes(text(),include_adjacent_scopes=False)
 assert old['economic_driver']=='CAPACITY_EXPANSION' and not old.get('adjacent_demand_cause')
 assert observe(new,0)['event_id']==observe(old,0)['event_id']
 assert _source_changes(text(),old)==[old] and _source_changes(text(),new)==[new]
 assert extract_economic_changes(UNSCOPED)==extract_economic_changes(UNSCOPED,include_adjacent_scopes=False)
 assert extract_economic_changes(text(),include_demand_scopes=False)==[old]
 store=ThemeStore(tmp_path/'theme_history');first,=store.ingest([observe(old,0)],now=T)
 raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 at=T+timedelta(hours=1);latest,=store.ingest([observe(new,0)],now=at)
 assert latest['theme_id']==first['theme_id'] and latest['scores']['distinct_economic_events']==1
 assert latest['economic_driver']=='CAPACITY_EXPANSION' and len(store.search(now=at))==1
 assert build_theme_bundle(store.search(as_of=T,now=at),decision_at=T,now=at,include_company_candidates=True)==raw


def test_normal_saved_feed_producer_consumer_scope_and_rebinding(tmp_path):
 from datetime import timezone
 from test_federated_news_search import setup_workspace,collect,GOV
 from test_new_source_adapter import registry
 from scripts import run_feed_analysis as producer
 from test_feed_analysis_delivery import read,republish
 source=setup_workspace(tmp_path,'source',registry())
 collect(source,registry(),GOV,[('a',text(),'https://gov.example.org/a')],at=datetime.now(timezone.utc))
 opts=producer.parser().parse_args(['--registry',str(source.registry_path),'--state',str(source.poll_state),'--inbox-root',str(source.inbox_root),'--analysis-root',str(tmp_path/'derived'),'--limit','10'])
 code,report=producer.evaluate(opts);assert code==0
 row=read(report)['results'][0]['economic_changes'][0]
 assert row['demand_scope']['destination']=='AI 서버'
 def tamper(data):data['results'][0]['economic_changes']=[extract_economic_changes(text('모바일'))[0]]
 with pytest.raises(SourceShareError):read(republish(report,tamper))


def test_ui_scope_is_displayed_with_no_customer_or_benefit_certification(tmp_path):
 row,=extract_economic_changes(text());themes=ThemeStore(tmp_path/'themes').ingest([observe(row,0)],now=T)
 cs=json.loads(build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True))['CompanyCandidates']
 comp=common_cause_comparisons(themes,cs)
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCommonCauseComparison(parent,input.themes[0],input.cs,input.comp);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 rendered=subprocess.check_output(['node','-e',code],input=json.dumps(dict(themes=themes,cs=cs,comp=comp)).encode()).decode()
 assert '명시 수요처: AI 서버' in rendered and '고객회사·계약·수혜 확인 아님' in rendered


def test_http_scoped_themes_search_pit_and_standard_bytes(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store=ThemeStore(tmp_path/'theme_history');observations=[]
 for n,scope in enumerate(['AI 서버','모바일']):observations.append(observe(extract_economic_changes(text(scope))[0],n))
 themes=store.ingest(observations,now=T)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return T.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  data=json.loads(fetch('/api/company-research',q='가상전자',as_of=T.isoformat()))
  entries=[e for c in data['company_timelines']['companies'] for e in c['entries']]
  assert {e['cause']['demand_scope']['destination'] for e in entries}=={'AI 서버','모바일'}
  assert len({e['theme_id'] for e in entries})==2
  period=json.loads(fetch('/api/period',date='2026-10-15',theme_sort='actions'))
  assert len(period['themes'])==2 and all(t['scores']['distinct_economic_events']==1 for t in period['themes'])
  assert fetch('/api/themes',as_of=T.isoformat(),company_candidates='1')==build_theme_bundle(store.search(now=T),decision_at=T,now=T,include_company_candidates=True)
  assert json.loads(fetch('/api/company-research',as_of=(T-timedelta(seconds=1)).isoformat()))['CompanyCandidates']==[]
 finally:server.shutdown();server.server_close();thread.join(2)


@pytest.mark.parametrize('new_first',[False,True])
def test_scope_metadata_variants_in_same_batch_cannot_duplicate_an_action(tmp_path,new_first):
 new,=extract_economic_changes(text());old,=extract_economic_changes(text(),include_adjacent_scopes=False)
 observations=[observe(new,0),observe(old,0)] if new_first else [observe(old,0),observe(new,0)]
 store=ThemeStore(tmp_path/'themes');theme,=store.ingest(observations,now=T)
 assert len(store.search(now=T))==1 and theme['scores']['distinct_economic_events']==1
 assert theme['event_ids']==[observations[0]['event_id']]


def test_first_sentence_company_is_not_an_end_use_or_borrowed_cause():
 source=text('가상전자, AI 서버',actor='새빛소재')
 assert all('adjacent_demand_cause' not in c for c in extract_economic_changes(source))


def test_publisher_scope_keeps_document_binding_and_source_named_official_id(tmp_path,monkeypatch):
 from test_publisher_theme_events import case,events
 source=text(actor='Alpha Devices')
 info=case(tmp_path/'source',monkeypatch,line='Alpha Devices는 Beta Systems와 HBM 공급 계약을 체결했다.\n'+source)
 observations=[r for r in events(info) if 'adjacent_demand_cause' in r['change']]
 row,=observations
 assert row['change']['demand_scope']['destination']=='AI 서버'
 assert row['source_binding']['document_sha256'] and row['change']['adjacent_demand_cause']['source_expression']==source
 assert row['company_mappings'][0]['entity_id']=='SEC_CIK:111111'
 theme,=ThemeStore(tmp_path/'themes').ingest(observations,now=info[-1])
 assert theme['entity_ids']==['SEC_CIK:111111']
 comp=common_cause_comparisons([theme])[theme['theme_id']]
 assert comp['rows'][0]['sources'][0]['cause']['demand_scope']['destination']=='AI 서버'
