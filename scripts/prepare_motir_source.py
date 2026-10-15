"""1_2 add the configured ministry RSS form feed in a SEPARATE private registry.

This does NOT alter existing two-source registry or launchd jobs. The official
press page advertises an RSS FORM POST, and states KOGL Type 1 (attribution).
Uses the existing metadata-only source policy; no full-text usage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from newscatalystos.provider_registry import SCHEMA, parse_provider_registry
from newscatalystos.source_share import SourceShareError

SOURCE = "motir-official-press"
ENDPOINT = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/rss"
RIGHTS = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c"


def create_document(now: datetime) -> bytes:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise SourceShareError("current source configuration time required")
    document = {
        "schema": SCHEMA,
        "providers": [{
            "provider_id": SOURCE,
            "kind": "GOVERNMENT_POLICY",
            "method": "RSS_POST",
            "endpoint": ENDPOINT,
            "grant": "OFFICIAL_TERMS_REVIEWED",
            "rights_reference": RIGHTS,
            "reviewed_at": now.isoformat(),
            "expires_at": None,
            "approved": True,
            "allow_full_text_storage": False,
            "hourly_limit": 1,
        }],
    }
    raw = (json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n").encode()
    assert parse_provider_registry(raw, now=now).approved_ids(at=now) == (SOURCE,)
    return raw


def write_private_registry(path: Path, *, now: datetime | None = None) -> Path:
    now = now or datetime.now(timezone.utc)
    if not path.is_absolute() or ".." in path.parts or path.is_symlink():
        raise SourceShareError("absolute private source registry path required")
    parent = path.parent
    if (not parent.is_dir() or parent.is_symlink() or
            parent.stat().st_uid != os.geteuid() or
            stat.S_IMODE(parent.stat().st_mode) & 0o077):
        raise SourceShareError("owner-only existing provider directory required")
    if path.name != "motir_authorized_sources.json":
        raise SourceShareError("cannot modify existing RSS registry")
    payload = create_document(now)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        dirfd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    base = Path.home() / "Library/Application Support/NewsCatalystOS/providers"
    p.add_argument("--out", type=Path, default=base / "motir_authorized_sources.json")
    p.add_argument("--write", action="store_true")
    opts = p.parse_args(argv)
    try:
        if opts.write:
            write_private_registry(opts.out)
        else:
            create_document(datetime.now(timezone.utc))
        print(json.dumps({
            "status": "MOTIR_PRIVATE_RSS_POST_REGISTRY_PREPARED" if opts.write
                      else "MOTIR_RIGHTS_REGISTRY_DRY_RUN",
            "provider_id": SOURCE,
            "rss_endpoint": ENDPOINT,
            "approved_source_count_for_sector_registry": 1,
            "existing_general_provider_registry_modified": False,
            "source_http_calls": 0, "article_fulltext_storage": False,
        }, sort_keys=True))
        return 0
    except (SourceShareError, OSError, ValueError) as exc:
        print(json.dumps({"status":"MOTIR_RIGHTS_REGISTRY_UNAVAILABLE",
                          "error_type":type(exc).__name__,
                          "source_http_calls":0}))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
