"""6_5 reviewed local exchange sessions are not automatic release certification."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from newscatalystos.market_calendar_review import SCHEMA, load_calendar_review
from newscatalystos.feed_operations import operation_status
from newscatalystos.source_share import SourceShareError
from test_feed_operations import completed
from test_new_source_adapter import registry

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


def sample(tmp_path, sessions=None, now=NOW):
    root = tmp_path / "private_calendar"
    root.mkdir(mode=0o700, parents=True)
    root.chmod(0o700)
    raw = b"Operator-retained synthetic market calendar example, not official KRX data"
    snapshot = root / "source_snapshot"
    snapshot.write_bytes(raw)
    snapshot.chmod(0o600)
    doc = {
        "schema": SCHEMA, "exchange": "XKRX",
        "source_url": "https://www.krx.co.kr/contents/market-calendar",
        "source_sha256": sha256(raw).hexdigest(),
        "source_first_observed_at": (now - timedelta(hours=2)).isoformat(),
        "reviewer_id": "reviewer-1",
        "reviewed_at": (now - timedelta(hours=1)).isoformat(),
        "session_dates": sessions if sessions is not None
                         else ["2026-10-14", "2026-10-15"],
    }
    target = root / "review.json"
    target.write_text(json.dumps(doc))
    target.chmod(0o600)
    return root, doc


def set_review(root, doc):
    (root / "review.json").write_text(json.dumps(doc))
    (root / "review.json").chmod(0o600)


def test_valid_owner_review_retains_integrity_but_not_independent_certification(tmp_path):
    root, data = sample(tmp_path)
    parsed = load_calendar_review(root, now=NOW)
    assert parsed.session_dates == frozenset(data["session_dates"])
    assert parsed.source_sha256 == data["source_sha256"]


def test_matching_real_ack_days_only_and_never_releases(tmp_path):
    state, inbox, _, _, _, _ = completed(tmp_path)
    base = operation_status(registry(), inbox, state)
    day = base["days_with_all_sources"][0]
    root, doc = sample(tmp_path, sessions=[day])
    doc["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    doc["source_first_observed_at"] = (datetime.now(timezone.utc) -
                                       timedelta(seconds=2)).isoformat()
    set_review(root, doc)
    calendar = load_calendar_review(root, now=datetime.now(timezone.utc))
    report = operation_status(registry(), inbox, state, calendar_review=calendar)
    assert report["operator_reviewed_calendar_days"] == [day]
    assert report["operator_reviewed_calendar_day_count"] == 1
    assert report["market_calendar_review_provided"] is True
    assert report["verified_exchange_trading_days"] == 0
    assert report["five_trading_day_operation_certified"] is False
    assert report["v1_release_ready"] is False


def test_calendar_with_no_ack_does_not_create_operating_days(tmp_path):
    state, inbox, _, _, _, _ = completed(tmp_path)
    report = operation_status(registry(), inbox, state)
    day = report["days_with_all_sources"][0]
    # Select a weekday in a different year, never an ACK from today's run.
    other_day = "2025-01-06" if day != "2025-01-06" else "2024-01-08"
    root, doc = sample(tmp_path, sessions=[other_day])
    doc["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    doc["source_first_observed_at"] = (datetime.now(timezone.utc) -
                                       timedelta(seconds=2)).isoformat()
    set_review(root, doc)
    approved = load_calendar_review(root, now=datetime.now(timezone.utc))
    answer = operation_status(registry(), inbox, state, calendar_review=approved)
    assert answer["operator_reviewed_calendar_day_count"] == 0
    assert answer["weekday_candidate_count"] == 1


@pytest.mark.parametrize("mutation", [
    {"reviewer_id": "UNASSIGNED"},
    {"exchange": "XNYS"},
    {"source_url": "https://not-krx.example.org/sessions"},
    {"source_sha256": "0" * 64},
    {"session_dates": ["2026-10-10"]},  # Saturday
    {"session_dates": ["2026-10-14", "2026-10-14"]},
    {"session_dates": ["2026-02-30"]},
    {"source_first_observed_at": "2026-10-14T12:01:00+00:00"},
    {"reviewed_at": "2026-10-14T12:01:00+00:00"},
])
def test_invalid_calendar_reviews_fail_closed(tmp_path, mutation):
    root, doc = sample(tmp_path)
    doc.update(mutation)
    set_review(root, doc)
    with pytest.raises(SourceShareError):
        load_calendar_review(root, now=NOW)


def test_private_source_tamper_and_insecure_permissions_rejected(tmp_path):
    root, _ = sample(tmp_path)
    (root / "source_snapshot").write_bytes(b"changed bytes")
    with pytest.raises(SourceShareError, match="SHA mismatch"):
        load_calendar_review(root, now=NOW)
    root, _ = sample(tmp_path / "second")
    (root / "review.json").chmod(0o644)
    with pytest.raises(SourceShareError):
        load_calendar_review(root, now=NOW)
    (root / "review.json").chmod(0o600)
    (root / "source_snapshot").unlink()
    (root / "source_snapshot").symlink_to(root / "review.json")
    with pytest.raises(SourceShareError):
        load_calendar_review(root, now=NOW)


def test_missing_optional_calendar_stays_unverified(tmp_path):
    state, inbox, _, _, _, _ = completed(tmp_path)
    report = operation_status(registry(), inbox, state)
    assert report["operator_reviewed_calendar_days"] == []
    assert report["operator_reviewed_calendar_day_count"] == 0
    assert report["market_calendar_review_provided"] is False
    assert report["verified_exchange_trading_days"] == 0


def test_unvalidated_object_does_not_enter_operational_status(tmp_path):
    state, inbox, _, _, _, _ = completed(tmp_path)
    with pytest.raises(SourceShareError, match="validated calendar"):
        operation_status(registry(), inbox, state, calendar_review={"date": "2026-10-14"})
