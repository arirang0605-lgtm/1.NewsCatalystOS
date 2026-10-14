"""2_6/3_6 cross-batch metrics, no invented real reviewers or news cases."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from newscatalystos import live_gold_samples as gold
from newscatalystos.source_share import SourceShareError
from scripts import run_gold_review
from test_live_gold_incremental import saved, with_new_item
from test_live_gold_samples import fill
from test_new_source_adapter import registry


def two_batches(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    work = tmp_path / "review_workspaces"
    a, b = gold.prepare_blank_human_review_sheets(
        first.folder, out, first.payload_sha256, first.pin_file, pins, work)
    with_new_item(monkeypatch, inbox, state)
    new = gold.freeze_real_gold_review_cases(
        registry(), inbox, state, out, pins, incremental_only=True)
    c, d = gold.prepare_blank_human_review_sheets(
        new.folder, out, new.payload_sha256, new.pin_file, pins, work)
    return out, pins, work, first, new, (a,b), (c,d)


def actual_reviewer_code(path, code):
    doc = json.loads(path.read_bytes())
    doc["reviewer_code"] = code
    path.write_text(json.dumps(doc))
    path.chmod(0o600)


def test_real_unlabeled_batch_readonly_aggregation_does_not_invent_accuracy(
    tmp_path, monkeypatch
):
    out, pins, work, first, new, a, b = two_batches(tmp_path, monkeypatch)
    before = (first.folder / "predictions.json").read_bytes()
    report = gold.summarize_all_gold_reviews(out, pins, work)
    assert report["sha_pinned_batch_count"] == 2
    assert report["sample_count"] == 4
    assert report["reviewed_by_two_agreeing_humans"] == 0
    assert report["missing_or_partial_human_case_count"] == 4
    assert report["additional_frozen_cases_required"] == 496
    assert report["duplicate_precision"] is None
    assert report["important_event_recall"] is None
    assert report["release_gate_verified"] is False
    assert (first.folder / "predictions.json").read_bytes() == before


def test_aggregate_uses_count_weighting_not_mean_of_per_batch_percentages(
    tmp_path, monkeypatch
):
    out, pins, work, first, new, old_sheets, new_sheets = two_batches(tmp_path, monkeypatch)
    for target, code in zip(old_sheets, ("REVIEWER_A", "REVIEWER_B")):
        actual_reviewer_code(target, code)
        fill(target, datetime.now(timezone.utc), {
            0:(True, True), 1:(False, False), 2:(False, False)})
    for target, code in zip(new_sheets, ("REVIEWER_A", "REVIEWER_B")):
        actual_reviewer_code(target, code)
        fill(target, datetime.now(timezone.utc), {0:(True, True)})
    left = gold.evaluate_live_gold_reviews(
        first.folder, out, first.payload_sha256, first.pin_file, pins, old_sheets)
    right = gold.evaluate_live_gold_reviews(
        new.folder, out, new.payload_sha256, new.pin_file, pins, new_sheets)
    r = gold.summarize_all_gold_reviews(out, pins, work)
    assert r["sample_count"] == r["reviewed_by_two_agreeing_humans"] == 4
    assert r["missing_or_partial_human_case_count"] == 0
    assert r["duplicate_tp"] == left["duplicate_tp"] + right["duplicate_tp"]
    assert r["duplicate_fp"] == left["duplicate_fp"] + right["duplicate_fp"]
    expected_precision = (
        r["duplicate_tp"] / (r["duplicate_tp"] + r["duplicate_fp"])
        if r["duplicate_tp"] + r["duplicate_fp"] else None
    )
    assert r["duplicate_precision"] == expected_precision
    assert r["labeled_important_case_count"] == (
        left["labeled_important_case_count"] + right["labeled_important_case_count"])
    assert r["mathematical_threshold_met_on_supplied_labels"] is False
    assert r["reviewer_independence_certified"] is False


def test_missing_reviewer_sheet_refuses_aggregate_instead_of_fake_zero(
    tmp_path, monkeypatch
):
    out, pins, work, first, new, a, b = two_batches(tmp_path, monkeypatch)
    b[1].unlink()
    with pytest.raises((SourceShareError, OSError)):
        gold.summarize_all_gold_reviews(out, pins, work)


def test_tampered_old_pin_blocks_all_batches(tmp_path, monkeypatch):
    out, pins, work, first, new, a, b = two_batches(tmp_path, monkeypatch)
    first.pin_file.unlink()
    with pytest.raises(SourceShareError):
        gold.summarize_all_gold_reviews(out, pins, work)


def test_aggregate_cli_uses_existing_review_files_and_no_api(
    tmp_path, monkeypatch
):
    out, pins, work, first, new, a, b = two_batches(tmp_path, monkeypatch)
    opts = run_gold_review.parser().parse_args([
        "--out-root", str(out), "--pin-root", str(pins),
        "aggregate", "--workspace-root", str(work)])
    code, result = run_gold_review.evaluate(opts)
    assert code == 0 and result["sample_count"] == 4
    assert result["new_provider_requests"] == result["ai_calls"] == 0
    assert result["release_gate_verified"] is False


def test_overlapping_legacy_freeze_prevents_falsified_cumulative_accuracy(
    tmp_path, monkeypatch
):
    out, pins, work, first, new, a, b = two_batches(tmp_path, monkeypatch)
    # Legacy full snapshots can duplicate the same case. Never count those
    # same cases twice toward a claimed 500-case independent gold set.
    # Create an additional legacy whole-source snapshot, not a new-only one.
    # Its cases overlap existing pinned batches and must not inflate 500 target.
    from test_feed_operations import completed
    other = tmp_path / "other_feed"
    other.mkdir()
    state, inbox, _, _, _, _ = completed(other)
    gold.freeze_real_gold_review_cases(registry(), inbox, state, out, pins)
    with pytest.raises(SourceShareError, match="overlapping historical"):
        gold.summarize_all_gold_reviews(out, pins, work)
