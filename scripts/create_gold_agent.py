"""Install only a separate private Mac RSS-gold freeze LaunchAgent (NOT RSS).

Existing RSS launchd service remains unchanged. Gold freeze reads already
completed, authorized RSS ACKs and puts SHA-pinned blind drafts in private
Mac/T5DATA; never populates truth or calls any data/AI provider.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import stat
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.source_share import SourceShareError
from scripts.create_triage_agent import _owner_dir

LABEL = "com.newscatalystos.gold"
INTERVAL = 3600


def gold_agent_spec(python: Path, project: Path, base: Path, logs: Path,
                    *, interval: int = INTERVAL) -> dict:
    if type(interval) is not int or not 1800 <= interval <= 3600:
        raise SourceShareError("gold capture interval outside 30-60 minutes")
    selected = (python, project, base, logs)
    if any(not Path(x).is_absolute() or ".." in Path(x).parts
           or any(part.casefold() == "eraleader" for part in Path(x).parts)
           for x in selected):
        raise SourceShareError("absolute NewsCatalystOS-only gold capture paths required")
    project, base, logs = Path(project), Path(base), Path(logs)
    script = project / "scripts" / "run_gold_capture_once.py"
    if not script.is_file():
        raise SourceShareError("existing gold capture runner required")
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(python), str(script),
            "--registry", str(base / "providers" / "authorized_sources.json"),
            "--inbox-root", str(base / "inbox" / "feed_triage"),
            "--state", str(base / "state" / "incremental_feeds.sqlite3"),
            "--out-root", str(project / "output" / "gold_review"),
            "--pin-root", str(base / "pins" / "live_gold"),
            "--workspace-root", str(base / "gold_review_workspace"),
            "--lock-root", str(base / "state"),
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
        "StandardOutPath": str(logs / "gold_stdout.log"),
        "StandardErrorPath": str(logs / "gold_stderr.log"),
    }


def write_gold_agent(spec: dict, dest: Path, logs: Path) -> Path:
    dest, logs = Path(dest), Path(logs)
    if (not dest.is_absolute() or dest.name != LABEL + ".plist"
            or dest.is_symlink() or spec.get("Label") != LABEL
            or spec.get("StandardOutPath") != str(logs / "gold_stdout.log")
            or spec.get("StandardErrorPath") != str(logs / "gold_stderr.log")
            or spec.get("StartInterval") != INTERVAL
            or spec.get("RunAtLoad") is not False):
        raise SourceShareError("unexpected gold launch agent config")
    _owner_dir(dest.parent)
    _owner_dir(logs)
    for name in ("gold_stdout.log", "gold_stderr.log"):
        path = logs / name
        if path.exists() or path.is_symlink():
            entry = path.lstat()
            if (not stat.S_ISREG(entry.st_mode) or entry.st_uid != os.geteuid()
                    or stat.S_IMODE(entry.st_mode) & 0o077 or path.is_symlink()):
                raise SourceShareError("gold launch log not owner-only")
        else:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags, 0o600)
            os.close(fd)
    body = plistlib.dumps(spec, sort_keys=True)
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(dest.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true",
                   help="only write new private plist; launchctl bootstrap is separate")
    p.add_argument("--dest", type=Path,
                   default=Path.home() / "Library/LaunchAgents" / (LABEL + ".plist"))
    opts = p.parse_args(argv)
    project = Path(__file__).resolve().parent.parent
    base = Path.home() / "Library/Application Support/NewsCatalystOS"
    try:
        config = gold_agent_spec(Path(sys.executable), project, base, base / "logs")
        if opts.write:
            write_gold_agent(config, opts.dest, base / "logs")
        print("GOLD_SNAPSHOT_LAUNCHD_CONFIG_VALID",
              "WRITTEN_NOT_ACTIVATED" if opts.write else "DRY_RUN",
              "INTERVAL", config["StartInterval"], "SOURCE_NETWORK_CALLS", 0,
              "HUMAN_LABELS", 0)
        return 0
    except (OSError, SourceShareError, ValueError, TypeError) as exc:
        print("GOLD_LAUNCHD_CONFIG_UNAVAILABLE", type(exc).__name__)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
