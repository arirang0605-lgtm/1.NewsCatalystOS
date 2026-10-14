"""Prospective private RSS gold capture: synthetic ACKs, never human truth."""
import argparse
from datetime import datetime, timezone

import pytest

from newscatalystos import live_gold_samples as gold
from newscatalystos.source_share import SourceShareError
from scripts import run_gold_capture_once as auto
from test_feed_operations import completed
from test_live_gold_samples import saved
from test_new_source_adapter import registry

NOW = datetime.now(timezone.utc)


def opts(tmp_path, monkeypatch, *, already_frozen=False):
    monkeypatch.setattr(gold, "_different_disk", lambda *_: True)
    monkeypatch.setattr(auto, "V1_PROVIDERS", ("synthetic-government-feed",))
    if already_frozen:
        state, inbox, out, pins, batch = saved(tmp_path, monkeypatch)
    else:
        state, inbox, _, _, _, _ = completed(tmp_path)
        out, pins, batch = tmp_path / "gold_batches", tmp_path / "mac_pin", None
    return argparse.Namespace(
        registry=tmp_path / "not-used.json",
        inbox_root=inbox, state=state, out_root=out, pin_root=pins,
        workspace_root=tmp_path / "private_review_workspaces",
        lock_root=tmp_path / "lock",
    ), batch


def run(params, **kwargs):
    return auto.capture(params, registry_reader=lambda _: registry(), **kwargs)


def test_first_incremental_capture_is_sha_pinned_and_creates_only_blank_forms(tmp_path, monkeypatch):
    params, _ = opts(tmp_path, monkeypatch)
    code, report = run(params)
    assert code == 0
    assert report["status"] == "NEW_VERIFIED_RSS_CANDIDATES_FROZEN"
    assert report["newly_frozen_cases"] == 3
    assert report["created_blank_reviewer_workspaces"] == 1
    assert report["total_pinned_unique_cases"] == 3
    assert report["human_gold_labels_created"] == report["ai_calls"] == 0
    assert report["source_network_requests"] == 0
    assert not report["release_gate_verified"]
    workspace = next(params.workspace_root.iterdir())
    a = workspace / "UNASSIGNED_A" / "answers.json"
    b = workspace / "UNASSIGNED_B" / "answers.json"
    import json
    assert all(x["true_duplicate"] is None for x in json.loads(a.read_bytes())["labels"])
    assert all(x["important_event"] is None for x in json.loads(b.read_bytes())["labels"])
    original = a.read_bytes()
    again, status = run(params)
    assert again == 0 and status["newly_frozen_cases"] == 0
    assert status["created_blank_reviewer_workspaces"] == 0
    assert a.read_bytes() == original


def test_missed_blank_forms_are_recreated_only_when_batch_pin_is_verified(tmp_path, monkeypatch):
    params, _ = opts(tmp_path, monkeypatch)
    genuine = auto.prepare_blank_human_review_sheets
    def sim_crash(*args, **kwargs):
        raise SourceShareError("test: after pin before blank forms")
    with monkeypatch.context() as patch:
        patch.setattr(auto, "prepare_blank_human_review_sheets", sim_crash)
        code, response = run(params)
        assert code == 4
        assert response["human_gold_labels_created"] == 0
    assert len(list(params.out_root.glob("gold_batch_*"))) == 1
    assert not list(params.workspace_root.glob("gold_batch_*"))
    code, summary = run(params)
    assert code == 0 and summary["newly_frozen_cases"] == 0
    assert summary["created_blank_reviewer_workspaces"] == 1
    assert len(list(params.workspace_root.glob("gold_batch_*"))) == 1


def test_broken_pin_and_existing_partial_human_workspace_never_overwritten(tmp_path, monkeypatch):
    params, _ = opts(tmp_path, monkeypatch)
    assert run(params)[0] == 0
    folder = next(params.workspace_root.iterdir())
    b = folder / "UNASSIGNED_B" / "answers.json"
    b.unlink()
    code, report = run(params)
    assert code == 4 and report["status"] == "AUTOMATIC_GOLD_CAPTURE_UNAVAILABLE"
    assert not b.exists()
    pin = next(params.pin_root.glob("gold_batch_*.pin.json"))
    pin.unlink()
    code, report = run(params)
    assert code == 4 and report["release_gate_verified"] is False
    assert not b.exists()


def test_concurrent_run_is_denied_no_new_batch(tmp_path, monkeypatch):
    params, _ = opts(tmp_path, monkeypatch)
    fd = auto._lock(params.lock_root)
    try:
        code, response = run(params)
        assert code == 4
        assert response["status"] == "AUTOMATIC_GOLD_CAPTURE_UNAVAILABLE"
        assert not params.out_root.exists()
    finally:
        import fcntl, os
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    assert run(params)[0] == 0


def test_unapproved_registry_fails_before_lock_or_publish(tmp_path, monkeypatch):
    params, _ = opts(tmp_path, monkeypatch)
    monkeypatch.setattr(auto, "V1_PROVIDERS", ("different-source",))
    code, output = run(params)
    assert code == 4
    assert not params.lock_root.exists()
    assert not params.out_root.exists()
    assert output["source_network_requests"] == 0


def test_missing_old_pin_does_not_create_second_batch(tmp_path, monkeypatch):
    params, batch = opts(tmp_path, monkeypatch, already_frozen=True)
    batch.pin_file.unlink()
    code, output = run(params)
    assert code == 4
    assert len(list(params.out_root.glob("gold_batch_*"))) == 1
    assert output["human_gold_labels_created"] == 0
