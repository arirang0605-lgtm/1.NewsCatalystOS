"""Read already-published RSS analysis; never reanalyze, poll, label, or trade.

The expected SHA comes from the producer's prior output, not this file's name.
Integrity of a stored report is not factual accuracy or source freshness.
No database, registry, AI credential or source document is opened by this reader.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from .analysis_cache import _decode
from .feed_analysis import SCHEMA as ANALYSIS_SCHEMA
from .official_relation_intake import _private_input
from .provider_registry import _safe_https_endpoint
from .reviewed_beneficiary_delivery import _handoff_root
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA = "newscatalyst.feed_analysis_delivery.v1"
MAX_REPORT_BYTES = 2_000_000  # Existing producer's bound, not a new acceptance gate.
AI_SUCCESS = frozenset({"ANALYZED_UNVERIFIED", "CACHE_HIT"})


def _time(now: datetime | None) -> datetime:
    return _when((now or datetime.now(timezone.utc)).isoformat(), "consumer time")


def _text(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise SourceShareError("invalid stored " + name)
    return value


def _validate_report(data: dict, now: datetime) -> datetime | None:
    """Check the stored format without rerunning economic rules or AI."""
    if (data.get("schema") != ANALYSIS_SCHEMA
            or data.get("status") not in {"FEED_ECONOMIC_ANALYSIS_READY", "NO_COMPLETED_FEED_INPUT"}
            or not isinstance(data.get("results"), list) or len(data["results"]) > 100
            or data.get("source_fetch_calls") != 0 or data.get("human_labels_added") != 0):
        raise SourceShareError("unsupported saved feed analysis")
    rows = data["results"]
    if data["status"] == "NO_COMPLETED_FEED_INPUT":
        if rows or data.get("new_ai_results") != 0 or data.get("cache_hits") != 0:
            raise SourceShareError("empty feed report contains results")
        return None  # Older empty reports have no producer timestamp; do not invent one.
    checked = _when(data.get("checked_at"), "producer checked time")
    if checked > now:
        raise SourceShareError("future analysis report")
    if (data.get("source_inputs_modified") is not False
            or data.get("article_body_included") is not False
            or data.get("verified_economic_facts") != 0
            or data.get("market_action") is not None
            or data.get("release_gate_verified") is not False):
        raise SourceShareError("stored analysis is not an unverified metadata result")
    for field in ("source_versions_checked", "matched_versions", "ai_eligible_candidates",
                  "new_ai_results", "cache_hits"):
        if type(data.get(field)) is not int or data[field] < 0:
            raise SourceShareError("invalid producer result count")
    if (not data["source_versions_checked"] >= data["matched_versions"] >= len(rows)
            or data.get("has_more_results") is not (data["matched_versions"] > len(rows))):
        raise SourceShareError("producer coverage counts disagree")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SourceShareError("invalid stored analysis row")
        provider = _text(row.get("provider_id"), "provider", 128)
        _text(row.get("document_id"), "document", 512)
        _text(row.get("headline"), "headline", 2048)
        _text(row.get("source_kind"), "source kind", 64)
        _safe_https_endpoint(row.get("source_url"))
        event = _must_sha(row.get("source_event_sha256"), "source event")
        title = _must_sha(row.get("source_title_sha256"), "title version")
        analysis = _must_sha(row.get("analysis_event_sha256"), "analysis event")
        _must_sha(row.get("source_triage_sha256"), "source triage")
        expected = sha256((provider + "\0" + event + "\0" + title).encode()).hexdigest()
        if analysis != expected or analysis in seen:
            raise SourceShareError("duplicate or mismatched source version")
        seen.add(analysis)
        source_at = _when(row.get("source_available_at"), "source available")
        analyzed_at = _when(row.get("analysis_available_at"), "analysis available")
        if not source_at <= analyzed_at <= checked:
            raise SourceShareError("source/analysis availability mismatch")
        if (any(row.get(k) is not False for k in (
                "verified_economic_fact", "verified_supply_transaction", "verified_beneficiary"))
                or row.get("revenue_estimate_krw") is not None
                or type(row.get("ai_eligible")) is not bool
                or type(row.get("reported_plan_only")) is not bool):
            raise SourceShareError("stored claim cannot become a confirmed fact or benefit")
        if (not isinstance(row.get("uncertainties"), list)
                or not isinstance(row.get("dimensions"), dict)
                or not isinstance(row.get("source_matched_fields"), list)
                or not isinstance(row.get("known_dimensions"), list)
                or not isinstance(row.get("unknown_dimensions"), list)):
            raise SourceShareError("stored evidence and uncertainty fields required")
        for item in row["source_matched_fields"]:
            if not isinstance(item, dict):
                raise SourceShareError("invalid source-matched field")
            _text(item.get("field"), "field name", 64)
            _text(item.get("value"), "source-matched value", 120)
            _must_sha(item.get("evidence_quote_sha256"), "source quote digest")
            if item.get("status") != "EXACT_SOURCE_MATCH_ISSUER_NOT_ATTESTED":
                raise SourceShareError("source phrase matching is not independent truth")
        _text(row.get("ai_status"), "AI status", 128)
        ai = row.get("ai_analysis")
        if ai is not None:
            raw = json.dumps(ai, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()
            result = _decode(raw)  # Existing AI schema + unverified classification checks.
            if (row["ai_status"] not in AI_SUCCESS or result.event_sha256 != analysis
                    or result.available_at > analyzed_at):
                raise SourceShareError("AI result does not match stored source/time")
            content = {"summary": result.summary, "claims": list(result.claims),
                       "uncertainties": list(result.uncertainties)}
            digest = sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
            if digest != result.content_sha256:
                raise SourceShareError("AI content digest mismatch")
        elif row["ai_status"] in AI_SUCCESS:
            raise SourceShareError("successful AI result missing from saved report")
    if (data["ai_eligible_candidates"] != sum(r["ai_eligible"] for r in rows)
            or data["cache_hits"] != sum(r["ai_status"] == "CACHE_HIT" for r in rows)
            or data["new_ai_results"] != sum(r["ai_status"] == "ANALYZED_UNVERIFIED" for r in rows)):
        raise SourceShareError("saved AI counters disagree with results")
    return checked


def consume_feed_analysis(
    report_file: Path, reports_root: Path, expected_sha256: str, *,
    provider_id: str | None = None, event_id: str | None = None,
    title_sha256: str | None = None, offset: int = 0, limit: int = 20,
    now: datetime | None = None,
) -> dict:
    """Read one SHA-selected report and page its original results, with no writes.

    Original source/analysis timestamps are preserved. Consumer availability is
    stamped after this read, never backdated to the article or analysis time.
    The reader does not certify current collection rights, source freshness,
    a historic backtest decision, human truth, or realized commercial benefits.
    """
    started = _time(now)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise SourceShareError("invalid result page")
    if provider_id is not None:
        _text(provider_id, "selected provider", 128)
    if event_id is not None:
        _must_sha(event_id, "selected source event")
    if title_sha256 is not None:
        _must_sha(title_sha256, "selected title version")
        if event_id is None:
            raise SourceShareError("title version selection requires a source event")
    expected = _must_sha(expected_sha256, "expected analysis report SHA")
    root = _handoff_root(reports_root, create=False)
    path = Path(report_file)
    if (path.parent != root or path.name != "feed_analysis_" + expected + ".json"
            or path.is_symlink()):
        raise SourceShareError("analysis report outside selected private root or SHA")
    raw = _private_input(path, MAX_REPORT_BYTES)
    if sha256(raw).hexdigest() != expected:
        raise SourceShareError("analysis report differs from expected SHA")
    data = _json(raw, "published feed analysis")
    produced = _validate_report(data, started)
    matches = [row for row in data["results"]
        if (provider_id is None or row["provider_id"] == provider_id)
        and (event_id is None or row["source_event_sha256"] == event_id)
        and (title_sha256 is None or row["source_title_sha256"] == title_sha256)]
    page = matches[offset:offset + limit]
    completed = _time(now)
    if completed < started:
        raise SourceShareError("consumer clock moved backwards")
    return {
        "schema": SCHEMA,
        "status": ("NO_COMPLETED_FEED_INPUT" if data["status"] == "NO_COMPLETED_FEED_INPUT"
                   else "FEED_ANALYSIS_READONLY_READY"),
        "analysis_schema": data["schema"], "producer_status": data["status"],
        "source_report_sha256": expected,
        "producer_checked_at": produced.isoformat() if produced is not None else None,
        "consumer_available_at": completed.isoformat(),
        "report_result_count": len(data["results"]), "matched_result_count": len(matches),
        "returned_result_count": len(page), "offset": offset,
        "has_more_matches": offset + len(page) < len(matches),
        "producer_summary": {k: data[k] for k in (
            "source_versions_checked", "matched_versions", "has_more_results",
            "ai_eligible_candidates", "new_ai_results", "cache_hits",
            "paid_execution_requested", "requested_ai_complete") if k in data},
        "rule_version": data.get("rule_version"),
        "routing_assumptions_not_acceptance_criteria": data.get("routing_assumptions_not_acceptance_criteria"),
        "results": page, "scope": "SAVED_ANALYSIS_REPORT_ONLY",
        "source_freshness_certified": False, "historical_decision_certified": False,
        "report_modified": False, "source_fetch_calls": 0, "ai_calls": 0,
        "database_writes": 0, "human_labels_added": 0,
        "verified_economic_facts": 0, "market_action": None,
    }
