"""Synthetic release metadata claims; no official release is attested."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from newscatalystos.era_capture_share import read_official_capture
from newscatalystos.official_normalization import normalize_official_capture
from newscatalystos.release_claim import (
    SCHEMA, STATUS, inspect_release_claim,
)
from newscatalystos.source_share import SourceShareError
from test_era_capture_share import NOW, fixture


def sample(tmp_path, provider="SEC"):
    source = "sec-submissions" if provider == "SEC" else "dart-disclosures"
    era, folder, pin = fixture(tmp_path, source)
    capture = read_official_capture(folder, era, pin, NOW, now=NOW)
    candidate = normalize_official_capture(capture, NOW)[0]
    claim = {
        "schema": SCHEMA,
        "provider_id": provider,
        "source_id": candidate.source_id,
        "source_document_id": candidate.provider_record_id,
        "issuer_id": "320193" if provider == "SEC" else "DART_CORP_SAMPLE",
        "revision_id": "v1",
        "revision_kind": "ORIGINAL",
        "supersedes_document_id": None,
        "claimed_published_at": ("2026-10-12T09:05:00Z" if provider == "SEC"
                                 else "2026-10-08T01:00:00Z"),
        "observed_at": "2026-10-12T12:00:00Z",
        "official_url": (
            "https://www.sec.gov/Archives/edgar/data/320193/"
            "000032019326000001/sample.htm"
            if provider == "SEC" else
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261008000001"
        ),
    }
    return candidate, claim, (folder / "raw_response.json").read_bytes(), folder


def inspect(candidate, claim, *, expected=None, decision=NOW):
    body = json.dumps(claim, sort_keys=True).encode()
    return inspect_release_claim(
        candidate, body, expected or sha256(body).hexdigest(),
        decision, now=NOW,
    )


@pytest.mark.parametrize("provider", ["SEC", "DART"])
def test_metadata_claim_remains_blocked_and_preserves_original(tmp_path, provider):
    candidate, claim, original, folder = sample(tmp_path, provider)
    result = inspect(candidate, claim)
    assert result.verification_status == STATUS
    assert result.claimed_published_at < result.first_seen_at
    assert result.source_sha256 == candidate.source_sha256
    assert result.source_receipt_sha256 == candidate.source_receipt_sha256
    with pytest.raises(SourceShareError, match="RawEvent promotion blocked"):
        result.to_raw_event()
    assert (folder / "raw_response.json").read_bytes() == original


def test_correction_provenance_is_recorded_not_certified(tmp_path):
    candidate, claim, _, _ = sample(tmp_path)
    claim.update(revision_id="v2", revision_kind="CORRECTION",
                 supersedes_document_id="0000320193-25-000001")
    item = inspect(candidate, claim)
    assert item.revision_kind == "CORRECTION"
    assert item.supersedes_document_id == "0000320193-25-000001"
    assert item.verification_status == STATUS


@pytest.mark.parametrize("changes", [
    {"source_document_id": "0000320193-26-000002"},
    {"provider_id": "DART"},
    {"source_id": "fake"},
    {"revision_kind": "FORGED"},
    {"revision_kind": "CORRECTION"},
    {"supersedes_document_id": "evil"},
    {"revision_kind": "CORRECTION", "supersedes_document_id": "0000320193-26-000001"},
    {"claimed_published_at": "2026-10-12T08:59:00Z"},
    {"claimed_published_at": "2026-10-12T10:31:00Z"},
    {"claimed_published_at": "2026-10-12T09:05:00"},
    {"observed_at": "2026-10-13T06:01:00Z"},
    {"official_url": "http://www.sec.gov/Archives/edgar/data/320193/000032019326000001/sample.htm"},
    {"official_url": "https://www.sec.gov.evil.test/Archives/edgar/data/320193/000032019326000001/sample.htm"},
    {"official_url": "https://www.sec.gov@evil.test/Archives/edgar/data/320193/000032019326000001/sample.htm"},
    {"official_url": "https://www.sec.gov/Archives/edgar/data/320193/999999999999999999/sample.htm"},
    {"official_url": "https://www.sec.gov/Archives/edgar/data/999999/000032019326000001/sample.htm"},
    {"official_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/sample.htm?key=x"},
])
def test_inconsistent_claim_rejected(tmp_path, changes):
    candidate, claim, _, _ = sample(tmp_path)
    claim.update(changes)
    with pytest.raises(SourceShareError):
        inspect(candidate, claim)


def test_dart_date_mismatch_rejected(tmp_path):
    candidate, claim, _, _ = sample(tmp_path, "DART")
    claim["claimed_published_at"] = "2026-10-09T01:00:00Z"
    with pytest.raises(SourceShareError, match="DART date"):
        inspect(candidate, claim)


def test_dart_url_wrong_document_rejected(tmp_path):
    candidate, claim, _, _ = sample(tmp_path, "DART")
    claim["official_url"] = claim["official_url"].replace("000001", "000002")
    with pytest.raises(SourceShareError, match="DART URL"):
        inspect(candidate, claim)


def test_krx_is_not_a_disclosure_candidate(tmp_path):
    era, folder, pin = fixture(tmp_path, "krx-kospi")
    capture = read_official_capture(folder, era, pin, NOW, now=NOW)
    candidate = normalize_official_capture(capture, NOW)[0]
    _, claim, _, _ = sample(tmp_path / "other")
    with pytest.raises(SourceShareError, match="not an unverified disclosure"):
        inspect(candidate, claim)


def test_external_pin_mismatch_rejected(tmp_path):
    candidate, claim, _, _ = sample(tmp_path)
    with pytest.raises(SourceShareError, match="independently pinned"):
        inspect(candidate, claim, expected="0" * 64)


def test_duplicate_json_keys_rejected(tmp_path):
    candidate, claim, _, _ = sample(tmp_path)
    body = json.dumps(claim).encode()[:-1] + b',"issuer_id":"forged"}'
    with pytest.raises(SourceShareError, match="invalid JSON"):
        inspect_release_claim(candidate, body, sha256(body).hexdigest(), NOW, now=NOW)


def test_unknown_fields_and_oversized_claim_rejected(tmp_path):
    candidate, claim, _, _ = sample(tmp_path)
    claim["embedded_news_original"] = "forbidden"
    with pytest.raises(SourceShareError, match="unexpected claim schema"):
        inspect(candidate, claim)
    body = b" " * 8193
    with pytest.raises(SourceShareError, match="independently pinned"):
        inspect_release_claim(candidate, body, sha256(body).hexdigest(), NOW, now=NOW)


def test_future_decision_or_claim_observation_rejected(tmp_path):
    candidate, claim, _, _ = sample(tmp_path)
    with pytest.raises(SourceShareError, match="future"):
        inspect(candidate, claim, decision=datetime(2026, 10, 14, tzinfo=timezone.utc))
    claim["observed_at"] = "2026-10-14T02:00:00Z"
    with pytest.raises(SourceShareError, match="PIT"):
        inspect(candidate, claim)


def test_fake_candidate_certification_rejected(tmp_path):
    candidate, claim, _, _ = sample(tmp_path)
    forged = replace(candidate, verified_published_at=NOW)
    with pytest.raises(SourceShareError, match="not an unverified disclosure"):
        inspect(forged, claim)
