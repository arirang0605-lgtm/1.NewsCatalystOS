"""Synthetic RSS -> existing PIN gold -> exact blind reviewer entry.

Simulated human answers in these tests are not live human gold evidence.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from newscatalystos import live_gold_samples as gold
from newscatalystos import search_gold_review as bridge
from newscatalystos.human_review_entry import list_review_cases
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from scripts import search_news, review_news_interactive
from scripts.run_feed_triage import _registry
from test_federated_news_search import (
    sample as source_sample, fingerprint, collect, write_registry,
    GOV, WIRE, MINISTRY, SHARED,
)
from test_new_source_adapter import NOW


@pytest.fixture
def prepared(source_sample, tmp_path, monkeypatch):
    sources, registries, _, _ = source_sample
    monkeypatch.setattr(gold, '_different_disk', lambda *_: True)
    workspaces, batches = [], []
    for source, registry in zip(sources, registries):
        workspace = bridge.GoldSearchWorkspace(
            source, tmp_path / ('gold_' + source.scope),
            tmp_path / ('pins_' + source.scope),
            tmp_path / ('reviews_' + source.scope),
        )
        batch = gold.freeze_real_gold_review_cases(
            registry, source.inbox_root, source.poll_state,
            workspace.out_root, workspace.pin_root,
        )
        gold.prepare_blank_human_review_sheets(
            batch.folder, workspace.out_root, batch.payload_sha256,
            batch.pin_file, workspace.pin_root, workspace.workspace_root,
        )
        workspaces.append(workspace)
        batches.append(batch)
    return tuple(workspaces), tuple(batches), registries


def query(workspaces, **kwargs):
    return bridge.search_gold_review_links(
        workspaces, '반도체', registry_reader=_registry, slot='UNASSIGNED_A', **kwargs,
    )


def test_three_source_join_reads_only_and_exposes_no_predictions(prepared, tmp_path, monkeypatch):
    workspaces, batches, _ = prepared
    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected write or network call')
    import newscatalystos.feed_transport as transport
    import newscatalystos.feed_recovery as recovery
    monkeypatch.setattr(transport, 'fetch_authorized_once', forbidden)
    monkeypatch.setattr(recovery, '_connect', forbidden)
    monkeypatch.setattr(gold, 'freeze_real_gold_review_cases', forbidden)
    monkeypatch.setattr(gold, 'prepare_blank_human_review_sheets', forbidden)
    before = fingerprint(tmp_path)
    report = query(workspaces)
    assert fingerprint(tmp_path) == before
    assert report['review_links_complete'] and report['coverage_complete']
    assert report['linked_case_count'] == report['ready_for_selected_reviewer_count'] == 5
    assert {r['provider_id'] for r in report['results']} == {GOV, WIRE, MINISTRY}
    assert report['human_labels_added'] == report['gold_batches_created'] == 0
    assert report['network_calls'] == report['ai_calls'] == 0
    assert not report['review_entry_executed'] and not report['release_gate_verified']
    encoded = json.dumps(report)
    for forbidden_field in ('predicted_duplicate', 'predicted_important',
                            'source_claim_classification', 'metadata_overlap_hints',
                            'true_duplicate', 'important_event', 'UNASSIGNED_B'):
        assert forbidden_field not in encoded
    assert report['selection_scope'] == 'QUERY_SUBSET_NOT_UNBIASED_EVALUATION_SAMPLE'
    for item in report['results']:
        key = '\0'.join(item[x] for x in ('provider_id', 'event_id', 'title_sha256'))
        assert item['case_sha256'] == sha256(key.encode()).hexdigest()
        assert item['batch_sha256'] in {batch.payload_sha256 for batch in batches}
        assert item['source_available_at'] <= item['gold_pinned_at'] <= item['link_verified_at']
        argv = item['review_entry_argv']
        assert argv[argv.index('--case-sha256') + 1] == item['case_sha256']
        assert '--reviewer-code' not in argv


def test_title_revision_not_yet_frozen_stays_pending_without_new_pin(prepared, tmp_path):
    workspaces, _, registries = prepared
    collect(workspaces[0].source, registries[0], GOV,
            [('a', '반도체 투자 40억원 추가 정정', SHARED)], at=NOW + timedelta(hours=3))
    before = fingerprint(tmp_path)
    report = query(workspaces)
    assert fingerprint(tmp_path) == before
    assert not report['review_links_complete'] and report['pending_unfrozen_count'] == 1
    pending = [r for r in report['results'] if r['link_status'] == 'NOT_FROZEN_YET']
    assert len(pending) == 1 and pending[0]['headline'] == '반도체 투자 40억원 추가 정정'
    assert pending[0]['review_entry_argv'] is None and pending[0]['batch_sha256'] is None
    assert report['linked_case_count'] == 5


def test_corrupt_ministry_pin_keeps_core_links_and_no_false_pending(prepared, tmp_path):
    workspaces, batches, _ = prepared
    batches[1].pin_file.unlink()
    before = fingerprint(tmp_path)
    report = query(workspaces)
    assert fingerprint(tmp_path) == before
    assert report['linked_case_count'] == 3 and not report['review_links_complete']
    ministry = [r for r in report['results'] if r['search_scope'] == 'motir']
    assert all(r['link_status'] == 'GOLD_DATA_UNAVAILABLE' for r in ministry)
    assert all(r['review_entry_argv'] is None for r in ministry)
    assert report['pending_unfrozen_count'] == 0


def test_pin_referencing_lost_batch_is_not_treated_as_unfrozen(prepared, tmp_path):
    import shutil
    workspaces, batches, _ = prepared
    shutil.rmtree(batches[1].folder)
    report = query(workspaces)
    assert report['linked_case_count'] == 3
    assert all(r['link_status'] == 'GOLD_DATA_UNAVAILABLE'
               for r in report['results'] if r['search_scope'] == 'motir')
    assert not batches[1].folder.exists()


def test_missing_selected_workspace_never_created(prepared, tmp_path):
    workspaces, _, _ = prepared
    absent = tmp_path / 'absent_review_space'
    workspaces = (workspaces[0], replace(workspaces[1], workspace_root=absent))
    report = query(workspaces)
    assert report['linked_case_count'] == 3 and not absent.exists()
    assert all(r['link_status'] == 'REVIEW_ENTRY_UNAVAILABLE'
               for r in report['results'] if r['search_scope'] == 'motir')


def test_never_reads_other_reviewers_answers(prepared, tmp_path):
    workspaces, batches, _ = prepared
    for workspace, batch in zip(workspaces, batches):
        (workspace.workspace_root / batch.folder.name / 'UNASSIGNED_B' / 'answers.json').unlink()
    before = fingerprint(tmp_path)
    report = query(workspaces)
    assert report['linked_case_count'] == 5 and report['review_links_complete']
    assert fingerprint(tmp_path) == before
    assert not report['other_reviewer_answers_exposed']


def test_revoked_source_is_not_exposed_from_old_gold(prepared):
    workspaces, _, registries = prepared
    revoked = ProviderRegistry(tuple(replace(p, approved=False) if p.provider_id == WIRE
                                     else p for p in registries[0].providers))
    write_registry(workspaces[0].source.registry_path, revoked)
    report = query(workspaces)
    assert WIRE not in {r['provider_id'] for r in report['results']}
    assert report['linked_case_count'] == 4


def test_future_pin_refused_before_link(prepared):
    workspaces, batches, _ = prepared
    content = json.loads(batches[1].pin_file.read_bytes())
    content['first_local_observed_at'] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    batches[1].pin_file.write_text(json.dumps(content))
    report = query(workspaces)
    assert report['linked_case_count'] == 3
    assert all(r['link_status'] == 'GOLD_DATA_UNAVAILABLE'
               for r in report['results'] if r['search_scope'] == 'motir')


def test_empty_search_does_not_open_or_create_gold_workspaces(prepared, monkeypatch, tmp_path):
    workspaces, _, _ = prepared
    monkeypatch.setattr(bridge, '_pinned_case_index', lambda *_: pytest.fail('unexpected gold lookup'))
    before = fingerprint(tmp_path)
    report = bridge.search_gold_review_links(workspaces, 'NOT_PRESENT_QUERY',
                registry_reader=_registry, slot='UNASSIGNED_A')
    assert report['results'] == [] and report['linked_case_count'] == 0
    assert fingerprint(tmp_path) == before


def cli_options(workspaces, scope='all'):
    args = ['--scope', scope, '--query', '반도체', '--review-links',
            '--reviewer-slot', 'UNASSIGNED_A']
    for workspace in workspaces:
        prefix = '--motir-' if workspace.source.scope == 'motir' else '--'
        for name, value in (
            ('registry', workspace.source.registry_path), ('state', workspace.source.poll_state),
            ('inbox-root', workspace.source.inbox_root), ('gold-out-root', workspace.out_root),
            ('gold-pin-root', workspace.pin_root), ('review-workspace-root', workspace.workspace_root),
        ):
            args += [prefix + name, str(value)]
    return search_news.parser().parse_args(args)


def test_search_cli_exact_link_arguments_and_both_scopes(prepared):
    workspaces, _, _ = prepared
    for scope, count in [('core', 3), ('motir', 2), ('all', 5)]:
        code, report = search_news.evaluate(cli_options(workspaces, scope))
        assert code == 0 and report['linked_case_count'] == count
        for item in report['results']:
            args = item['review_entry_argv'][4:] + ['--reviewer-code', 'REVIEWER_A']
            parsed = review_news_interactive.parser().parse_args(args)
            assert parsed.case_sha256 == item['case_sha256']
            assert parsed.batch_sha256 == item['batch_sha256']
    opts = cli_options(workspaces)
    opts.reviewer_slot = None
    code, report = search_news.evaluate(opts)
    assert code == 4 and report['status'] == 'SEARCH_DATA_UNAVAILABLE'


def test_cli_reports_missing_pin_as_partial_not_success(prepared):
    workspaces, batches, _ = prepared
    batches[1].pin_file.unlink()
    code, report = search_news.evaluate(cli_options(workspaces))
    assert code == 4 and report['linked_case_count'] == 3


def test_exact_case_entry_does_not_review_first_or_already_submitted_case(prepared):
    workspaces, batches, _ = prepared
    workspace, batch = workspaces[0], batches[0]
    page = list_review_cases(workspace.out_root, workspace.pin_root, workspace.workspace_root,
                             batch.payload_sha256, 'UNASSIGNED_A', limit=25)
    target = page['cases'][-1]  # deliberately NOT the first case
    args = bridge._entry_arguments(workspace, batch.payload_sha256,
                                    target['case_sha256'], 'UNASSIGNED_A')[4:]
    opts = review_news_interactive.parser().parse_args(args + ['--reviewer-code', 'REVIEWER_A'])
    answer_a = workspace.workspace_root / batch.folder.name / 'UNASSIGNED_A' / 'answers.json'
    answer_b = workspace.workspace_root / batch.folder.name / 'UNASSIGNED_B' / 'answers.json'
    other_before = answer_b.read_bytes()
    frozen_before = (batch.folder / 'predictions.json').read_bytes()
    replies = iter(['yes', 'no', 'yes', 'Synthetic human reviewed the approved source independently.', 'yes'])
    shown = []
    code, report = review_news_interactive.run_one(
        opts, input_func=lambda _: next(replies), output_func=lambda *line: shown.append(line))
    assert code == 0 and report['case_sha256'] == target['case_sha256']
    answered = [row for row in json.loads(answer_a.read_bytes())['labels']
                if row['true_duplicate'] is not None]
    assert len(answered) == 1 and answered[0]['case_sha256'] == target['case_sha256']
    assert answer_b.read_bytes() == other_before
    assert (batch.folder / 'predictions.json').read_bytes() == frozen_before
    assert ('Headline:', target['headline']) in shown
    after = answer_a.read_bytes()
    code, report = review_news_interactive.run_one(
        opts, input_func=lambda _: pytest.fail('must not prompt another case'), output_func=lambda *_: None)
    assert code == 0 and report['status'] == 'SELECTED_CASE_ALREADY_SUBMITTED'
    assert report['human_labels_added'] == 0 and report['remaining'] == batch.sample_count - 1
    assert answer_a.read_bytes() == after


def test_unknown_target_does_not_fall_back_or_write(prepared, tmp_path):
    workspaces, batches, _ = prepared
    workspace, batch = workspaces[0], batches[0]
    opts = review_news_interactive.parser().parse_args(
        bridge._entry_arguments(workspace, batch.payload_sha256, 'f' * 64, 'UNASSIGNED_A')[4:]
        + ['--reviewer-code', 'REVIEWER_A'])
    before = fingerprint(tmp_path)
    code, report = review_news_interactive.run_one(
        opts, input_func=lambda _: pytest.fail('unknown target prompted'), output_func=lambda *_: None)
    assert code == 4 and report['human_labels_added'] == 0
    assert fingerprint(tmp_path) == before


def test_partial_target_answer_is_not_claimed_submitted(prepared):
    workspaces, batches, _ = prepared
    workspace, batch = workspaces[0], batches[0]
    case = list_review_cases(workspace.out_root, workspace.pin_root, workspace.workspace_root,
                             batch.payload_sha256, 'UNASSIGNED_A')['cases'][0]['case_sha256']
    answers = workspace.workspace_root / batch.folder.name / 'UNASSIGNED_A' / 'answers.json'
    content = json.loads(answers.read_bytes())
    next(r for r in content['labels'] if r['case_sha256'] == case)['true_duplicate'] = True
    answers.write_text(json.dumps(content))
    with pytest.raises(SourceShareError, match='incomplete'):
        list_review_cases(workspace.out_root, workspace.pin_root, workspace.workspace_root,
                          batch.payload_sha256, 'UNASSIGNED_A', case_sha256=case)


def test_inaccurate_search_blind_join_refused(prepared, monkeypatch):
    workspaces, _, _ = prepared
    original = bridge.search_completed_workspaces
    def wrong(*args, **kwargs):
        report = original(*args, **kwargs)
        report['results'][0]['headline'] += ' false metadata'
        return report
    monkeypatch.setattr(bridge, 'search_completed_workspaces', wrong)
    report = query(workspaces)
    bad = [row for row in report['results'] if row['headline'].endswith(' false metadata')]
    assert len(bad) == 1 and bad[0]['link_status'] == 'REVIEW_ENTRY_UNAVAILABLE'
    assert bad[0]['batch_sha256'] is None and bad[0]['review_entry_argv'] is None


def test_missing_gold_directory_is_never_created(prepared, tmp_path):
    workspaces, _, _ = prepared
    absent = tmp_path / 'no_gold_root'
    changed = (workspaces[0], replace(workspaces[1], out_root=absent))
    report = query(changed)
    assert not absent.exists() and report['linked_case_count'] == 3


@pytest.mark.parametrize('slot', [None, 'A', 'UNASSIGNED_C'])
def test_explicit_valid_reviewer_slot_required(prepared, slot):
    with pytest.raises(SourceShareError, match='slot'):
        bridge.search_gold_review_links(prepared[0], '반도체', registry_reader=_registry, slot=slot)


def test_submitted_slot_hidden_and_other_slot_still_independent(prepared):
    workspaces, _, _ = prepared
    item = query(workspaces)['results'][0]
    args = item['review_entry_argv'][4:] + ['--reviewer-code', 'REVIEWER_A']
    opts = review_news_interactive.parser().parse_args(args)
    answers = iter(['yes', 'no', 'yes', 'Synthetic reviewer checked the source; not live human evidence.', 'yes'])
    code, _ = review_news_interactive.run_one(
        opts, input_func=lambda _: next(answers), output_func=lambda *_: None)
    assert code == 0
    report_a = query(workspaces)
    submitted = next(r for r in report_a['results'] if r['case_sha256'] == item['case_sha256'])
    assert submitted['link_status'] == 'SELECTED_SLOT_ALREADY_SUBMITTED'
    assert submitted['review_entry_argv'] is None and report_a['linked_case_count'] == 5
    assert report_a['ready_for_selected_reviewer_count'] == 4
    report_b = bridge.search_gold_review_links(workspaces, '반도체',
                  registry_reader=_registry, slot='UNASSIGNED_B')
    assert report_b['ready_for_selected_reviewer_count'] == 5
    assert 'REVIEWER_A' not in json.dumps(report_b)
    assert 'true_duplicate' not in json.dumps(report_a)


def test_global_limit_not_misreported_as_all_candidates(prepared):
    report = query(prepared[0], limit=1)
    assert report['matched_document_versions'] == 5
    assert report['returned_case_count'] == report['linked_case_count'] == 1
    assert report['has_more_matches']


def test_damaged_source_keeps_only_healthy_source_review_links(prepared):
    workspaces, _, _ = prepared
    workspaces[1].source.registry_path.unlink()
    code, report = search_news.evaluate(cli_options(workspaces))
    assert code == 4 and not report['coverage_complete']
    assert report['linked_case_count'] == 3
    assert all(r['search_scope'] == 'core' for r in report['results'])
