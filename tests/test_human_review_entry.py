"""Human review entry regression: all labels here are SYNTHETIC test actions."""
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from newscatalystos import live_gold_samples as gold
from newscatalystos.human_review_entry import list_review_cases, record_review_once
from newscatalystos.source_share import SourceShareError
from scripts import run_gold_review
from test_live_gold_samples import saved


def setup(tmp_path, monkeypatch):
    state, inbox, out, pins, batch = saved(tmp_path, monkeypatch)
    work = tmp_path / "reviewer_workspace"
    a, b = gold.prepare_blank_human_review_sheets(
        batch.folder, out, batch.payload_sha256, batch.pin_file, pins, work,
    )
    return out, pins, batch, work, a, b


def note(path, case, words):
    filename = path.parent / ("evidence_" + case + ".txt")
    filename.write_text(words, encoding="utf-8")
    filename.chmod(0o600)
    return filename


def test_local_review_list_blind_unlabeled_only(tmp_path, monkeypatch):
    out, pins, batch, work, a, b = setup(tmp_path, monkeypatch)
    report = list_review_cases(out, pins, work, batch.payload_sha256, "UNASSIGNED_A")
    assert report["unreviewed_count"] == batch.sample_count
    assert len(report["cases"]) == batch.sample_count
    assert all("headline" in row and "source_url" in row for row in report["cases"])
    assert "predicted_duplicate" not in str(report)
    assert not report["release_gate_verified"]
    assert not report["human_labels_added"]


def test_two_distinct_manual_decisions_feed_existing_aggregate_without_false_certification(
    tmp_path, monkeypatch,
):
    out, pins, batch, work, a, b = setup(tmp_path, monkeypatch)
    case = list_review_cases(
        out, pins, work, batch.payload_sha256, "UNASSIGNED_A"
    )["cases"][0]["case_sha256"]
    first_note = note(a, case, "Reviewer A checked the cited source URL and rationale.")
    second_note = note(b, case, "Reviewer B independently checked source and wrote notes.")
    original_frozen = (batch.folder / "predictions.json").read_bytes()
    first = record_review_once(out, pins, work, batch.payload_sha256,
                               "UNASSIGNED_A", "REVIEWER_A", case, True,
                               True, first_note)
    assert first["human_independence_certified"] is False
    assert (a.parent / "review_history" / (case + ".receipt.json")).exists()
    after_a = gold.evaluate_live_gold_reviews(
        batch.folder, out, batch.payload_sha256, batch.pin_file, pins, (a,b)
    )
    assert after_a["reviewed_by_two_agreeing_humans"] == 0
    record_review_once(out, pins, work, batch.payload_sha256,
                       "UNASSIGNED_B", "REVIEWER_B", case, True,
                       True, second_note)
    after_two = gold.summarize_all_gold_reviews(out, pins, work)
    assert after_two["reviewed_by_two_agreeing_humans"] == 1
    assert after_two["additional_agreed_human_cases_required"] == 499
    assert after_two["reviewer_independence_certified"] is False
    assert after_two["release_gate_verified"] is False
    assert (batch.folder / "predictions.json").read_bytes() == original_frozen
    assert list_review_cases(out, pins, work, batch.payload_sha256,
                             "UNASSIGNED_A")["unreviewed_count"] == 2


def test_review_cannot_change_completed_answer_or_identity(tmp_path, monkeypatch):
    out, pins, batch, work, a, b = setup(tmp_path, monkeypatch)
    case = list_review_cases(out, pins, work, batch.payload_sha256,
                             "UNASSIGNED_A")["cases"][0]["case_sha256"]
    evidence = note(a, case, "Written explanation for one actual review action.")
    record_review_once(out, pins, work, batch.payload_sha256,
                       "UNASSIGNED_A", "REVIEWER_A", case, False, False, evidence)
    before = a.read_bytes()
    with pytest.raises(SourceShareError, match="completed"):
        record_review_once(out, pins, work, batch.payload_sha256,
                           "UNASSIGNED_A", "REVIEWER_A", case, True, True, evidence)
    with pytest.raises(SourceShareError, match="identity"):
        record_review_once(out, pins, work, batch.payload_sha256,
                           "UNASSIGNED_A", "REVIEWER_OTHER",
                           list_review_cases(out,pins,work,batch.payload_sha256,
                                             "UNASSIGNED_A")["cases"][0]["case_sha256"],
                           True, True, evidence)
    assert a.read_bytes() == before


