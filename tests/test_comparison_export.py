"""Synthetic pinned delivery and consumer integrity; not external integration."""
from datetime import datetime,timedelta
from hashlib import sha256
import json,os,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen
import pytest
from newscatalystos.comparison_export import query_comparison_export,read_comparison_export,publish_comparison_export,read_comparison_file
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import _bytes
from newscatalystos.standard_delivery import build_theme_bundle
from test_cross_product_demand import case,T,END
from test_cross_product_period import run,LATER
from test_adjacent_demand_scope import text,observe
from newscatalystos.economic_changes import extract_economic_changes
from test_federated_news_search import fingerprint


def export(store,**kw):return query_comparison_export(store,as_of=kw.pop('as_of',END),now=kw.pop('now',END),identity_root=None,**kw)

def test_deterministic_period_export_preserves_canonical_and_old_query(tmp_path):
 store,themes,*_=case(tmp_path);disk=fingerprint(tmp_path)
 standard=build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)
 raw=export(store,since=END,activity='changed');value=read_comparison_export(raw,sha256(raw).hexdigest(),decision_at=END,now=END)
 expected,selected,_=run(store)
 assert set(value['product_comparisons'])=={t['theme_id'] for t in selected}
 assert value['comparison']==expected and len(value['selected_snapshots'])==len(selected)==1
 assert value['comparison']['groups'][0]['period_change']['formed_in_period']
 assert raw==export(store,since=END,activity='changed') and disk==fingerprint(tmp_path)
 row,=extract_economic_changes(text(actor='빛결반도체',product='NAND'));store.ingest([observe(row,10)],now=LATER)
 assert raw==export(store,since=END,activity='changed',now=LATER)
 assert standard==build_theme_bundle(store.search(as_of=END,now=LATER),decision_at=END,now=LATER,include_company_candidates=True)

@pytest.mark.parametrize('query,groups',[('가상전자',1),('AI 서버',1),('무관',0)])
def test_search_pins_conditions_and_related_products(tmp_path,query,groups):
 store,*_=case(tmp_path,actors=('동명전자','동명전자') if query=='AI 서버' else ('가상전자','새빛소재'))
 value=json.loads(export(store,query=query));assert value['query']['q']==query
 assert len(value['comparison']['groups'])==groups
 if groups:
  group=value['comparison']['groups'][0];assert len(group['products'])==2 and group['unresolved_company_contexts']==2
  assert not group['verified_real_transaction'] and not group['verified_real_benefit']

def test_missing_baseline_retains_current(tmp_path,monkeypatch):
 store,*_=case(tmp_path)
 def broken(*a,**k):raise OSError('synthetic unavailable baseline')
 monkeypatch.setattr(store,'period_versions',broken)
 result=json.loads(export(store,since=END))['comparison']
 assert result['period_status']=='UNAVAILABLE' and len(result['groups'])==1

@pytest.mark.parametrize('fault',['sha','future','reverse','source','noncanonical','duplicate','schema','product_pin'])
def test_consumer_rejects_tampering_future_and_invalid_envelopes(tmp_path,fault):
 store,*_=case(tmp_path);raw=export(store);v=json.loads(raw)
 if fault=='future':v['query']['as_of']=LATER.isoformat()
 elif fault=='reverse':v['query']['since']=LATER.isoformat()
 elif fault=='source':v['comparison']['groups'][0]['products'][0]['actions'][0]['sources'][0]['recorded_at']=LATER.isoformat()
 elif fault=='schema':v['schema']='wrong'
 elif fault=='product_pin':next(iter(v['product_comparisons'].values()))['theme_snapshot_sha256']='f'*64
 if fault not in {'sha','noncanonical','duplicate'}:raw=_bytes(v)
 if fault=='noncanonical':raw=json.dumps(v).encode()
 if fault=='duplicate':raw=raw[:-1]+b',"orders_enabled":false}'
 digest='0'*64 if fault=='sha' else sha256(raw).hexdigest()
 with pytest.raises(SourceShareError):read_comparison_export(raw,digest,decision_at=END,now=END)

def test_private_atomic_idempotent_publication_and_independent_consumer(tmp_path):
 store,*_=case(tmp_path);raw=export(store);root=tmp_path/'exports'
 receipt=publish_comparison_export(raw,root,now=END)
 assert receipt==publish_comparison_export(raw,root,now=END)
 path=next(root.iterdir());assert path.stat().st_mode&0o777==0o600 and root.stat().st_mode&0o777==0o700
 assert len(list(root.iterdir()))==1
 assert read_comparison_file(path,root,receipt['sha256'],decision_at=END,now=END)==json.loads(raw)
 path.unlink();path.symlink_to(tmp_path/'outside')
 with pytest.raises((SourceShareError,OSError)):publish_comparison_export(raw,root,now=END)
 assert not list(root.glob('*.tmp'))

def test_cli_comparison_and_existing_standard_bytes(tmp_path):
 store,themes,*_=case(tmp_path);root=tmp_path/'theme_history'
 args=['python3','scripts/search_themes.py','--root',str(root),'--as-of',END.isoformat()]
 env={**os.environ,'PYTHONPATH':'src'}
 raw=subprocess.check_output(args+['--comparison'],env=env)
 assert raw==export(store)
 standard=subprocess.check_output(args+['--company-candidates'],env=env)
 assert standard==build_theme_bundle(themes,decision_at=END,now=END,include_company_candidates=True)

