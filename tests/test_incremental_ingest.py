"""1_3 offline incrementality, request budgets and durable failure isolation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

import pytest

from newscatalystos.feed_transport import FeedTransportError
from newscatalystos.incremental_ingest import incremental_poll, state_snapshot
from newscatalystos.new_source_adapter import FeedObservation, STATUS
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import registry, NOW

NAME = "synthetic-government-feed"


def reg(hourly_limit=2, enabled=True):
    base = registry(enabled)
    return ProviderRegistry((replace(base.providers[0], hourly_limit=hourly_limit),))


def state(tmp_path):
    return tmp_path / "state" / "incremental.sqlite3"


def item(at=NOW, id="a" * 64):
    return FeedObservation(
        provider_id=NAME, event_id=id,
        document_id="synthetic-id", headline="example",
        source_url="https://gov.example.org/entry",
        first_seen_at=at, reported_published_at=None, verification_status=STATUS,
    )


def fetch(rows, calls):
    def run(_registry, _name, *, at):
        calls.append((_name, at))
        return rows
    return run


def test_first_fetch_and_durable_duplicate_suppression(tmp_path):
    path = state(tmp_path)
    calls = []
    first = incremental_poll(reg(), NAME, path, now=NOW,
                             fetcher=fetch((item(),), calls))
    assert first.new_count == 1
    assert first.duplicate_count == 0
    assert first.watermark == NOW
    assert first.usable_from == NOW
    assert first.certified_raw_event_count == 0
    later = NOW + timedelta(minutes=31)
    second = incremental_poll(reg(), NAME, path, now=later,
                              fetcher=fetch((item(later),), calls))
    assert second.new_count == 0
    assert second.duplicate_count == 1
    assert len(calls) == 2
    snap = state_snapshot(path, NAME)
    assert snap["seen_count"] == 1
    assert snap["last_success_at"] == later.isoformat()
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(path.parent).st_mode & 0o777 == 0o700


def test_rate_limit_and_success_budget_are_persistent(tmp_path):
    path = state(tmp_path)
    calls = []
    incremental_poll(reg(), NAME, path, now=NOW,
                     fetcher=fetch((item(),), calls))
    with pytest.raises(SourceShareError, match="rate or backoff"):
        incremental_poll(reg(), NAME, path, now=NOW + timedelta(seconds=1),
                         fetcher=fetch((item(),), calls))
    assert len(calls) == 1
    later = NOW + timedelta(minutes=30)
    incremental_poll(reg(), NAME, path, now=later,
                     fetcher=fetch((item(later),), calls))
    with pytest.raises(SourceShareError, match="hourly"):
        incremental_poll(reg(), NAME, path, now=later + timedelta(seconds=2),
                         fetcher=fetch((item(),), calls))
    assert len(calls) == 2


def test_persistent_watcher_adds_only_new_event(tmp_path):
    path = state(tmp_path)
    incremental_poll(reg(), NAME, path, now=NOW, fetcher=fetch((item(),), []))
    later = NOW + timedelta(minutes=31)
    result = incremental_poll(
        reg(), NAME, path, now=later,
        fetcher=fetch((item(later), item(later, "b" * 64)), []),
    )
    assert result.new_count == 1
    assert result.duplicate_count == 1
    assert state_snapshot(path, NAME)["seen_count"] == 2


def test_transient_429_preserves_watermark_and_is_retryable_next_run(tmp_path):
    path = state(tmp_path)
    fast = reg(hourly_limit=10000)
    incremental_poll(fast, NAME, path, now=NOW, fetcher=fetch((item(),), []))
    later = NOW + timedelta(seconds=4)
    def throttled(*_args, **_kwargs):
        raise FeedTransportError("provider HTTP status 429", http_code=429)
    with pytest.raises(FeedTransportError):
        incremental_poll(fast, NAME, path, now=later, fetcher=throttled)
    snap = state_snapshot(path, NAME)
    assert snap["last_success_at"] == NOW.isoformat()
    assert snap["seen_count"] == 1
    assert snap["failure_count"] == 1
    with pytest.raises(SourceShareError, match="backoff"):
        incremental_poll(fast, NAME, path, now=later + timedelta(seconds=10),
                         fetcher=fetch((item(),), []))
    resumed_at = later + timedelta(seconds=61)
    result = incremental_poll(fast, NAME, path, now=resumed_at,
                              fetcher=fetch((item(resumed_at),), []))
    assert result.new_count == 0
    assert state_snapshot(path, NAME)["failure_count"] == 0


def test_http_403_permanent_block_without_changes_to_existing_rows(tmp_path):
    path = state(tmp_path)
    fast = reg(hourly_limit=10000)
    incremental_poll(fast, NAME, path, now=NOW, fetcher=fetch((item(),), []))
    def denied(*_args, **_kwargs):
        raise FeedTransportError("provider HTTP status 403", http_code=403)
    with pytest.raises(FeedTransportError):
        incremental_poll(fast, NAME, path, now=NOW + timedelta(seconds=2),
                         fetcher=denied)
    snap = state_snapshot(path, NAME)
    assert snap["status"] == "PERMISSION_BLOCKED"
    assert snap["seen_count"] == 1
    assert snap["last_success_at"] == NOW.isoformat()
    with pytest.raises(SourceShareError, match="blocked"):
        incremental_poll(fast, NAME, path, now=NOW + timedelta(days=5),
                         fetcher=fetch((item(),), []))


def test_no_era_source_or_expired_rights_can_reserve(tmp_path):
    calls = []
    path = state(tmp_path)
    with pytest.raises(SourceShareError, match="not approved"):
        incremental_poll(reg(enabled=False), NAME, path, now=NOW,
                         fetcher=fetch((item(),), calls))
    with pytest.raises(SourceShareError, match="not approved"):
        incremental_poll(reg(), "sec-submissions", path, now=NOW,
                         fetcher=fetch((item(),), calls))
    assert not calls
    assert not path.exists()


def test_future_row_cannot_advance_watermark_or_persist_fake_event(tmp_path):
    path = state(tmp_path)
    future = NOW + timedelta(days=1)
    with pytest.raises(SourceShareError, match="first-observation PIT"):
        incremental_poll(reg(), NAME, path, now=NOW,
                         fetcher=fetch((item(future),), []))
    snap = state_snapshot(path, NAME)
    assert snap["last_success_at"] is None
    assert snap["seen_count"] == 0


def test_state_directory_symlink_or_world_readable_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SourceShareError, match="owner-only"):
        incremental_poll(reg(), NAME, link / "test.sqlite3", now=NOW,
                         fetcher=fetch((item(),), []))
    outside.chmod(0o755)
    with pytest.raises(SourceShareError, match="owner-only"):
        incremental_poll(reg(), NAME, outside / "test.sqlite3", now=NOW,
                         fetcher=fetch((item(),), []))


def test_clock_backstep_fails_before_new_network_call(tmp_path):
    path = state(tmp_path)
    base = reg(hourly_limit=10000)
    old_review = ProviderRegistry((
        replace(base.providers[0], reviewed_at=NOW - timedelta(days=1)),
    ))
    incremental_poll(old_review, NAME, path, now=NOW,
                     fetcher=fetch((item(),), []))
    calls = []
    with pytest.raises(SourceShareError, match="clock"):
        incremental_poll(old_review, NAME, path,
                         now=NOW - timedelta(minutes=1),
                         fetcher=fetch((item(),), calls))
    assert calls == []


def test_403_unblock_requires_new_operator_rights_review(tmp_path):
    from newscatalystos.incremental_ingest import resume_after_rights_review
    path = state(tmp_path)
    basic = reg(hourly_limit=10000)
    blocked_at = NOW + timedelta(seconds=4)
    def denied(*_args, **_kwargs):
        raise FeedTransportError("provider HTTP status 403", http_code=403)
    with pytest.raises(FeedTransportError):
        incremental_poll(basic, NAME, path, now=blocked_at, fetcher=denied)
    with pytest.raises(SourceShareError, match="fresh operator rights review"):
        resume_after_rights_review(basic, NAME, path,
                                   now=blocked_at + timedelta(days=1))
    rechecked = ProviderRegistry((
        replace(basic.providers[0], reviewed_at=blocked_at + timedelta(hours=1)),
    ))
    assert resume_after_rights_review(
        rechecked, NAME, path, now=blocked_at + timedelta(hours=2)
    )
    assert state_snapshot(path, NAME)["status"] == "ACTIVE"
    later = blocked_at + timedelta(hours=2, seconds=1)
    restored = incremental_poll(rechecked, NAME, path, now=later,
                                fetcher=fetch((item(later),), []))
    assert restored.new_count == 1


def test_invalid_event_digest_rolls_back_success_state(tmp_path):
    path = state(tmp_path)
    invalid = replace(item(), event_id="NOT_SHA")
    with pytest.raises(SourceShareError, match="event digest"):
        incremental_poll(reg(), NAME, path, now=NOW,
                         fetcher=fetch((invalid,), []))
    state_info = state_snapshot(path, NAME)
    assert state_info["seen_count"] == 0
    assert state_info["last_success_at"] is None