def test_wrong_location_evidence_or_unassigned_rejected_without_edit(tmp_path, monkeypatch):
    out, pins, batch, work, a, b = setup(tmp_path, monkeypatch)
    case = list_review_cases(out,pins,work,batch.payload_sha256,
                             "UNASSIGNED_A")["cases"][0]["case_sha256"]
    evidence = note(a, case, "Reviewer supplied private local evidence text.")
    before = a.read_bytes()
    for code in ("UNASSIGNED_X","bad name"):
        with pytest.raises(SourceShareError):
            record_review_once(out, pins, work, batch.payload_sha256,
                               "UNASSIGNED_A",code,case,True,False,evidence)
    evidence.chmod(0o644)
    with pytest.raises(SourceShareError):
        record_review_once(out, pins, work, batch.payload_sha256,
                           "UNASSIGNED_A","REVIEWER_A",case,True,False,evidence)
    evidence.chmod(0o600)
    elsewhere = tmp_path / "outside.txt"
    elsewhere.write_text("Not in the reviewer slot; unauthorized.")
    elsewhere.chmod(0o600)
    with pytest.raises(SourceShareError,match="private slot"):
        record_review_once(out, pins, work, batch.payload_sha256,
                           "UNASSIGNED_A","REVIEWER_A",case,True,False,elsewhere)
    assert a.read_bytes() == before


def test_cli_review_flags_require_explicit_human_confirmation(tmp_path, monkeypatch):
    out, pins, batch, work, a, b = setup(tmp_path, monkeypatch)
    args = run_gold_review.parser().parse_args([
        "--out-root",str(out),"--pin-root",str(pins),"review-list",
        "--expected-sha256",batch.payload_sha256,
        "--reviewer-slot","UNASSIGNED_A","--workspace-root",str(work),
    ])
    status, rows = run_gold_review.evaluate(args)
    assert status == 0 and rows["unreviewed_count"] == 3
    case = rows["cases"][0]["case_sha256"]
    evidence = note(a,case,"Manual evidence content for CLI synthetic test.")
    base = [
        "--out-root",str(out),"--pin-root",str(pins),"review-one",
        "--expected-sha256",batch.payload_sha256,
        "--reviewer-slot","UNASSIGNED_A","--workspace-root",str(work),
        "--reviewer-code","REVIEWER_A","--case-sha256",case,
        "--true-duplicate","true","--important-event","false",
        "--evidence-file",str(evidence),
    ]
    with pytest.raises(SystemExit):
        run_gold_review.parser().parse_args(base)
    complete = run_gold_review.parser().parse_args(base+["--confirm-human-review"])
    status, result = run_gold_review.evaluate(complete)
    assert status == 0 and result["status"] == "HUMAN_SUPPLIED_REVIEW_RECORDED_NOT_CERTIFIED"
    assert result["release_gate_verified"] is False


def test_missing_reviewer_workspace_is_not_created_by_blind_list(tmp_path, monkeypatch):
    _, _, out, pins, batch = saved(tmp_path, monkeypatch)
    absent = tmp_path / "not-yet-created-review-space"
    with pytest.raises(SourceShareError, match="workspace unavailable"):
        list_review_cases(out, pins, absent, batch.payload_sha256, "UNASSIGNED_A")
    assert not absent.exists()


def test_evidence_symlink_cannot_be_passed_as_manual_review(tmp_path, monkeypatch):
    out, pins, batch, work, a, b = setup(tmp_path, monkeypatch)
    case = list_review_cases(out, pins, work, batch.payload_sha256,
                             "UNASSIGNED_A")["cases"][0]["case_sha256"]
    external = tmp_path / "external_evidence.txt"
    external.write_text("External reference text not part of the reviewer workspace.")
    external.chmod(0o600)
    evidence = a.parent / ("evidence_" + case + ".txt")
    evidence.symlink_to(external)
    with pytest.raises(SourceShareError, match="private slot"):
        record_review_once(out, pins, work, batch.payload_sha256, "UNASSIGNED_A",
                           "REVIEWER_A", case, False, False, evidence)
    assert json.loads(a.read_bytes())["reviewer_code"] == "UNASSIGNED_A"
