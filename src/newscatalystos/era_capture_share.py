"""Read-only adapter for EraLeader's original, atomically renamed official captures.

The collector already published each first_<uuid>/ directory by os.replace,
but the receipt does *not* certify issuer identity, full history or release time.
A SHA256 pin MUST arrive from a separate trusted record; never self-pin on read.
No imports from, network calls to, or writes to EraLeader.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from .source_share import (
    SourceShareError, _check_directory, _json, _must_sha, _read_regular, _when
)

CAPTURE_SCHEMA = "eraleader.official_api_first_received_raw.v1"
SOURCES = {
    "krx-kospi": "KRX",
    "krx-kosdaq": "KRX",
    "dart-disclosures": "DART",
    "sec-submissions": "SEC",
    "sec-companyfacts": "SEC",
}
MAX_BODY = 24 * 1024 * 1024
MAX_RECORDS = 20_000
_CAPTURE_NAME = re.compile(r"first_[0-9a-f]{32}\Z")
_DIGITS_14 = re.compile(r"[0-9]{14}\Z")


@dataclass(frozen=True)
class OfficialRecord:
    """Record metadata only; NOT a cleared company/security/issuer mapping."""
    record_id: str
    provider_record_id: str
    provider_day: str | None
    available_at: datetime
    release_at: None = None
    issuer_attested: bool = False
    # SEC provider's acceptance timestamp: evidence of acceptance, NOT
    # independent proof of public release or local availability.
    provider_acceptance_at: datetime | None = None


@dataclass(frozen=True)
class OfficialCapture:
    source_id: str
    provider_id: str
    source_schema: str
    source_request_value: str
    first_seen_at: datetime
    first_receipt_sha256: str
    raw_sha256: str
    quality: str
    observed_count: int
    records: tuple[OfficialRecord, ...]
    completeness_certified: bool = False
    release_time_verified: bool = False
    historical_pit_certified: bool = False


def _date(value: object) -> str:
    if type(value) is not str:
        raise SourceShareError("missing source market day")
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("noncanonical")
    except ValueError as exc:
        raise SourceShareError("invalid source day") from exc
    return value


def _source_rows(source: str, data: dict, request_value: str,
                 first_seen: datetime) -> tuple[tuple[OfficialRecord, ...], str, int]:
    records: list[OfficialRecord] = []
    def add(identifier: str, day: str | None = None,
            acceptance_at: datetime | None = None) -> None:
        if not isinstance(identifier, str) or not identifier or len(identifier) > 128:
            raise SourceShareError("invalid provider record identifier")
        stable = sha256((source + "\x00" + identifier).encode("utf8")).hexdigest()
        records.append(OfficialRecord(
            record_id=stable, provider_record_id=identifier,
            provider_day=day, available_at=first_seen,
            provider_acceptance_at=acceptance_at))
    if source.startswith("krx-"):
        day = _date(request_value)
        rows = data.get("OutBlock_1")
        if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
            raise SourceShareError("KRX records malformed")
        codes = set()
        for row in rows:
            if not isinstance(row, dict) or row.get("BAS_DD") != day.replace("-", ""):
                raise SourceShareError("KRX market day mismatch")
            code = row.get("ISU_CD")
            if (not isinstance(code, str) or
                not re.fullmatch("[A-Za-z0-9]{6}", code) or code in codes or
                not isinstance(row.get("TDD_CLSPRC"), str)):
                raise SourceShareError("KRX daily record invalid/duplicated")
            codes.add(code)
            add(code + ":" + day, day)
        quality = "ROWS_RECEIVED_NOT_PIT_CERTIFIED" if rows else "NO_DAILY_ROWS"
        return tuple(records), quality, len(rows)
    if source == "dart-disclosures":
        day = _date(request_value)
        if data.get("status") == "013":
            if data.get("list") not in (None, []):
                raise SourceShareError("DART no-data contradictory rows")
            return (), "NO_DISCLOSURES_FOR_DAY", 0
        if data.get("status") != "000":
            raise SourceShareError("DART returned error state")
        rows = data.get("list")
        if not isinstance(rows, list) or len(rows) > 100:
            raise SourceShareError("DART page invalid")
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or row.get("rcept_dt") != day.replace("-", ""):
                raise SourceShareError("DART filing day mismatch")
            number = row.get("rcept_no")
            if not isinstance(number, str) or not _DIGITS_14.fullmatch(number) or number in seen:
                raise SourceShareError("DART receipt id invalid/duplicated")
            seen.add(number)
            add(number, day)
        count = data.get("total_count")
        if type(count) is str and count.isdecimal():
            count = int(count)
        if type(count) is not int or count < len(rows):
            raise SourceShareError("DART reported invalid total")
        quality = ("INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY" if count > len(rows)
                   else "ROWS_RECEIVED_NOT_PIT_CERTIFIED")
        return tuple(records), quality, len(rows)
    if not re.fullmatch("[0-9]{1,10}", request_value):
        raise SourceShareError("SEC CIK request invalid")
    cik = data.get("cik")
    if type(cik) not in (int, str) or not str(cik).isdigit() or int(cik) != int(request_value):
        raise SourceShareError("SEC registrant identity mismatch")
    if source == "sec-submissions":
        recent = data.get("filings", {}).get("recent")
        if not isinstance(recent, dict):
            raise SourceShareError("SEC submissions payload missing")
        accessions = recent.get("accessionNumber")
        acceptance = recent.get("acceptanceDateTime")
        if (not isinstance(accessions, list) or not isinstance(acceptance, list) or
            len(accessions) != len(acceptance) or len(accessions) > MAX_RECORDS):
            raise SourceShareError("SEC acceptance metadata invalid")
        used = set()
        for ref, stamp in zip(accessions, acceptance):
            if (not isinstance(ref, str) or
                not re.fullmatch("[0-9]{10}-[0-9]{2}-[0-9]{6}", ref) or ref in used or
                not isinstance(stamp, str) or not stamp):
                raise SourceShareError("SEC submission identifiers invalid/duplicated")
            used.add(ref)
            acceptance_at = _when(stamp, "SEC acceptanceDateTime")
            if acceptance_at > first_seen:
                raise SourceShareError("SEC acceptance after first local receipt")
            # Provider acceptance != verified publication != first local receipt.
            add(ref, acceptance_at=acceptance_at)
        return tuple(records), "RECENT_SUBMISSIONS_NOT_FULL_HISTORY", len(accessions)
    facts = data.get("facts")
    if not isinstance(facts, dict) or not facts or len(facts) > MAX_RECORDS:
        raise SourceShareError("SEC companyfacts invalid")
    # A taxonomy group is NOT a fresh earnings/disclosure event.
    return (), "FINANCIAL_FACT_TAXONOMIES_NOT_PIT_CERTIFIED", len(facts)


def read_official_capture(
    capture_dir: Path,
    era_root: Path,
    expected_receipt_sha256: str,
    decision_at: datetime,
    *,
    now: datetime | None = None,
) -> OfficialCapture:
    """Consume only a fully atomically published EraLeader capture, strictly as-of.

    The original 2026 collector's atomically renamed first_* capture directory
    is the publication boundary. Independent externally pinned receipt SHA is
    mandatory. Reject incomplete staging directories and any mutable/tampered
    response; return metadata only, never the copyrighted/private raw body.
    """
    capture_dir, era_root = Path(capture_dir), Path(era_root)
    expected_receipt_sha256 = _must_sha(expected_receipt_sha256, "receipt_sha256 pin")
    _check_directory(capture_dir, era_root)
    if (capture_dir.parent != era_root / "output" / "official_api_capture" or
        not _CAPTURE_NAME.fullmatch(capture_dir.name)):
        raise SourceShareError("not an atomically published first capture")
    if not isinstance(decision_at, datetime):
        raise SourceShareError("decision_at must be timezone-aware")
    decision = _when(decision_at.isoformat(), "decision_at")
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if decision > instant:
        raise SourceShareError("decision in future")
    # check metadata both before and after reading; mode may be synthesized 0700
    # on external SSD, require same UID and zero group/other privileges.
    import os
    import stat
    for file in [capture_dir, capture_dir / "first_receipt.json", capture_dir / "raw_response.json"]:
        try:
            info = file.lstat()
        except OSError as exc:
            raise SourceShareError("capture evidence unavailable") from exc
        if (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077 or
            (not stat.S_ISDIR(info.st_mode) if file == capture_dir else
             not stat.S_ISREG(info.st_mode))):
            raise SourceShareError("capture evidence not owner-private regular files")
    receipt_bytes = _read_regular(capture_dir / "first_receipt.json", 32768)
    if sha256(receipt_bytes).hexdigest() != expected_receipt_sha256:
        raise SourceShareError("first receipt SHA differs from trusted pin")
    receipt = _json(receipt_bytes, "first_receipt")
    if (receipt.get("schema") != CAPTURE_SCHEMA or
        receipt.get("source") not in SOURCES or
        receipt.get("publisher_release_time_verified") is not False or
        receipt.get("full_historic_universe_pit_certified") is not False or
        receipt.get("issuer_share_class_independently_attested") is not False or
        receipt.get("official_leader_promotions") != 0 or
        receipt.get("no_external_timestamp_notary") is not True):
        raise SourceShareError("receipt schema/trust boundary invalid")
    first_seen = _when(receipt.get("first_local_received_at_utc"), "first_local_received_at_utc")
    if first_seen > decision or first_seen > instant:
        raise SourceShareError("capture unavailable at decision time")
    source = receipt["source"]
    kind = receipt.get("request_kind")
    value = receipt.get("request_value")
    if kind != ("cik" if source.startswith("sec-") else "market_day"):
        raise SourceShareError("incorrect source request kind")
    if type(value) is not str:
        raise SourceShareError("source request missing")
    length = receipt.get("raw_length_bytes")
    count = receipt.get("provider_row_count")
    if (type(length) is not int or not 0 < length <= MAX_BODY or
        type(count) is not int or not 0 <= count <= MAX_RECORDS):
        raise SourceShareError("receipt length/count invalid")
    raw = _read_regular(capture_dir / "raw_response.json", MAX_BODY)
    digest = _must_sha(receipt.get("raw_sha256"), "raw_sha256")
    if len(raw) != length or sha256(raw).hexdigest() != digest:
        raise SourceShareError("source evidence bytes invalid")
    data = _json(raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw, "raw_response")
    records, quality, observed = _source_rows(source, data, value, first_seen)
    if quality != receipt.get("quality") or observed != count:
        raise SourceShareError("source count/quality mismatch")
    # Catch a concurrent change to receipt/raw while reader worked.
    if (_read_regular(capture_dir / "first_receipt.json", 32768) != receipt_bytes or
        sha256(_read_regular(capture_dir / "raw_response.json", MAX_BODY)).hexdigest() != digest):
        raise SourceShareError("capture changed during read")
    return OfficialCapture(
        source_id=source, provider_id=SOURCES[source], source_schema=CAPTURE_SCHEMA,
        source_request_value=value, first_seen_at=first_seen, first_receipt_sha256=expected_receipt_sha256,
        raw_sha256=digest, quality=quality, observed_count=observed, records=records)
