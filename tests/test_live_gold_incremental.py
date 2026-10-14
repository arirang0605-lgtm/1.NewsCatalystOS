"""2_6/3_6: prospective new-only RSS gold batches preserve old frozen work.

Synthetic additions here verify integrity and non-overlap, NOT real gold labels.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from copy import deepcopy
import json

import pytest

from newscatalystos import live_gold_samples as gold
from newscatalystos.source_share import SourceShareError
from test_live_gold_samples import saved
from test_new_source_adapter import registry
from scripts import run_gold_review


def with_new_item(monkeypatch, inbox, state):
    original_rows = gold._rows
    def patched(reg, path, db, at):
        actual = list(original_rows(reg, path, db, at))
        assert actual
        ack, triage, source = actual[0]
        item = deepcopy(source)
        item["event_id"] = sha256(b"independent-new-rss-event").hexdigest()
        item["title_sha256"] = sha256(b"independent-new-rss-title").hexdigest()
        item["headline"] = "New observed feed title - synthetic"
        return tuple(actual + [(ack, triage, item)])
    monkeypatch.setattr(gold, "_rows", patched)


def test_incremental_freeze_only_unseen_preserves_original_batch(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    first_predict_bytes = (first.folder / "predictions.json").read_bytes()
    first_pin_bytes = first.pin_file.read_bytes()
    with_new_item(monkeypatch, inbox, state)
    new = gold.freeze_real_gold_review_cases(
        registry(), inbox, state, out, pins, incremental_only=True,
    )
    assert new.sample_count == 1
    assert new.prior_frozen_case_count == 3
    assert new.payload_sha256 != first.payload_sha256
    assert first.folder.exists() and first.pin_file.exists()
    assert (first.folder / "predictions.json").read_bytes() == first_predict_bytes
    assert first.pin_file.read_bytes() == first_pin_bytes
    original, _ = gold._load_pinned_predictions(
        first.folder, out, first.payload_sha256, first.pin_file, pins,
        datetime.now(timezone.utc),
    )
    fresh, _ = gold._load_pinned_predictions(
        new.folder, out, new.payload_sha256, new.pin_file, pins,
        datetime.now(timezone.utc),
    )
    assert not set(x.case_sha256 for x in original).intersection(
        x.case_sha256 for x in fresh)
    assert json.loads((new.folder / "predictions.json").read_bytes())[
        "prior_frozen_batch_sha256s"] == [first.payload_sha256]
    # Every case now exists in a pinned batch. No new freeze or overwrite.
    with pytest.raises(SourceShareError, match="no new verified"):
        gold.freeze_real_gold_review_cases(
            registry(), inbox, state, out, pins, incremental_only=True)
    assert len(list(out.glob("gold_batch_*"))) == 2


def test_corrupted_or_unpinned_old_batch_blocks_incremental_freeze(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    with_new_item(monkeypatch, inbox, state)
    first.pin_file.unlink()
    with pytest.raises(SourceShareError):
        gold.freeze_real_gold_review_cases(
            registry(), inbox, state, out, pins, incremental_only=True)
    assert len(list(out.glob("gold_batch_*"))) == 1


def test_tampered_predictions_refuse_incremental_even_if_new_rows_exist(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    with_new_item(monkeypatch, inbox, state)
    f = first.folder / "predictions.json"
    f.write_bytes(f.read_bytes() + b"changed")
    with pytest.raises(SourceShareError, match="SHA"):
        gold.freeze_real_gold_review_cases(
            registry(), inbox, state, out, pins, incremental_only=True)


def test_two_overlapping_historical_batches_refuse_cumulative_counts(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    # Legacy default freeze all is unchanged; overlapping historical case sets
    # must never be added together and misrepresented as distinct labels.
    gold.freeze_real_gold_review_cases(registry(), inbox, state, out, pins)
    with pytest.raises(SourceShareError, match="overlapping historical"):
        gold.freeze_real_gold_review_cases(
            registry(), inbox, state, out, pins, incremental_only=True)


def test_cli_new_only_reports_cumulative_cases_without_labels(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    with_new_item(monkeypatch, inbox, state)
    monkeypatch.setattr(run_gold_review, "_registry", lambda _unused: registry())
    from argparse import Namespace
    code, payload = run_gold_review.evaluate(Namespace(
        command="freeze", registry=tmp_path / "unused.json",
        state=state, inbox_root=inbox, out_root=out, pin_root=pins,
        new_only=True,
    ))
    assert code == 0
    assert payload["case_count"] == 1
    assert payload["prior_frozen_case_count"] == 3
    assert payload["cumulative_unique_frozen_case_count"] == 4
    assert payload["remaining_cases_to_500"] == 496
    assert payload["human_gold_labeled_cases"] == 0
    assert payload["release_gate_verified"] is False
    assert payload["ai_calls"] == payload["new_provider_requests"] == 0


def test_cli_new_only_flag_is_explicit(tmp_path):
    parser = run_gold_review.parser()
    opts = parser.parse_args(["freeze", "--new-only"])
    assert opts.new_only is True
    assert parser.parse_args(["freeze"]).new_only is False


def test_progress_reports_new_live_cases_without_writing_or_claiming_gold(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    with_new_item(monkeypatch, inbox, state)
    previous = set(out.iterdir())
    progress = gold.gold_freeze_progress(registry(), inbox, state, out, pins)
    assert progress["historical_sha_pinned_batches"] == 1
    assert progress["distinct_sha_pinned_cases"] == 3
    assert progress["eligible_current_source_cases"] == 4
    assert progress["new_unfrozen_cases"] == 1
    assert progress["remaining_to_500_if_frozen"] == 496
    assert progress["independent_human_gold_labeled_cases"] == 0
    assert out.exists() and set(out.iterdir()) == previous
    assert progress["release_gate_verified"] is False
    new = gold.freeze_real_gold_review_cases(
        registry(), inbox, state, out, pins, incremental_only=True,
    )
    updated = gold.gold_freeze_progress(registry(), inbox, state, out, pins)
    assert updated["distinct_sha_pinned_cases"] == 4
    assert updated["new_unfrozen_cases"] == 0
    assert updated["remaining_to_500_if_frozen"] == 496
    assert new.folder.exists()


def test_progress_never_skips_unpinned_historical_batch(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    first.pin_file.unlink()
    with pytest.raises(SourceShareError):
        gold.gold_freeze_progress(registry(), inbox, state, out, pins)


def test_progress_cli_works_without_mutating_gold_folders(tmp_path, monkeypatch):
    state, inbox, out, pins, first = saved(tmp_path, monkeypatch)
    monkeypatch.setattr(run_gold_review, "_registry", lambda _: registry())
    from argparse import Namespace
    params = Namespace(
        command="progress", registry=tmp_path / "not-read.json",
        state=state, inbox_root=inbox, out_root=out, pin_root=pins,
    )
    contents_before = (first.folder / "predictions.json").read_bytes()
    code, result = run_gold_review.evaluate(params)
    assert code == 0 and result["distinct_sha_pinned_cases"] == 3
    assert result["new_unfrozen_cases"] == 0
    assert (first.folder / "predictions.json").read_bytes() == contents_before
    assert run_gold_review.parser().parse_args(["progress"]).command == "progress"
