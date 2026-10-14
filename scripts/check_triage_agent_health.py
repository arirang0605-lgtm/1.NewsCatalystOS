"""6_5 read-only health check for the existing approved RSS launchd agent.

Does not start/stop agents, poll feeds, modify a database, or certify exchange
trading days. A launchd 'not running' state is normal between hourly ticks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from xml.parsers.expat import ExpatError

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.source_share import SourceShareError
from scripts.create_triage_agent import LABEL, INTERVAL, V1_PROVIDERS, launchd_spec

MAX_LOG_TAIL = 65536
GRACE_SECONDS = 900
SERVICE_RE = re.compile(r"^\s*(runs|last exit code|run interval) = (\d+)(?: seconds)?$", re.M)


def _private_regular(path: Path) -> os.stat_result:
    if path.is_symlink():
        raise SourceShareError("private agent file cannot be symlink")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("agent file must be owner-only")
    return info


def _safe_read(path: Path, *, limit: int) -> bytes:
    info = _private_regular(path)
    if info.st_size > limit:
        raise SourceShareError("agent config exceeds limit")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        current = os.fstat(fd)
        if current.st_ino != info.st_ino or current.st_dev != info.st_dev:
            raise SourceShareError("agent file changed during read")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(limit + 1)
        if len(body) > limit:
            raise SourceShareError("agent config exceeds limit")
        return body
    finally:
        os.close(fd)


def _last_log_line(path: Path) -> tuple[dict, float]:
    info = _private_regular(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        current = os.fstat(fd)
        if current.st_ino != info.st_ino or current.st_dev != info.st_dev:
            raise SourceShareError("agent log changed during read")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            start = max(0, current.st_size - MAX_LOG_TAIL)
            stream.seek(start)
            body = stream.read(MAX_LOG_TAIL)
        lines = body.splitlines()
        if start:
            lines = lines[1:]  # discard a potentially truncated JSON line
        if not lines:
            raise SourceShareError("no complete agent run log")
        result = json.loads(lines[-1])
        if not isinstance(result, dict):
            raise SourceShareError("invalid agent log entry")
        return result, current.st_mtime
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SourceShareError("invalid agent run log") from exc
    finally:
        os.close(fd)


def evaluate_health(*, plist_data: bytes, project: Path, base: Path,
                    launch_text: str, duplicate_active: bool, last_log: dict,
                    log_mtime: float, now: datetime) -> dict:
    """Validate exact installed schedule and fresh successful tick; no network."""
    result = {"status": "AGENT_UNHEALTHY", "reasons": [],
              "expected_providers": list(V1_PROVIDERS),
              "last_tick_status": "UNKNOWN",
              "last_exit_code": None,
              "runs": 0, "log_age_seconds": None}
    reasons = result["reasons"]
    try:
        spec = plistlib.loads(plist_data)
        args = spec["ProgramArguments"]
        if (not isinstance(args, list) or not args or
                not isinstance(args[0], str) or
                not Path(args[0]).is_absolute() or
                not Path(args[0]).name.startswith("python")):
            raise SourceShareError("unexpected launchd python binary")
        expected = launchd_spec(
            Path(args[0]), project,
            base / "providers" / "authorized_sources.json",
            base / "state" / "incremental_feeds.sqlite3",
            base / "state" / "triage_exact_index.sqlite3",
            base / "inbox" / "feed_triage", base / "logs")
        if spec != expected:
            reasons.append("AGENT_CONFIG_MISMATCH")
    except (KeyError, ValueError, TypeError, ExpatError,
            plistlib.InvalidFileException, SourceShareError):
        reasons.append("AGENT_CONFIG_INVALID")

    parsed = dict((name, int(value)) for name, value in SERVICE_RE.findall(launch_text))
    result["runs"] = parsed.get("runs", 0)
    result["last_exit_code"] = parsed.get("last exit code")
    if (parsed.get("run interval") != INTERVAL or
            result["runs"] < 1 or result["last_exit_code"] is None):
        reasons.append("AGENT_NOT_RUNNING_AS_EXPECTED")
    elif result["last_exit_code"] != 0:
        reasons.append("LAST_RUN_FAILED")
    if duplicate_active:
        reasons.append("DUPLICATE_SCHEDULER_ACTIVE")

    age = (now.timestamp() - log_mtime)
    if age < -GRACE_SECONDS:
        reasons.append("LOG_MTIME_IN_FUTURE")
    else:
        result["log_age_seconds"] = max(0, int(age))
        if age > 2 * INTERVAL + GRACE_SECONDS:
            reasons.append("NO_RECENT_TICK")
    providers = last_log.get("providers")
    rows = (providers if isinstance(providers, list) and
            all(isinstance(p, dict) for p in providers) else [])
    actual_ids = [p.get("provider_id") for p in rows]
    result["last_tick_status"] = last_log.get("status", "UNKNOWN")
    if (last_log.get("status") != "SCHEDULED_TICK_COMPLETE_OR_NOT_DUE"
            or last_log.get("providers_failed") != 0
            or sorted(actual_ids) != sorted(V1_PROVIDERS)
            or len(actual_ids) != len(V1_PROVIDERS)
            or last_log.get("ai_call_count") != 0
            or last_log.get("official_era_api_request_count") != 0
            or last_log.get("stored_article_body_count") != 0
            or any(p.get("status") not in
                   {"FEED_METADATA_TRIAGE_READY", "NOT_DUE", "NO_PENDING_REPLAY"}
                   for p in rows)):
        reasons.append("LAST_TICK_UNVERIFIED")
    if not reasons:
        result["status"] = "AGENT_HEALTHY_OBSERVED"
    return result


def check(*, project: Path, base: Path, home: Path | None = None,
          now: datetime | None = None, runner=subprocess.run) -> tuple[int, dict]:
    home = home or Path.home()
    plist = home / "Library" / "LaunchAgents" / (LABEL + ".plist")
    stdout = base / "logs" / "triage_stdout.log"
    stderr = base / "logs" / "triage_stderr.log"
    try:
        data = _safe_read(plist, limit=16384)
        _private_regular(stderr)
        last_log, log_mtime = _last_log_line(stdout)
        uid = os.geteuid()
        live = runner(["launchctl", "print", f"gui/{uid}/{LABEL}"],
                      capture_output=True, text=True, timeout=5, check=False)
        competing = runner(
            ["launchctl", "print", f"gui/{uid}/com.newscatalystos.incremental"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if live.returncode != 0:
            return 4, {"status": "AGENT_UNHEALTHY",
                       "reasons": ["AGENT_NOT_LOADED"]}
        report = evaluate_health(
            plist_data=data, project=project, base=base,
            launch_text=live.stdout[:25000],
            duplicate_active=(competing.returncode == 0),
            last_log=last_log, log_mtime=log_mtime,
            now=now or datetime.now(timezone.utc),
        )
        return (0 if report["status"] == "AGENT_HEALTHY_OBSERVED" else 4), report
    except (SourceShareError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return 4, {"status": "AGENT_EVIDENCE_UNAVAILABLE",
                   "error_type": type(exc).__name__}


def main() -> int:
    project = Path(__file__).resolve().parent.parent
    base = Path.home() / "Library" / "Application Support" / "NewsCatalystOS"
    code, report = check(project=project, base=base)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
