"""6_5 local evidence of repeated feed triage runs; never certify trading days.

Counts validated, owner-private checkpoint acknowledgments only. A successful
poll+triage on five different weekdays is not by itself proof of five Korean
exchange sessions, source freshness, external publication time, or V1 release.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .evidence_archive import _private_root
from .feed_recovery import (
    _ack_is_valid, pending_retry_checkpoints,
    read_retry_checkpoint, check_committed_ingest,
)
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _json, _read_regular, _when

ACK_FILENAME = re.compile(r"[0-9a-f]{64}\.json\Z")


def operation_status(
    registry: ProviderRegistry, inbox_root: Path, state: Path, *,
    now: datetime | None = None,
) -> dict:
    """Report actual completed source/day coverage, not a release approval."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved registry required")
    authorized = tuple(sorted(registry.approved_ids(at=at)))
    root = _private_root(inbox_root)
    ack_root = root / "acked"
    days: dict[str, set[str]] = {}
    completed = 0
    if ack_root.exists() or ack_root.is_symlink():
        ack_root = _private_root(ack_root)
        for entry in sorted(ack_root.iterdir()):
            if (not ACK_FILENAME.fullmatch(entry.name) or entry.is_symlink()
                    or not entry.is_file()):
                raise SourceShareError("invalid operations receipt in private folder")
            digest = entry.name[:-5]
            if not _ack_is_valid(root, digest, at):
                raise SourceShareError("unverified operational receipt")
            record = _json(_read_regular(entry, 4096), "operations receipt")
            provider = record["provider_id"]
            if provider not in authorized:
                continue
            checkpoint = read_retry_checkpoint(
                root / ("pending_" + digest), root, digest,
            )
            if (checkpoint.poll.provider_id != provider
                    or len(checkpoint.poll.observations) != record["record_count"]
                    or checkpoint.poll.usable_from != _when(
                        record["poll_verified_at"], "completed poll watermark")):
                raise SourceShareError("operational receipt does not match source checkpoint")
            check_committed_ingest(state, checkpoint.poll, now=at)
            # A completed analysis can be counted only on the recorded day,
            # not the poll's earlier timestamp or a retroactive as-of date.
            day = _when(record["confirmed_at"], "operation confirmed").astimezone(
                ZoneInfo("Asia/Seoul")).date().isoformat()
            days.setdefault(day, set()).add(provider)
            completed += 1
    fully_covered = tuple(sorted(day for day, providers in days.items()
                                 if set(authorized) <= providers and authorized))
    weekday_candidates = tuple(day for day in fully_covered
                               if datetime.fromisoformat(day).weekday() < 5)
    pending = sum(len(pending_retry_checkpoints(
        root, state, registry, name, now=at,
    )) for name in authorized)
    return {
        "status": ("WEEKDAY_COVERAGE_RECORDED_NEEDS_EXCHANGE_DAY_REVIEW"
                   if len(weekday_candidates) >= 5 else "OPERATIONS_IN_PROGRESS"),
        "approved_source_count": len(authorized),
        "completed_triage_receipts": completed,
        "days_with_all_sources": list(fully_covered),
        "weekday_candidate_days": list(weekday_candidates),
        "weekday_candidate_count": len(weekday_candidates),
        "pending_recovery_checkpoints": pending,
        "verified_exchange_trading_days": 0,
        "five_trading_day_operation_certified": False,
        "independent_physical_recovery_verified": False,
        "v1_release_ready": False,
    }
