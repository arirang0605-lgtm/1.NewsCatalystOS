"""Stored RSS title search -> existing SHA-pinned rules/AI metadata, synthetic inputs."""
from copy import deepcopy
import json

import pytest

from newscatalystos.feed_analysis_delivery import attach_saved_analysis_to_search
from newscatalystos.source_share import SourceShareError
from scripts import search_news
from test_feed_analysis_delivery import produce
from test_federated_news_search import fingerprint


def _options(opts, stored, *, include=True):
    args = ["--query", "반도체", "--scope", "motir",
            "--motir-registry", str(opts.registry),
            "--motir-state", str(opts.state),
            "--motir-inbox-root", str(opts.inbox_root), "--limit", "20"]
    if include:
        args += ["--analysis-report-file", stored["private_report_file"],
                 "--analysis-reports-root", str(opts.analysis_root / "reports"),
                 "--analysis-expected-sha256", stored["report_sha256"]]
    return search_news.parser().parse_args(args)


def test_search_saved_analysis_matches_exact_source_versions_without_writes(tmp_path):
    opts, code, stored = produce(tmp_path)
    assert code == 0
    before = fingerprint(tmp_path)
    status, result = search_news.evaluate(_options(opts, stored))
    assert status == 0 and result["coverage_complete"]
    assert result["saved_analysis_report_sha256"] == stored["report_sha256"]
    assert result["saved_analysis_matches"] == len(result["results"]) == 3
    assert result["saved_analysis_unmatched"] == 0
    assert not result["fact_verified_by_search"]
    assert not result["historical_analysis_join_certified"]
    assert not result["analysis_source_freshness_certified"]
    assert result["network_calls"] == result["ai_calls"] == 0
    for found in result["results"]:
        assert found["saved_analysis"] in stored["results"]
        assert found["saved_analysis"]["source_event_sha256"] == found["event_id"]
        assert found["saved_analysis"]["source_title_sha256"] == found["title_sha256"]
        assert not found["saved_analysis"]["verified_beneficiary"]
        assert not found["verified_supply_transaction"]
    assert fingerprint(tmp_path) == before


def test_without_opt_in_remains_ordinary_search(tmp_path):
    opts, _, stored = produce(tmp_path)
    status, report = search_news.evaluate(_options(opts, stored, include=False))
    assert status == 0
    assert "saved_analysis_report_sha256" not in report
    assert all("saved_analysis" not in row for row in report["results"])


def test_wrong_digest_or_partial_selection_returns_no_search_results(tmp_path):
    opts, _, stored = produce(tmp_path)
    bad = _options(opts, stored)
    bad.analysis_expected_sha256 = "f" * 64
    status, result = search_news.evaluate(bad)
    assert status == 4 and result["status"] == "SEARCH_DATA_UNAVAILABLE"
    assert "results" not in result and "headline" not in json.dumps(result)
    partial = _options(opts, stored)
    partial.analysis_expected_sha256 = None
    status, result = search_news.evaluate(partial)
    assert status == 4 and "results" not in result


def test_same_ids_with_changed_evidence_are_rejected_not_merged(tmp_path):
    opts, _, stored = produce(tmp_path)
    status, search = search_news.evaluate(_options(opts, stored, include=False))
    assert status == 0
    original = deepcopy(search)
    first = original["results"][0]
    first["headline"] += " 조작"
    from pathlib import Path
    path = Path(stored["private_report_file"])
    with pytest.raises(SourceShareError):
        attach_saved_analysis_to_search(original, path, path.parent, stored["report_sha256"])


def test_analysis_not_in_selected_report_is_explicitly_missing(tmp_path):
    opts, _, stored = produce(tmp_path)
    status, search = search_news.evaluate(_options(opts, stored, include=False))
    assert status == 0
    from pathlib import Path
    path = Path(stored["private_report_file"])
    # A distinct source identity cannot inherit a neighbor's economic claim.
    unrelated = deepcopy(search)
    unrelated["results"] = [dict(unrelated["results"][0], event_id="a" * 64)]
    joined = attach_saved_analysis_to_search(unrelated, path, path.parent, stored["report_sha256"])
    assert joined["saved_analysis_matches"] == 0
    assert joined["saved_analysis_unmatched"] == 1
    assert joined["results"][0]["saved_analysis"] is None
