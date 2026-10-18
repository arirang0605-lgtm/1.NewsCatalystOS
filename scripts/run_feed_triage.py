"""One rate-limited approved feed poll -> first-stage semiconductor review queue.

No second provider request. Reuses 1_3 watermark, 2_1 text, 2_2 dedup,
2_3 conservative grouping, 2_4 rumor filter and 3_5 unknown-impact boundary.
No AI calls, DART/SEC/KRX collection, article body or trading outputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import stat
from pathlib import Path

from newscatalystos.feed_triage import triage_committed_feed, publish_feed_triage
from newscatalystos.incremental_ingest import incremental_poll
from newscatalystos.feed_recovery import (
    save_retry_checkpoint, pending_retry_checkpoints,
    check_committed_ingest, acknowledge_retry_checkpoint,
)
from newscatalystos.provider_registry import MAX_BYTES, parse_provider_registry
from newscatalystos.source_share import SourceShareError, _read_regular


def _registry(path: Path):
    try:
        info = path.lstat()
        parent = path.parent.lstat()
    except OSError as exc:
        raise SourceShareError("private source registry unavailable") from exc
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
            or not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise SourceShareError("owner-only source registry required")
    return parse_provider_registry(_read_regular(path, MAX_BYTES))


def default_state() -> Path:
    return (Path.home() / "Library" / "Application Support" /
            "NewsCatalystOS" / "state" / "incremental_feeds.sqlite3")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    base = Path.home() / "Library" / "Application Support" / "NewsCatalystOS"
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--provider-id", required=True)
    p.add_argument("--state", type=Path, default=default_state())
    p.add_argument("--dedup-state", type=Path,
                   default=base / "state" / "triage_exact_index.sqlite3")
    p.add_argument("--output-root", type=Path,
                   default=Path(__file__).resolve().parent.parent / "output")
    p.add_argument("--inbox-root", type=Path,
                   default=base / "inbox" / "feed_triage")
    p.add_argument("--replay-only", action="store_true",
                   help="Process pending durable metadata without provider HTTP")
    return p


def evaluate(opts: argparse.Namespace, *, manual_metadata: bytes | None = None) -> tuple[int, dict]:
    try:
        registry = _registry(opts.registry)
        manual = registry.active(opts.provider_id).method == "MANUAL_METADATA"
        if manual_metadata is not None and not manual:
            raise SourceShareError("local metadata input requires explicit manual source")
        if manual_metadata is not None:
            from newscatalystos.new_source_adapter import parse_authorized_feed
            # Reject malformed/body-bearing input before any ledger mutation.
            parse_authorized_feed(registry, opts.provider_id, manual_metadata)
        if manual and manual_metadata is None and not opts.replay_only:
            raise SourceShareError("manual source requires explicit local metadata input")
        pending = pending_retry_checkpoints(
            opts.inbox_root, opts.state, registry, opts.provider_id,
        )
        recovered = bool(pending)
        if recovered:
            receipt = pending[0]
            poll = receipt.poll
        elif opts.replay_only:
            return 0, {"status": "NO_PENDING_REPLAY",
                       "provider_id": opts.provider_id, "network_called": False,
                       "ai_call_count": 0}
        else:
            written = []
            poll = incremental_poll(
                registry, opts.provider_id, opts.state,
                fetcher=(lambda reg, name, at=None: parse_authorized_feed(
                    reg, name, manual_metadata, observed_at=at)) if manual else None,
                before_commit=lambda result: written.append(
                    save_retry_checkpoint(opts.inbox_root, result)),
            )
            if len(written) != 1:
                raise SourceShareError("feed poll did not produce durable retry checkpoint")
            receipt = written[0]
        check_committed_ingest(opts.state, poll)
        # The ingestion commit completes before analysis; replay begins NOW,
        # never retrospectively at the old source/publication timestamp.
        checked = datetime.now(timezone.utc)
        screened = triage_committed_feed(
            registry, poll, opts.dedup_state, decision_at=checked,
            now=checked,
            replayed_from_checkpoint=recovered,
        )
        folder = publish_feed_triage(screened, opts.output_root)
        acknowledge_retry_checkpoint(
            opts.inbox_root, receipt, folder, screened.payload_sha256,
        )
        return 0, {
            "status": ("RECOVERED_FROM_DURABLE_CHECKPOINT"
                       if recovered else "FEED_METADATA_TRIAGE_READY"),
            "network_called": not recovered and not manual,
            **({"acquisition_method": "MANUAL_METADATA"} if manual else {}),
            "provider_id": opts.provider_id,
            "checkpoint_sha256": receipt.payload_sha256,
            "poll_status": poll.status,
            "feed_count": screened.observed_count,
            "new_provider_ids": screened.newly_seen_count,
            "semiconductor_keyword_candidates": screened.keyword_candidate_count,
            "triage_payload_sha256": screened.payload_sha256,
            "private_triage_folder": str(folder),
            "verified_fact_count": 0, "ai_call_count": 0,
            "stored_article_body_count": 0,
        }
    except (SourceShareError, OSError, ValueError) as exc:
        message = str(exc)
        if "rate or backoff" in message or "hourly request budget" in message:
            return 0, {
                "status": "NOT_DUE",
                "provider_id": opts.provider_id,
                "new_provider_ids": 0, "ai_call_count": 0,
            }
        return 4, {
            "status": "DATA_UNAVAILABLE",
            "reason": "APPROVED_FEED_OR_TRIAGE_FAILED",
            "error_type": type(exc).__name__,
            "verified_fact_count": 0, "ai_call_count": 0,
        }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
