"""Install a *separate* hourly ministry-only RSS policy LaunchAgent.

The initial two V1 approved RSS services, EraLeader, and all gold labels remain
unchanged. Operator rights registry must already exist on Mac; no robots.
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

from scripts.create_triage_agent import _owner_dir
from newscatalystos.source_share import SourceShareError

LABEL = "com.newscatalystos.motir"
INTERVAL = 3600


def motir_launchd_spec(python: Path, project: Path, base: Path) -> dict:
    paths=(python,project,base)
    if any(not Path(p).is_absolute() or ".." in Path(p).parts
           or any(part.casefold()=="eraleader" for part in Path(p).parts)
           for p in paths):
        raise SourceShareError("absolute dedicated NewsCatalystOS paths required")
    project,base=Path(project),Path(base)
    script=project/"scripts"/"run_motir_policy_once.py"
    if not script.is_file():
        raise SourceShareError("MOTIR sector runner unavailable")
    return {
        "Label":LABEL,
        "ProgramArguments":[str(python),str(script)],
        "EnvironmentVariables":{"PYTHONPATH":str(project/"src"),
                                "PYTHONDONTWRITEBYTECODE":"1"},
        "WorkingDirectory":str(project),
        "RunAtLoad":False,
        "KeepAlive":False,
        "StartInterval":INTERVAL,
        "ProcessType":"Background",
        "Umask":0o077,
        "StandardOutPath":str(base/"logs"/"motir_stdout.log"),
        "StandardErrorPath":str(base/"logs"/"motir_stderr.log"),
    }


def install_new_motir_launchd(spec:dict, target:Path, logs:Path)->Path:
    target,logs=Path(target),Path(logs)
    if (not target.is_absolute() or target.name!=LABEL+".plist"
        or target.is_symlink() or spec.get("Label")!=LABEL
        or spec.get("StartInterval")!=INTERVAL
        or spec.get("RunAtLoad") is not False
        or spec.get("StandardOutPath")!=str(logs/"motir_stdout.log")
        or spec.get("StandardErrorPath")!=str(logs/"motir_stderr.log")):
        raise SourceShareError("invalid dedicated MOTIR LaunchAgent config")
    _owner_dir(target.parent,mode=0o700)
    _owner_dir(logs,mode=0o700)
    for name in ("motir_stdout.log","motir_stderr.log"):
        f=logs/name
        if f.exists() or f.is_symlink():
            info=f.lstat()
            if (f.is_symlink() or not stat.S_ISREG(info.st_mode)
                    or info.st_uid!=os.geteuid() or
                    stat.S_IMODE(info.st_mode)&0o077):
                raise SourceShareError("unsafe private MOTIR log")
        else:
            fd=os.open(f,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            os.close(fd)
    body=plistlib.dumps(spec)
    fd=os.open(target,os.O_EXCL|os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,"wb") as output:
        output.write(body)
        output.flush()
        os.fsync(output.fileno())
    directory=os.open(target.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return target


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write",action="store_true")
    p.add_argument("--destination",type=Path,
                   default=Path.home()/"Library/LaunchAgents"/(LABEL+".plist"))
    opts=p.parse_args(argv)
    base=Path.home()/"Library/Application Support/NewsCatalystOS"
    try:
        spec=motir_launchd_spec(Path(sys.executable),PROJECT,base)
        if opts.write:
            install_new_motir_launchd(spec,opts.destination,base/"logs")
        print("MOTIR_DEDICATED_SOURCE_AGENT_CONFIG_VALID",
              "WRITTEN_NOT_RUNNING" if opts.write else "DRY_RUN",
              "INTERVAL",INTERVAL,"OVERWRITTEN_RSS_AGENTS",0)
        return 0
    except (SourceShareError,OSError,TypeError,ValueError) as exc:
        print("MOTIR_AGENT_CONFIG_UNAVAILABLE",type(exc).__name__)
        return 4


if __name__=="__main__":
    raise SystemExit(main())
