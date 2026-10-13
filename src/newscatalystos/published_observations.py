"""Fail-closed read-only consumer of NewsCatalystOS private research batches.

The caller supplies a previously trusted SHA256 of the *payload*, never
learned from the mutable publication marker. This verifies local metadata
integrity, NOT issuer identity / official release time / historical notarization.
EraLeader API, DB, source and Git are never accessed or modified here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
import stat

from .era_capture_share import SOURCES
from .observed_batch import (STATUS, SCHEMA as BATCH_SCHEMA, LEGACY_SCHEMA,
                             ObservedOfficialRow, ObservedOfficialSource)
from .source_share import SourceShareError, _json, _must_sha, _read_regular, _when

MARKER_SCHEMA = "newscatalyst.observed_publication.v1"
MAX_MARKER_BYTES = 8192
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20_000
QUALITIES = {
    "krx-kospi": frozenset({"ROWS_RECEIVED_NOT_PIT_CERTIFIED", "NO_DAILY_ROWS"}),
    "krx-kosdaq": frozenset({"ROWS_RECEIVED_NOT_PIT_CERTIFIED", "NO_DAILY_ROWS"}),
    "dart-disclosures": frozenset({"INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY",
                                   "ROWS_RECEIVED_NOT_PIT_CERTIFIED",
                                   "NO_DISCLOSURES_FOR_DAY"}),
    "sec-submissions": frozenset({"RECENT_SUBMISSIONS_NOT_FULL_HISTORY"}),
    "sec-companyfacts": frozenset({"FINANCIAL_FACT_TAXONOMIES_NOT_PIT_CERTIFIED"}),
}
ROW_KEYS = frozenset({
    "source_id", "provider_id", "evidence_id", "provider_record_id",
    "provider_day", "provider_acceptance_at", "first_seen_at", "usable_from",
    "original_sha256", "receipt_sha256", "source_quality", "published_at",
    "issuer_verified", "classification",
})
BATCH_KEYS = frozenset({
    "schema", "status", "reference_sha256", "anchor_first_observed_at",
    "decision_at", "source_count", "row_count", "research_only",
    "certified_raw_event_count", "rows",
})
SOURCE_KEYS = frozenset({
    "source_id", "provider_id", "first_seen_at", "original_sha256",
    "receipt_sha256", "source_quality", "observed_count", "metadata_count",
})
MARKER_KEYS = frozenset({
    "schema", "status", "payload_sha256", "payload_size_bytes",
    "payload_file", "certified_raw_event_count", "first_local_published_at",
})


@dataclass(frozen=True)
class PublishedResearchObservations:
    """Research-only records; NEVER classified as certified RawEvents."""
    payload_sha256: str
    local_published_at: datetime
    anchor_observed_at: datetime
    batch_decision_at: datetime
    source_count: int
    rows: tuple[ObservedOfficialRow, ...]
    source_coverage: tuple[ObservedOfficialSource, ...]
    coverage_verified: bool
    research_only: bool = True

    def as_of(self, decision_at: datetime, *, now: datetime | None = None
              ) -> tuple[ObservedOfficialRow, ...]:
        when = _when(
            decision_at.isoformat() if isinstance(decision_at, datetime) else None,
            "decision_at",
        )
        instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if when < self.local_published_at or when > instant:
            raise SourceShareError("publication unavailable at requested decision")
        return self.rows


def _safe_publication_directory(publication: Path, root: Path) -> None:
    if (not publication.is_absolute() or not root.is_absolute()
            or publication.parent != root or publication.name.startswith(".")
            or publication == root or ".." in publication.parts):
        raise SourceShareError("publication outside approved root")
    for directory in (root, publication):
        try:
            info = directory.lstat()
        except OSError as exc:
            raise SourceShareError("publication directory missing") from exc
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise SourceShareError("publication directory must be owner-private")


def read_published_observations(
    publication: Path, root: Path, expected_payload_sha256: str,
    decision_at: datetime, *, now: datetime | None = None,
) -> PublishedResearchObservations:
    """Read a *completed* atomic publication using an out-of-band payload pin.

    Historical replay is allowed no earlier than this batch's local publication,
    even if its source captures were received much earlier.
    """
    publication, root = Path(publication), Path(root)
    _safe_publication_directory(publication, root)
    expected = _must_sha(expected_payload_sha256, "independent payload pin")
    when = _when(
        decision_at.isoformat() if isinstance(decision_at, datetime) else None,
        "decision_at",
    )
    instant = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if when > instant:
        raise SourceShareError("decision in future")
    marker_bytes = _read_regular(publication / "publication.json", MAX_MARKER_BYTES)
    marker = _json(marker_bytes, "publication marker")
    if (set(marker) != MARKER_KEYS or marker["schema"] != MARKER_SCHEMA or
            marker["status"] != "COMPLETE_RESEARCH_ONLY" or
            marker["payload_file"] != "observations.json" or
            type(marker["certified_raw_event_count"]) is not int or
            marker["certified_raw_event_count"] != 0 or
            marker["payload_sha256"] != expected):
        raise SourceShareError("unverified or incomplete research publication")
    size = marker["payload_size_bytes"]
    if type(size) is not int or not 0 < size <= MAX_PAYLOAD_BYTES:
        raise SourceShareError("invalid observation payload bound")
    published = _when(marker["first_local_published_at"], "local publication")
    if published > when or published > instant:
        raise SourceShareError("publication did not exist at decision")
    data_bytes = _read_regular(publication / "observations.json", MAX_PAYLOAD_BYTES)
    if len(data_bytes) != size or sha256(data_bytes).hexdigest() != expected:
        raise SourceShareError("research payload SHA or length mismatch")
    batch = _json(data_bytes, "observations")
    schema = batch.get("schema")
    if schema == BATCH_SCHEMA:
        if set(batch) != (BATCH_KEYS | {"source_coverage"}):
            raise SourceShareError("v2 source coverage contract invalid")
    elif schema == LEGACY_SCHEMA:
        if set(batch) != BATCH_KEYS:
            raise SourceShareError("legacy observation schema invalid")
    else:
        raise SourceShareError("unknown research observation schema")
    if (batch["status"] != STATUS or
            batch["research_only"] is not True or
            type(batch["certified_raw_event_count"]) is not int or
            batch["certified_raw_event_count"] != 0):
        raise SourceShareError("observation status/schema invalid")
    _must_sha(batch["reference_sha256"], "reference_sha256")
    anchored = _when(batch["anchor_first_observed_at"], "anchor observed_at")
    captured_at = _when(batch["decision_at"], "batch decision")
    if not anchored <= captured_at <= published:
        raise SourceShareError("batch contains retrospective information")
    count = batch["row_count"]
    sources = batch["source_count"]
    records = batch["rows"]
    if (type(count) is not int or not 0 <= count <= MAX_ROWS or
            type(sources) is not int or not 1 <= sources <= len(SOURCES) or
            not isinstance(records, list) or len(records) != count):
        raise SourceShareError("observation count/coverage mismatch")
    coverage: list[ObservedOfficialSource] = []
    by_source: dict[str, ObservedOfficialSource] = {}
    if schema == BATCH_SCHEMA:
        summaries = batch["source_coverage"]
        if not isinstance(summaries, list) or len(summaries) != sources:
            raise SourceShareError("source coverage count mismatch")
        for info in summaries:
            if not isinstance(info, dict) or set(info) != SOURCE_KEYS:
                raise SourceShareError("invalid source coverage metadata")
            source_id = info["source_id"]
            if source_id not in SOURCES or source_id in by_source:
                raise SourceShareError("duplicated or unknown source in coverage")
            if info["provider_id"] != SOURCES[source_id]:
                raise SourceShareError("source coverage provider mismatch")
            quality = info["source_quality"]
            if not isinstance(quality, str) or quality not in QUALITIES[source_id]:
                raise SourceShareError("source coverage quality invalid")
            first = _when(info["first_seen_at"], "coverage first_seen_at")
            if first > anchored:
                raise SourceShareError("coverage first receipt after anchor")
            observed_n, metadata_n = info["observed_count"], info["metadata_count"]
            if (type(observed_n) is not int or type(metadata_n) is not int or
                    not 0 <= metadata_n <= observed_n <= MAX_ROWS):
                raise SourceShareError("invalid source capture counts")
            if source_id == "sec-companyfacts":
                if metadata_n != 0:
                    raise SourceShareError("companyfacts taxonomy cannot become news events")
            elif metadata_n != observed_n:
                raise SourceShareError("source observations/metadata counts differ")
            if quality in ("NO_DAILY_ROWS", "NO_DISCLOSURES_FOR_DAY") and observed_n:
                raise SourceShareError("no-data quality contradicted by records")
            summary = ObservedOfficialSource(
                source_id=source_id, provider_id=SOURCES[source_id],
                first_seen_at=first,
                original_sha256=_must_sha(info["original_sha256"], "coverage original_sha256"),
                receipt_sha256=_must_sha(info["receipt_sha256"], "coverage receipt_sha256"),
                source_quality=quality, observed_count=observed_n, metadata_count=metadata_n,
            )
            by_source[source_id] = summary
            coverage.append(summary)
        if sum(x.metadata_count for x in coverage) != count:
            raise SourceShareError("source coverage metadata sum mismatch")
    observed = []
    seen = set()
    seen_sources = set()
    for raw in records:
        if not isinstance(raw, dict) or set(raw) != ROW_KEYS:
            raise SourceShareError("unexpected observation fields")
        source = raw["source_id"]
        if source not in SOURCES or raw["provider_id"] != SOURCES[source]:
            raise SourceShareError("unknown observation source")
        evidence = _must_sha(raw["evidence_id"], "evidence_id")
        pair = (source, evidence)
        if pair in seen:
            raise SourceShareError("duplicate research observation")
        seen.add(pair)
        seen_sources.add(source)
        doc = raw["provider_record_id"]
        if not isinstance(doc, str) or not 0 < len(doc) <= 128:
            raise SourceShareError("invalid source document id")
        stable_id = sha256((source + "\x00" + doc).encode("utf8")).hexdigest()
        if evidence != stable_id:
            raise SourceShareError("evidence identifier differs from official source document")
        original = _must_sha(raw["original_sha256"], "original_sha256")
        receipt = _must_sha(raw["receipt_sha256"], "receipt_sha256")
        provider_day = raw["provider_day"]
        if provider_day is not None:
            if not isinstance(provider_day, str):
                raise SourceShareError("invalid provider day")
            try:
                if date.fromisoformat(provider_day).isoformat() != provider_day:
                    raise ValueError("noncanonical")
            except ValueError as exc:
                raise SourceShareError("invalid provider day") from exc
        acceptance = raw["provider_acceptance_at"]
        if acceptance is not None:
            if source != "sec-submissions":
                raise SourceShareError("acceptance timestamp for wrong source")
            acceptance = _when(acceptance, "acceptance timestamp")
        seen_at = _when(raw["first_seen_at"], "first_seen_at")
        usable = _when(raw["usable_from"], "usable_from")
        if (usable != max(anchored, seen_at) or seen_at > captured_at or
                (acceptance is not None and acceptance > seen_at)):
            raise SourceShareError("research observation PIT violation")
        if (raw["published_at"] is not None or raw["issuer_verified"] is not False
                or raw["classification"] != STATUS):
            raise SourceShareError("uncertified event promoted inside research")
        quality = raw["source_quality"]
        if (not isinstance(quality, str) or quality not in QUALITIES[source] or
                source == "sec-companyfacts" or
                (source in ("krx-kospi", "krx-kosdaq", "dart-disclosures")
                 and provider_day is None) or
                (source == "sec-submissions" and acceptance is None)):
            raise SourceShareError("invalid source-specific research quality")
        if schema == BATCH_SCHEMA:
            parent = by_source.get(source)
            if (parent is None or parent.first_seen_at != seen_at or
                    parent.original_sha256 != original or
                    parent.receipt_sha256 != receipt or
                    parent.source_quality != quality):
                raise SourceShareError("row differs from signed source coverage")
        observed.append(ObservedOfficialRow(
            source_id=source, provider_id=SOURCES[source],
            evidence_id=evidence, provider_record_id=doc,
            provider_day=provider_day, provider_acceptance_at=acceptance,
            first_seen_at=seen_at, usable_from=usable,
            original_sha256=original, receipt_sha256=receipt,
            source_quality=quality,
        ))
    if schema == BATCH_SCHEMA:
        totals = {source_id: 0 for source_id in by_source}
        for row in observed:
            totals[row.source_id] += 1
        if any(totals[x.source_id] != x.metadata_count for x in coverage):
            raise SourceShareError("source coverage row count mismatch")
    elif len(seen_sources) > sources:
        raise SourceShareError("legacy source coverage smaller than observations")
    # Re-read the marker after consuming payload to detect a publication race.
    if _read_regular(publication / "publication.json", MAX_MARKER_BYTES) != marker_bytes:
        raise SourceShareError("publication marker changed while reading")
    return PublishedResearchObservations(
        payload_sha256=expected, local_published_at=published,
        anchor_observed_at=anchored, batch_decision_at=captured_at,
        source_count=sources, rows=tuple(observed),
        source_coverage=tuple(coverage), coverage_verified=(schema == BATCH_SCHEMA),
    )
