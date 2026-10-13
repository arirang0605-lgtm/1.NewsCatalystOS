"""Verify actual cross-device backup/isolated restore of NewsCatalystOS state.

The live state stays read-only. Does not touch EraLeader, install schedules,
fetch external APIs, or make a V1.0 five-trading-day release assertion.
Snapshots are private under .local_backups/ (excluded by .gitignore).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from newscatalystos.physical_recovery import ALLOWED, verify_physical_recovery
from newscatalystos.physical_recovery_pin import (
    record_recovery_pin, verify_recovery_from_pin,
)
from newscatalystos.source_share import SourceShareError


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parent.parent
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-name", choices=("ALL", *sorted(ALLOWED)), default="ALL")
    p.add_argument("--backup-root", type=Path,
                   default=project / ".local_backups")
    p.add_argument("--restore-parent", type=Path,
                   default=base / "restore_checks")
    p.add_argument("--pin-root", type=Path,
                   default=base / "pins" / "physical_recovery")
    p.add_argument("--verify-pin", type=Path,
                   help="later re-restore from a previously retained Mac-side SHA pin")
    return p


def evaluate(opts: argparse.Namespace) -> tuple[int, dict]:
    base = Path.home() / "Library/Application Support/NewsCatalystOS/state"
    source_names = (sorted(ALLOWED) if opts.source_name == "ALL"
                    else (opts.source_name,))
    results = []
    try:
        if opts.verify_pin is not None:
            restored = verify_recovery_from_pin(
                opts.verify_pin, opts.pin_root, opts.backup_root,
                opts.restore_parent,
            )
            return 0, {
                "status": "STORED_PIN_COLD_RESTORE_PASS",
                "restored_source": restored.name,
                "independent_pin_rechecked": True,
                "restored_sqlite_integrity": True,
                "five_trading_day_operation_certified": False,
                "offsite_backup_verified": False,
                "v1_release_ready": False,
            }
        for name in source_names:
            verified = verify_physical_recovery(
                base / name, opts.backup_root, opts.restore_parent,
            )
            pinned = record_recovery_pin(
                verified, opts.backup_root, opts.pin_root,
            )
            results.append({
                "source": name,
                "independent_pin_saved": pinned.pin_path.is_file(),
                "snapshot_bytes": verified.snapshot_bytes,
                "backup_on_distinct_device": verified.source_and_backup_on_different_devices,
                "isolated_restore": verified.restored_to_separate_directory,
                "restored_sqlite_integrity": verified.restored_sqlite_integrity,
            })
    except (SourceShareError, OSError, ValueError) as exc:
        return 4, {
            "status": "LOCAL_PHYSICAL_RECOVERY_NOT_VERIFIED",
            "successful_state_count": len(results),
            "error_type": type(exc).__name__,
            "five_trading_day_operation_certified": False,
            "offsite_backup_verified": False,
        }
    return 0, {
        "status": "LOCAL_CROSS_DEVICE_SQLITE_RECOVERY_AND_PIN_PASS",
        "successful_state_count": len(results),
        "results": results,
        "five_trading_day_operation_certified": False,
        "offsite_backup_verified": False,
        "v1_release_ready": False,
    }


def main(argv: list[str] | None = None) -> int:
    code, report = evaluate(parser().parse_args(argv))
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