def test_http_screen_and_export_use_identical_pinned_result(tmp_path,monkeypatch):
 from scripts import open_research_dashboard as dashboard
 store,*_=case(tmp_path)
 class Clock(datetime):
  @classmethod
  def now(cls,tz=None):return END.astimezone(tz)
 monkeypatch.setattr(dashboard,'datetime',Clock)
 server=dashboard.DashboardServer(0,tmp_path/'reports',tmp_path/'notes',tmp_path)
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 def get(route,**kw):
  with urlopen(f'http://127.0.0.1:{server.server_port}'+route+'?'+urlencode(kw)) as r:return r.read(),r.headers
 try:
  for route,kw in [('/api/company-research',dict(q='가상전자',as_of=END.isoformat(),since=END.isoformat(),activity='changed')),('/api/period',dict(date='2026-10-15',theme_activity='all'))]:
   data=json.loads(get(route,**kw)[0]);pin=data['comparison_export'];q={k:v for k,v in pin['query'].items() if v is not None}
   raw,headers=get('/api/comparison-export',**q)
   assert sha256(raw).hexdigest()==headers['X-Content-SHA256']==pin['sha256']
   assert json.loads(raw)['comparison']==data['cross_product_demand']
   for tid,product in data['common_cause_comparisons'].items():assert json.loads(raw)['product_comparisons'][tid]==product
 finally:server.shutdown();server.server_close();thread.join(2)

def test_dashboard_download_uses_loaded_time_and_current_search():
 code="""const fs=require('node:fs'),vm=require('node:vm');let output;
 const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
 vm.runInNewContext(code+';output(comparisonExportURL({as_of:"fixed",since:"start",activity:"changed"}," 새빛소재 "));',{URLSearchParams,output:x=>output=x});process.stdout.write(output);"""
 result=subprocess.check_output(['node','-e',code]).decode()
 from urllib.parse import parse_qs,urlsplit
 assert parse_qs(urlsplit(result).query)=={'as_of':['fixed'],'since':['start'],'activity':['changed'],'q':['새빛소재']}

@pytest.mark.parametrize('polarity',['RETRACT','CONTRADICT'])
def test_source_amount_and_removed_or_conflicting_context_survive_export(tmp_path,polarity):
 from test_adjacent_contract_amount import text as contract
 from newscatalystos.theme_emergence import ThemeStore,economic_observation
 store=ThemeStore(tmp_path/'theme_history');observations=[]
 for i,(product,actor) in enumerate([('HBM','가상전자'),('DRAM','새빛소재')]):
  row,=extract_economic_changes(contract(product=product,actor=actor));observations.append(observe(row,i))
 store.ingest(observations,now=T)
 first=export(store,as_of=T,now=T)
 for p in json.loads(first)['comparison']['groups'][0]['products']:
  amount=p['actions'][0]['sources'][0]['cause']['contract_amount']
  assert amount['source_expression']=='3000억원' and not amount['verified_revenue']
 base=observations[0]
 negative=economic_observation(base['change'],origin_reference='https://example.org/correction',source_url='https://example.org/correction',source_id='synthetic',source_available_at=END.isoformat(),polarity=polarity,supersedes_event_id=base['event_id'])
 store.ingest([negative],now=END)
 v=json.loads(export(store,since=END))['comparison'];group,=v['groups']
 if polarity=='RETRACT':
  assert group['status']=='PERIOD_CONTEXT_ONLY' and group['period_change']['removed_product_codes']==['HBM']
 else:assert any(p['counterevidence'] for p in group['products'])
 assert first==export(store,as_of=T,now=END)

def test_browser_download_preserves_received_bytes_and_preview(tmp_path):
 store,*_=case(tmp_path);raw=export(store)
 code='''const fs=require('node:fs'),vm=require('node:vm'),webcrypto=require('node:crypto').webcrypto;
 const bytes=fs.readFileSync(0),elements={};let saved;
 class Element{constructor(){this.children=[];this.value="가상전자"}append(...a){this.children.push(...a)}replaceChildren(...a){this.children=a}click(){saved=this.download}remove(){}}
 for(const id of ["comparison-export","comparison-export-status","comparison-export-preview","item-filter"])elements[id]=new Element();
 const document={getElementById:id=>elements[id],createElement:()=>new Element(),body:new Element()};
 const code=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
 const hash=require('node:crypto').createHash('sha256').update(bytes).digest('hex');let blob;
 const context={document,URLSearchParams,crypto:webcrypto,TextDecoder,Blob,URL:{createObjectURL:b=>{blob=b;return 'local'},revokeObjectURL:()=>{}},fetch:async()=>({ok:true,arrayBuffer:async()=>Uint8Array.from(bytes).buffer,headers:{get:()=>hash}})};
 vm.runInNewContext(code+';currentData={comparison_export:{query:{as_of:"fixed",activity:"all"}}};downloadComparison()',context).then(async()=>{if(Buffer.compare(Buffer.from(await blob.arrayBuffer()),bytes))throw Error('bytes changed');process.stdout.write(JSON.stringify({saved,preview:elements['comparison-export-preview'],status:elements['comparison-export-status'].textContent}))});'''
 result=json.loads(subprocess.check_output(['node','-e',code],input=raw))
 assert result['saved']=='comparison_export_'+sha256(raw).hexdigest()+'.json'
 assert '내보낸 비교 결과' in json.dumps(result,ensure_ascii=False) and 'HBM' in json.dumps(result)
