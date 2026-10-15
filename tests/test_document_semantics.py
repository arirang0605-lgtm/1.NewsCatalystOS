"""Licensed body semantics: synthetic source and provider; no real API calls."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
import json

import pytest

from newscatalystos.motir_document_analysis import (
    analyze_motir_document, publish_motir_document_analysis, consume_motir_document_analysis,
)
from newscatalystos.news_semantics import DOCUMENT_PROMPT_VERSION, parse_document_events
from newscatalystos.research_dashboard import scan_saved_documents
from newscatalystos.source_share import SourceShareError
from newscatalystos.theme_emergence import ThemeStore
from scripts import run_motir_document_analysis as cli
from scripts import run_motir_policy_once as scheduler
from test_motir_document_analysis import case, fake_key
from test_news_semantics import proposal, response
from test_ai_gemini_transport import LocalOpener, packet


def test_body_to_events_themes_saved_view_and_cached_replay(tmp_path, fake_key):
    title, event = proposal()
    body = title + '. ' + '본문 설명입니다. ' * 10
    source, args = case(tmp_path, body)
    root = tmp_path / 'documents' / args['binding_sha256']
    model = tmp_path / 'model.json'
    model.write_text(json.dumps(asdict(args['model'])))
    model.chmod(0o600)
    opts = cli.parser().parse_args([
        '--binding-path', str(args['binding_path']), '--binding-sha256', args['binding_sha256'],
        '--archive-root', str(args['archive_root']), '--article-registry', str(source[2].registry_path),
        '--analysis-root', str(root), '--model-config', str(model), '--semantic-ai',
        '--analyze-existing', '--allow-paid', '--ai-ledger', str(args['ai_ledger']),
        '--company-identity-config', str(tmp_path/'absent.json')])
    # Use the article authorization, not the RSS registry.
    from unittest.mock import patch
    opener = LocalOpener(response(event))
    with patch.object(cli, '_registry', return_value=args['article_registry']):
        code, result = cli.evaluate(opts, opener=opener)
        assert code == 0 and opener.calls == 1
        opts.allow_paid = False
        replay_code, replay = cli.evaluate(opts, opener=opener)
    assert replay_code == 0 and opener.calls == 1 and replay['cache_hits'] == 1
    assert replay['theme_versions_created'] == 0
    from pathlib import Path
    report = consume_motir_document_analysis(Path(result['private_report_file']), result['report_sha256'])
    assert report['semantic_analysis']['events'] == [event]
    assert report['ai_analysis']['prompt_version'] == DOCUMENT_PROMPT_VERSION
    assert report['economic_changes'][0]['entity_ids'] == ['가온']
    assert report['economic_changes'][0]['verified_economic_effect'] is False
    sent = json.loads(opener.requests[0].data)
    prompt = json.loads(sent['contents'][0]['parts'][0]['text'])
    assert prompt['source_kind'] == 'LICENSED_DOCUMENT'
    assert 'article_text' in sent['systemInstruction']['parts'][0]['text']
    assert body.strip() in json.loads(prompt['document'])['article_text']
    now = datetime.now(timezone.utc)
    themes = ThemeStore(root.parent/'theme_history').search(now=now)
    assert themes[0]['entity_ids'] == ['가온']
    assert themes[0]['scores']['distinct_economic_events'] == 1
    rows, status = scan_saved_documents(root.parent, [dict(
        source_event_sha256=report['source_event_sha256'], headline='연결된 원래 제목')], now=now)
    assert status['saved_reports_skipped'] == 0
    assert rows[0]['bound_title'] == '연결된 원래 제목'
    assert rows[0]['semantic_analysis']['events'] == [event]
    assert rows[0]['ai_claims'] == []  # No encoded event JSON in the summary UI.
    early, _ = scan_saved_documents(root.parent, [], now=datetime.fromisoformat(report['source_available_at'])-timedelta(seconds=1))
    assert early == []


@pytest.mark.parametrize('field,value', [('actors', ['없는기업']), ('cause_quote', '없는 원인'),
    ('quote', '본문에 없는 문장'), ('action', []), ('driver', {})])
def test_unsupported_body_proposal_stays_cached_without_new_events(tmp_path, fake_key, field, value):
    text, event = proposal()
    _, args = case(tmp_path, text + '. ' + '자료 설명. '*20)
    event[field] = value
    opener = LocalOpener(response(event))
    report = analyze_motir_document(**args, semantic_ai=True, analyze_existing=True, allow_paid=True, opener=opener)
    assert report['semantic_analysis']['status'] == 'UNSUPPORTED_PROPOSAL'
    assert report['economic_changes'] == []
    replay = analyze_motir_document(**args, semantic_ai=True, analyze_existing=True, allow_paid=True, opener=opener)
    assert replay['cache_hits'] == 1 and opener.calls == 1
    path, pin = publish_motir_document_analysis(replay, tmp_path/'reports')
    assert consume_motir_document_analysis(path, pin)['semantic_analysis']['events'] == []


def test_paragraph_context_keeps_plans_and_denials_without_tainting_other_events():
    text, event = proposal()
    from test_ai_provider import config, request
    from newscatalystos.ai_provider import run_ai_analysis
    result = run_ai_analysis(config('GEMINI'), request(), transport=lambda *_: {
        'result': {'summary':'합성', 'claims':[json.dumps(event,ensure_ascii=False)], 'uncertainties':[]},
        'usage':{'input_tokens':10,'output_tokens':10}})
    events, _ = parse_document_events(result, '다른 회사의 사업 계획은 검토 중이다.\n'+text)
    assert events[0]['phase'] == 'SOURCE_REPORTED'
    events, _ = parse_document_events(result, text+'라는 계획을 발표했다.')
    assert events[0]['phase'] == 'PLANNED'
    for suffix in ('라는 보도를 부인했다.', '라는 지난 발표된 계획을 점검했다.'):
        with pytest.raises(SourceShareError):
            parse_document_events(result, text+suffix)


def test_semantic_report_binding_event_and_context_tampering_rejected(tmp_path, fake_key):
    text, event = proposal()
    _, args = case(tmp_path, text+'. '+'자료 설명. '*20)
    report = analyze_motir_document(**args, semantic_ai=True, analyze_existing=True,
        allow_paid=True, opener=LocalOpener(response(event)))
    for field, value in [('binding_sha256','0'*64), ('document_sha256','0'*64),
                         ('events',[]), ('evidence_contexts',['바꿔치기 문장'])]:
        changed = deepcopy(report)
        changed['semantic_analysis'][field] = value
        path, pin = publish_motir_document_analysis(changed,tmp_path/'reports')
        with pytest.raises(SourceShareError):
            consume_motir_document_analysis(path,pin)


def test_existing_body_events_preserve_ids_when_ai_adds_company(tmp_path, fake_key):
    from newscatalystos.theme_emergence import economic_observation
    text = '가온, 반도체 공장에 20조원을 신규 투자하기로 결정했다.'
    _, args = case(tmp_path, text+' '+'자금 집행과 실제 매출은 미확인이다. '*4)
    before = analyze_motir_document(**args)
    event = dict(actors=['가온'],action='INVESTMENT',phase='SOURCE_REPORTED',topic='반도체',
        driver='UNKNOWN',quote=text,cause_quote='')
    after = analyze_motir_document(**args, semantic_ai=True, allow_paid=True, opener=LocalOpener(response(event)))
    assert len(before['economic_changes']) == len(after['economic_changes']) == 1
    kwargs = dict(origin_reference=before['source_url'],source_url=before['source_url'],
        source_id='motir-official-press',source_available_at=before['source_available_at'])
    assert economic_observation(before['economic_changes'][0],**kwargs)['event_id'] == economic_observation(after['economic_changes'][0],**kwargs)['event_id']


def test_scheduler_bounds_document_semantics_and_replay_disables_payment(tmp_path):
    from argparse import Namespace
    jobs = [{'binding_path':str(tmp_path/f'b{i}'), 'binding_sha256':str(i)*64,
             'archive_root':str(tmp_path/'archive'), 'article_registry':str(tmp_path/'registry')} for i in (1,2)]
    opts = Namespace(analysis_root=tmp_path/'analysis',allow_paid_ai=True,replay_only=False,
        semantic_ai=True,semantic_call_limit=1)
    seen=[]
    def runner(args):
        seen.append(args)
        return 0, {'ai_adapter_attempted':args.allow_paid}
    scheduler._analyze_documents(opts,runner,extra_jobs=jobs)
    assert [a.allow_paid for a in seen] == [True,False]
    assert all(a.semantic_ai for a in seen)
    seen.clear();opts.replay_only=True
    scheduler._analyze_documents(opts,runner,extra_jobs=jobs)
    assert [a.allow_paid for a in seen] == [False,False]


def test_policy_events_do_not_require_company_or_investment_amount(tmp_path, fake_key):
    text = '산업부는 반도체 전담 조직 신설안을 의결했다.'
    _, args = case(tmp_path, text+' '+'시행 시점과 기업별 효과는 미확인이다. '*4)
    event = dict(actors=[],action='POLICY_CHANGE',phase='SOURCE_REPORTED',topic='반도체',
        driver='UNKNOWN',quote=text,cause_quote='')
    opener = LocalOpener(response(event))
    report = analyze_motir_document(**args, semantic_ai=True, analyze_existing=True,
        allow_paid=True, opener=opener)
    assert report['semantic_analysis']['events'] == [event]
    sent = json.loads(opener.requests[0].data)
    assert 'Government policy changes are eligible even with no company named' in sent['systemInstruction']['parts'][0]['text']
    assert report['verified_real_benefit'] is False
    scheduled = analyze_motir_document(**args, semantic_ai=True, analyze_existing=False,
        allow_paid=True, opener=opener)
    assert scheduled['ai_status'] == 'CACHE_HIT' and opener.calls == 1
    assert scheduled['input_sha256'] == report['input_sha256']
