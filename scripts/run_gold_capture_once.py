"""Prospective SHA-pinned blind RSS-gold capture from EXISTING completed ACKs.

Safe for a separate Mac user LaunchAgent: no feed/official API requests, no
models, no article bodies, no human labels. Never changes RSS ingestion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts.run_feed_triage import _registry, default_state
from scripts.create_triage_agent import V1_PROVIDERS
from newscatalystos.evidence_archive import _private_root
from newscatalystos.live_gold_samples import (
    gold_freeze_progress, freeze_real_gold_review_cases,
    prepare_blank_human_review_sheets, evaluate_live_gold_reviews,
)
from newscatalystos.source_share import SourceShareError, _when


def parser() -> argparse.ArgumentParser:
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", type=Path, default=base / "providers" / "authorized_sources.json")
    p.add_argument("--inbox-root", type=Path, default=base / "inbox" / "feed_triage")
    p.add_argument("--state", type=Path, default=default_state())
    p.add_argument("--out-root", type=Path, default=PROJECT / "output" / "gold_review")
    p.add_argument("--pin-root", type=Path, default=base / "pins" / "live_gold")
    p.add_argument("--workspace-root", type=Path, default=base / "gold_review_workspace")
    p.add_argument("--lock-root", type=Path, default=base / "state")
    return p


def _lock(root: Path):
    base = _private_root(root)
    path = base / "gold_capture.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise SourceShareError("gold capture lock not owner-private")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SourceShareError("gold capture already running") from exc
        return fd
    except BaseException:
        os.close(fd)
        raise


def _finish_missing_workspaces(out_root: Path, pin_root: Path,
                               workspace_root: Path, *, now: datetime) -> int:
    """Repair only ABSENT blank worksheets, never replace existing human work."""
    from newscatalystos.live_gold_samples import _prior_frozen_ids
    _, digests = _prior_frozen_ids(out_root, pin_root, now)
    protected = _private_root(workspace_root)
    created = 0
    for digest in digests:
        batch = out_root / ("gold_batch_" + digest)
        pin = pin_root / ("gold_batch_" + digest + ".pin.json")
        reviews_dir = protected / batch.name
        if reviews_dir.is_symlink():
            raise SourceShareError("symlink gold reviewer workspace")
        if not reviews_dir.exists():
            prepare_blank_human_review_sheets(
                batch, out_root, digest, pin, pin_root, protected, now=now,
            )
            created += 1
            continue
        # Existing submissions must validate; never auto-reset a bad or
        # incomplete human reviewer directory.
        a = reviews_dir / "UNASSIGNED_A" / "answers.json"
        b = reviews_dir / "UNASSIGNED_B" / "answers.json"
        evaluate_live_gold_reviews(
            batch, out_root, digest, pin, pin_root, (a, b), now=now,
        )
    return created


def capture(opts: argparse.Namespace, *, now: datetime | None = None,
            registry_reader=_registry) -> tuple[int, dict]:
    """One finite, exclusive sweep; no external calls or human truth claims."""
    lock_fd = None
    try:
        checked = _when((now or datetime.now(timezone.utc)).isoformat(), "gold capture start")
        registry = registry_reader(opts.registry)
        if set(registry.approved_ids(at=checked)) != set(V1_PROVIDERS):
            raise SourceShareError("exact two approved V1 RSS sources required")
        lock_fd = _lock(opts.lock_root)
        snapshot = gold_freeze_progress(
            registry, opts.inbox_root, opts.state, opts.out_root, opts.pin_root,
            now=checked,
        )
        added = 0
        if snapshot["new_unfrozen_cases"]:
            result = freeze_real_gold_review_cases(
                registry, opts.inbox_root, opts.state, opts.out_root, opts.pin_root,
                now=checked, incremental_only=True,
            )
            added = result.sample_count
            if added != snapshot["new_unfrozen_cases"]:
                raise SourceShareError("new gold case count changed during freeze")
        forms = _finish_missing_workspaces(
            opts.out_root, opts.pin_root, opts.workspace_root,
            now=datetime.now(timezone.utc) if now is None else checked,
        )
        updated = gold_freeze_progress(
            registry, opts.inbox_root, opts.state, opts.out_root, opts.pin_root,
            now=datetime.now(timezone.utc) if now is None else checked,
        )
        if updated["new_unfrozen_cases"] != 0:
            raise SourceShareError("unfinished new gold cases still available")
        return 0, {
            "status": ("NEW_VERIFIED_RSS_CANDIDATES_FROZEN"
                       if added else "NO_NEW_VERIFIED_RSS_CANDIDATES"),
            "newly_frozen_cases": added,
            "created_blank_reviewer_workspaces": forms,
            "total_pinned_unique_cases": updated["distinct_sha_pinned_cases"],
            "remaining_to_500": updated["remaining_to_500_if_frozen"],
            "source_network_requests": 0,
            "ai_calls": 0,
            "human_gold_labels_created": 0,
            "release_gate_verified": False,
        }
    except (SourceShareError, OSError, ValueError, TypeError) as exc:
        return 4, {
            "status": "AUTOMATIC_GOLD_CAPTURE_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "source_network_requests": 0, "ai_calls": 0,
            "human_gold_labels_created": 0,
            "release_gate_verified": False,
        }
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


def main(argv: list[str] | None = None) -> int:
    code, report = capture(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
