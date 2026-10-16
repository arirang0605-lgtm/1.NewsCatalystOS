"""Pure JS presentation/search helpers against stored dashboard projections."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import subprocess

import pytest
from newscatalystos.research_dashboard import scan_saved_analysis,build_period
from test_parallel_company_actions import case
from test_federated_news_search import fingerprint


def present(item,terms=(),theme=None):
    # Execute only the pure prefix, before rendering/listeners/network code.
    code="""
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync('scripts/dashboard_assets/app.js','utf8').split('function renderItems(){')[0];
const context={input};
const result=vm.runInNewContext(source+`;
const original=JSON.stringify(input);
const terms=input.terms.map(t=>t.toLocaleLowerCase());
JSON.stringify({label:categoryLabel(input.item),
  matches:terms.map(t=>matchesFinding(input.item,t)),
  themes:terms.map(t=>matchesTheme(input.theme,t,[],{})),
  unchanged:original===JSON.stringify(input)});`,context);
process.stdout.write(result);
"""
    payload=dict(item=item,terms=list(terms),theme=theme or dict(source_refs=item.get('economic_changes',[])))
    return json.loads(subprocess.check_output(['node','-e',code],input=json.dumps(payload).encode()))


def change(action,phase='SOURCE_REPORTED'):
    return dict(action=action,phase=phase,topic='HBM')


@pytest.mark.parametrize(('actions','label','terms'),[
    ([change('CONTRACT'),change('INVESTMENT')],'계약 · 출처 보도 / 투자 결정 · 출처 보도',['계약','투자 결정','INVESTMENT']),
    ([change('PRODUCTION_START')],'생산 개시 · 출처 보도',['생산 개시','생산 시작','양산','PRODUCTION_START']),
    ([change('CAPACITY_ADDITION')],'생산능력 확대 · 출처 보도',['생산능력 확대','증설','CAPACITY_ADDITION']),
    ([change('CONTRACT','PLANNED')],'계약 · 계획 단계',['계획 단계','PLANNED']),
    ([change('POLICY_CHANGE','ADOPTED_NOT_YET_EFFECTIVE')],'정책 변화 · 의결 · 시행 전',['정책 변화','시행 전']),
    ([change('CONTRACT'),change('INVESTMENT','PLANNED')],'계약 · 출처 보도 / 투자 결정 · 계획 단계',['계약','투자 결정']),
    ([change('INVESTMENT')]*2,'투자 결정 · 출처 보도',['투자 결정']),
])
def test_labels_and_shared_finding_theme_search(actions,label,terms):
    item=dict(headline='합성 기사',provider='synthetic',category=None,economic_changes=actions)
    result=present(item,terms+['없는 행동'])
    assert result['label']==label and result['unchanged']
    assert result['matches']==result['themes']==[True]*len(terms)+[False]


@pytest.mark.parametrize(('category','label'),[
    ('CONTRACT_TERMINATION','계약 종료 보도'),('CONTRACT_REDUCTION','계약 감액 보도'),
    ('CONTRACT_DELAY','납기 지연 보도'),
])
def test_followup_warning_precedes_action(category,label):
    result=present(dict(category=category,economic_changes=[change('CONTRACT')]),[label])
    assert result['label']==label and result['matches']==[True] and result['unchanged']


@pytest.mark.parametrize(('item','label'),[
    ({'category':None},'분류 없음'),
    ({'category':'NEW_CONTRACT','reported_plan_only':True},'신규 계약 계획 보도'),
    ({'category':'LICENSED_ARTICLE_ANALYSIS'},'허가 본문 분석'),
    ({'category':None,'economic_changes':[change('CONTRACT','UNKNOWN')]},'계약 · 단계 미확인'),
])
def test_unknown_empty_and_existing_category_fallback(item,label):
    assert present(item)['label']==label


def test_saved_category_search_and_source_qualifiers_preserved():
    item=dict(headline='가상전자 합성 기사',provider='synthetic',category='NEW_CONTRACT',
              economic_changes=[change('CONTRACT')],company_identity={'name':'가상전자'},ai_status='NOT_ELIGIBLE')
    result=present(item,['신규 계약','NEW_CONTRACT','가상전자','synthetic'])
    assert all(result['matches']) and result['unchanged']


def test_saved_report_projection_multi_action_one_record_and_readonly(tmp_path):
    theme,args,store,events,first,at,old=case(tmp_path)
    before=fingerprint(tmp_path)
    rows,source=scan_saved_analysis(args['reports_root'],document_root=args['document_root'],now=args['now'])
    assert len(rows)==1 and rows[0]['category'] is None and len(rows[0]['economic_changes'])==2
    data=build_period(rows,[],'day',rows[0]['day'],source_info=source)
    assert data['counts']['items']==1 and len(data['items'])==1
    result=present(data['items'][0],['투자 결정','계약 체결'],theme)
    assert result['label']=='계약 · 출처 보도 / 투자 결정 · 출처 보도'
    assert all(result['matches']) and all(result['themes']) and result['unchanged']
    assert fingerprint(tmp_path)==before


def test_licensed_body_projection_with_action_and_no_record_duplication(tmp_path):
    from test_motir_document_analysis import case as body_case
    from newscatalystos.motir_document_analysis import analyze_motir_document,publish_motir_document_analysis
    from newscatalystos.research_dashboard import scan_saved_documents
    source,opts=body_case(tmp_path,body=('가상전자, HBM 주문 증가로 생산 시작. 추가 근거는 미확인이다. ')*3)
    report=analyze_motir_document(**opts);docs=tmp_path/'documents'
    publish_motir_document_analysis(report,docs/('a'*64)/'reports')
    before=fingerprint(tmp_path)
    rows,_=scan_saved_documents(docs,[],now=datetime.now(timezone.utc)+timedelta(seconds=1))
    assert len(rows)==1 and rows[0]['category']=='LICENSED_ARTICLE_ANALYSIS'
    result=present(rows[0],['생산 개시','생산 시작'])
    assert result['label']=='생산 개시 · 출처 보도' and all(result['matches'])
    assert rows[0]['content_scope']=='LICENSED_ARTICLE_TEXT' and fingerprint(tmp_path)==before
