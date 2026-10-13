"""5_2 official issuer screening: only pinned original metadata, never contracts."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json

import pytest

from newscatalystos import official_filing_context as context_mod
from newscatalystos.era_capture_share import read_official_capture
from newscatalystos.official_filing_context import (
    FilingContext, _decode_dart, _decode_sec, read_pinned_filing_context,
)
from newscatalystos.official_review_queue import build_official_review_queue
from newscatalystos.source_share import SourceShareError
from newscatalystos.verified_reference import VerifiedOfficialSources
from test_era_capture_share import fixture as captured, NOW
from test_official_review_queue import observed


def environments(tmp_path, monkeypatch):
    dart = {
        "status": "000", "total_count": 101,
        "list": [{
            "rcept_no": "20261008000001", "rcept_dt": "20261008",
            "corp_code": "00000001", "corp_name": "가상반도체",
            "stock_code": "005930",
            "report_nm": "반도체 설비 계약 검토(거래 사실 미확인)",
        }],
    }
    era, directory, pin = captured(tmp_path, "dart-disclosures",
                                   raw_overrides=dart)
    dart_dir = directory.with_name("first_" + "a" * 32)
    directory.rename(dart_dir)
    sec = {
        "cik": 320193, "name": "Synthetic Semiconductor Buyer",
        "tickers": ["DEMO"], "filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001"],
            "acceptanceDateTime": ["2026-10-12T09:00:00.000Z"],
            "form": ["10-Q"], "primaryDocDescription": ["Quarterly business review"],
        }},
    }
    era2, sec_dir, _ = captured(tmp_path, "sec-submissions", raw_overrides=sec)
    assert era == era2
    first = read_official_capture(dart_dir, era, pin, NOW, now=NOW)
    from hashlib import sha256 as digest
    sec_pin = digest((sec_dir / "first_receipt.json").read_bytes()).hexdigest()
    second = read_official_capture(sec_dir, era, sec_pin, NOW, now=NOW)
    expected = VerifiedOfficialSources("f" * 64, (first, second))
    monkeypatch.setattr(context_mod, "verify_with_local_anchor",
                        lambda *_a, **_kw: expected)
    return era, dart_dir, sec_dir, first, second


def test_both_official_sources_join_by_exact_verified_receipts(tmp_path, monkeypatch):
    era, dart_dir, sec_dir, first, second = environments(tmp_path, monkeypatch)
    paths = tuple(p for folder in (dart_dir, sec_dir) for p in folder.iterdir())
    before = {str(p):sha256(p.read_bytes()).hexdigest() for p in paths}
    records = read_pinned_filing_context(
        era, era / "output/official_api_integrated_20261012/official_api_pit_research.json",
        tmp_path / "independent.pin.json", now=NOW,
    )
    assert len(records) == 2
    d = records[("dart-disclosures", "20261008000001")]
    s = records[("sec-submissions", "0000320193-26-000001")]
    assert d.issuer_name_observed == "가상반도체"
    assert d.issuer_namespace_observed == "DART_CORP"
    assert d.issuer_code_observed == "00000001"
    assert d.ticker_observed == "005930"
    assert d.source_receipt_sha256 == first.first_receipt_sha256
    assert d.original_sha256 == first.raw_sha256
    assert s.issuer_name_observed == "Synthetic Semiconductor Buyer"
    assert s.issuer_namespace_observed == "SEC_CIK"
    assert s.issuer_code_observed == "320193"
    assert s.filing_type_observed == "10-Q"
    assert s.ticker_observed == "DEMO"
    assert all(not v.issuer_authority_attested
                   and not v.filing_text_available
                   and not v.actual_supply_relation_verified
               for v in records.values())
    assert before == {str(p):sha256(p.read_bytes()).hexdigest() for p in paths}


def test_raw_sha_mutation_blocks_official_context(tmp_path, monkeypatch):
    era, dart_dir, sec_dir, first, second = environments(tmp_path, monkeypatch)
    with open(dart_dir / "raw_response.json", "ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(SourceShareError, match="SHA differs"):
        read_pinned_filing_context(
            era, era / "output/official_api_integrated_20261012/official_api_pit_research.json",
            tmp_path / "separate.pin.json", now=NOW,
        )


def test_missing_pinned_source_fails_instead_of_partial_context(tmp_path, monkeypatch):
    era, dart_dir, sec_dir, first, second = environments(tmp_path, monkeypatch)
    monkeypatch.setattr(context_mod, "verify_with_local_anchor",
                        lambda *_a, **_kw: VerifiedOfficialSources("f" * 64, (first,)))
    with pytest.raises(SourceShareError, match="DART and SEC"):
        read_pinned_filing_context(era, era / "any", tmp_path / "pin", now=NOW)


@pytest.mark.parametrize("mutate,expected", [
    ({"corp_code": "00001"}, "issuer code"),
    ({"corp_name": ""}, "issuer name"),
    ({"report_nm": ""}, "report title"),
    ({"stock_code": "SHR"}, "stock code"),
])
def test_dart_report_company_values_fail_closed(tmp_path, monkeypatch, mutate, expected):
    era, dart_dir, _, capture, _ = environments(tmp_path, monkeypatch)
    data = json.loads((dart_dir / "raw_response.json").read_bytes())
    data["list"][0].update(mutate)
    with pytest.raises(SourceShareError, match=expected):
        _decode_dart(data, capture, NOW)


def test_sec_metadata_array_disagreement_is_not_silent(tmp_path, monkeypatch):
    era, dart_dir, sec_dir, _, capture = environments(tmp_path, monkeypatch)
    data = json.loads((sec_dir / "raw_response.json").read_bytes())
    data["filings"]["recent"]["form"] = []
    with pytest.raises(SourceShareError, match="arrays mismatch"):
        _decode_sec(data, capture, NOW)
    data["filings"]["recent"]["form"] = ["10-Q"]
    data["name"] = ""
    with pytest.raises(SourceShareError, match="registrant name"):
        _decode_sec(data, capture, NOW)


def _hint(row, at):
    return FilingContext(
        row.source_id, row.source_document_id, row.receipt_sha256,
        row.original_sha256, "가상반도체", "DART_CORP", "00000001",
        "005930", "DART_REPORT", "반도체 공급계약 이행 여부 미확인",
        at,
    )


def test_existing_review_queue_can_filter_verified_issuer_title_without_promotion(tmp_path):
    _, _, _, at, observations = observed(tmp_path)
    row = observations.observations[0]
    hint = _hint(row, at)
    result = build_official_review_queue(
        observations, decision_at=at, now=at,
        filing_context={(row.source_id,row.source_document_id):hint},
        issuer_contains="반도체", title_contains="공급계약",
        filing_form="DART_REPORT",
    )
    body = json.loads(result.payload)
    assert body["total_eligible"] == body["selected_count"] == 1
    assert body["schema"] == "newscatalyst.official_relation_review_queue.v2"
    assert body["context_mode"] == "PINNED_FIRST_CAPTURE_FILING_METADATA"
    item = body["items"][0]
    assert item["issuer_name_observed"] == "가상반도체"
    assert item["semiconductor_keyword_hint_only"] is True
    assert item["issuer_authority_attested"] is False
    assert item["industry_relevance"] == "UNKNOWN_UNSCREENED"
    assert item["supply_relation_status"] == "UNREVIEWED"
    assert not item["official_document_text_available"]
    assert not item["verified_real_transaction"]
    absent = build_official_review_queue(
        observations, decision_at=at, now=at,
        filing_context={(row.source_id,row.source_document_id):hint},
        filing_form="10-Q",
    )
    assert absent.total_eligible == 0
    assert absent.selected_count == 0


def test_unpinned_or_wrong_receipt_context_refused(tmp_path):
    _, _, _, at, obs = observed(tmp_path)
    row = obs.observations[0]
    with pytest.raises(SourceShareError, match="requires independently pinned"):
        build_official_review_queue(obs, decision_at=at, now=at,
                                    issuer_contains="반도체")
    wrong = replace(_hint(row, at), source_receipt_sha256="0" * 64)
    with pytest.raises(SourceShareError, match="SHA/PIT"):
        build_official_review_queue(
            obs, decision_at=at, now=at,
            filing_context={(row.source_id,row.source_document_id): wrong},
        )
    future = replace(_hint(row, at), local_context_verified_at=at+timedelta(seconds=1))
    with pytest.raises(SourceShareError, match="SHA/PIT"):
        build_official_review_queue(
            obs, decision_at=at, now=at,
            filing_context={(row.source_id,row.source_document_id): future},
        )


def test_cli_pinned_context_filters_actual_typed_v2_issuer_metadata(
    tmp_path, monkeypatch,
):
    import argparse
    from scripts import build_official_review_queue as cli
    pub, root, pin, at, observations = observed(tmp_path)
    row = observations.observations[0]
    info = _hint(row, at)
    called = []
    def screened_context(era_root, reference, anchor, *, now=None):
        called.append((era_root, reference, anchor))
        return {(row.source_id,row.source_document_id):info}
    monkeypatch.setattr(cli, "read_pinned_filing_context", screened_context)
    options = argparse.Namespace(
        publication=pub, publication_root=root, payload_sha256=pin,
        source_id="dart-disclosures", document_id=None, limit=20, offset=0,
        output_root=tmp_path / "official-worklist",
        with_pinned_issuer_context=True,
        era_root=tmp_path / "read-only-era-root",
        era_report=tmp_path / "read-only-era-index",
        independent_anchor=tmp_path / "mac-trusted-pin.json",
        issuer_contains="가상", title_contains="공급계약", filing_form="DART_REPORT",
    )
    code, report = cli.evaluate(options, now=at)
    assert code == 0 and report["issuer_context_verified"] is True
    assert report["item_count"] == 1
    assert len(called) == 1
    entry = json.loads((Path(report["queue_path"]) / "queue.json").read_bytes())
    assert entry["issuer_contains"] == "가상"
    assert entry["items"][0]["issuer_name_observed"] == "가상반도체"
    assert not entry["items"][0]["verified_real_transaction"]
    assert not entry["items"][0]["official_document_text_available"]


def test_cli_no_unpinned_name_filter_or_faux_independent_anchor(tmp_path):
    import argparse
    from scripts import build_official_review_queue as cli
    pub, root, pin, at, obs = observed(tmp_path)
    params = argparse.Namespace(
        publication=pub, publication_root=root, payload_sha256=pin,
        source_id="dart-disclosures", document_id=None, limit=20, offset=0,
        output_root=tmp_path / "no-unpinned",
        with_pinned_issuer_context=False,
        era_root=None, era_report=None, independent_anchor=None,
        issuer_contains="반도체", title_contains=None, filing_form=None,
    )
    code, report = cli.evaluate(params, now=at)
    assert code == 4 and report["status"] == "DATA_UNAVAILABLE"
    assert not params.output_root.exists()
    params.with_pinned_issuer_context = True
    code, report = cli.evaluate(params, now=at)
    assert code == 4 and report["status"] == "DATA_UNAVAILABLE"
    assert not params.output_root.exists()
