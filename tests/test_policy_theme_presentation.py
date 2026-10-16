"""Read-only display projection from synthetic immutable theme snapshots."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,subprocess,threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest
from newscatalystos.theme_emergence import ThemeStore,theme_presentation,_bytes
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.company_evidence import company_evidence
from newscatalystos.theme_company_identity import filter_research
from test_feed_analysis import setup,run
from test_federated_news_search import collect,GOV,fingerprint
from test_new_source_adapter import NOW
from test_order_growth import observation
from test_policy_company_actions import CAUSE
from hashlib import sha256


def case(tmp_path):
    titles=[
        '가상전자, '+CAUSE+' 생산 시작',
        '새빛소재, '+CAUSE+' 생산능력 확대',
        '미래장비, '+CAUSE.replace('미국','일본')+' 생산 시작',
        '한빛전자, '+CAUSE.replace('수출','수입')+' 생산 시작',
        '솔빛전자, '+CAUSE.replace('완화','폐지')+' 생산 시작',
        '별빛전자, HBM 수출 규제 완화로 생산 시작',
        '누리전자, HBM 수요 증가로 생산 시작',
    ]
    info=setup(tmp_path,titles[0])
    collect(info[0],info[1],GOV,[(f'display-{i}',t,f'https://gov.example.org/display-{i}') for i,t in enumerate(titles[1:],1)],at=NOW+timedelta(hours=1))
    at=datetime.now(timezone.utc)+timedelta(seconds=1);report=run(info,now=at)
    root=tmp_path/'reports';docs=tmp_path/'documents'
    publish_feed_analysis(report,root/'core/reports')
    events=[observation(r,c) for r in report['results'] for c in r['economic_changes']]
    store=ThemeStore(docs/'theme_history')
    first_event=next(e for e in events if e['change']['entity_ids']==['가상전자'])
    first=store.ingest([first_event],now=at)[0]
    later=at+timedelta(seconds=1)
    store.ingest([e for e in events if e!=first_event],now=later)
    rows=store.search(now=later)
    args=dict(reports_root=root,document_root=docs,feeds=[dict(registry=info[0].registry_path,
        inbox=info[0].inbox_root,state=info[0].poll_state)],as_of=later,now=later+timedelta(seconds=1))
    return rows,args,store,first,at


def test_distinct_display_search_and_immutable_snapshots(tmp_path):
    rows,args,store,first,at=case(tmp_path)
    before=fingerprint(tmp_path);raw=_bytes(rows)
    displays=[theme_presentation(t) for t in rows]
    assert len(rows)==6 and len({d['name'] for d in displays})==6
    assert sum(t['scores']['company_breadth'] for t in rows)==7
    expected='HBM · 미국 · 첨단칩통제법 · 수출규제 완화 · 정책 기반 확대'
    selected=store.search(query=expected,as_of=args['as_of'],now=args['now'])
    assert len(selected)==1 and selected[0]['scores']['company_breadth']==2
    assert '미국' not in selected[0]['provisional_name']
    assert '일본' in next(d['name'] for d in displays if '일본' in d['name'])
    assert any('수입규제 완화' in d['name'] for d in displays)
    assert any('수출규제 폐지' in d['name'] for d in displays)
    assert any('관할 미확인 · 정책명 미확인' in d['name'] for d in displays)
    old=next(t for t in rows if t['economic_driver']=='DEMAND_EXPANSION')
    assert theme_presentation(old)['name']==old['provisional_name']
    assert store.search(as_of=at,now=args['now'])==[first]
    assert theme_presentation(first)['as_of']==first['decision_at']
    assert store.search(query=expected,as_of=at,now=args['now'])==[first]
    assert _bytes(rows)==raw and fingerprint(tmp_path)==before


def test_company_basis_and_canonical_delivery_are_unchanged(tmp_path):
    rows,args,store,first,at=case(tmp_path)
    before=fingerprint(tmp_path)
    raw=build_theme_bundle(rows,decision_at=args['as_of'],now=args['now'],include_company_candidates=True)
    for row in rows:theme_presentation(row)
    assert build_theme_bundle(rows,decision_at=args['as_of'],now=args['now'],include_company_candidates=True)==raw
    data=read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=args['as_of'],now=args['now'])
    target=next(t for t in rows if '미래장비' in t['entity_ids'])
    candidate=next(c for c in data['CompanyCandidates'] if c['entity_id']=='미래장비')
    assert '일본' in candidate['inclusion_basis'][0]['reason']
    assert not candidate['verified_real_benefit']
    item=company_evidence(target,'미래장비',**args)['items'][0]
    assert item['status']=='READY' and '일본' in item['excerpt']
    research={'CompanyCandidates':deepcopy(data['CompanyCandidates'])}
    filter_research(research,rows,theme_presentation(target)['name'])
    assert [c['entity_id'] for c in research['CompanyCandidates']]==['미래장비']
    assert fingerprint(tmp_path)==before


@pytest.mark.parametrize('fault',['inactive','invalidated','retracted','recorded_future','source_future'])
def test_display_does_not_borrow_ineligible_policy_refs(tmp_path,fault):
    rows,args,store,first,at=case(tmp_path)
    theme=deepcopy(first);ref=deepcopy(first['source_refs'][0])
    ref['policy_cause']=deepcopy(ref['policy_cause'])
    from newscatalystos.economic_changes import extract_economic_changes
    ref['policy_cause']=extract_economic_changes('가상전자, '+CAUSE.replace('미국','일본')+' 생산 시작')[0]['policy_cause']
    if fault=='inactive':ref['event_id']='0'*64
    if fault=='invalidated':
        ref['event_id']='0'*64;theme['event_ids'].append(ref['event_id']);theme['invalidated_event_ids'].append(ref['event_id'])
    if fault=='retracted':ref['polarity']='RETRACT'
    if fault=='recorded_future':ref['recorded_at']=args['now'].isoformat()
    if fault=='source_future':ref['source_available_at']=args['now'].isoformat()
    theme['source_refs'].append(ref)
    assert theme_presentation(theme)==theme_presentation(first)


def test_js_title_and_search_use_projection_without_mutating_theme(tmp_path):
    rows,args,*_=case(tmp_path)
    target=next(t for t in rows if '미래장비' in t['entity_ids'])
    display=theme_presentation(target)
    code="""
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
process.stdout.write(vm.runInNewContext(source+`;
const before=JSON.stringify(input);
JSON.stringify({title:themeTitle(input.theme,input.display),legacy:themeTitle(input.theme),
match:matchesTheme(input.theme,input.display.name.toLocaleLowerCase(),[],{},input.display),
other:matchesTheme(input.theme,'없는정책',[],{},input.display),unchanged:before===JSON.stringify(input)});`,{input}));
"""
    result=json.loads(subprocess.check_output(['node','-e',code],input=json.dumps({'theme':target,'display':display}).encode()))
    assert result==dict(title=display['name'],legacy=target['provisional_name'],match=True,other=False,unchanged=True)


def test_period_api_keeps_stored_names_and_returns_display_sidecar(tmp_path,monkeypatch):
    from scripts import open_research_dashboard as dashboard
    from newscatalystos import company_evidence as evidence
    rows,args,store,first,at=case(tmp_path)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return args['now'].astimezone(tz)
    monkeypatch.setattr(dashboard,'datetime',Clock)
    monkeypatch.setattr(evidence,'installed_sources',lambda base:(args['feeds'],[]))
    server=dashboard.DashboardServer(0,args['reports_root'],tmp_path/'notes',args['document_root'])
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    before=fingerprint(args['document_root'])
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        day=args['now'].astimezone(dashboard.KST).date().isoformat()
        with urlopen(url+'/api/period?'+urlencode({'view':'day','date':day})) as response:data=json.load(response)
        assert data['counts']['items']==7 and data['themes']==rows
        assert len(data['theme_presentations'])==6
        target=next(t for t in rows if '미래장비' in t['entity_ids'])
        label=data['theme_presentations'][target['theme_id']]['name']
        with urlopen(url+'/api/themes?'+urlencode({'q':label,'company_candidates':'1'})) as response:found=json.load(response)
        assert found['ThemeCandidates']==[target]
        query=urlencode({'theme_id':target['theme_id'],'entity_id':'미래장비','as_of':data['as_of']})
        with urlopen(url+'/api/company-evidence?'+query) as response:detail=json.load(response)
        assert detail['items'][0]['status']=='READY' and '일본' in detail['items'][0]['excerpt']
        assert fingerprint(args['document_root'])==before
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def test_cli_export_and_period_change_search_keep_original_snapshots(tmp_path,monkeypatch,capsys):
    from scripts import search_themes as cli
    from newscatalystos.theme_changes import compare_themes
    rows,args,store,first,at=case(tmp_path)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return args['now'].astimezone(tz)
    monkeypatch.setattr(cli,'datetime',Clock)
    target=next(t for t in rows if '미래장비' in t['entity_ids'])
    label=theme_presentation(target)['name'];before=fingerprint(args['document_root'])
    assert cli.main(['--root',str(store.root),'--query',label,'--company-candidates'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['ThemeCandidates']==[target]
    assert result['CompanyCandidates'][0]['entity_id']=='미래장비'
    changed=compare_themes(store,since=at,as_of=args['as_of'],now=args['now'],query=label)
    assert [t['theme_id'] for t in changed['ThemeChanges']]==[target['theme_id']]
    assert changed['ThemeChanges'][0]['provisional_name']==target['provisional_name']
    assert fingerprint(args['document_root'])==before
