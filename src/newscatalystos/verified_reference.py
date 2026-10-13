"""Read-only check of a separately pinned EraLeader research receipt index.

This index is research-only, not a cryptographic notary or a release-time proof.
No automatic root trust: caller supplies SHA256 of prior research index record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from .era_capture_share import OfficialCapture, SOURCES, read_official_capture
from .source_share import (SourceShareError, _check_directory, _json, _must_sha,
                           _read_regular, _when)

REPORT_SCHEMA = "eraleader.official_api_pit_research_bridge.v1"


@dataclass(frozen=True)
class VerifiedOfficialSources:
    report_sha256: str
    captures: tuple[OfficialCapture, ...]
    research_only: bool = True


def verify_official_research_reference(
    era_root: Path, report_file: Path, expected_report_sha256: str,
    decision_at: datetime, *, now: datetime | None = None,
) -> VerifiedOfficialSources:
    """Match prior pinned research index to atomic first captures, without writes.

    Pin source MUST be an independently preserved trusted record, not computed
    from the potentially modified report inside this function.
    """
    era_root, report_file = Path(era_root), Path(report_file)
    _must_sha(expected_report_sha256, "expected_report_sha256")
    _check_directory(report_file.parent, era_root)
    if report_file.name != "official_api_pit_research.json":
        raise SourceShareError("unapproved research reference name")
    report_bytes = _read_regular(report_file, 2 * 1024 * 1024)
    if sha256(report_bytes).hexdigest() != expected_report_sha256:
        raise SourceShareError("research reference SHA pin mismatch")
    report = _json(report_bytes, "official_api_pit_research")
    if (report.get("schema") != REPORT_SCHEMA or
        report.get("watch_type") != "PRICE_ONLY_RESEARCH_NOT_CERTIFIED" or
        report.get("historic_universe_pit_verified") is not False or
        report.get("issuer_share_class_verified") is not False or
        report.get("dart_sec_financial_pit_joined") is not False or
        report.get("official_leaders") != 0):
        raise SourceShareError("not an unpromoted research-only index")
    reference_time = _when(report.get("decision_at"), "reference.decision_at")
    decision = _when(decision_at.isoformat(), "decision_at")
    if reference_time > decision:
        raise SourceShareError("reference was not available at decision")
    sources = report.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= len(SOURCES):
        raise SourceShareError("invalid source reference count")
    source_ids = set()
    pin_index = {}
    for row in sources:
        if not isinstance(row, dict) or row.get("source") not in SOURCES:
            raise SourceShareError("source reference is not official")
        name = row["source"]
        if name in source_ids:
            raise SourceShareError("duplicate source reference")
        source_ids.add(name)
        pin = _must_sha(row.get("first_receipt_sha256"), "source receipt pin")
        pin_index[pin] = row
    if len(pin_index) != len(sources):
        raise SourceShareError("duplicate receipt pin")
    capture_root = era_root / "output" / "official_api_capture"
    _check_directory(capture_root, era_root)
    matched: dict[str, OfficialCapture] = {}
    for item in capture_root.iterdir():
        if (not item.name.startswith("first_") or
            item.is_symlink() or not item.is_dir()):
            continue
        receipt_path = item / "first_receipt.json"
        try:
            receipt_bytes = _read_regular(receipt_path, 32768)
        except SourceShareError:
            continue  # publication directory may not belong to pinned set
        digest = sha256(receipt_bytes).hexdigest()
        if digest not in pin_index:
            continue
        reference = pin_index[digest]
        if digest in matched:
            raise SourceShareError("ambiguous duplicate pinned capture")
        capture = read_official_capture(
            item, era_root, digest, decision_at, now=now)
        if (capture.first_seen_at > reference_time or
            capture.source_id != reference["source"] or
            capture.quality != reference.get("quality") or
            capture.raw_sha256 != reference.get("raw_sha256") or
            capture.observed_count != reference.get("row_count")):
            raise SourceShareError("prior index differs from original capture")
        matched[digest] = capture
    if len(matched) != len(pin_index):
        raise SourceShareError("one or more pinned captures missing")
    if _read_regular(report_file, 2 * 1024 * 1024) != report_bytes:
        raise SourceShareError("reference modified during read")
    return VerifiedOfficialSources(
        report_sha256=expected_report_sha256,
        captures=tuple(matched[pin] for pin in pin_index))
