"""2_6/3_6 offline audit of REAL SHA-pinned blind news sample composition.

Review confidence is NOT measured by accumulating generic RSS headlines.
This audit exposes source/role concentration and semiconductor title hints,
while keeping human review blind and preserving every private gold batch.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .feed_triage import _matched_terms
from .live_gold_samples import (
    BLIND_SCHEMA, MAX_FILE, _load_pinned_predictions, _prior_frozen_ids,
    summarize_all_gold_reviews,
)
from .source_share import SourceShareError, _json, _read_regular, _when

SUPPORTED_ROLES = frozenset({"OFFICIAL_AGENCY", "COMPANY_IR", "PRESS_RELEASE"})


def audit_gold_scope(
    out_root: Path, pin_root: Path, workspace_root: Path, *,
    now: datetime | None = None,
) -> dict:
    """Verified frozen metadata only; no new source collection, labels or writes."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "scope audit at")
    verified_ids, digests = _prior_frozen_ids(out_root, pin_root, at)
    if not digests:
        raise SourceShareError("no pinned RSS gold batches")
    source_counts = Counter()
    role_counts = Counter()
    keyword_by_provider = Counter()
    keyword_cases = 0
    earliest_source_day = None
    latest_source_day = None
    first_freeze_day = None
    last_freeze_day = None
    for digest in digests:
        name = "gold_batch_" + digest
        folder = Path(out_root) / name
        pin = Path(pin_root) / (name + ".pin.json")
        predictions, pinned_at = _load_pinned_predictions(
            folder, out_root, digest, pin, pin_root, at,
        )
        by_case = {row.case_sha256: row for row in predictions}
        blind = _json(
            _read_regular(folder / "blind_cases.json", MAX_FILE),
            "gold source composition",
        )
        if (blind.get("schema") != BLIND_SCHEMA
                or blind.get("predictions_visible_to_reviewer") is not False
                or not isinstance(blind.get("cases"), list)
                or len(blind["cases"]) != len(by_case)):
            raise SourceShareError("invalid pinned blind source composition")
        seen = set()
        freeze_day = pinned_at.date().isoformat()
        first_freeze_day = min(first_freeze_day, freeze_day) if first_freeze_day else freeze_day
        last_freeze_day = max(last_freeze_day, freeze_day) if last_freeze_day else freeze_day
        for case in blind["cases"]:
            if not isinstance(case, dict):
                raise SourceShareError("invalid source role metadata")
            identity = case.get("case_sha256")
            prediction = by_case.get(identity)
            if identity in seen or prediction is None:
                raise SourceShareError("blind source mismatches frozen prediction")
            seen.add(identity)
            if (case.get("source_sha256") != prediction.source_sha256
                    or not isinstance(case.get("provider_id"), str)
                    or not 1 <= len(case["provider_id"]) <= 128
                    or case.get("source_role") not in SUPPORTED_ROLES
                    or not isinstance(case.get("headline"), str)
                    or not 0 < len(case["headline"]) <= 512
                    or case.get("economic_fact_verified") is not False):
                raise SourceShareError("untrustworthy source composition record")
            available = _when(case.get("source_available_at"), "gold case available")
            acknowledged = _when(case.get("first_acknowledged_at"), "case ACK time")
            if (available != prediction.source_available_at
                    or available > acknowledged or acknowledged > pinned_at):
                raise SourceShareError("gold source observation/PIT order mismatch")
            source_counts[case["provider_id"]] += 1
            role_counts[case["source_role"]] += 1
            day = available.date().isoformat()
            earliest_source_day = min(earliest_source_day, day) if earliest_source_day else day
            latest_source_day = max(latest_source_day, day) if latest_source_day else day
            if _matched_terms(case["headline"]):
                keyword_cases += 1
                keyword_by_provider[case["provider_id"]] += 1
        if len(seen) != len(by_case):
            raise SourceShareError("incomplete frozen source metadata")
    if sum(source_counts.values()) != len(verified_ids):
        raise SourceShareError("duplicated or incomplete pinned source sample")
    # Reuse 2-human, 2-batch existing validator rather than treating any
    # keyword, machine prediction or blank review as human ground truth.
    human = summarize_all_gold_reviews(out_root, pin_root, workspace_root, now=at)
    if human["sample_count"] != len(verified_ids):
        raise SourceShareError("human gold/sample scope count inconsistent")
    total = len(verified_ids)
    warnings = []
    if len(source_counts) <= 2:
        warnings.append("NARROW_PROVIDER_DIVERSITY_REVIEW_REQUIRED")
    if "PRESS_RELEASE" in role_counts and "INDEPENDENT_NEWSROOM" not in role_counts:
        warnings.append("PRESS_RELEASES_ARE_NOT_INDEPENDENT_JOURNALISM")
    if keyword_cases < total:
        warnings.append("SEMICONDUCTOR_KEYWORD_COVERAGE_NOT_REPRESENTATIVE")
    if human["reviewed_by_two_agreeing_humans"] < total:
        warnings.append("TWO_HUMAN_GOLD_LABELS_INCOMPLETE")
    return {
        "status": "PINNED_RSS_SCOPE_REVIEW_REQUIRED_NOT_SECTOR_CERTIFIED",
        "sha_pinned_batch_count": len(digests),
        "unique_frozen_case_count": total,
        "approved_provider_case_counts": dict(sorted(source_counts.items())),
        "observed_source_role_case_counts": dict(sorted(role_counts.items())),
        "semiconductor_title_keyword_hints": keyword_cases,
        "semiconductor_title_keyword_hints_by_provider": dict(sorted(keyword_by_provider.items())),
        "other_title_cases_without_semiconductor_keywords": total - keyword_cases,
        "semiconductor_title_keyword_share": keyword_cases / total,
        "earliest_source_available_day_utc": earliest_source_day,
        "latest_source_available_day_utc": latest_source_day,
        "first_local_pin_day_utc": first_freeze_day,
        "last_local_pin_day_utc": last_freeze_day,
        "two_reviewer_agreed_cases": human["reviewed_by_two_agreeing_humans"],
        "unreviewed_or_partial_cases": human["missing_or_partial_human_case_count"],
        "disputed_human_cases": human["disputed_case_count"],
        "missing_unique_case_count_to_500": max(0, 500 - total),
        "missing_two_human_agreements_to_500": max(
            0, 500 - human["reviewed_by_two_agreeing_humans"]),
        "warnings": warnings,
        "sector_recall_precision_certified": False,
        "reviewer_independence_certified": False,
        "release_gate_verified": False,
        "rss_requests": 0,
        "official_era_requests": 0,
        "ai_calls": 0,
    }
