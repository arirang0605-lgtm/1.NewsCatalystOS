"""Synthetic project stage reports; never independent expenditure confirmation."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.theme_emergence import ThemeStore,economic_observation
from newscatalystos.theme_changes import compare_themes
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.source_share import SourceShareError
from newscatalystos.company_evidence import company_evidence
from test_service_realization import claim,T
from test_policy_company_actions import case as source_case
from test_federated_news_search import fingerprint

PREFIX='가상전자, HBM 수요 증가로 '
DECISION=PREFIX+'「청해공장」 투자 결정'
EXECUTION=PREFIX+'「청해공장」 투자 집행'
LATER=T+timedelta(hours=2)


def pair():return [claim(DECISION,0),claim(EXECUTION,1)]


def test_named_stages_keep_events_pit_sources_and_count_one_investment(tmp_path):
    decision,execution=pair();store=ThemeStore(tmp_path/'themes')
    legacy=deepcopy(decision);del legacy['change']['investment_project']
    first=store.ingest([legacy],now=T)[0]
    raw=build_theme_bundle([first],decision_at=T,now=T,include_company_candidates=True)
    latest=store.ingest([decision,execution],now=LATER)[0]
    assert latest['theme_id']==first['theme_id'] and latest['first_detected_at']==first['first_detected_at']
    assert latest['event_ids']==sorted([decision['event_id'],execution['event_id']])
    assert latest['scores']['distinct_economic_events']==1 and len(latest['source_refs'])==3
    link,=latest['investment_stage_links']
    assert link['project_name']=='청해공장' and not link['is_execution_confirmed']
    for source,row in zip(link['sources'],(decision,execution)):
        assert source['source_url']==row['source_url'] and source['evidence_sha256']==row['change']['source_paragraph_sha256']
        proof=source['project_evidence'];assert proof['expression_sha256']==sha256(proof['source_expression'].encode()).hexdigest()
    before=fingerprint(tmp_path)
    assert store.search(as_of=T,now=LATER)==[first]
    assert raw==build_theme_bundle([first],decision_at=T,now=LATER,include_company_candidates=True)
    bundle=build_theme_bundle([latest],decision_at=LATER,now=LATER,include_company_candidates=True)
    value=read_theme_bundle(bundle,sha256(bundle).hexdigest(),decision_at=LATER,now=LATER)
    c,=value['CompanyCandidates'];assert not c['verified_real_transaction'] and not c['verified_real_benefit']
    b=c['inclusion_basis'][-1];assert b['kind']=='SOURCE_REPORTED_INVESTMENT_STAGES' and len(b['source_urls'])==2
    diff,=compare_themes(store,since=T+timedelta(seconds=1),as_of=LATER,now=LATER,query='청해공장')['ThemeChanges']
    assert diff['investment_stage_links_added']==[link]
    assert diff['events']['independent_actions_added']==0 and diff['events']['added'][0]['kind']=='FOLLOWUP_OBSERVATION'
    assert any(r['code']=='REPORTED_INVESTMENT_EXECUTION' for r in diff['reasons'])
    assert fingerprint(tmp_path)==before
    assert store.ingest([decision,execution],now=LATER+timedelta(seconds=1))==[]


@pytest.mark.parametrize('title',[
 EXECUTION.replace('청해','남해'),EXECUTION.replace('「청해공장」','신규 공장'),
 EXECUTION.replace('「청해공장」','「신규공장」'),EXECUTION.replace('가상전자','새빛소재'),
 EXECUTION.replace('가상전자','가상전자와 새빛소재'),
 EXECUTION.replace('「청해공장」','「청해공장」 및 「남해공장」'),
 EXECUTION.replace('「청해공장」','「청해공장 및 남해공장」'),
 EXECUTION.replace('HBM','DRAM'),EXECUTION+' 예정',EXECUTION+' 계획',
])
def test_unidentified_different_multiple_or_planned_not_linked(tmp_path,title):
    observations=[claim(DECISION,0),claim(title,1)]
    themes=ThemeStore(tmp_path/'themes').ingest(observations,now=LATER)
    assert not any(t.get('investment_stage_links') for t in themes)
    assert sum(t['scores']['distinct_economic_events'] for t in themes)==2


@pytest.mark.parametrize('tail',[' 취소',' 보류','하지 않았다',' 보도를 부인했다',' 여부 확인'])
def test_denied_execution_cannot_link(tail):
    assert not any(c.get('investment_project') for c in extract_economic_changes(EXECUTION+tail))


@pytest.mark.parametrize('offset',[0,-1])
def test_execution_source_must_follow_decision(tmp_path,offset):
    decision,execution=pair();execution['source_available_at']=(T+timedelta(hours=offset)).isoformat()
    theme=ThemeStore(tmp_path/'themes').ingest([decision,execution],now=LATER)[0]
    assert not theme.get('investment_stage_links')


def test_ambiguous_decisions_and_later_republication(tmp_path):
    decision,execution=pair();store=ThemeStore(tmp_path/'themes')
    theme=store.ingest([decision,execution],now=LATER)[0]
    repeat=deepcopy(decision);repeat['source_url']='https://example.org/reprint';repeat['source_available_at']=LATER.isoformat()
    latest=store.ingest([repeat],now=LATER+timedelta(seconds=1))[0]
    assert latest['scores']['distinct_economic_events']==1 and len(latest['investment_stage_links'])==1
    other=claim(DECISION.replace('결정','확정'),0)
    ambiguous=store.ingest([other],now=LATER+timedelta(seconds=2))[0]
    assert not ambiguous.get('investment_stage_links') and ambiguous['scores']['distinct_economic_events']==3
    assert store.search(as_of=LATER,now=LATER+timedelta(seconds=2))==[theme]


@pytest.mark.parametrize('mutation',['confirmed','source','project','future','missing','ambiguous','conflict'])
def test_invalid_export_is_rejected(tmp_path,mutation):
    theme=ThemeStore(tmp_path/'themes').ingest(pair(),now=LATER)[0]
    link=theme['investment_stage_links'][0]
    if mutation=='confirmed':link['is_execution_confirmed']=True
    if mutation=='source':link['sources'][0]['source_url']='https://example.org/wrong'
    if mutation=='project':link['sources'][0]['project_evidence']['project_name']='다른공장'
    if mutation=='future':link['decision_at']=(LATER+timedelta(seconds=1)).isoformat()
    if mutation=='missing':theme['source_refs']=theme['source_refs'][1:]
    if mutation=='ambiguous':
        ref=deepcopy(next(r for r in theme['source_refs'] if r['action']=='INVESTMENT'))
        ref['event_id']='a'*64;theme['event_ids'].append(ref['event_id']);theme['source_refs'].append(ref)
    if mutation=='conflict':theme['conflicting_event_ids'].append(link['decision_event_id'])
    with pytest.raises(SourceShareError):build_theme_bundle([theme],decision_at=LATER,now=LATER)


def case(tmp_path):
    return source_case(tmp_path,titles=[DECISION,EXECUTION,'새빛소재, HBM 수요 증가로 생산 시작'])


def test_saved_title_pipeline_company_basis_and_source_excerpt(tmp_path):
    theme,args,store,report,events,first,at=case(tmp_path)
    assert len(theme['investment_stage_links'])==1 and theme['scores']['distinct_economic_events']==2
    before=fingerprint(tmp_path)
    items=company_evidence(theme,'가상전자',**args)['items']
    assert len(items)==2 and all(i['status']=='READY' for i in items)
    assert {i['excerpt'] for i in items}=={DECISION,EXECUTION}
    assert report['source_fetch_calls']==report['new_ai_results']==0
    assert fingerprint(tmp_path)==before


def test_unlinked_decision_still_forms_theme_and_legacy_identity():
    decision=pair()[0];old=deepcopy(decision['change']);del old['investment_project']
    legacy=economic_observation(old,**{k:v for k,v in decision.items() if k not in {'change','event_id'}})
    assert legacy['event_id']==decision['event_id']


def test_licensed_body_retains_project_proof(tmp_path):
    from test_motir_document_analysis import case as body_case
    from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
    _,args=body_case(tmp_path,(EXECUTION+'. 실제 지출 금액은 확인되지 않았다. ')*3)
    report=analyze_motir_document(**args)
    proof=report['economic_changes'][0]['investment_project'];assert proof['project_name']=='청해공장'
    path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
    assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_planned_decision_and_conflicting_report_do_not_form_execution_history(tmp_path):
    planned=claim(DECISION+' 계획',0);execution=claim(EXECUTION,1)
    assert planned['change']['phase']=='PLANNED'
    store=ThemeStore(tmp_path/'planned');theme=store.ingest([planned,execution],now=LATER)[0]
    assert not theme.get('investment_stage_links')
    decision,execution=pair();store=ThemeStore(tmp_path/'conflict')
    first=store.ingest([decision,execution],now=LATER)[0]
    correction=economic_observation(execution['change'],origin_reference='https://example.org/conflict',
        source_url='https://example.org/conflict',source_id='synthetic',source_available_at=LATER.isoformat(),
        polarity='CONTRADICT',supersedes_event_id=execution['event_id'],content_scope='RSS_TITLE_METADATA')
    at=LATER+timedelta(seconds=1);theme=store.ingest([correction],now=at)[0]
    assert not theme.get('investment_stage_links') and theme['status']=='WEAKENING'
    assert store.search(as_of=LATER,now=at)==[first]
    build_theme_bundle([theme],decision_at=at,now=at)


def test_separate_company_actions_still_create_emerging_theme(tmp_path):
    observations=pair()+[claim('새빛소재, HBM 수요 증가로 생산 시작',1),
                         claim('미래장비, HBM 수요 증가로 공급 계약 체결',1)]
    theme=ThemeStore(tmp_path/'themes').ingest(observations,now=LATER)[0]
    assert theme['scores']['distinct_economic_events']==3 and theme['status']=='EMERGING'
    assert theme['scores']['company_breadth']==3 and len(theme['event_ids'])==4


def test_project_proof_cannot_be_transplanted_to_another_title(tmp_path):
    from newscatalystos.feed_analysis_delivery import _validate_report
    theme,args,store,report,*_=case(tmp_path)
    forged=deepcopy(report)
    row=next(r for r in forged['results'] if r['headline']==DECISION)
    row['economic_changes'][0]['investment_project']=extract_economic_changes(DECISION.replace('청해','남해'))[0]['investment_project']
    with pytest.raises(SourceShareError,match='saved source title'):_validate_report(forged,args['now'])


def test_period_http_and_company_evidence_show_link_sources(tmp_path,monkeypatch):
    import json,threading
    from datetime import datetime
    from urllib.parse import urlencode
    from urllib.request import urlopen
    from scripts import open_research_dashboard as dashboard
    from newscatalystos import company_evidence as evidence
    theme,args,*_=case(tmp_path)
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
        assert data['themes'][0]['investment_stage_links']==theme['investment_stage_links']
        candidate=next(c for c in data['company_candidates'] if c['entity_id']=='가상전자')
        assert candidate['inclusion_basis'][-1]['kind']=='SOURCE_REPORTED_INVESTMENT_STAGES'
        with urlopen(url+'/api/company-evidence?'+urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})) as response:detail=json.load(response)
        assert len(detail['items'])==2 and all(i['status']=='READY' for i in detail['items'])
        with urlopen(url+'/api/themes?'+urlencode({'q':'청해공장'})) as response:found=json.load(response)
        assert found['ThemeCandidates']==[theme]
    finally:
        server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(args['document_root'])==before


def test_ui_stage_history_has_both_source_links(tmp_path):
    import json,subprocess
    from test_research_action_labels import present
    theme=ThemeStore(tmp_path/'themes').ingest(pair(),now=LATER)[0]
    assert present({'headline':'합성','economic_changes':[]},['청해공장'],theme)['themes']==[True]
    code="""
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
const fn=source.slice(source.indexOf('function renderInvestmentStages('),source.indexOf('function renderThemeChanges('));
const nodes=[],links=JSON.parse(fs.readFileSync(0,'utf8'));
const context={links,parent:{append(n){nodes.push(n)}},node:(tag,cls,text)=>({tag,text})};
vm.runInNewContext(fn+';renderInvestmentStages(parent,links);',context);
process.stdout.write(JSON.stringify(nodes));
"""
    nodes=json.loads(subprocess.check_output(['node','-e',code],input=json.dumps(theme['investment_stage_links']).encode()))
    assert '결정 → 집행 보도 연결' in nodes[0]['text'] and '독립 확인되지 않음' in nodes[0]['text']
    assert [n['href'] for n in nodes if n['tag']=='a']==[r['source_url'] for r in theme['investment_stage_links'][0]['sources']]


def test_legacy_named_decision_phase_and_excerpt_remain_readable(tmp_path):
    from datetime import datetime,timezone
    from test_feed_analysis import setup,run
    from test_order_growth import observation
    from newscatalystos.feed_analysis import publish_feed_analysis
    from newscatalystos.feed_analysis_delivery import consume_feed_analysis
    text=DECISION+' 계획';info=setup(tmp_path,text);at=datetime.now(timezone.utc)
    report=run(info,now=at);row=report['results'][0]
    old,=extract_economic_changes(text,include_investment_projects=False)
    old['evidence_level']='REPORTED';assert old['phase']=='SOURCE_REPORTED'
    row['economic_changes']=[old];root=tmp_path/'reports';docs=tmp_path/'documents'
    path,pin=publish_feed_analysis(report,root/'core/reports')
    assert consume_feed_analysis(path,path.parent,pin,now=at)['results'][0]['economic_changes']==[old]
    theme=ThemeStore(docs/'theme_history').ingest([observation(row,old)],now=at)[0]
    result=company_evidence(theme,'가상전자',reports_root=root,document_root=docs,as_of=at,now=at,
        feeds=[dict(registry=info[0].registry_path,inbox=info[0].inbox_root,state=info[0].poll_state)])
    assert result['items'][0]['status']=='READY' and result['items'][0]['excerpt']==text
    assert not theme.get('investment_stage_links')


@pytest.mark.parametrize('tail',[' 여부 확인',' 설명회',' 가능성',' 전망'])
def test_decision_discussion_does_not_supply_project_stage_evidence(tail):
    assert not any(c.get('investment_project') for c in extract_economic_changes(DECISION+tail))
