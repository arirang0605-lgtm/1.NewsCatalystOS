"""6_5 operational receipts reflect real completed local work, not trading-day certification."""
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from newscatalystos.feed_operations import operation_status
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.feed_recovery import (
    pending_retry_checkpoints, acknowledge_retry_checkpoint,
)
from newscatalystos.feed_triage import triage_committed_feed, publish_feed_triage
from newscatalystos.source_share import SourceShareError
from test_feed_recovery import acquired, paths, NAME
from test_new_source_adapter import registry


def completed(tmp_path):
    state, dedup, inbox, output = paths(tmp_path)
    poll, receipts, _ = acquired(tmp_path)
    receipt = receipts[0]
    now = datetime.now(timezone.utc)
    triage = triage_committed_feed(
        registry(), poll, dedup, decision_at=now, now=now,
    )
    folder = publish_feed_triage(triage, output)
    ack = acknowledge_retry_checkpoint(inbox, receipt, folder, triage.payload_sha256)
    return state, inbox, output, receipt, ack, folder


def test_no_runs_does_not_claim_five_trading_days(tmp_path):
    state, _, inbox, _ = paths(tmp_path)
    record = operation_status(registry(), inbox, state)
    assert record["status"] == "OPERATIONS_IN_PROGRESS"
    assert record["completed_triage_receipts"] == 0
    assert record["daily_source_coverage"] == []
    assert record["partial_source_days"] == []
    assert record["pending_recovery_checkpoints"] == 0
    assert record["verified_exchange_trading_days"] == 0
    assert not record["five_trading_day_operation_certified"]
    assert not record["v1_release_ready"]


def test_completed_local_run_is_recorded_but_not_certified_market_day(tmp_path):
    state, inbox, output, receipt, ack, folder = completed(tmp_path)
    report = operation_status(registry(), inbox, state)
    assert report["approved_source_count"] == 1
    assert report["completed_triage_receipts"] == 1
    assert len(report["days_with_all_sources"]) == 1
    assert report["daily_source_coverage"] == [{
        "date": report["days_with_all_sources"][0],
        "completed_sources": [NAME],
        "missing_sources": [],
    }]
    assert report["partial_source_days"] == []
    assert report["pending_recovery_checkpoints"] == 0
    assert report["verified_exchange_trading_days"] == 0
    assert report["five_trading_day_operation_certified"] is False
    assert report["independent_physical_recovery_verified"] is False
    assert report["v1_release_ready"] is False
    audit = json.loads(ack.read_bytes())
    assert audit["checkpoint_sha256"] == receipt.payload_sha256
    assert audit["provider_id"] == NAME
    assert audit["record_count"] == 3
    assert audit["triage_folder"] == str(folder)


def test_operations_report_rejects_tampered_result_or_ack(tmp_path):
    state, inbox, output, receipt, ack, folder = completed(tmp_path)
    data = (folder / "triage.json").read_bytes()
    (folder / "triage.json").write_bytes(data + b"corrupt")
    with pytest.raises(SourceShareError, match="corrupted|invalid JSON"):
        operation_status(registry(), inbox, state)
    (folder / "triage.json").write_bytes(data)
    doc = json.loads(ack.read_bytes())
    doc["provider_id"] = "forged-provider"
    ack.write_text(json.dumps(doc))
    # A forged provider cannot mark a real pending checkpoint as completed.
    with pytest.raises(SourceShareError, match="corrupted"):
        operation_status(registry(), inbox, state)


def test_completed_status_never_doubles_from_repeat_check(tmp_path):
    state, inbox, _, _, _, _ = completed(tmp_path)
    first = operation_status(registry(), inbox, state)
    second = operation_status(registry(), inbox, state)
    assert first["completed_triage_receipts"] == 1
    assert second["completed_triage_receipts"] == 1


def test_partial_approved_provider_day_is_visible_without_fake_certification(tmp_path):
    state, inbox, _, _, _, _ = completed(tmp_path)
    original = registry()
    extra = replace(
        original.providers[0],
        provider_id="synthetic-other-approved",
        endpoint="https://another.example.org/feed",
    )
    both = ProviderRegistry(original.providers + (extra,))
    report = operation_status(both, inbox, state)
    assert report["approved_source_count"] == 2
    assert report["days_with_all_sources"] == []
    assert len(report["daily_source_coverage"]) == 1
    entry = report["daily_source_coverage"][0]
    assert entry["completed_sources"] == [NAME]
    assert entry["missing_sources"] == ["synthetic-other-approved"]
    assert report["partial_source_days"] == [entry["date"]]
    assert report["weekday_candidate_count"] == 0
    assert report["verified_exchange_trading_days"] == 0
    assert report["five_trading_day_operation_certified"] is False


def test_physical_dr_flag_requires_both_live_operational_state_pins(
    tmp_path, monkeypatch,
):
    from newscatalystos import feed_operations
    from newscatalystos.physical_recovery import ALLOWED
    state, _, inbox, _ = paths(tmp_path)
    physical = tmp_path / "pins"
    backups = tmp_path / "backup"
    monkeypatch.setattr(
        feed_operations, "checked_local_recovery_sources",
        lambda pin_root, backup_root: frozenset({"incremental_feeds.sqlite3"}),
    )
    partial = operation_status(
        registry(), inbox, state, physical_pin_root=physical, backup_root=backups,
    )
    assert partial["local_recovery_source_count"] == 1
    assert not partial["independent_physical_recovery_verified"]
    monkeypatch.setattr(
        feed_operations, "checked_local_recovery_sources",
        lambda pin_root, backup_root: frozenset(ALLOWED),
    )
    complete = operation_status(
        registry(), inbox, state, physical_pin_root=physical, backup_root=backups,
    )
    assert complete["independent_physical_recovery_verified"] is True
    assert complete["local_recovery_source_count"] == 2
    assert complete["offsite_backup_verified"] is False
    assert complete["five_trading_day_operation_certified"] is False
    assert complete["v1_release_ready"] is False
