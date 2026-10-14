"""Freeze actual approved RSS metadata into a blind gold-review workflow.

These tests use synthetic RSS and synthetic HUMAN labels; they do NOT
certify independence or accuracy for the real live 39-title candidates.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil

import pytest

from newscatalystos import live_gold_samples as gold
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from scripts import run_gold_review
from test_feed_operations import completed
from test_feed_recovery import paths
from test_new_source_adapter import registry


def saved(tmp_path, monkeypatch):
    state, inbox, _, receipt, ack, folder = completed(tmp_path)
    monkeypatch.setattr(gold, "_different_disk", lambda *_: True)
    out = tmp_path / "gold_batches"
    pins = tmp_path / "separate_mac_pins"
    frozen = gold.freeze_real_gold_review_cases(registry(),inbox,state,out,pins)
    return state,inbox,out,pins,frozen


def sheets(out, pin, code_a="REVIEWER_A", code_b="REVIEWER_B"):
    originals = pin.folder / "human_review_template.json"
    targets = []
    for code in (code_a,code_b):
        d=out / ("labels_"+code)
        d.mkdir(mode=0o700)
        path=d/"answers.json"
        raw=json.loads(originals.read_bytes())
        raw["reviewer_code"]=code
        path.write_text(json.dumps(raw),encoding="utf-8")
        path.chmod(0o600)
        targets.append(path)
    return tuple(targets)


def test_freeze_preserves_full_prediction_sha_and_blind_templates(tmp_path, monkeypatch):
    state,inbox,out,pins,report=saved(tmp_path,monkeypatch)
    assert report.sample_count==3
    assert report.pin_file.parent==pins
    assert report.folder.name=="gold_batch_"+report.payload_sha256
    assert report.folder.stat().st_mode & 0o077==0
    assert report.pin_file.stat().st_mode & 0o077==0
    prediction=json.loads((report.folder/"predictions.json").read_bytes())
    blind=json.loads((report.folder/"blind_cases.json").read_bytes())
    template=json.loads((report.folder/"human_review_template.json").read_bytes())
    assert prediction["schema"]==gold.PREDICTIONS_SCHEMA
    assert prediction["independent_gold_review_count"]==0
    assert len(prediction["cases"])==3
    assert len(blind["cases"])==3
    assert blind["predictions_visible_to_reviewer"] is False
    assert template["reviewer_code"]=="UNASSIGNED"
    assert all(x["true_duplicate"] is None and x["important_event"] is None
               for x in template["labels"])
    assert not any("predicted_" in str(x) for x in blind["cases"])
    assert not any("predicted_" in str(x) for x in template["labels"])
    assert sha256((report.folder/"predictions.json").read_bytes()).hexdigest()==report.payload_sha256
    assert all(x["predicted_at"]==x["pin_first_observed_at"]
               for x in prediction["cases"])
    assert report.independently_labeled_cases==0 and not report.release_certified


def test_blank_human_templates_do_not_generate_accuracy_or_release_claims(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    reviews=sheets(out,batch)
    result=gold.evaluate_live_gold_reviews(
        batch.folder,out,batch.payload_sha256,batch.pin_file,pins,reviews,
    )
    assert result["sample_count"]==3
    assert result["reviewed_by_two_agreeing_humans"]==0
    assert result["missing_or_partial_human_case_count"]==3
    assert result["duplicate_precision"] is None
    assert result["important_event_recall"] is None
    assert result["required_additional_cases"]==497
    assert not result["human_truth_invented"]
    assert result["human_truth_invented"] is False
    assert result["release_gate_verified"] is False


def fill(path, now, truth):
    doc=json.loads(path.read_bytes())
    for idx,row in enumerate(doc["labels"]):
        if idx not in truth:
            continue
        duplicate,important=truth[idx]
        row["true_duplicate"]=duplicate
        row["important_event"]=important
        row["review_evidence_sha256"]=sha256(
            (doc["reviewer_code"]+row["case_sha256"]+str(duplicate)).encode()
        ).hexdigest()
        row["reviewed_at"]=now.isoformat()
    path.write_text(json.dumps(doc),encoding="utf-8")
    path.chmod(0o600)


def test_two_synthetic_human_answers_evaluate_existing_metrics_only(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    a,b=sheets(out,batch)
    recorded=datetime.now(timezone.utc)
    fill(a,recorded,{0:(True,True),1:(False,False),2:(False,False)})
    fill(b,recorded,{0:(True,True),1:(False,False),2:(False,False)})
    data=gold.evaluate_live_gold_reviews(
        batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
    )
    assert data["reviewed_by_two_agreeing_humans"]==3
    assert data["missing_or_partial_human_case_count"]==0
    assert data["disputed_case_count"]==0
    assert not data["mathematical_threshold_met"]
    assert not data["independent_provenance_certified"]
    assert not data["release_gate_verified"]


def test_dispute_and_unfinished_reviews_stay_unresolved(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    a,b=sheets(out,batch)
    at=datetime.now(timezone.utc)
    fill(a,at,{0:(True,True)})
    fill(b,at,{0:(False,True)})
    result=gold.evaluate_live_gold_reviews(
        batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
    )
    assert result["reviewed_by_two_agreeing_humans"]==0
    assert result["disputed_case_count"]==1
    assert result["missing_or_partial_human_case_count"]==2
    assert not result["release_gate_verified"]


@pytest.mark.parametrize("target",["predictions.json","blind_cases.json",
                                   "human_review_template.json"])
def test_modified_frozen_batch_or_blind_sheet_fails_against_other_disk_pin(
    tmp_path,monkeypatch,target
):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    f=batch.folder/target
    f.write_bytes(f.read_bytes()+b"new facts")
    a,b=sheets(out,batch) if target=="predictions.json" else (
        None,None
    )
    if a is None:
        # Template may now be corrupt; just pass absent reviewers. Pin should
        # reject the altered frozen batch BEFORE accessing answer files.
        a=out/"no-such-answer-a.json"
        b=out/"no-such-answer-b.json"
    with pytest.raises(SourceShareError,match="SHA|pin|gold"):
        gold.evaluate_live_gold_reviews(
            batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
        )


def test_wrong_expected_digest_and_missing_pin_refuse_all_reviews(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    a,b=sheets(out,batch)
    with pytest.raises(SourceShareError,match="untrusted|mismatch"):
        gold.evaluate_live_gold_reviews(
            batch.folder,out,"f"*64,batch.pin_file,pins,(a,b),
        )
    batch.pin_file.unlink()
    with pytest.raises(SourceShareError):
        gold.evaluate_live_gold_reviews(
            batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
        )


def test_no_approved_live_provider_does_not_create_frozen_cases(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    from dataclasses import replace
    revoked=ProviderRegistry((replace(registry().providers[0],approved=False),))
    with pytest.raises(SourceShareError):
        gold.freeze_real_gold_review_cases(revoked,inbox,state,out,pins)
    assert len(list(out.iterdir()))==1


def test_future_or_unauthorized_human_review_is_rejected(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    a,b=sheets(out,batch)
    at=datetime.now(timezone.utc)-timedelta(days=1)
    fill(a,at,{0:(True,True)})
    with pytest.raises(SourceShareError,match="before independent"):
        gold.evaluate_live_gold_reviews(
            batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
        )
    fill(a,datetime.now(timezone.utc),{0:(True,True)})
    a.chmod(0o644)
    with pytest.raises(SourceShareError,match="owner-only"):
        gold.evaluate_live_gold_reviews(
            batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
        )


def test_cli_freeze_and_evaluate_end_to_end_with_real_source_fixture(tmp_path,monkeypatch):
    state,inbox,output,_receipt,_ack,_folder=completed(tmp_path)
    out=tmp_path/"private_gold_batches"
    pins=tmp_path/"mac_sha_pins"
    monkeypatch.setattr(gold,"_different_disk",lambda *_:True)
    monkeypatch.setattr(run_gold_review,"_registry",lambda _:registry())
    opts=__import__("argparse").Namespace(
        command="freeze",registry=tmp_path/"unused_registry",
        state=state,inbox_root=inbox,out_root=out,pin_root=pins,
    )
    code,report=run_gold_review.evaluate(opts)
    assert code==0 and report["case_count"]==3
    assert report["human_gold_labeled_cases"]==0
    assert report["new_provider_requests"]==0
    batch=gold.GoldBatch(
        Path(report["batch_folder"]),Path(report["independent_mac_pin"]),
        report["prediction_payload_sha256"],report["case_count"],
        datetime.now(timezone.utc)
    )
    a,b=sheets(out,batch)
    params=__import__("argparse").Namespace(
        command="evaluate",out_root=out,pin_root=pins,
        batch_folder=batch.folder,pin_file=batch.pin_file,
        expected_sha256=batch.payload_sha256,
        review_file=[a,b]
    )
    code,evaluated=run_gold_review.evaluate(params)
    assert code==0 and evaluated["missing_or_partial_human_case_count"]==3
    assert evaluated["release_gate_verified"] is False


def test_mac_blank_review_workspaces_are_not_actual_human_labels(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    workspace=tmp_path/"Mac_human_gold_workspace"
    a,b=gold.prepare_blank_human_review_sheets(
        batch.folder,out,batch.payload_sha256,batch.pin_file,pins,workspace,
    )
    assert a!=b
    assert a.stat().st_mode & 0o077==0
    assert b.stat().st_mode & 0o077==0
    assert a.parent.stat().st_mode & 0o077==0
    assert b.parent.stat().st_mode & 0o077==0
    x,y=json.loads(a.read_bytes()),json.loads(b.read_bytes())
    assert x["reviewer_code"]=="UNASSIGNED_A"
    assert y["reviewer_code"]=="UNASSIGNED_B"
    assert all(item["true_duplicate"] is None for item in x["labels"])
    result=gold.evaluate_live_gold_reviews(
        batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
    )
    assert result["reviewed_by_two_agreeing_humans"]==0
    assert result["missing_or_partial_human_case_count"]==3
    assert result["release_gate_verified"] is False
    with pytest.raises(SourceShareError,match="workspace exists"):
        gold.prepare_blank_human_review_sheets(
            batch.folder,out,batch.payload_sha256,batch.pin_file,pins,workspace,
        )
    assert a.is_file() and b.is_file()


def test_draft_cli_reports_zero_reviewed_not_two_real_humans(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    from argparse import Namespace
    opts=Namespace(
        command="draft", out_root=out,pin_root=pins,
        batch_folder=batch.folder,expected_sha256=batch.payload_sha256,
        pin_file=batch.pin_file,
        workspace_root=tmp_path/"actual_private_mac_workspace"
    )
    code,report=run_gold_review.evaluate(opts)
    assert code==0 and report["status"]=="TWO_BLANK_REVIEWER_WORKSPACES_PREPARED"
    assert len(report["blank_review_files"])==2
    assert report["human_gold_labeled_cases"]==0
    assert report["independent_humans_authenticated"] is False
    assert report["release_gate_verified"] is False


def test_filled_labels_with_unassigned_placeholder_are_not_reviewed(tmp_path,monkeypatch):
    state,inbox,out,pins,batch=saved(tmp_path,monkeypatch)
    a,b=gold.prepare_blank_human_review_sheets(
        batch.folder,out,batch.payload_sha256,batch.pin_file,pins,
        tmp_path/"Mac_draft_space",
    )
    fill(a,datetime.now(timezone.utc),{0:(True,True)})
    with pytest.raises(SourceShareError,match="replace unassigned placeholder"):
        gold.evaluate_live_gold_reviews(
            batch.folder,out,batch.payload_sha256,batch.pin_file,pins,(a,b),
        )
