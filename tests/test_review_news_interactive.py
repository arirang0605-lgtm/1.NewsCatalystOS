"""Interactive 2_6/3_6 human review path; synthetic inputs ONLY."""
from argparse import Namespace
from pathlib import Path
import json

import pytest

from scripts.review_news_interactive import run_one, parser
from newscatalystos import live_gold_samples as gold
from test_live_gold_samples import saved


def setup(tmp_path, monkeypatch):
    state, inbox, out, pins, batch = saved(tmp_path, monkeypatch)
    work = tmp_path / "reviewer_workspaces"
    a, b = gold.prepare_blank_human_review_sheets(
        batch.folder, out, batch.payload_sha256, batch.pin_file, pins, work,
    )
    return Namespace(
        out_root=out, pin_root=pins, workspace_root=work,
        batch_sha256=batch.payload_sha256, slot="UNASSIGNED_A",
        reviewer_code="REVIEWER_A",
    ), batch, a, b


def reply(*strings):
    answers = iter(strings)
    def ask(_question):
        return next(answers)
    return ask


def test_user_says_no_without_creating_evidence_or_labels(tmp_path, monkeypatch):
    opts, batch, a, b = setup(tmp_path, monkeypatch)
    original = a.read_bytes()
    shown = []
    code, report = run_one(opts, input_func=reply("no"),
                           output_func=lambda *value: shown.append(value))
    assert code == 0 and report["human_labels_added"] == 0
    assert report["status"] == "SKIPPED_NOT_HUMAN_REVIEWED"
    assert a.read_bytes() == original
    assert any(line[0] == "Headline:" for line in shown)
    assert not list(a.parent.glob("evidence_*.txt"))


def test_completed_one_case_uses_existing_sha_pinned_intake_only(tmp_path, monkeypatch):
    opts, batch, a, b = setup(tmp_path, monkeypatch)
    original = (batch.folder / "predictions.json").read_bytes()
    code, report = run_one(opts, input_func=reply(
        "yes", "no", "yes",
        "I checked the approved source and found a material new event.",
        "yes",
    ), output_func=lambda *_: None)
    assert code == 0 and report["human_labels_added"] == 1
    assert report["release_gate_verified"] is False
    assert not report["human_independence_certified"]
    assert len(list(a.parent.glob("evidence_*.txt"))) == 1
    assert json.loads(a.read_bytes())["reviewer_code"] == "REVIEWER_A"
    assert (batch.folder / "predictions.json").read_bytes() == original
    preview = gold.evaluate_live_gold_reviews(
        batch.folder, opts.out_root, batch.payload_sha256,
        batch.pin_file, opts.pin_root, (a, b),
    )
    assert preview["reviewed_by_two_agreeing_humans"] == 0
    assert preview["release_gate_verified"] is False
    assert preview["missing_or_partial_human_case_count"] == batch.sample_count


@pytest.mark.parametrize("choices", [
    ("sometimes",),
    ("yes", "maybe"),
    ("yes", "no", "invalid"),
    ("yes", "no", "yes", "tiny"),
])
def test_invalid_or_ambiguous_answer_never_updates_sheet(tmp_path, monkeypatch, choices):
    opts, batch, a, b = setup(tmp_path, monkeypatch)
    content = a.read_bytes()
    code, report = run_one(opts, input_func=reply(*choices),
                           output_func=lambda *_: None)
    assert code == 4 and report["human_labels_added"] == 0
    assert a.read_bytes() == content
    assert not list(a.parent.glob("evidence_*.txt"))


def test_second_confirmation_no_never_writes_human_answer(tmp_path, monkeypatch):
    opts, batch, a, b = setup(tmp_path, monkeypatch)
    code, report = run_one(opts, input_func=reply(
        "yes", "yes", "no",
        "The person reviewed only the permitted source and this is not important.",
        "no",
    ), output_func=lambda *_: None)
    assert code == 0 and report["status"] == "SKIPPED_NOT_HUMAN_REVIEWED"
    assert not list(a.parent.glob("evidence_*.txt"))
    assert json.loads(a.read_bytes())["reviewer_code"] == "UNASSIGNED_A"


def test_cli_parses_explicit_batch_slot_and_reviewer():
    opts = parser().parse_args([
        "--batch-sha256", "a" * 64,
        "--slot", "UNASSIGNED_B", "--reviewer-code", "REVIEWER_B",
    ])
    assert opts.batch_sha256 == "a" * 64 and opts.slot == "UNASSIGNED_B"


def test_no_prompt_automatic_defaults_cannot_submit(tmp_path, monkeypatch):
    opts, batch, a, b = setup(tmp_path, monkeypatch)
    code, report = run_one(opts, input_func=lambda _: (_ for _ in ()).throw(EOFError()),
                           output_func=lambda *_: None)
    assert code == 4 and report["human_labels_added"] == 0
    assert json.loads(a.read_bytes())["reviewer_code"] == "UNASSIGNED_A"
