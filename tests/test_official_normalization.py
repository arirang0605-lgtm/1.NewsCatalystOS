"""Timestamp meaning and no-release-promotion regressions (synthetic only)."""
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from newscatalystos.era_capture_share import read_official_capture
from newscatalystos.official_normalization import (
    BLOCKED, normalize_official_capture
)
from newscatalystos.source_share import SourceShareError
from test_era_capture_share import NOW, fixture


def candidates(tmp_path, source):
    era, directory, pin = fixture(tmp_path, source)
    capture = read_official_capture(directory, era, pin, NOW, now=NOW)
    return capture, normalize_official_capture(capture, NOW)


@pytest.mark.parametrize("source", [
    "krx-kospi", "krx-kosdaq", "dart-disclosures",
    "sec-submissions", "sec-companyfacts",
])
def test_all_sources_are_metadata_not_promoted(tmp_path, source):
    capture, events = candidates(tmp_path, source)
    assert len(events) == len(capture.records)
    for event in events:
        assert event.verified_published_at is None
        assert event.first_seen_at == capture.first_seen_at
        assert event.classification == BLOCKED
        assert event.source_receipt_sha256 == capture.first_receipt_sha256
        with pytest.raises(SourceShareError, match="RawEvent promotion blocked"):
            event.to_raw_event()


def test_dart_date_is_not_invented_as_publication_time(tmp_path):
    _, events = candidates(tmp_path, "dart-disclosures")
    assert events[0].provider_day == "2026-10-08"
    assert events[0].provider_acceptance_at is None
    assert events[0].verified_published_at is None


def test_sec_acceptance_distinct_from_first_seen_and_release(tmp_path):
    capture, events = candidates(tmp_path, "sec-submissions")
    expected = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)
    assert capture.records[0].provider_acceptance_at == expected
    assert events[0].provider_acceptance_at == expected
    assert expected < events[0].first_seen_at
    assert events[0].verified_published_at is None


@pytest.mark.parametrize("stamp", [
    "not a date", "2026-10-12", "2026-10-12T10:31:00Z",
    "2026-10-13T11:00:00+09:00",
])
def test_sec_bad_or_future_acceptance_blocked(tmp_path, stamp):
    payload = {"cik": 320193, "filings": {"recent": {
        "accessionNumber": ["0000320193-26-000001"],
        "acceptanceDateTime": [stamp],
    }}}
    era, directory, pin = fixture(tmp_path, "sec-submissions",
                                  raw_overrides=payload)
    with pytest.raises(SourceShareError):
        read_official_capture(directory, era, pin, NOW, now=NOW)


def test_research_candidate_rejects_fake_release(tmp_path):
    capture, _ = candidates(tmp_path, "dart-disclosures")
    forged = replace(capture.records[0], release_at=NOW)
    with pytest.raises(SourceShareError, match="unverified research"):
        normalize_official_capture(replace(capture, records=(forged,)), NOW)


def test_research_candidate_rejects_unsupported_claim(tmp_path):
    capture, _ = candidates(tmp_path, "krx-kospi")
    with pytest.raises(SourceShareError, match="unsupported certification"):
        normalize_official_capture(replace(capture, release_time_verified=True), NOW)


def test_asof_before_receipt_rejected(tmp_path):
    capture, _ = candidates(tmp_path, "krx-kospi")
    with pytest.raises(SourceShareError, match="unavailable"):
        normalize_official_capture(capture, datetime(2026, 10, 11, tzinfo=timezone.utc))


def test_sec_timestamp_attached_to_non_sec_rejected(tmp_path):
    capture, _ = candidates(tmp_path, "krx-kospi")
    fake = replace(capture.records[0], provider_acceptance_at=datetime(
        2026, 10, 8, tzinfo=timezone.utc))
    with pytest.raises(SourceShareError, match="non-SEC"):
        normalize_official_capture(replace(capture, records=(fake,)), NOW)
