"""Synthetic exact two-sentence demand -> capacity claims, no source invention."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json,subprocess
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation,validate_change
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.company_search import company_search_context,match_company_search
from newscatalystos.company_timeline import company_timelines,select_timelines
from newscatalystos.source_share import SourceShareError
from test_theme_emergence import T
from test_federated_news_search import fingerprint

TEXT='HBM 수요가 증가하고 있다. 이에 따라 가상전자는 HBM 생산능력을 확대했다.'


def observe(change,n=1):
 return economic_observation(change,origin_reference=f'https://example.org/{n}',source_url=f'https://example.org/{n}',source_id='synthetic',source_available_at=T.isoformat(),source_binding={'source_event_sha256':sha256(str(n).encode()).hexdigest(),'document_sha256':sha256(TEXT.encode()).hexdigest()})


@pytest.mark.parametrize('product',['HBM','DRAM','NAND'])
def test_literal_spans_and_shared_paragraph_source_binding(product):
 text=TEXT.replace('HBM',product);change,=extract_economic_changes(text)
 assert (change['topic'],change['economic_driver'],change['action'],change['phase'],change['entity_ids'])==(product,'DEMAND_EXPANSION','CAPACITY_ADDITION','SOURCE_REPORTED',['가상전자'])
 proof=change['adjacent_demand_cause']
 for prefix in ('cause','action'):
  start,end=proof[prefix+'_span'];expression=proof['source_expression'][start:end]
  assert expression==proof[prefix+'_expression'] and sha256(expression.encode()).hexdigest()==proof[prefix+'_sha256']
 assert proof['source_expression']==text and proof['paragraph_sha256']==change['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
 assert not change['verified_economic_effect'];validate_change(change)


@pytest.mark.parametrize('text',[
 TEXT.replace('. 이에','! 이에'),
 TEXT.replace('가상전자','새빛소재'),
])
def test_explicit_sentence_punctuation_and_company_names(text):
 row,=extract_economic_changes(text)
 assert row.get('adjacent_demand_cause') and row['economic_driver']=='DEMAND_EXPANSION'


@pytest.mark.parametrize('text',[
 TEXT.replace('. 이에','.\n이에'),TEXT.replace('이에 따라','한편'),
 TEXT.replace('가상전자','이회사'),TEXT.replace('가상전자','회사'),
 TEXT.replace('가상전자','가상전자와 새빛소재'),TEXT.replace('가상전자','가상전자와새빛전자'),
 TEXT.replace('HBM 생산','DRAM 생산'),TEXT.replace('증가하고 있다','증가할 전망이다'),
 TEXT.replace('증가하고 있다','증가하지 않았다'),TEXT.replace('증가하고 있다','지난해 증가했다'),
 TEXT.replace('확대했다','확대할 계획이다'),TEXT.replace('확대했다','확대하지 않았다'),
 TEXT.replace('확대했다','확대했다는 소문이다'),TEXT.replace('HBM 수요가','HBM과 DRAM 수요가'),
 'DRAM 수요가 감소했다. '+TEXT,
 TEXT+' HBM 수요가 감소했다.',TEXT.replace('수요가','주문과 수요가'),
 TEXT.replace('HBM 수요가 증가하고 있다.','“HBM 수요가 증가하고 있다.”'),
 TEXT.replace('이에 따라','이에 따라 다른 기업에 따르면'),
])
def test_ambiguous_unrelated_denied_historical_or_planned_context_cannot_supply_cause(text):
 rows=extract_economic_changes(text)
 assert all('adjacent_demand_cause' not in c for c in rows)


@pytest.mark.parametrize('field',['cause_sha256','action_span','source_actor','product','paragraph_sha256'])
def test_proof_tampering_rejected(field):
 row,=extract_economic_changes(TEXT)
 row['adjacent_demand_cause'][field]=[0,1] if field=='action_span' else 'invalid'
 with pytest.raises(SourceShareError):validate_change(row)


def test_existing_action_id_and_prior_pit_version_survive_later_cause(tmp_path):
 old,=extract_economic_changes(TEXT,include_adjacent_demand=False)
 new,=extract_economic_changes(TEXT)
 original=observe(old);fresh=observe(new)
 assert fresh['event_id']==original['event_id']
 store=ThemeStore(tmp_path/'theme_history');first,=store.ingest([original],now=T)
 raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
 at=T+timedelta(hours=1);latest,=store.ingest([fresh],now=at)
 assert latest['theme_id']==first['theme_id'] and latest['economic_driver']=='CAPACITY_EXPANSION'
 assert latest['scores']['distinct_economic_events']==1 and latest['first_detected_at']==T.isoformat()
 assert len(store.search(now=at))==1
 assert store.ingest([fresh],now=at)==[]
 assert build_theme_bundle(store.search(as_of=T,now=at),decision_at=T,now=at,include_company_candidates=True)==raw
 # Existing assignments remain in their original capacity theme; no silent migration.
 comparison=common_cause_comparisons([latest])[latest['theme_id']]
 assert comparison['excluded_incompatible_refs']==1


def test_new_companies_share_demand_theme_source_comparison_and_exact_search(tmp_path):
 store=ThemeStore(tmp_path/'theme_history');rows=[]
 for n,name in enumerate(['가상전자','새빛소재','빛결반도체'],1):
  c,=extract_economic_changes(TEXT.replace('가상전자',name));rows.append(observe(c,n))
 themes=store.ingest(rows,now=T);theme,=themes
 assert theme['economic_driver']=='DEMAND_EXPANSION' and theme['scores']['distinct_economic_events']==3
 disk=fingerprint(tmp_path);raw=build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True)
 cs=json.loads(raw)['CompanyCandidates'];ctx=company_search_context(themes,cs);comp=common_cause_comparisons(themes,cs)
 comparison=comp[theme['theme_id']]
 assert len(comparison['rows'])==3
 assert all(s['cause']['kind']=='adjacent_demand_cause' for r in comparison['rows'] for s in r['sources'])
 timeline=company_timelines(themes,cs,ctx,comp,as_of=T)
 selected=select_timelines(timeline,match_company_search(ctx,'가상전자'),'가상전자')
 company,=selected['companies'];entry,=company['entries']
 assert company['entity_id']=='가상전자' and entry['cause']['action_expression'] in TEXT
 assert entry['source_binding']==rows[0]['source_binding'] and entry['source_available_at']==T.isoformat()
 assert all(not s['verified_economic_effect'] for s in [r['change'] for r in rows])
 assert raw==build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True) and disk==fingerprint(tmp_path)


def test_single_sentence_and_saved_pre_extension_reader_unchanged():
 text='가상전자, HBM 수요 증가로 생산능력 확대'
 assert extract_economic_changes(text)==extract_economic_changes(text,include_adjacent_demand=False)
 from newscatalystos.feed_analysis_delivery import _source_changes
 old,=extract_economic_changes(TEXT,include_adjacent_demand=False);new,=extract_economic_changes(TEXT)
 assert _source_changes(TEXT,old)==[old] and _source_changes(TEXT,new)==[new]


def test_ui_separates_exact_cause_and_action_sentences(tmp_path):
 row,=extract_economic_changes(TEXT);themes=ThemeStore(tmp_path/'theme_history').ingest([observe(row)],now=T)
 cs=json.loads(build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True))['CompanyCandidates']
 comp=common_cause_comparisons(themes,cs)
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';renderCommonCauseComparison(parent,input.themes[0],input.cs,input.comp);',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 text=subprocess.check_output(['node','-e',code],input=json.dumps(dict(themes=themes,cs=cs,comp=comp)).encode()).decode()
 assert '인접 문장의 명시적 원인 연결' in text and '원인 문장: HBM 수요가 증가하고 있다.' in text
 assert '행동 문장: 이에 따라 가상전자는 HBM 생산능력을 확대했다.' in text


def test_publisher_document_names_and_pinned_ids_keep_adjacent_source_proof(tmp_path,monkeypatch):
 from test_publisher_theme_events import case,events
 text=TEXT.replace('가상전자','Alpha Devices')
 info=case(tmp_path/'source',monkeypatch,line='Alpha Devices는 Beta Systems와 HBM 공급 계약을 체결했다.\n'+text)
 observations=[r for r in events(info) if 'adjacent_demand_cause' in r['change']];row,=observations
 assert row['change']['economic_driver']=='DEMAND_EXPANSION'
 assert row['change']['entity_ids']==['Alpha Devices']
 assert row['company_mappings'][0]['entity_id']=='SEC_CIK:111111'
 assert row['source_binding']['document_sha256']
 theme,=ThemeStore(tmp_path/'theme_history').ingest(observations,now=info[-1])
 assert theme['entity_ids']==['SEC_CIK:111111']
 cs=json.loads(build_theme_bundle([theme],decision_at=info[-1],now=info[-1],include_company_candidates=True))['CompanyCandidates']
 comp=common_cause_comparisons([theme],cs)[theme['theme_id']]
 assert comp['rows'][0]['sources'][0]['cause']['source_expression']==text


def test_saved_feed_producer_consumer_and_false_source_binding(tmp_path):
 from datetime import datetime,timezone
 from test_federated_news_search import setup_workspace,collect,GOV
 from test_new_source_adapter import registry
 from scripts import run_feed_analysis as producer
 from test_feed_analysis_delivery import read,republish
 source=setup_workspace(tmp_path,'source',registry())
 collect(source,registry(),GOV,[('a',TEXT,'https://gov.example.org/a')],at=datetime.now(timezone.utc))
 opts=producer.parser().parse_args(['--registry',str(source.registry_path),'--state',str(source.poll_state),'--inbox-root',str(source.inbox_root),'--analysis-root',str(tmp_path/'derived'),'--limit','10'])
 code,report=producer.evaluate(opts);assert code==0
 result=read(report)['results'][0]
 assert result['economic_changes'][0]['adjacent_demand_cause']['source_expression']==TEXT
 def tamper(data):
  row=data['results'][0]
  # A valid proof for another literal company must still fail source rebinding.
  other,=extract_economic_changes(TEXT.replace('가상전자','새빛소재'))
  row['economic_changes']=[other]
 bad=republish(report,tamper)
 with pytest.raises(SourceShareError):read(bad)


def test_http_demand_theme_and_source_proofs_keep_past_and_standard_bytes(tmp_path,monkeypatch):
 import threading
 from datetime import datetime
 from urllib.request import urlopen
 from urllib.parse import urlencode
 from scripts import open_research_dashboard as dashboard
 row,=extract_economic_changes(TEXT);store=ThemeStore(tmp_path/'theme_history');themes=store.ingest([observe(row)],now=T)
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
  entry=data['company_timelines']['companies'][0]['entries'][0]
  assert entry['economic_driver']=='DEMAND_EXPANSION' and entry['cause']['kind']=='adjacent_demand_cause'
  assert entry['cause']['source_expression']==TEXT
  period=json.loads(fetch('/api/period',date='2026-10-15',theme_sort='actions'))
  assert period['themes'][0]['economic_driver']=='DEMAND_EXPANSION'
  assert period['theme_order']['entries'][themes[0]['theme_id']]['independent_actions_added']==1
  assert fetch('/api/themes',as_of=T.isoformat(),company_candidates='1')==build_theme_bundle(themes,decision_at=T,now=T,include_company_candidates=True)
  old=json.loads(fetch('/api/company-research',as_of=(T-timedelta(seconds=1)).isoformat()))
  assert old['CompanyCandidates']==[]
 finally:server.shutdown();server.server_close();thread.join(2)


def test_directory_named_actor_preserves_legacy_identity_without_erasing_name():
 text=TEXT.replace('가상전자','Alpha Devices')
 new,=extract_economic_changes(text,company_names=['Alpha Devices'])
 old,=extract_economic_changes(text,company_names=['Alpha Devices'],include_adjacent_demand=False)
 assert new['entity_ids']==['Alpha Devices'] and new.get('original_entity_ids')==old.get('original_entity_ids')
 validate_change(new)
 assert observe(new)['event_id']==observe(old)['event_id']


def test_standard_delivery_rejects_tampered_adjacent_source_spans(tmp_path):
 row,=extract_economic_changes(TEXT)
 theme,=ThemeStore(tmp_path/'theme_history').ingest([observe(row)],now=T)
 theme['source_refs'][0]['adjacent_demand_cause']['action_sha256']='f'*64
 with pytest.raises(SourceShareError):build_theme_bundle([theme],decision_at=T,now=T)
