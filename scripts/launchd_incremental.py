"""Build a private macOS launchd *template*; never activate background jobs.

Use the resulting private plist with launchctl under the configured source policy.
No API secrets or network requests are stored or made here.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import stat
import sys

from newscatalystos.source_share import SourceShareError

LABEL = "com.newscatalystos.incremental"
INTERVAL = 900


def launchd_spec(
    python_exe: Path, runner: Path, registry: Path, state: Path,
    src: Path, *, interval: int = INTERVAL,
) -> dict:
    if type(interval) is not int or not 300 <= interval <= 3600:
        raise SourceShareError("launch interval must be 5 to 60 minutes")
    paths = (python_exe, runner, registry, state, src)
    if any(not Path(p).is_absolute() or ".." in Path(p).parts for p in paths):
        raise SourceShareError("all launchd arguments must be absolute paths")
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(python_exe), str(runner), "--registry", str(registry),
            "--state", str(state), "--all-approved",
        ],
        "EnvironmentVariables": {"PYTHONPATH": str(src),
                                 "PYTHONDONTWRITEBYTECODE": "1"},
        "StartInterval": interval,
        "RunAtLoad": False,
        "KeepAlive": False,
        "ProcessType": "Background",
    }


def save_private_template(plist: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.lstat()
    if (not stat.S_ISDIR(info.st_mode) or path.parent.is_symlink()
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("launch template directory must be owner-only")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise SourceShareError("launch template exists or cannot be created") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(plistlib.dumps(plist, sort_keys=True))
        stream.flush()
        os.fsync(stream.fileno())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    default_root = Path.home() / "Library" / "Application Support" / "NewsCatalystOS"
    p.add_argument("--out", type=Path,
                   default=default_root / "launchd" / (LABEL + ".plist"))
    p.add_argument("--interval", type=int, default=INTERVAL)
    p.add_argument("--write", action="store_true",
                   help="Write private template; do NOT install or activate launchd")
    opts = p.parse_args(argv)
    project = Path(__file__).resolve().parent.parent
    try:
        spec = launchd_spec(
            Path(sys.executable), project / "scripts" / "run_incremental_feed.py",
            default_root / "providers" / "authorized_sources.json",
            default_root / "state" / "incremental_feeds.sqlite3",
            project / "src", interval=opts.interval,
        )
        if opts.write:
            save_private_template(spec, opts.out)
        print("VALID_LAUNCH_SPEC", "WRITTEN_NOT_ACTIVATED" if opts.write else "DRY_RUN",
              "INTERVAL_SECONDS", spec["StartInterval"])
        return 0
    except (SourceShareError, OSError, ValueError) as exc:
        print("DATA_UNAVAILABLE", type(exc).__name__)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
