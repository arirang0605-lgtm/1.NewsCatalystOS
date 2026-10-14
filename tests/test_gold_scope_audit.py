"""Audit SHA-pinned real-source cohort quality; synthetic data are not gold."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from newscatalystos import live_gold_samples as gold
from newscatalystos.gold_scope_audit import audit_gold_scope
from newscatalystos.source_share import SourceShareError
from scripts import run_gold_review
from test_live_gold_samples import saved
from test_live_gold_aggregate import two_batches


def prepared(tmp_path, monkeypatch):
    state, inbox, out, pins, batch = saved(tmp_path, monkeypatch)
    workspace = tmp_path / "review-workspaces"
    gold.prepare_blank_human_review_sheets(
        batch.folder, out, batch.payload_sha256,
        batch.pin_file, pins, workspace,
    )
    return out, pins, workspace, batch


def test_pinned_scope_counts_real_source_kinds_and_does_not_fabricate_relevance(
    tmp_path, monkeypatch
):
    out, pins, workspace, batch = prepared(tmp_path, monkeypatch)
    result = audit_gold_scope(out, pins, workspace)
    assert result["sha_pinned_batch_count"] == 1
    assert result["unique_frozen_case_count"] == 3
    assert sum(result["approved_provider_case_counts"].values()) == 3
    assert sum(result["observed_source_role_case_counts"].values()) == 3
    assert (result["semiconductor_title_keyword_hints"] +
            result["other_title_cases_without_semiconductor_keywords"] == 3)
    assert 0 <= result["semiconductor_title_keyword_share"] <= 1
    assert result["two_reviewer_agreed_cases"] == 0
    assert result["unreviewed_or_partial_cases"] == 3
    assert result["sector_recall_precision_certified"] is False
    assert result["release_gate_verified"] is False
    assert result["rss_requests"] == result["official_era_requests"] == result["ai_calls"] == 0
    assert "NARROW_PROVIDER_DIVERSITY_REVIEW_REQUIRED" in result["warnings"]


def test_two_pinned_batches_not_double_counted_and_date_order_visible(
    tmp_path, monkeypatch
):
    out, pins, workspace, first, second, a, b = two_batches(tmp_path, monkeypatch)
    result = audit_gold_scope(out, pins, workspace)
    assert result["unique_frozen_case_count"] == 4
    assert result["sha_pinned_batch_count"] == 2
    assert result["two_reviewer_agreed_cases"] == 0
    assert result["missing_unique_case_count_to_500"] == 496
    assert result["missing_two_human_agreements_to_500"] == 500
    assert result["first_local_pin_day_utc"] <= result["last_local_pin_day_utc"]
    assert result["earliest_source_available_day_utc"] <= result["latest_source_available_day_utc"]


def test_modified_blind_list_cannot_change_sector_counts(
    tmp_path, monkeypatch
):
    out, pins, workspace, batch = prepared(tmp_path, monkeypatch)
    blind = batch.folder / "blind_cases.json"
    blind.write_bytes(blind.read_bytes() + b"tamper")
    with pytest.raises(SourceShareError):
        audit_gold_scope(out, pins, workspace)


def test_missing_pin_and_human_reviews_fail_not_claim_gold(
    tmp_path, monkeypatch
):
    out, pins, workspace, batch = prepared(tmp_path, monkeypatch)
    a = (workspace / batch.folder.name / "UNASSIGNED_A" / "answers.json")
    a.unlink()
    with pytest.raises((SourceShareError, OSError)):
        audit_gold_scope(out, pins, workspace)
    a.write_bytes((batch.folder / "human_review_template.json").read_bytes())
    a.chmod(0o600)
    batch.pin_file.unlink()
    with pytest.raises(SourceShareError):
        audit_gold_scope(out, pins, workspace)


def test_scope_cli_reports_only_aggregate_counts_not_headlines(tmp_path, monkeypatch):
    out, pins, workspace, batch = prepared(tmp_path, monkeypatch)
    options = run_gold_review.parser().parse_args([
        "--out-root", str(out), "--pin-root", str(pins),
        "scope-audit", "--workspace-root", str(workspace),
    ])
    code, result = run_gold_review.evaluate(options)
    assert code == 0
    assert result["unique_frozen_case_count"] == 3
    assert result["release_gate_verified"] is False
    assert "headline" not in str(result)
    assert "case_sha256" not in str(result)
    assert result["status"] == "PINNED_RSS_SCOPE_REVIEW_REQUIRED_NOT_SECTOR_CERTIFIED"


def test_operator_cannot_audit_untrusted_empty_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(gold, "_different_disk", lambda *_: True)
    root = tmp_path / "out"
    pin = tmp_path / "pin"
    root.mkdir(mode=0o700)
    pin.mkdir(mode=0o700)
    root.chmod(0o700)
    pin.chmod(0o700)
    with pytest.raises(SourceShareError, match="no pinned"):
        audit_gold_scope(root, pin, tmp_path)
