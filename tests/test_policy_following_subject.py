"""Policy-first synthetic articles with explicit subjects; no network/paid AI."""
from hashlib import sha256
import json

import pytest
from newscatalystos.economic_changes import extract_economic_changes
from newscatalystos.company_evidence import company_evidence
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.research_dashboard import scan_saved_analysis
from test_policy_company_actions import CAUSE,case as policy_case
from test_federated_news_search import fingerprint


@pytest.mark.parametrize('subject,names',[
    ('가상전자는',['가상전자']),('가상전자가',['가상전자']),('가상전자,',['가상전자']),
    ('가상전자와 새빛소재는',['가상전자','새빛소재']),
    ('가상전자 및 새빛소재는',['가상전자','새빛소재']),
])
def test_explicit_subject_after_policy(subject,names):
    text=CAUSE+' '+subject+' 생산 시작'
    row=extract_economic_changes(text)[0]
    assert row['entity_ids']==names and row['action']=='PRODUCTION_START'
    assert row['economic_driver']=='POLICY_ENABLEMENT' and row['phase']=='SOURCE_REPORTED'
    assert row['policy_cause']['source_expression']==CAUSE
    assert row['source_paragraph_sha256']==sha256(text.encode()).hexdigest()
    assert not row['verified_economic_effect']


def test_directory_names_planning_and_parallel_actions():
    rows=extract_economic_changes(CAUSE+' 별빛공업은 생산능력 확대 계획',company_names=['별빛공업'])
    assert rows[0]['entity_ids']==['별빛공업'] and rows[0]['phase']=='PLANNED'
    rows=extract_economic_changes(CAUSE.replace('완화로','완화에 대비해')+' 가상전자는 생산 시작 및 신규 투자 결정')
    assert [r['action'] for r in rows]==['PRODUCTION_START','INVESTMENT']
    assert all(r['entity_ids']==['가상전자'] and r['phase']=='PLANNED' for r in rows)


@pytest.mark.parametrize('text',[
    CAUSE+' 생산 시작',CAUSE+' 그 회사는 생산 시작',CAUSE+' 해당 기업은 생산 시작',
    CAUSE+' 가상전자를 위해 생산 시작',CAUSE+' 가상전자의 고객은 생산 시작',
    CAUSE+' 가상전자는 새빛소재의 생산 시작을 지원',
    '새빛소재, '+CAUSE+' 가상전자는 생산 시작',
    '업계에 따르면 '+CAUSE+' 가상전자는 생산 시작',
    CAUSE+' 가상전자는 생산 시작했고 그 회사는 생산능력 확대',
    CAUSE+' 가상전자는 DRAM 수요 증가로 생산 시작',
    CAUSE+' 가상전자는 DRAM 생산 시작',
    CAUSE+' 가상전자는 생산 시작을 검토 중이다',
    CAUSE+' 가상전자는 생산 시작 보도를 부인했다',
    CAUSE+' 가상전자는 생산 시작 취소',
])
def test_no_inferred_subject_or_scope_transfer(text):
    assert extract_economic_changes(text)==[]


def test_second_company_clause_does_not_inherit_first_policy():
    rows=extract_economic_changes(CAUSE+' 가상전자는 생산을 시작했고 새빛소재는 DRAM 생산능력 확대 계획')
    assert [(r['entity_ids'],r['economic_driver'],r['phase']) for r in rows]==[
        (['가상전자'],'POLICY_ENABLEMENT','SOURCE_REPORTED'),
        (['새빛소재'],'CAPACITY_EXPANSION','PLANNED')]
    assert 'policy_cause' not in rows[1]


def case(tmp_path):
    return policy_case(tmp_path,titles=[CAUSE+' 가상전자는 생산 시작',
        '새빛소재, '+CAUSE+' 생산능력 확대',CAUSE+' 미래장비는 신규 공장 투자 결정'])


def test_mixed_sentence_order_to_one_theme_and_company_evidence(tmp_path):
    theme,args,store,report,events,first,at=case(tmp_path)
    assert theme['status']=='EMERGING' and theme['scores']['company_breadth']==3
    assert theme['scores']['distinct_economic_events']==3
    assert store.search(as_of=at,now=args['now'])==[first]
    assert store.ingest(events,now=args['now'])==[]
    before=fingerprint(tmp_path)
    rows,info=scan_saved_analysis(args['reports_root'],now=args['now'])
    assert len(rows)==3 and info['saved_reports_skipped']==0
    for company in ['가상전자','새빛소재','미래장비']:
        result=company_evidence(theme,company,**args)
        assert len(result['items'])==1 and result['items'][0]['status']=='READY'
        assert company in result['items'][0]['excerpt']
    bundle=json.loads(build_theme_bundle([theme],decision_at=args['as_of'],now=args['now'],include_company_candidates=True))
    assert len(bundle['CompanyCandidates'])==3
    assert all(CAUSE in c['inclusion_basis'][0]['reason'] and not c['verified_real_benefit'] for c in bundle['CompanyCandidates'])
    assert fingerprint(tmp_path)==before


def test_licensed_body_uses_following_subject(tmp_path):
    from test_motir_document_analysis import case as body_case
    from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis,consume_motir_document_analysis
    text=CAUSE+' 가상전자는 생산 시작. '
    _,args=body_case(tmp_path,text*3)
    report=analyze_motir_document(**args)
    assert [(r['action'],r['entity_ids']) for r in report['economic_changes']]==[('PRODUCTION_START',['가상전자'])]
    path,pin=publish_motir_document_analysis(report,tmp_path/'reports')
    assert consume_motir_document_analysis(path,pin)['economic_changes']==report['economic_changes']


def test_dashboard_delivers_following_subject_and_source_excerpt(tmp_path,monkeypatch):
    from datetime import datetime
    import threading
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
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        day=args['now'].astimezone(dashboard.KST).date().isoformat()
        with urlopen(url+'/api/period?'+urlencode({'view':'day','date':day})) as response:data=json.load(response)
        assert data['counts']['items']==3 and len(data['themes'])==1
        assert any(r['headline']==CAUSE+' 가상전자는 생산 시작' and
            r['economic_changes'][0]['entity_ids']==['가상전자'] for r in data['items'])
        query=urlencode({'theme_id':theme['theme_id'],'entity_id':'가상전자','as_of':data['as_of']})
        with urlopen(url+'/api/company-evidence?'+query) as response:detail=json.load(response)
        assert detail['items'][0]['status']=='READY'
        assert detail['items'][0]['excerpt']==CAUSE+' 가상전자는 생산 시작'
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
