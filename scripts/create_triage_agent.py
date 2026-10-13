"""6_5 private user launchd schedule for already approved NewsCatalystOS RSS.

Generate only a non-secret LaunchAgent; activation is a separate explicit
launchctl action. This does not change any EraLeader or official API source.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import stat
import sys

from newscatalystos.source_share import SourceShareError

LABEL = "com.newscatalystos.triage"
V1_PROVIDERS = ("mss-official-press", "newswire-public-rss-it")
INTERVAL = 3600


def launchd_spec(python: Path, project: Path, registry: Path,
                 state: Path, dedup: Path, inbox: Path,
                 logs: Path, *, interval: int = INTERVAL) -> dict:
    if type(interval) is not int or not 1800 <= interval <= 3600:
        raise SourceShareError("triage cadence must be 30 to 60 minutes")
    inputs = (python, project, registry, state, dedup, inbox, logs)
    if any(not Path(p).is_absolute() or ".." in Path(p).parts
           or any(s.casefold() == "eraleader" for s in Path(p).parts)
           for p in inputs):
        raise SourceShareError("absolute non-EraLeader paths required")
    project = Path(project)
    if not (project / "scripts" / "run_scheduled_triage.py").is_file():
        raise SourceShareError("existing NewsCatalystOS scheduler entrypoint required")
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(python), str(project / "scripts" / "run_scheduled_triage.py"),
            "--once",
            "--registry", str(registry),
            "--state", str(state),
            "--dedup-state", str(dedup),
            "--inbox-root", str(inbox),
            "--output-root", str(project / "output"),
            *sum((["--provider-id", n] for n in V1_PROVIDERS), []),
        ],
        "EnvironmentVariables": {
            "PYTHONPATH": str(project / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "WorkingDirectory": str(project),
        "StartInterval": interval,
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
        "Umask": 0o077,
        "StandardOutPath": str(logs / "triage_stdout.log"),
        "StandardErrorPath": str(logs / "triage_stderr.log"),
    }


def _owner_dir(path: Path, *, mode: int = 0o700) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.is_symlink():
        raise SourceShareError("absolute non-symlink directory required")
    path.mkdir(mode=mode, parents=True, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o022):
        raise SourceShareError("owner-controlled launchd directory required")
    return path


def write_launch_agent(spec: dict, dest: Path, log_root: Path) -> Path:
    dest = Path(dest)
    log_root = Path(log_root)
    if dest.name != LABEL + ".plist" or not dest.is_absolute():
        raise SourceShareError("unexpected launchd label path")
    _owner_dir(dest.parent, mode=0o700)
    _owner_dir(log_root, mode=0o700)
    if (log_root.resolve() == dest.parent.resolve()
            or spec.get("Label") != LABEL
            or spec.get("StandardOutPath") != str(log_root / "triage_stdout.log")
            or spec.get("StandardErrorPath") != str(log_root / "triage_stderr.log")):
        raise SourceShareError("unexpected launchd service or output paths")
    # Log outputs can be created by launchd; initialize as owner-only first.
    for name in ("triage_stdout.log", "triage_stderr.log"):
        path = log_root / name
        if path.exists() or path.is_symlink():
            if path.is_symlink():
                raise SourceShareError("launchd log symlink not permitted")
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise SourceShareError("launchd logs must be owner-only")
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags, 0o600)
            os.close(fd)
    body = plistlib.dumps(spec, sort_keys=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(dest, flags, 0o600)
    except FileExistsError as exc:
        raise SourceShareError("existing launchd service cannot be overwritten") from exc
    with os.fdopen(fd, "wb") as file:
        file.write(body)
        file.flush()
        os.fsync(file.fileno())
    dirfd = os.open(dest.parent, os.O_RDONLY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)
    return dest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parent.parent
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    p.add_argument("--write", action="store_true", help="create, do not activate launchd")
    p.add_argument("--interval", type=int, default=INTERVAL)
    p.add_argument("--dest", type=Path,
                   default=Path.home() / "Library/LaunchAgents" / (LABEL + ".plist"))
    opts = p.parse_args(argv)
    try:
        logs = base / "logs"
        spec = launchd_spec(
            Path(sys.executable), project,
            base / "providers" / "authorized_sources.json",
            base / "state" / "incremental_feeds.sqlite3",
            base / "state" / "triage_exact_index.sqlite3",
            base / "inbox" / "feed_triage", logs,
            interval=opts.interval,
        )
        if opts.write:
            write_launch_agent(spec, opts.dest, logs)
        print("TRIAGE_LAUNCHD_CONFIG_VALID",
              "WRITTEN_NOT_ACTIVATED" if opts.write else "DRY_RUN",
              "INTERVAL", spec["StartInterval"],
              "EXPLICIT_PROVIDERS", len(V1_PROVIDERS))
        return 0
    except (SourceShareError, OSError, ValueError) as exc:
        print("LAUNCHD_CONFIG_UNAVAILABLE", type(exc).__name__)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
