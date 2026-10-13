"""5_2 issuer/title/form screening from ALREADY captured, locally pinned DART/SEC.

Source bytes are read-only EraLeader first-capture publications, never live API.
The Mac-side independent SHA anchor proves local integrity and availability,
NOT independent issuer identity, actual contract terms or public release time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from .era_capture_share import MAX_BODY, OfficialCapture
from .pin_anchor import verify_with_local_anchor
from .source_share import SourceShareError, _check_directory, _json, _read_regular, _when

SUPPORTED = ("dart-disclosures", "sec-submissions")
CAPTURE_DIRECTORY = re.compile(r"first_[a-f0-9]{32}\Z")
DART_CODE = re.compile(r"[0-9]{8}\Z")
SEC_CODE = re.compile(r"[0-9]{1,10}\Z")
TICKER = re.compile(r"[0-9A-Za-z.:-]{1,20}\Z")


@dataclass(frozen=True)
class FilingContext:
    source_id: str
    document_id: str
    source_receipt_sha256: str
    original_sha256: str
    issuer_name_observed: str
    issuer_namespace_observed: str
    issuer_code_observed: str
    ticker_observed: str | None
    filing_type_observed: str
    filing_heading_observed: str
    local_context_verified_at: datetime
    issuer_authority_attested: bool = False
    filing_text_available: bool = False
    actual_supply_relation_verified: bool = False


def _text(value: object, label: str, limit: int, *, blank: bool = False) -> str:
    if (not isinstance(value, str) or len(value) > limit
            or (not blank and not value.strip())
            or any(ord(ch) < 32 and ch not in "\t\r\n" for ch in value)):
        raise SourceShareError(f"unsafe official filing {label}")
    return " ".join(value.split())


def _find_capture(era_root: Path, reference: OfficialCapture) -> Path:
    root = era_root / "output" / "official_api_capture"
    _check_directory(root, era_root)
    found = []
    for entry in root.iterdir():
        if (not CAPTURE_DIRECTORY.fullmatch(entry.name)
                or entry.is_symlink() or not entry.is_dir()):
            continue
        _check_directory(entry, era_root)
        try:
            receipt = _read_regular(entry / "first_receipt.json", 32_768)
        except SourceShareError:
            continue
        if sha256(receipt).hexdigest() == reference.first_receipt_sha256:
            found.append(entry)
    if len(found) != 1:
        raise SourceShareError("one uniquely pinned official capture required")
    return found[0]


def _decode_dart(data: dict, capture: OfficialCapture, checked: datetime
                 ) -> dict[tuple[str, str], FilingContext]:
    rows = data.get("list")
    if not isinstance(rows, list) or len(rows) != capture.observed_count:
        raise SourceShareError("pinned DART filing count mismatch")
    output = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SourceShareError("invalid DART filing metadata")
        number = row.get("rcept_no")
        if not isinstance(number, str) or not re.fullmatch(r"[0-9]{14}", number):
            raise SourceShareError("invalid DART filing receipt")
        issuer_code = row.get("corp_code")
        if not isinstance(issuer_code, str) or not DART_CODE.fullmatch(issuer_code):
            raise SourceShareError("invalid DART issuer code")
        ticker = row.get("stock_code")
        if ticker is not None and ticker != "":
            if not isinstance(ticker, str) or not re.fullmatch(r"[0-9]{6}", ticker):
                raise SourceShareError("invalid DART stock code")
        else:
            ticker = None
        name = _text(row.get("corp_name"), "issuer name", 200)
        heading = _text(row.get("report_nm"), "report title", 1500)
        key = (capture.source_id, number)
        if key in output:
            raise SourceShareError("duplicate DART filing metadata")
        output[key] = FilingContext(
            capture.source_id, number, capture.first_receipt_sha256,
            capture.raw_sha256, name, "DART_CORP", issuer_code, ticker,
            "DART_REPORT", heading, checked,
        )
    return output


def _decode_sec(data: dict, capture: OfficialCapture, checked: datetime
                ) -> dict[tuple[str, str], FilingContext]:
    recent = data.get("filings", {}).get("recent")
    if not isinstance(recent, dict):
        raise SourceShareError("invalid SEC recent filing metadata")
    ids = recent.get("accessionNumber")
    forms = recent.get("form")
    descriptions = recent.get("primaryDocDescription")
    if (not isinstance(ids, list) or not isinstance(forms, list)
            or not isinstance(descriptions, list)
            or len(ids) != len(forms) or len(ids) != len(descriptions)
            or len(ids) != capture.observed_count):
        raise SourceShareError("pinned SEC filing metadata arrays mismatch")
    cik = str(data.get("cik", "")).lstrip("0") or "0"
    if not SEC_CODE.fullmatch(cik):
        raise SourceShareError("SEC registrant code unsupported")
    issuer = _text(data.get("name"), "SEC registrant name", 200)
    ticks = data.get("tickers", [])
    if not isinstance(ticks, list) or len(ticks) > 30:
        raise SourceShareError("SEC ticker metadata unsupported")
    ticker = None
    if ticks:
        ticker = _text(ticks[0], "SEC reported ticker", 20)
        if not TICKER.fullmatch(ticker):
            raise SourceShareError("unsafe SEC ticker metadata")
    output = {}
    for doc, form, desc in zip(ids, forms, descriptions):
        if not isinstance(doc, str) or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", doc):
            raise SourceShareError("unsafe SEC accession ID")
        filing_type = _text(form, "SEC form type", 64)
        title = _text(desc, "SEC form heading", 900, blank=True)
        key = (capture.source_id, doc)
        if key in output:
            raise SourceShareError("duplicate SEC filing metadata")
        output[key] = FilingContext(
            capture.source_id, doc, capture.first_receipt_sha256,
            capture.raw_sha256, issuer, "SEC_CIK", cik, ticker,
            filing_type, title, checked,
        )
    return output


def read_pinned_filing_context(
    era_root: Path, research_index: Path, independent_anchor: Path,
    *, now: datetime | None = None,
) -> dict[tuple[str, str], FilingContext]:
    """Derive typed issuer/form metadata from the exact locally pinned raw SHA."""
    start = _when((now or datetime.now(timezone.utc)).isoformat(), "filing context read")
    era_root = Path(era_root)
    trusted = verify_with_local_anchor(
        era_root, Path(research_index), Path(independent_anchor), start,
    )
    captures = [c for c in trusted.captures if c.source_id in SUPPORTED]
    if len(captures) != len(SUPPORTED) or {c.source_id for c in captures} != set(SUPPORTED):
        raise SourceShareError("DART and SEC signed-off snapshots required")
    result = {}
    for capture in captures:
        folder = _find_capture(era_root, capture)
        raw = _read_regular(folder / "raw_response.json", MAX_BODY)
        if sha256(raw).hexdigest() != capture.raw_sha256:
            raise SourceShareError("original official capture SHA differs from pinned reference")
        contents = _json(raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw,
                         "pinned official filing metadata")
        completed = _when((now or datetime.now(timezone.utc)).isoformat(),
                          "context verification complete")
        metadata = (_decode_dart(contents, capture, completed)
                    if capture.source_id == "dart-disclosures"
                    else _decode_sec(contents, capture, completed))
        record_index = {r.provider_record_id:r.record_id for r in capture.records}
        if set(record_index) != {document for _, document in metadata}:
            raise SourceShareError("metadata differs from verified capture filing identities")
        for key, context in metadata.items():
            if (sha256((context.source_id+"\0"+context.document_id).encode()).hexdigest()
                    != record_index[context.document_id]):
                raise SourceShareError("metadata official document hash disagreement")
            if key in result:
                raise SourceShareError("duplicate joined official filing metadata")
            result[key] = context
        if sha256(_read_regular(folder / "raw_response.json", MAX_BODY)).hexdigest() != capture.raw_sha256:
            raise SourceShareError("source changed while creating filing screening context")
    return result
