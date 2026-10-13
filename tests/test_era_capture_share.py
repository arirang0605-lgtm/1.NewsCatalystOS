"""Purely synthetic security/PIT tests for existing EraLeader official first captures."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from newscatalystos.era_capture_share import read_official_capture
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 13, 6, tzinfo=timezone.utc)
FIRST = "2026-10-12T10:30:00+00:00"
SHA = "0" * 64


def fixture(tmp_path, source="krx-kospi", receipt_overrides=None, raw_overrides=None):
    era = tmp_path / "eraleader"
    directory = era / "output" / "official_api_capture" / ("first_" + "b" * 32)
    directory.mkdir(parents=True)
    directory.chmod(0o700)
    rows = [{"BAS_DD": "20261008", "ISU_CD": "005930", "TDD_CLSPRC": "75000"}]
    samples = {
        "krx-kospi": ({"OutBlock_1": rows}, "2026-10-08", "ROWS_RECEIVED_NOT_PIT_CERTIFIED", 1),
        "krx-kosdaq": ({"OutBlock_1": rows}, "2026-10-08", "ROWS_RECEIVED_NOT_PIT_CERTIFIED", 1),
        "dart-disclosures": ({"status": "000", "total_count": 101, "list": [
            {"rcept_no": "20261008000001", "rcept_dt": "20261008"}]},
            "2026-10-08", "INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY", 1),
        "sec-submissions": ({"cik": 320193, "filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001"],
            "acceptanceDateTime": ["2026-10-12T09:00:00.000Z"]}}},
            "320193", "RECENT_SUBMISSIONS_NOT_FULL_HISTORY", 1),
        "sec-companyfacts": ({"cik": 320193, "facts": {
            "us-gaap": {}, "dei": {}}},
            "320193", "FINANCIAL_FACT_TAXONOMIES_NOT_PIT_CERTIFIED", 2),
    }
    raw, requested, quality, count = samples[source]
    raw.update(raw_overrides or {})
    body = (json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (directory / "raw_response.json").write_bytes(body)
    (directory / "raw_response.json").chmod(0o600)
    receipt = {
        "schema": "eraleader.official_api_first_received_raw.v1",
        "source": source, "first_local_received_at_utc": FIRST,
        "request_kind": "cik" if source.startswith("sec-") else "market_day",
        "request_value": requested, "raw_sha256": sha256(body).hexdigest(),
        "raw_length_bytes": len(body), "provider_row_count": count,
        "quality": quality, "publisher_release_time_verified": False,
        "full_historic_universe_pit_certified": False,
        "issuer_share_class_independently_attested": False,
        "official_leader_promotions": 0, "no_external_timestamp_notary": True,
    }
    receipt.update(receipt_overrides or {})
    bytes_ = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (directory / "first_receipt.json").write_bytes(bytes_)
    (directory / "first_receipt.json").chmod(0o600)
    return era, directory, sha256(bytes_).hexdigest()


def read(era, folder, pin, when=NOW):
    return read_official_capture(folder, era, pin, when, now=NOW)


@pytest.mark.parametrize("source,provider,observed,num_records", [
    ("krx-kospi", "KRX", 1, 1),
    ("krx-kosdaq", "KRX", 1, 1),
    ("dart-disclosures", "DART", 1, 1),
    ("sec-submissions", "SEC", 1, 1),
    ("sec-companyfacts", "SEC", 2, 0),
])
def test_source_data_readonly_and_pit_restricted(tmp_path, source, provider, observed, num_records):
    era, folder, pin = fixture(tmp_path, source)
    before = {f.name: sha256(f.read_bytes()).digest() for f in folder.iterdir()}
    result = read(era, folder, pin)
    assert result.source_id == source and result.provider_id == provider
    assert result.observed_count == observed
    assert len(result.records) == num_records
    assert result.first_seen_at == datetime.fromisoformat(FIRST)
    assert not result.completeness_certified
    assert not result.release_time_verified
    assert not result.historical_pit_certified
    assert all(rec.available_at == result.first_seen_at for rec in result.records)
    assert all(rec.release_at is None and not rec.issuer_attested for rec in result.records)
    assert before == {f.name: sha256(f.read_bytes()).digest() for f in folder.iterdir()}
    assert read(era, folder, pin) == result


def test_dart_receipt_date_not_invented_as_timestamp(tmp_path):
    era, folder, pin = fixture(tmp_path, "dart-disclosures")
    output = read(era, folder, pin)
    assert output.quality == "INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY"
    assert output.records[0].provider_day == "2026-10-08"
    assert output.records[0].release_at is None


def test_mismatched_external_pin_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    with pytest.raises(SourceShareError, match="trusted pin"):
        read(era, folder, SHA)


def test_bad_pinned_raw_response_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    (folder / "raw_response.json").write_bytes(b'{"OutBlock_1":[]}')
    with pytest.raises(SourceShareError, match="evidence bytes"):
        read(era, folder, pin)


def test_future_first_received_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path, receipt_overrides={
        "first_local_received_at_utc": "2026-10-14T10:00:00+00:00"})
    with pytest.raises(SourceShareError, match="unavailable"):
        read(era, folder, pin)


def test_before_first_received_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    with pytest.raises(SourceShareError, match="unavailable"):
        read(era, folder, pin, datetime(2026, 10, 11, tzinfo=timezone.utc))


def test_future_decision_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    with pytest.raises(SourceShareError, match="decision in future"):
        read(era, folder, pin, datetime(2026, 10, 14, tzinfo=timezone.utc))


@pytest.mark.parametrize("override", [
    {"full_historic_universe_pit_certified": True},
    {"issuer_share_class_independently_attested": True},
    {"publisher_release_time_verified": True},
    {"no_external_timestamp_notary": False},
    {"official_leader_promotions": 1},
    {"source": "untrusted-social"},
    {"provider_row_count": 999},
    {"quality": "FULL_HISTORY_VERIFIED"},
])
def test_false_attestations_or_counts_rejected(tmp_path, override):
    era, folder, pin = fixture(tmp_path, receipt_overrides=override)
    with pytest.raises(SourceShareError):
        read(era, folder, pin)


def test_inflight_capture_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    new = folder.parent / ".api_inflight_testing"
    folder.rename(new)
    with pytest.raises(SourceShareError, match="atomically published"):
        read(era, new, pin)


def test_missing_raw_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    (folder / "raw_response.json").unlink()
    with pytest.raises(SourceShareError):
        read(era, folder, pin)


def test_symlink_capture_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    alias = folder.parent / ("first_" + "c" * 32)
    alias.symlink_to(folder, target_is_directory=True)
    with pytest.raises(SourceShareError, match="symlink"):
        read(era, alias, pin)


def test_symlink_receipt_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    origin = folder / "first_receipt.json"
    other = tmp_path / "outside.json"
    origin.rename(other)
    origin.symlink_to(other)
    with pytest.raises(SourceShareError):
        read(era, folder, pin)


def test_duplicate_krx_records_rejected(tmp_path):
    rows = [{"BAS_DD": "20261008", "ISU_CD": "005930", "TDD_CLSPRC": "75000"}] * 2
    era, folder, pin = fixture(tmp_path, raw_overrides={"OutBlock_1": rows},
                               receipt_overrides={"provider_row_count": 2})
    with pytest.raises(SourceShareError, match="duplicated"):
        read(era, folder, pin)


def test_incorrect_dart_day_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path, source="dart-disclosures",
        raw_overrides={"list": [{"rcept_no": "20261008000001", "rcept_dt": "20261009"}]})
    with pytest.raises(SourceShareError, match="day mismatch"):
        read(era, folder, pin)


def test_wrong_sec_cik_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path, source="sec-submissions", raw_overrides={"cik": 11111})
    with pytest.raises(SourceShareError, match="identity mismatch"):
        read(era, folder, pin)


def test_naive_decision_rejected(tmp_path):
    era, folder, pin = fixture(tmp_path)
    with pytest.raises(SourceShareError, match="timezone"):
        read(era, folder, pin, datetime(2026, 10, 13))
