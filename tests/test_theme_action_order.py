"""Synthetic discovery ordering from immutable period comparisons."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError
import pytest
from newscatalystos.theme_action_order import order_theme_actions
from newscatalystos.theme_changes import compare_themes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.common_cause_comparison import common_cause_comparisons
from newscatalystos.standard_delivery import build_theme_bundle
from test_theme_emergence import event,T
from test_service_realization import pair as service_pair
from test_investment_project_history import pair as investment_pair
from test_federated_news_search import fingerprint

START=T+timedelta(minutes=1)
A=T+timedelta(hours=1)
END=T+timedelta(hours=2)


def case(tmp_path):
 store=ThemeStore(tmp_path/'theme_history')
 originals=[event(1,topic='HBM'),event(10,topic='DRAM'),event(20,topic='NAND')]
 store.ingest(originals,now=T)
 store.ingest([event(2,topic='HBM'),event(3,topic='HBM')],now=A)
 reprint=deepcopy(originals[1]);reprint['source_url']='https://example.org/reprint'
 store.ingest([reprint],now=END)
 return store,originals


def ordered(store,*,since=START,as_of=END,mode='actions'):
 themes=store.search(as_of=as_of,now=END)
 changes=compare_themes(store,since=since,as_of=as_of,now=END)
 comparisons=common_cause_comparisons(themes)
 return order_theme_actions(themes,changes,comparisons,since=since,as_of=as_of,mode=mode)


def topic_order(rows):return [r['topic_aliases'][0] for r in rows]


def test_independent_actions_beat_newer_reprint_and_keep_zero_candidates(tmp_path):
 store,_=case(tmp_path);disk=fingerprint(tmp_path)
 themes=store.search(now=END);before=deepcopy(themes)
 canonical=build_theme_bundle(themes,decision_at=END,now=END)
 latest,meta=ordered(store,mode='latest');rows,meta=ordered(store)
 assert latest==themes and topic_order(rows)==['HBM','DRAM','NAND']
 assert meta['status']=='READY' and meta['criteria'][:3]==['PERIOD_EVIDENCE_AVAILABLE_DESC','INDEPENDENT_ACTIONS_ADDED_DESC','NEW_EVENT_PARTICIPANTS_DESC']
 h,d,n=[meta['entries'][r['theme_id']] for r in rows]
 assert (h['independent_actions_added'],h['new_event_participant_count'])==(2,2)
 assert len(h['action_group_ids'])==2 and h['new_participant_entity_ids']==['가상기업2','가상기업3']
 assert d['independent_actions_added']==n['independent_actions_added']==0
 assert themes==before and disk==fingerprint(tmp_path)
 assert build_theme_bundle(store.search(now=END),decision_at=END,now=END)==canonical


def test_equal_actions_use_new_participants_then_latest_and_stable_id(tmp_path):
 store=ThemeStore(tmp_path/'theme_history')
 store.ingest([event(1,topic='HBM',company='같은기업'),event(10,topic='DRAM')],now=T)
 store.ingest([event(2,topic='HBM',company='같은기업'),event(11,topic='DRAM')],now=A)
 rows,meta=ordered(store)
 assert topic_order(rows)==['DRAM','HBM']
 assert [meta['entries'][r['theme_id']]['independent_actions_added'] for r in rows]==[1,1]
 # With both periods empty, newest decision then ID resolves ties deterministically.
 rows,meta=ordered(store,since=END)
 assert rows==sorted(rows,key=lambda t:(t['decision_at'],t['theme_id']),reverse=True)
 assert all(e['independent_actions_added']==0 for e in meta['entries'].values())


@pytest.mark.parametrize('pair',[service_pair,investment_pair])
def test_same_project_followup_is_not_a_new_action(tmp_path,pair):
 plan,start=pair();store=ThemeStore(tmp_path/'theme_history')
 store.ingest([plan],now=T);store.ingest([start],now=END)
 rows,meta=ordered(store);entry=meta['entries'][rows[0]['theme_id']]
 assert entry['status']=='READY' and entry['independent_actions_added']==entry['new_event_participant_count']==0
 assert entry['action_group_ids']==[]


def test_identity_and_supply_only_changes_do_not_raise_discovery_order(tmp_path):
 from test_theme_supply_chain import setup,attach
 info,out,pub,store,_,first=setup(tmp_path/'supply')
 linked=info[-1]+timedelta(seconds=1);attach(store,out,pub,linked)
 themes=store.search(now=linked);changes=compare_themes(store,since=linked,as_of=linked,now=linked)
 rows,meta=order_theme_actions(themes,changes,common_cause_comparisons(themes),since=linked,as_of=linked,mode='actions')
 assert all(e['independent_actions_added']==e['new_event_participant_count']==0 for e in meta['entries'].values())
 store=ThemeStore(tmp_path/'identity');row=event(company='가상기업')
 row=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'event_id','change'}},source_binding={'source_event_sha256':'a'*64,'document_sha256':'b'*64})
 store.ingest([row],now=T)
 later=economic_observation(row['change'],**{k:v for k,v in row.items() if k not in {'event_id','change'}},company_mappings=[{'source_name':'가상기업','entity_id':'DART_CORP:12345678','evidence_sha256':'c'*64}])
 store.ingest([later],now=END)
 rows,meta=ordered(store)
 assert all(e['independent_actions_added']==e['new_event_participant_count']==0 for e in meta['entries'].values())


@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_new_action_order_keeps_exclusion_and_conflicting_state(tmp_path,polarity):
 store,originals=case(tmp_path)
 store.ingest([event(4,topic='HBM',polarity=polarity,target=originals[0]['event_id'])],now=END)
 rows,meta=ordered(store);h=next(t for t in rows if 'HBM' in t['topic_aliases']);entry=meta['entries'][h['theme_id']]
 assert entry['independent_actions_added']==2
 assert entry['independent_actions_removed']==(1 if polarity=='RETRACT' else 0)
 assert h['invalidated_event_ids'] if polarity=='RETRACT' else h['conflicting_event_ids']
 assert not meta['verified_real_benefit'] and not meta['verified_market_leader']


@pytest.mark.parametrize('fault',['period','snapshot','comparison','missing','count'])
def test_bad_or_missing_period_is_local_unknown_not_zero_or_other_snapshot(tmp_path,fault):
 store,_=case(tmp_path);themes=store.search(now=END)
 changes=compare_themes(store,since=START,as_of=END,now=END);comparisons=common_cause_comparisons(themes)
 tid=themes[0]['theme_id'];row=next(r for r in changes['ThemeChanges'] if r['theme_id']==tid)
 if fault=='period':changes['since']=T.isoformat()
 if fault=='snapshot':row['after']['snapshot_sha256']='f'*64
 if fault=='comparison':comparisons[tid]['theme_snapshot_sha256']='f'*64
 if fault=='missing':changes['ThemeChanges'].remove(row)
 if fault=='count':row['events']['independent_actions_added']+=1
 rows,meta=order_theme_actions(themes,changes,comparisons,since=START,as_of=END,mode='actions')
 assert len(rows)==3 and meta['entries'][tid]['status']=='UNAVAILABLE'
 assert meta['entries'][tid]['independent_actions_added'] is None
 assert meta['status']==('UNAVAILABLE' if fault=='period' else 'PARTIAL')
 if fault!='period':assert rows[-1]['theme_id']==tid


def test_old_query_does_not_use_future_changes_and_timezone_bounds_match(tmp_path):
 store,_=case(tmp_path);rows,meta=ordered(store,as_of=T,since=T)
 assert all(len(t['event_ids'])==1 for t in rows)
 assert all(e['independent_actions_added']==1 for e in meta['entries'].values())
 kst=timezone(timedelta(hours=9))
 assert ordered(store,since=START.astimezone(kst),as_of=END.astimezone(kst))==ordered(store)
 with pytest.raises(ValueError):ordered(store,mode='invented')


def test_ui_order_values_and_comparison_connect_to_new_action_sources(tmp_path):
 store,_=case(tmp_path);themes,meta=ordered(store);comparisons=common_cause_comparisons(themes)
 cs=json.loads(build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True))['CompanyCandidates']
 code='''const fs=require('node:fs'),vm=require('node:vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
class Element{constructor(tag){this.tag=tag;this.children=[]}append(...a){this.children.push(...a)}}
const document={createElement:t=>new Element(t)},parent=new Element('root');
const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
vm.runInNewContext(code+';for(const t of input.themes){renderThemeActionOrder(parent,input.order.entries[t.theme_id]);renderCommonCauseComparison(parent,t,input.cs,input.comparisons,input.order.entries[t.theme_id]);}',{input,document,parent});process.stdout.write(JSON.stringify(parent));'''
 text=subprocess.check_output(['node','-e',code],input=json.dumps(dict(themes=themes,order=meta,cs=cs,comparisons=comparisons)).encode()).decode()
 assert '선택 기간 독립 행동 추가 2개 · 제외 0개 · 새 행동의 신규 당사자 2개' in text
 assert '기간 내 새 독립 행동의 당사자 근거' in text and '공통 원인 · 기업별 행동·출처 비교' in text
 assert 'https://example.org/official/2' in text and '대장주 확정이 아닙니다.' in text


def test_http_order_and_filters_preserve_canonical_and_unavailable_cards(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,originals=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def fetch(route,**params):
  with urlopen(f'http://127.0.0.1:{server.server_port}{route}?'+urlencode(params)) as r:return r.read()
 try:
  # Day starts before the synthetic first observation: all three themes are new.
  latest=json.loads(fetch('/api/period',date='2026-10-15'))
  for activity in ('all','changed','new','updated'):
   params=dict(date='2026-10-15',theme_activity=activity)
   old=json.loads(fetch('/api/period',**params));data=json.loads(fetch('/api/period',theme_sort='actions',**params))
   assert sorted(data['themes'],key=lambda t:t['theme_id'])==sorted(old['themes'],key=lambda t:t['theme_id'])
   assert data['company_candidates']==old['company_candidates']
   assert data['theme_order']['mode']=='actions' and data['theme_order']['status']=='READY'
   if data['themes']:assert topic_order(data['themes'])[0]=='HBM'
  with pytest.raises(HTTPError) as exc:fetch('/api/period',date='2026-10-15',theme_sort='invented')
  assert exc.value.code==400
  raw=fetch('/api/themes',as_of=END.isoformat(),company_candidates='1')
  assert raw==build_theme_bundle(store.search(now=END),decision_at=END,now=END,include_company_candidates=True)
  future=json.loads(fetch('/api/period',date='2099-01-01',theme_activity='all',theme_sort='actions'))
  assert future['theme_order']['status']=='UNAVAILABLE' and len(future['themes'])==3
  def unavailable(*a,**k):raise OSError('synthetic comparison missing')
  monkeypatch.setattr(dashboard,'compare_themes',unavailable)
  failed=json.loads(fetch('/api/period',date='2026-10-15',theme_sort='actions'))
  assert failed['theme_status']=='READY' and failed['theme_order']['status']=='UNAVAILABLE'
  assert failed['themes']==latest['themes'] and all(v['independent_actions_added'] is None for v in failed['theme_order']['entries'].values())
 finally:server.shutdown();server.server_close();thread.join(2)
