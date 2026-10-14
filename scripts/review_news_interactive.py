"""Interactive, one-case-at-a-time human review of SHA-pinned live RSS cases.

This program cannot decide answers by itself. It opens no URLs, fetches no
news, uses no AI, and never changes the frozen prediction source. The human
reviews the displayed citation themselves and supplies both decisions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.human_review_entry import list_review_cases, record_review_once
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch-sha256", required=True)
    p.add_argument("--slot", choices=("UNASSIGNED_A", "UNASSIGNED_B"), required=True)
    p.add_argument("--reviewer-code", required=True)
    p.add_argument("--out-root", type=Path, default=PROJECT / "output" / "gold_review")
    p.add_argument("--pin-root", type=Path, default=base / "pins" / "live_gold")
    p.add_argument("--workspace-root", type=Path, default=base / "gold_review_workspace")
    return p


def _affirm(input_func, question: str) -> bool:
    response = input_func(question).strip().lower()
    if response not in ("yes", "no"):
        raise SourceShareError("only an explicit yes or no is accepted")
    return response == "yes"


def run_one(opts: argparse.Namespace, *, input_func=input, output_func=print) -> tuple[int, dict]:
    """Only one explicitly reviewed event per invocation. No automated labels."""
    try:
        page = list_review_cases(
            opts.out_root, opts.pin_root, opts.workspace_root,
            opts.batch_sha256, opts.slot, limit=1,
        )
        if not page["cases"]:
            return 0, {"status": "NO_UNREVIEWED_CASE", "remaining": 0,
                       "human_labels_added": 0, "release_gate_verified": False}
        item = page["cases"][0]
        output_func("Source:", item["source_url"])
        output_func("Headline:", item["headline"])
        output_func("Case SHA:", item["case_sha256"])
        if not _affirm(input_func, "Did you personally examine the source and sufficient evidence? (yes/no): "):
            return 0, {"status": "SKIPPED_NOT_HUMAN_REVIEWED",
                       "human_labels_added": 0, "release_gate_verified": False}
        duplicate = _affirm(input_func, "Is this a duplicate of an already-known event? (yes/no): ")
        important = _affirm(input_func, "Is this an important NEW economic event? (yes/no): ")
        output_func("Write your own brief evidence note. Do not paste paid article text or credentials.")
        rationale = input_func("Evidence link/context and reason (at least 16 UTF-8 bytes): ").strip()
        evidence = rationale.encode("utf-8")
        if not 16 <= len(evidence) <= 16384 or any(ord(c) < 32 for c in rationale):
            raise SourceShareError("reviewer-authored bounded single-line evidence required")
        if not _affirm(input_func, "Confirm that these decisions and note are your own human review? (yes/no): "):
            return 0, {"status": "SKIPPED_NOT_HUMAN_REVIEWED",
                       "human_labels_added": 0, "release_gate_verified": False}
        slot_dir = (Path(opts.workspace_root) / ("gold_batch_" + opts.batch_sha256) /
                    opts.slot)
        note = slot_dir / ("evidence_" + item["case_sha256"] + ".txt")
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(note, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(evidence + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            note.unlink(missing_ok=True)
            raise
        result = record_review_once(
            opts.out_root, opts.pin_root, opts.workspace_root,
            opts.batch_sha256, opts.slot, opts.reviewer_code,
            item["case_sha256"], duplicate, important, note,
        )
        return 0, {"status": result["status"], "case_sha256": item["case_sha256"],
                   "human_labels_added": 1,
                   "human_independence_certified": False,
                   "release_gate_verified": False}
    except (SourceShareError, OSError, ValueError, EOFError) as exc:
        return 4, {"status": "HUMAN_REVIEW_INPUT_UNAVAILABLE",
                   "error_type": type(exc).__name__, "human_labels_added": 0,
                   "release_gate_verified": False}


def main(argv: list[str] | None = None) -> int:
    code, report = run_one(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
