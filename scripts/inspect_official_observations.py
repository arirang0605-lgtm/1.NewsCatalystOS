"""Read verified EraLeader captures and atomically publish private metadata.

No collector/API calls. The output is research-only, NOT certified RawEvents.
The report is staged into a fresh directory then atomically renamed on the
same filesystem. On filesystems without hardlinks (e.g. exFAT), this works.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import stat
import tempfile
import uuid

from newscatalystos.observed_batch import build_observed_official_batch
from newscatalystos.pin_anchor import read_local_reference_anchor
from newscatalystos.source_share import SourceShareError
from newscatalystos.verified_reference import verify_official_research_reference


def _write_fsynced(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _private_output(name: str, data: bytes, *, root: Path | None = None) -> Path:
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}\.json", name)
            or ".." in name):
        raise SourceShareError("invalid private output filename")
    root = (Path(__file__).resolve().parent.parent / "output"
            if root is None else Path(root))
    try:
        root.mkdir(mode=0o700, exist_ok=True)
        info = root.lstat()
    except OSError as exc:
        raise SourceShareError("private output directory unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or root.is_symlink()
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("private output must be owner-only project directory")
    # New random identity: never replace a previous completed publication.
    publication = root / (name[:-5] + "_" + uuid.uuid4().hex)
    staging = Path(tempfile.mkdtemp(prefix=".staging_", dir=root))
    try:
        staging.chmod(0o700)
        _write_fsynced(staging / "observations.json", data)
        marker = {
            "schema": "newscatalyst.observed_publication.v1",
            "status": "COMPLETE_RESEARCH_ONLY",
            "payload_sha256": sha256(data).hexdigest(),
            "payload_size_bytes": len(data),
            "payload_file": "observations.json",
            "certified_raw_event_count": 0,
        }
        marker_bytes = (json.dumps(marker, sort_keys=True, separators=(",", ":"))
                        + "\n").encode("utf-8")
        _write_fsynced(staging / "publication.json", marker_bytes)
        dfd = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        if publication.exists():
            raise SourceShareError("publication identity collision")
        os.rename(staging, publication)
        dfd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except (OSError, SourceShareError) as exc:
        raise SourceShareError("private research publication unavailable") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return publication


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--era-root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--output-name", help="research publication prefix, private output/")
    opts = parser.parse_args()
    decision = datetime.now(timezone.utc)
    anchor = read_local_reference_anchor(
        opts.era_root, opts.reference, opts.anchor, decision
    )
    sources = verify_official_research_reference(
        opts.era_root, opts.reference, anchor.report_sha256, decision
    )
    batch = build_observed_official_batch(
        sources, anchor.observed_at, decision
    )
    print("SOURCE_CAPTURE_COUNT", batch.source_count)
    print("RESEARCH_METADATA_ROWS", len(batch.rows))
    print("CERTIFIED_RAW_EVENTS", 0)
    print("PUBLIC_RELEASE_AT", "UNKNOWN")
    print("STATUS", "RESEARCH_ONLY_RELEASE_UNVERIFIED")
    if opts.output_name:
        path = _private_output(opts.output_name, batch.to_json_bytes())
        print("PRIVATE_METADATA_PUBLICATION", path)


if __name__ == "__main__":
    main()
