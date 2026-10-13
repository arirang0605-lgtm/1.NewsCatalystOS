"""1_6 quality monitoring and pending failure/recovery queue."""
from datetime import timedelta
import sqlite3

import pytest

from newscatalystos.incremental_ingest import incremental_poll
from newscatalystos.feed_transport import FeedTransportError
from newscatalystos.quality_watch import check_sources, unresolved_count
from newscatalystos.source_share import SourceShareError
from test_incremental_ingest import NAME, NOW, reg, state, fetch, item


def test_unseen_provider_is_pending_not_fabricated_complete(tmp_path):
    path = state(tmp_path)
    result = check_sources(reg(), path, now=NOW)
    assert len(result) == 1
    assert result[0].status == "NOT_COLLECTED"
    assert result[0].queue_status == "PENDING"
    assert unresolved_count(path) == 1
    assert check_sources(reg(), path, now=NOW)[0].incident_id == result[0].incident_id
    assert unresolved_count(path) == 1


def test_after_capture_pending_alert_is_resolved_not_erased(tmp_path):
    path = state(tmp_path)
    first = check_sources(reg(hourly_limit=10000), path, now=NOW)[0]
    incremental_poll(reg(hourly_limit=10000), NAME, path, now=NOW,
                     fetcher=fetch((item(),), []))
    later = NOW + timedelta(seconds=2)
    updated = check_sources(reg(hourly_limit=10000), path, now=later)[0]
    assert updated.status == "HEALTHY"
    assert updated.queue_status == "CLEAR"
    assert unresolved_count(path) == 0
    with sqlite3.connect(path) as conn:
        old = conn.execute(
            "SELECT first_reported_at,resolved_at FROM quality_incidents WHERE incident_id=?",
            (first.incident_id,),
        ).fetchone()
    assert old[0] and old[1]


def test_stale_and_missing_coverage_are_exposed(tmp_path):
    path = state(tmp_path)
    incremental_poll(reg(hourly_limit=10000), NAME, path, now=NOW,
                     fetcher=fetch((item(),), []))
    latest = NOW + timedelta(hours=5)
    report = check_sources(reg(hourly_limit=10000), path, now=latest)[0]
    assert report.status == "STALE"
    assert report.gap_seconds == 5 * 3600
    assert report.queue_status == "PENDING"
    assert unresolved_count(path) == 1


def test_access_denied_is_blocked_and_pending_not_completed(tmp_path):
    path = state(tmp_path)
    fast = reg(hourly_limit=10000)
    def denied(*a, **k):
        raise FeedTransportError("provider HTTP status 403", http_code=403)
    with pytest.raises(FeedTransportError):
        incremental_poll(fast, NAME, path, now=NOW, fetcher=denied)
    report = check_sources(fast, path, now=NOW + timedelta(seconds=10))[0]
    assert report.status == "AUTH_BLOCKED"
    assert report.queue_status == "PENDING"
    assert report.last_success_at is None


def test_429_retry_is_pending_and_recovery_resolves_gap(tmp_path):
    path = state(tmp_path)
    fast = reg(hourly_limit=10000)
    def denied(*a, **k):
        raise FeedTransportError("provider HTTP status 429", http_code=429)
    with pytest.raises(FeedTransportError):
        incremental_poll(fast, NAME, path, now=NOW, fetcher=denied)
    check_at = NOW + timedelta(seconds=5)
    incident = check_sources(fast, path, now=check_at)[0]
    assert incident.status == "RETRY_PENDING"
    assert unresolved_count(path) == 1
    later = NOW + timedelta(seconds=65)
    incremental_poll(fast, NAME, path, now=later,
                     fetcher=fetch((item(later),), []))
    recovered = check_sources(fast, path, now=later)[0]
    assert recovered.status == "HEALTHY"
    assert unresolved_count(path) == 0


def test_empty_feed_never_advances_watermark(tmp_path):
    path = state(tmp_path)
    with pytest.raises(SourceShareError, match="empty feed"):
        incremental_poll(reg(), NAME, path, now=NOW, fetcher=fetch((), []))
    status = check_sources(reg(), path, now=NOW)[0]
    assert status.status == "RETRY_PENDING"
    assert status.last_success_at is None
    assert unresolved_count(path) == 1


def test_unapproved_provider_not_counted_as_missing_capture(tmp_path):
    path = state(tmp_path)
    status = check_sources(reg(enabled=False), path, now=NOW)[0]
    assert status.status == "NOT_AUTHORIZED"
    assert status.queue_status == "NOT_APPLICABLE"
    assert unresolved_count(path) == 0


@pytest.mark.parametrize("seconds", [0, 1, 299, 7*86400+1, "3600", True])
def test_invalid_freshness_policy_rejected(tmp_path, seconds):
    with pytest.raises(SourceShareError, match="freshness"):
        check_sources(reg(), state(tmp_path), now=NOW,
                      freshness_seconds=seconds)


def test_future_success_is_never_marked_healthy(tmp_path):
    path = state(tmp_path)
    future = NOW + timedelta(hours=1)
    incremental_poll(reg(), NAME, path, now=future,
                     fetcher=fetch((item(future),), []))
    with pytest.raises(SourceShareError, match="in future"):
        check_sources(reg(), path, now=NOW)
