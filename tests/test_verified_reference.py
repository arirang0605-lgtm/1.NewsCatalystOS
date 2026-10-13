"""Reference-index trust-anchor tests, synthetic-only and EraLeader-safe."""
from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from newscatalystos.source_share import SourceShareError
from newscatalystos.verified_reference import verify_official_research_reference
from test_era_capture_share import NOW, fixture


def report_fixture(tmp_path, overrides=None):
    era, directory, pin = fixture(tmp_path)
    import json as _json
    receipt = _json.loads((directory / "first_receipt.json").read_bytes())
    report = {
        "schema": "eraleader.official_api_pit_research_bridge.v1",
        "decision_at": "2026-10-12T11:10:00+00:00",
        "watch_type": "PRICE_ONLY_RESEARCH_NOT_CERTIFIED",
        "historic_universe_pit_verified": False,
        "issuer_share_class_verified": False,
        "dart_sec_financial_pit_joined": False,
        "official_leaders": 0,
        "sources": [{
            "source": "krx-kospi", "first_receipt_sha256": pin,
            "quality": "ROWS_RECEIVED_NOT_PIT_CERTIFIED",
            "raw_sha256": receipt["raw_sha256"], "row_count": 1,
        }],
    }
    report.update(overrides or {})
    folder = era / "output" / "official_api_integrated_20261012"
    folder.mkdir()
    file = folder / "official_api_pit_research.json"
    body = json.dumps(report, sort_keys=True).encode()
    file.write_bytes(body)
    return era, file, sha256(body).hexdigest(), directory


def read(era, file, pin, decision=NOW):
    return verify_official_research_reference(era, file, pin, decision, now=NOW)


def test_pinned_reference_validates_original_readonly(tmp_path):
    era, file, pin, directory = report_fixture(tmp_path)
    prior = {str(f): sha256(f.read_bytes()).digest()
             for f in (list(directory.iterdir()) + [file])}
    result = read(era, file, pin)
    assert len(result.captures) == 1
    assert result.captures[0].source_id == "krx-kospi"
    assert result.research_only
    assert prior == {str(f): sha256(f.read_bytes()).digest()
                     for f in (list(directory.iterdir()) + [file])}


def test_wrong_reference_sha_fails(tmp_path):
    era, file, pin, directory = report_fixture(tmp_path)
    with pytest.raises(SourceShareError, match="reference SHA"):
        read(era, file, "f" * 64)


def test_prior_index_false_certification_fails(tmp_path):
    era, file, pin, directory = report_fixture(tmp_path,
                                               {"historic_universe_pit_verified": True})
    with pytest.raises(SourceShareError, match="research-only"):
        read(era, file, pin)


def test_duplicate_reference_fails(tmp_path):
    era, file, pin, directory = report_fixture(tmp_path)
    obj = json.loads(file.read_bytes())
    obj["sources"].append(obj["sources"][0])
    file.write_bytes(json.dumps(obj).encode())
    pin = sha256(file.read_bytes()).hexdigest()
    with pytest.raises(SourceShareError, match="duplicate source"):
        read(era, file, pin)


def test_wrong_earlier_report_time_fails(tmp_path):
    era, file, pin, directory = report_fixture(tmp_path, {"decision_at": "2026-10-11T09:00:00+00:00"})
    with pytest.raises(SourceShareError, match="prior index differs"):
        read(era, file, pin)


def test_future_report_not_usable_at_earlier_decision(tmp_path):
    era, file, pin, directory = report_fixture(tmp_path)
    with pytest.raises(SourceShareError, match="reference was not available"):
        read(era, file, pin, datetime(2026, 10, 12, 10, 55, tzinfo=timezone.utc))


def test_mutated_receipt_rejected_by_pinned_report(tmp_path):
    era, file, pin, directory = report_fixture(tmp_path)
    (directory / "first_receipt.json").write_bytes(b"{}")
    with pytest.raises(SourceShareError, match="missing"):
        read(era, file, pin)
