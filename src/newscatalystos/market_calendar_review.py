"""6_5 offline, operator-reviewed exchange calendar matched to real ACK days.

The operator must preserve an actual authorized source excerpt alongside a
private calendar review. Matching dates cannot on its own independently
certify sessions, PIT timing, five-day operation, or V1 release.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit

from .evidence_archive import _read_once
from .source_share import SourceShareError, _json, _must_id, _must_sha, _when

SCHEMA = "newscatalyst.market_calendar_review.v1"
MAX_REVIEW_BYTES = 16384
MAX_SOURCE_BYTES = 8 * 1024 * 1024
FIELDS = frozenset({
    "schema", "exchange", "source_url", "source_sha256",
    "source_first_observed_at", "reviewer_id", "reviewed_at", "session_dates",
})


@dataclass(frozen=True)
class CalendarReview:
    session_dates: frozenset[str]
    source_sha256: str
    reviewed_at: datetime


def _trusted_dir(path: Path) -> Path:
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts or path.is_symlink()
            or any(part.lower() == "eraleader" for part in path.parts)):
        raise SourceShareError("private calendar review directory required")
    try:
        info = path.lstat()
    except OSError as exc:
        raise SourceShareError("calendar review directory unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or path.resolve(strict=True) != path):
        raise SourceShareError("unsafe calendar review directory")
    return path


def load_calendar_review(folder: Path, *, now: datetime | None = None) -> CalendarReview:
    """Verify owner-only on-disk review AND actual source snapshot SHA (no GET)."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    folder = _trusted_dir(folder)
    doc = _json(_read_once(folder / "review.json", MAX_REVIEW_BYTES), "calendar review")
    if set(doc) != FIELDS or doc["schema"] != SCHEMA or doc["exchange"] != "XKRX":
        raise SourceShareError("invalid exchange calendar review schema")
    source_url = doc["source_url"]
    if not isinstance(source_url, str) or len(source_url) > 2000:
        raise SourceShareError("invalid exchange calendar source")
    try:
        parsed = urlsplit(source_url)
    except ValueError as exc:
        raise SourceShareError("invalid calendar URL") from exc
    if (parsed.scheme != "https" or not parsed.hostname
            or not (parsed.hostname == "krx.co.kr" or parsed.hostname.endswith(".krx.co.kr"))
            or parsed.username or parsed.password or parsed.fragment or parsed.port):
        raise SourceShareError("KRX HTTPS calendar source reference required")
    expected = _must_sha(doc["source_sha256"], "calendar source digest")
    source = _read_once(folder / "source_snapshot", MAX_SOURCE_BYTES)
    if sha256(source).hexdigest() != expected:
        raise SourceShareError("calendar source SHA mismatch")
    first_seen = _when(doc["source_first_observed_at"], "source observed at")
    reviewed = _when(doc["reviewed_at"], "calendar reviewed at")
    if first_seen > reviewed or reviewed > at:
        raise SourceShareError("calendar review has impossible observation order")
    reviewer = _must_id(doc["reviewer_id"], "calendar reviewer")
    if reviewer.upper().startswith(("UNASSIGNED", "SYNTHETIC", "TEST_")):
        raise SourceShareError("unassigned calendar reviewer")
    dates = doc["session_dates"]
    if (not isinstance(dates, list) or not 1 <= len(dates) <= 400
            or any(not isinstance(v, str) for v in dates)):
        raise SourceShareError("bounded session date list required")
    checked = set()
    for val in dates:
        try:
            parsed_day = date.fromisoformat(val)
        except ValueError as exc:
            raise SourceShareError("invalid calendar session") from exc
        if parsed_day.isoformat() != val or parsed_day.weekday() >= 5:
            raise SourceShareError("noncanonical or weekend calendar session")
        if val in checked:
            raise SourceShareError("duplicate calendar session")
        checked.add(val)
    return CalendarReview(frozenset(checked), expected, reviewed)
