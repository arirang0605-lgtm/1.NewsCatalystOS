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
from .physical_recovery import ALLOWED
from .physical_recovery_pin import checked_local_recovery_sources
from .market_calendar_review import CalendarReview
from .source_share import SourceShareError, _json, _read_regular, _when

ACK_FILENAME = re.compile(r"[0-9a-f]{64}\.json\Z")


def operation_status(
    registry: ProviderRegistry, inbox_root: Path, state: Path, *,
    now: datetime | None = None,
    physical_pin_root: Path | None = None,
    backup_root: Path | None = None,
    calendar_review: CalendarReview | None = None,
) -> dict:
    """Report actual completed source/day coverage, not a release approval."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved registry required")
    authorized = tuple(sorted(registry.approved_ids(at=at)))
    if (physical_pin_root is None) != (backup_root is None):
        raise SourceShareError("both physical pin and backup roots required")
    local_restored = (checked_local_recovery_sources(
        physical_pin_root, backup_root,
    ) if physical_pin_root is not None else frozenset())
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
    if calendar_review is not None and not isinstance(calendar_review, CalendarReview):
        raise SourceShareError("validated calendar review required")
    if calendar_review is not None and calendar_review.reviewed_at > at:
        raise SourceShareError("calendar reviewed after operation check")
    # A private human-reviewed snapshot is informative, not independently
    # authenticated exchange session evidence and never a release gate.
    calendar_matched = sorted(set(fully_covered).intersection(
        calendar_review.session_dates if calendar_review else frozenset()))
    # For each actually observed day, expose missing approved feeds for operator
    # follow-up. Repeated hourly ACKs never multiply day/source coverage.
    daily_coverage = [
        {
            "date": day,
            "completed_sources": sorted(providers),
            "missing_sources": sorted(set(authorized) - providers),
        }
        for day, providers in sorted(days.items())
    ]
    partial_days = [row["date"] for row in daily_coverage
                    if row["missing_sources"]]
    pending = sum(len(pending_retry_checkpoints(
        root, state, registry, name, now=at,
    )) for name in authorized)
    return {
        "status": ("FEED_RECOVERY_PENDING" if pending else
                   "FEED_RUNS_RECORDED" if fully_covered else "OPERATIONS_IN_PROGRESS"),
        "observation_blocks_operation": False,
        "recorded_collection_days": len(fully_covered),
        "evidence_scope": "FEED_COLLECTION_ONLY",
        "approved_source_count": len(authorized),
        "completed_triage_receipts": completed,
        "days_with_all_sources": list(fully_covered),
        "daily_source_coverage": daily_coverage,
        "partial_source_days": partial_days,
        "weekday_candidate_days": list(weekday_candidates),
        "weekday_candidate_count": len(weekday_candidates),
        "operator_reviewed_calendar_days": calendar_matched,
        "operator_reviewed_calendar_day_count": len(calendar_matched),
        "market_calendar_review_provided": calendar_review is not None,
        "pending_recovery_checkpoints": pending,
        "verified_exchange_trading_days": 0,
        "five_trading_day_operation_certified": False,
        "independent_physical_recovery_verified": set(ALLOWED).issubset(local_restored),
        "local_recovery_source_count": len(local_restored),
        "offsite_backup_verified": False,
        "v1_release_ready": False,
    }
