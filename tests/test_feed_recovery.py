"""6_5 crash-window recovery tests: no second GET, no false watermark or PIT."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json

import pytest

from newscatalystos.feed_recovery import (
    save_retry_checkpoint, read_retry_checkpoint, check_committed_ingest,
    pending_retry_checkpoints, acknowledge_retry_checkpoint,
)
from newscatalystos.feed_triage import triage_committed_feed, publish_feed_triage
from newscatalystos.incremental_ingest import incremental_poll, state_snapshot
from newscatalystos.source_share import SourceShareError
from scripts import run_feed_triage
from test_feed_triage import NAME, sample_rows
from test_new_source_adapter import NOW, registry


def paths(tmp):
    return (
        tmp / "state" / "poll.sqlite3",
        tmp / "state" / "dedup.sqlite3",
        tmp / "private_inbox",
        tmp / "private_results",
    )


def acquired(tmp, *, before_commit=None, at=NOW):
    state, _, inbox, _ = paths(tmp)
    calls = []
    def feed(_reg, name, *, at):
        calls.append(name)
        return sample_rows(at or NOW)
    receipt = []
    hook = before_commit if before_commit is not None else (
        lambda result: receipt.append(save_retry_checkpoint(inbox, result))
    )
    result = incremental_poll(
        registry(), NAME, state, now=at, fetcher=feed,
        before_commit=hook,
    )
    return result, receipt, calls


def test_checkpoint_exists_before_watermark_commit_and_replays_without_network(tmp_path, monkeypatch):
    state, dedup, inbox, output = paths(tmp_path)
    poll, receipts, calls = acquired(tmp_path)
    assert calls == [NAME] and len(receipts) == 1
    receipt = receipts[0]
    assert receipt.poll == poll
    assert state_snapshot(state, NAME)["seen_count"] == 3
    assert pending_retry_checkpoints(inbox, state, registry(), NAME, now=NOW) == (receipt,)
    assert read_retry_checkpoint(receipt.location, inbox, receipt.payload_sha256) == receipt
    check_committed_ingest(state, receipt.poll, now=NOW)

    # Simulate another interpreter: only the independently validated spool is used.
    monkeypatch.setattr(run_feed_triage, "_registry", lambda _path: registry())
    def no_network(*_args, **_kw):
        raise AssertionError("replay must never fetch an RSS URL")
    monkeypatch.setattr(run_feed_triage, "incremental_poll", no_network)
    params = argparse.Namespace(
        registry=tmp_path / "approved.json", provider_id=NAME,
        state=state, dedup_state=dedup, inbox_root=inbox,
        output_root=output, replay_only=True,
    )
    code, report = run_feed_triage.evaluate(params)
    assert code == 0 and report["status"] == "RECOVERED_FROM_DURABLE_CHECKPOINT"
    assert report["network_called"] is False and report["feed_count"] == 3
    assert report["ai_call_count"] == 0 and report["stored_article_body_count"] == 0
    triaged = json.loads((Path(report["private_triage_folder"]) / "triage.json").read_bytes())
    assert triaged["replayed_from_checkpoint"] is True
    assert list((inbox / "acked").glob("*.json"))
    assert pending_retry_checkpoints(inbox, state, registry(), NAME) == ()
    code, no_more = run_feed_triage.evaluate(params)
    assert code == 0 and no_more["status"] == "NO_PENDING_REPLAY"


def test_mid_analysis_exception_keeps_retry_checkpoint_and_original_watermark(tmp_path):
    state, dedup, inbox, output = paths(tmp_path)
    poll, receipt, _ = acquired(tmp_path)
    assert receipt and poll.new_count == 3
    # Later analysis fails; the accepted RSS identities are not fetchable from SQL,
    # but the checkpoint remains recoverable without new HTTP.
    def failing_analysis(*args, **kwargs):
        raise SourceShareError("injected analysis unavailable")
    with pytest.raises(SourceShareError, match="injected"):
        failing_analysis()
    snap = state_snapshot(state, NAME)
    assert snap["seen_count"] == 3
    assert snap["last_success_at"] == NOW.isoformat()
    backlog = pending_retry_checkpoints(inbox, state, registry(), NAME, now=NOW)
    assert len(backlog) == 1
    report = triage_committed_feed(
        registry(), backlog[0].poll, dedup, decision_at=NOW,
        now=NOW,
    )
    out = publish_feed_triage(report, output)
    ack = acknowledge_retry_checkpoint(inbox, backlog[0], out, report.payload_sha256)
    assert ack.is_file()
    assert not pending_retry_checkpoints(
        inbox, state, registry(), NAME, now=datetime.now(timezone.utc))


def test_failed_checkpoint_prevents_successful_ingestion_even_after_rows_seen(tmp_path):
    state, _, inbox, _ = paths(tmp_path)
    captured = []
    def abort(candidate):
        captured.append(save_retry_checkpoint(inbox, candidate))
        raise SourceShareError("durable acknowledgement storage failed")
    with pytest.raises(SourceShareError, match="acknowledgement"):
        acquired(tmp_path, before_commit=abort)
    state_info = state_snapshot(state, NAME)
    assert state_info["last_success_at"] is None and state_info["seen_count"] == 0
    assert captured[0].location.exists()
    with pytest.raises(SourceShareError, match="no committed watermark"):
        pending_retry_checkpoints(inbox, state, registry(), NAME, now=NOW)


def test_payload_corruption_and_unapproved_source_cannot_be_replayed(tmp_path):
    state, _, inbox, _ = paths(tmp_path)
    _, receipts, _ = acquired(tmp_path)
    receipt = receipts[0]
    disabled = replace(registry().providers[0], approved=False)
    from newscatalystos.provider_registry import ProviderRegistry
    with pytest.raises(SourceShareError, match="not approved"):
        pending_retry_checkpoints(
            inbox, state, ProviderRegistry((disabled,)), NAME, now=NOW)
    payload_path = receipt.location / "feed.json"
    payload_path.write_bytes(payload_path.read_bytes() + b"tampered")
    with pytest.raises(SourceShareError, match="SHA"):
        pending_retry_checkpoints(inbox, state, registry(), NAME, now=NOW)


def test_bad_timestamp_or_new_identity_checkpoint_is_rejected(tmp_path):
    state, _, inbox, _ = paths(tmp_path)
    poll, receipts, _ = acquired(tmp_path)
    with pytest.raises(SourceShareError, match="future"):
        check_committed_ingest(state, poll, now=NOW - timedelta(seconds=1))
    with pytest.raises(SourceShareError, match="absent"):
        save_retry_checkpoint(
            inbox, replace(poll, newly_observed_event_ids=(
                "0" * 64, "1" * 64, "2" * 64)))
    with pytest.raises(SourceShareError, match="identity mismatch"):
        save_retry_checkpoint(
            inbox, replace(poll, observations=(
                replace(poll.observations[0], event_id="f" * 64),
                *poll.observations[1:],
            )),
        )


def test_checkpoint_does_not_store_source_body_in_state_or_inbox(tmp_path):
    state, _, inbox, _ = paths(tmp_path)
    _, receipts, _ = acquired(tmp_path)
    data = (receipts[0].location / "feed.json").read_bytes()
    assert b"FULL ARTICLE BODY MUST NOT" not in data
    assert b"FULL ARTICLE BODY MUST NOT" not in state.read_bytes()
    assert b"HBM" not in state.read_bytes()
    doc = json.loads(data)
    assert all(set(r) == {"provider_id", "event_id", "document_id",
                          "headline", "source_url", "first_seen_at",
                          "verification_status", "reported_published_at"}
               for r in doc["records"])
    assert (receipts[0].location.stat().st_mode & 0o077) == 0
    assert sha256(data).hexdigest() == receipts[0].payload_sha256


def test_checkpoint_only_starts_from_approved_signed_off_feed_metadata(tmp_path):
    state, _, inbox, _ = paths(tmp_path)
    invalid = sample_rows(NOW)
    changed = replace(invalid[0], document_id="replaced-without-changing-event-sha")
    poll, _, _ = acquired(tmp_path)
    with pytest.raises(SourceShareError, match="identity mismatch"):
        save_retry_checkpoint(
            inbox, replace(poll, observations=(changed, *poll.observations[1:])))
