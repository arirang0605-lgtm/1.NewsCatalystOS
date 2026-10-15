"""Semantic extraction through existing AI/cache/ledger -> theme -> saved UI."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json
import pytest
from newscatalystos import news_semantics as semantic
from newscatalystos.feed_analysis import publish_feed_analysis
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle,read_theme_bundle
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.source_share import SourceShareError
from scripts import run_feed_analysis
from test_feed_analysis import setup,run
from test_ai_provider import config
from test_ai_gemini_transport import LocalOpener,packet,key
from test_federated_news_search import collect, GOV, fingerprint
from test_new_source_adapter import registry,NOW


def proposal(actor='가온',action='PRODUCTION_START',topic='광자냉각',phase='SOURCE_REPORTED'):
    verb={'CONTRACT':'거래를 성사시켰다','CAPACITY_ADDITION':'제조 공간을 두 배로 넓혔다'}.get(action,'제조라인을 돌리기 시작했다')
    title=f'{actor}, {topic} 주문이 몰리자 {verb}'
    return title,dict(actors=[actor],action=action,phase=phase,topic=topic,
        driver='DEMAND_EXPANSION',quote=title,cause_quote=f'{topic} 주문이 몰리자')


def response(event):
    return packet(result={'summary':'주문 증가와 연관된 기업 행동이라는 해석입니다.',
        'claims':[json.dumps(event,ensure_ascii=False,separators=(',',':'))],
        'uncertainties':['제목 보도만으로 실거래를 확인할 수 없습니다.']})


def test_real_pipeline_extracts_actors_and_connects_three_actions_without_regex(tmp_path,key):
    title,event=proposal();info=setup(tmp_path,title);source=info[0]
    before=fingerprint(source.inbox_root.parent)
    model_file=tmp_path/'model.json'
    from dataclasses import asdict
    model_file.write_text(json.dumps(asdict(config('GEMINI'))));model_file.chmod(0o600)
    work=tmp_path/'analysis/core'
    opts=run_feed_analysis.parser().parse_args(['--registry',str(source.registry_path),
        '--state',str(source.poll_state),'--inbox-root',str(source.inbox_root),'--analysis-root',str(work),
        '--model-config',str(model_file),'--allow-paid','--semantic-ai','--semantic-call-limit','1'])
    now=datetime.now(timezone.utc)+timedelta(minutes=1)
    code,first=run_feed_analysis.evaluate(opts,opener=LocalOpener(response(event)),now=now)
    assert code==0 and first['semantic_ai_attempts']==1
    assert first['results'][0]['economic_changes'][0]['entity_ids']==['가온']
    assert first['results'][0]['economic_changes'][0]['extraction_method']=='AI_SOURCE_SPAN_MATCHED'
    store=ThemeStore(work/'theme_history');earliest=store.search(now=now)
    assert earliest[0]['status']=='CANDIDATE'
    assert fingerprint(source.inbox_root.parent)==before
    for n,actor in enumerate(['나래','다솜']):
        title,event=proposal(actor,action=['CONTRACT','CAPACITY_ADDITION'][n])
        collect(source,registry(),GOV,[(f'event-{n}',title,f'https://gov.example.org/{n}')],at=NOW+timedelta(hours=n+1))
        now+=timedelta(minutes=1)
        opener=LocalOpener(response(event))
        code,result=run_feed_analysis.evaluate(opts,opener=opener,now=now)
        assert code==0 and opener.calls==1
    themes=store.search(now=now)
    assert len(themes)==1 and themes[0]['status']=='EMERGING'
    assert themes[0]['scores']['distinct_economic_events']==3
    assert themes[0]['entity_ids']==['가온','나래','다솜']
    assert themes[0]['verified_beneficiary_count']==0
    assert store.search(as_of=datetime.fromisoformat(earliest[0]['decision_at']),now=now)==earliest
    p=Path(result['private_report_file'])
    assert consume_feed_analysis(p,p.parent,result['report_sha256'],now=now)['results']==result['results']
    cards,_=scan_saved_analysis(work.parent,now=now)
    assert len([c for c in cards if c.get('semantic_analysis',{}).get('events')])==3
    raw=build_theme_bundle(themes,decision_at=now,now=now)
    assert read_theme_bundle(raw,sha256(raw).hexdigest(),decision_at=now,now=now)['ThemeCandidates']==themes
    opener=LocalOpener(b'not used')
    opts.allow_paid=False
    replay=run_feed_analysis.evaluate(opts,opener=opener,now=now+timedelta(minutes=1))[1]
    assert opener.calls==0 and replay['semantic_ai_attempts']==0 and replay['theme_versions_created']==0


@pytest.mark.parametrize('field,value',[('actors',['없는회사']),('quote','원문에 없는 내용입니다'),
    ('cause_quote','가짜 수요'),('topic','없는기술')])
def test_unsupported_spans_do_not_reach_theme_or_retry_paid_call(tmp_path,key,field,value):
    title,event=proposal();event[field]=value
    info=setup(tmp_path,title);opener=LocalOpener(response(event))
    report=run(info,semantic_ai=True,model=config('GEMINI'),allow_paid=True,opener=opener)
    row=report['results'][0]
    assert row['semantic_analysis']['status']=='UNSUPPORTED_PROPOSAL'
    assert row['economic_changes']==[]
    assert run(info,semantic_ai=True,model=config('GEMINI'),allow_paid=True,opener=opener)['semantic_ai_attempts']==0
    assert opener.calls==1


def test_plan_and_empty_no_change_output_and_budget_limit(tmp_path,key):
    title,event=proposal(phase='PLANNED')
    info=setup(tmp_path,title)
    assert run(info,semantic_ai=True,semantic_call_limit=0,model=config('GEMINI'),allow_paid=True)['results'][0]['semantic_analysis']['status']=='NOT_ANALYZED_NO_CALL'
    row=run(info,semantic_ai=True,model=config('GEMINI'),allow_paid=True,opener=LocalOpener(response(event)))['results'][0]
    assert row['economic_changes'][0]['phase']=='PLANNED'
    bad=deepcopy(row['semantic_analysis']);bad['events'][0]['actors']=['조작회사']
    row['semantic_analysis']=bad
    with pytest.raises(SourceShareError):semantic.validate_saved(row,datetime.now(timezone.utc))


def test_existing_event_gets_source_actor_without_new_event_id(tmp_path,key):
    from newscatalystos.theme_emergence import economic_observation
    title='NICE평가정보, AI 기반 정부지원사업 맞춤 추천 서비스 출시'
    info=setup(tmp_path,title)
    original=run(info)['results'][0]['economic_changes'][0]
    event=dict(actors=['NICE평가정보'],action='BUSINESS_START',phase='SOURCE_REPORTED',
        topic='AI 기반 정부지원사업 맞춤 추천 서비스',driver='UNKNOWN',quote=title,cause_quote='')
    row=run(info,semantic_ai=True,model=config('GEMINI'),allow_paid=True,
        opener=LocalOpener(response(event)))['results'][0]
    enhanced=row['economic_changes'][0]
    assert enhanced['entity_ids']==['NICE평가정보'] and enhanced['original_entity_ids']==[]
    kwargs=dict(origin_reference=row['source_url'],source_url=row['source_url'],
        source_id=row['provider_id'],source_available_at=row['source_available_at'],content_scope='RSS_TITLE_METADATA')
    assert economic_observation(original,**kwargs)['event_id']==economic_observation(enhanced,**kwargs)['event_id']


def test_negated_claim_and_missing_quote_cannot_create_action(tmp_path,key):
    title,event=proposal()
    title+=' 사실무근';event['quote']=title
    info=setup(tmp_path,title)
    row=run(info,semantic_ai=True,model=config('GEMINI'),allow_paid=True,
        opener=LocalOpener(response(event)))['results'][0]
    assert row.get('semantic_analysis',{}).get('status') in {'UNSUPPORTED_PROPOSAL',None}
    assert row['economic_changes']==[]


def test_scheduler_replay_preserves_no_paid_calls_with_semantic_mode(tmp_path,key):
    from scripts import run_scheduled_triage as scheduler
    from test_scheduled_feed_analysis import opts
    from dataclasses import asdict
    title,event=proposal();info=setup(tmp_path,title)
    model=tmp_path/'model.json';model.write_text(json.dumps(asdict(config('GEMINI'))));model.chmod(0o600)
    params=opts(info[0],info[4],operation='--replay-only')
    params.semantic_ai=True;params.semantic_call_limit=1;params.allow_paid_ai=True
    params.analysis_model_config=model
    opener=LocalOpener(b'never call')
    code,report=scheduler.execute(params,feed_runner=lambda _: (0,{'status':'NO_PENDING_REPLAY'}),
        analysis_runner=lambda a:run_feed_analysis.evaluate(a,opener=opener))
    assert code==0 and opener.calls==0
    assert report['providers'][0]['analysis']['semantic_ai_attempts']==0
