"""Freeze prospective RSS title cases and preview independent human gold reviews.

Use `freeze` to export actual approved RSS cases with model/rule decisions
hidden from both reviewer sheets. Copy human_review_template.json to two
separate owner-only directories and fill only human labels/evidence.
Use `evaluate` with two separate completed/partial reviewer sheets. This
NEVER certifies 500-case holdout, actual accuracy, issuer releases or V1 tag.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry, default_state
from newscatalystos.live_gold_samples import (
    freeze_real_gold_review_cases, evaluate_live_gold_reviews,
    prepare_blank_human_review_sheets, gold_freeze_progress,
    summarize_all_gold_reviews,
)
from newscatalystos.human_review_entry import (
    list_review_cases, record_review_once, recover_interrupted_review,
)
from newscatalystos.gold_scope_audit import audit_gold_scope
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__)
    base=Path.home()/"Library/Application Support/NewsCatalystOS"
    p.add_argument("--out-root",type=Path,default=PROJECT/"output"/"gold_review")
    p.add_argument("--pin-root",type=Path,default=base/"pins"/"live_gold")
    commands=p.add_subparsers(dest="command",required=True)
    freeze=commands.add_parser("freeze",help="capture actually received RSS predictions now")
    freeze.add_argument("--registry",type=Path,default=base/"providers"/"authorized_sources.json")
    freeze.add_argument("--state",type=Path,default=default_state())
    freeze.add_argument("--inbox-root",type=Path,default=base/"inbox"/"feed_triage")
    freeze.add_argument("--new-only", action="store_true",
                        help="exclude every earlier verified frozen case; never overwrite old human work")
    progress=commands.add_parser("progress",help="read-only SHA-verified candidate counts")
    progress.add_argument("--registry",type=Path,default=base/"providers"/"authorized_sources.json")
    progress.add_argument("--state",type=Path,default=default_state())
    progress.add_argument("--inbox-root",type=Path,default=base/"inbox"/"feed_triage")
    drafts=commands.add_parser("draft",help="make two BLANK review sheets on Mac")
    drafts.add_argument("--batch-folder",type=Path,required=True)
    drafts.add_argument("--expected-sha256",required=True)
    drafts.add_argument("--pin-file",type=Path,required=True)
    drafts.add_argument("--workspace-root",type=Path,
                       default=base/"gold_review_workspace")
    portfolio=commands.add_parser("aggregate",help="read-only verified all-batch metrics")
    portfolio.add_argument("--workspace-root",type=Path,
                           default=base/"gold_review_workspace")
    scope=commands.add_parser("scope-audit",help="read-only pinned source/sector sample bias audit")
    scope.add_argument("--workspace-root",type=Path,
                       default=base/"gold_review_workspace")
    browse=commands.add_parser("review-list",help="show local blind cases awaiting human review")
    browse.add_argument("--expected-sha256",required=True)
    browse.add_argument("--reviewer-slot",required=True,choices=["UNASSIGNED_A","UNASSIGNED_B"])
    browse.add_argument("--workspace-root",type=Path,default=base/"gold_review_workspace")
    browse.add_argument("--offset",type=int,default=0)
    browse.add_argument("--limit",type=int,default=10)
    submit=commands.add_parser("review-one",help="record one human decision from private source note")
    submit.add_argument("--expected-sha256",required=True)
    submit.add_argument("--reviewer-slot",required=True,choices=["UNASSIGNED_A","UNASSIGNED_B"])
    submit.add_argument("--reviewer-code",required=True)
    submit.add_argument("--workspace-root",type=Path,default=base/"gold_review_workspace")
    submit.add_argument("--case-sha256",required=True)
    submit.add_argument("--true-duplicate",required=True,choices=["true","false"])
    submit.add_argument("--important-event",required=True,choices=["true","false"])
    submit.add_argument("--evidence-file",required=True,type=Path)
    submit.add_argument("--confirm-human-review",action="store_true",required=True,
                        help="confirm real source examination, not auto-generated labels")
    recover=commands.add_parser("review-recover",
                                help="resume a fully SHA-pinned interrupted human submission")
    recover.add_argument("--expected-sha256",required=True)
    recover.add_argument("--reviewer-slot",required=True,choices=["UNASSIGNED_A","UNASSIGNED_B"])
    recover.add_argument("--workspace-root",type=Path,default=base/"gold_review_workspace")
    recover.add_argument("--case-sha256",required=True)
    read=commands.add_parser("evaluate",help="preview evidence-linked label metrics")
    read.add_argument("--batch-folder",type=Path,required=True)
    read.add_argument("--expected-sha256",required=True)
    read.add_argument("--pin-file",type=Path,required=True)
    read.add_argument("--review-file",type=Path,action="append",required=True)
    return p


def evaluate(opts: argparse.Namespace) -> tuple[int,dict]:
    try:
        if opts.command=="progress":
            return 0, gold_freeze_progress(
                _registry(opts.registry), opts.inbox_root, opts.state,
                opts.out_root, opts.pin_root,
            )
        if opts.command=="aggregate":
            return 0, summarize_all_gold_reviews(
                opts.out_root, opts.pin_root, opts.workspace_root,
            )
        if opts.command=="scope-audit":
            return 0, audit_gold_scope(
                opts.out_root, opts.pin_root, opts.workspace_root,
            )
        if opts.command=="review-list":
            return 0, list_review_cases(
                opts.out_root, opts.pin_root, opts.workspace_root,
                opts.expected_sha256, opts.reviewer_slot,
                offset=opts.offset, limit=opts.limit,
            )
        if opts.command=="review-recover":
            return 0, recover_interrupted_review(
                opts.out_root, opts.pin_root, opts.workspace_root,
                opts.expected_sha256, opts.reviewer_slot, opts.case_sha256,
            )
        if opts.command=="review-one":
            if opts.confirm_human_review is not True:
                raise SourceShareError("explicit human confirmation required")
            return 0, record_review_once(
                opts.out_root, opts.pin_root, opts.workspace_root,
                opts.expected_sha256, opts.reviewer_slot, opts.reviewer_code,
                opts.case_sha256, opts.true_duplicate == "true",
                opts.important_event == "true", opts.evidence_file,
            )
        if opts.command=="freeze":
            registry=_registry(opts.registry)
            result=freeze_real_gold_review_cases(
                registry,opts.inbox_root,opts.state,opts.out_root,opts.pin_root,
                incremental_only=getattr(opts, "new_only", False),
            )
            return 0,{
                "status":"REAL_RSS_CASES_FROZEN_AWAITING_HUMAN_GOLD_LABELS",
                "case_count":result.sample_count,
                "prior_frozen_case_count":result.prior_frozen_case_count,
                "cumulative_unique_frozen_case_count":(
                    result.prior_frozen_case_count + result.sample_count),
                "remaining_cases_to_500":max(
                    0, 500 - result.prior_frozen_case_count - result.sample_count),
                "batch_folder":str(result.folder),
                "independent_mac_pin":str(result.pin_file),
                "prediction_payload_sha256":result.payload_sha256,
                "source_fact_verified_count":0,
                "human_gold_labeled_cases":0,
                "required_independent_gold_cases":500,
                "new_provider_requests":0,
                "ai_calls":0,
                "release_gate_verified":False,
            }
        if opts.command=="draft":
            sheets=prepare_blank_human_review_sheets(
                opts.batch_folder,opts.out_root,opts.expected_sha256,
                opts.pin_file,opts.pin_root,opts.workspace_root,
            )
            return 0,{
                "status":"TWO_BLANK_REVIEWER_WORKSPACES_PREPARED",
                "blank_review_files":[str(p) for p in sheets],
                "human_gold_labeled_cases":0,
                "independent_humans_authenticated":False,
                "new_provider_requests":0,"ai_calls":0,
                "release_gate_verified":False,
            }
        if opts.command=="evaluate":
            if len(opts.review_file)!=2:
                raise SourceShareError("two separate reviewer files required")
            result=evaluate_live_gold_reviews(
                opts.batch_folder,opts.out_root,opts.expected_sha256,
                opts.pin_file,opts.pin_root,tuple(opts.review_file),
            )
            return 0,result
        raise SourceShareError("unknown gold review command")
    except (SourceShareError,OSError,ValueError,TypeError) as exc:
        return 4,{
            "status":"GOLD_REVIEW_INPUT_UNAVAILABLE",
            "error_type":type(exc).__name__,
            "human_gold_labeled_cases":0,
            "release_gate_verified":False,
            "new_provider_requests":0,
            "ai_calls":0,
        }


def main(argv:list[str]|None=None) -> int:
    code,report=evaluate(parser().parse_args(argv))
    print(json.dumps(report,sort_keys=True,ensure_ascii=False))
    return code


if __name__=="__main__":
    raise SystemExit(main())
