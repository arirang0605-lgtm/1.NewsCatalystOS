"""6_6 conservative V1.0 release-gate checklist, never an automatic release.

A test file or a manually set Boolean is NOT independent operational proof.
This screen reports deficiencies from supplied metadata. The 2026-10-15 user
policy removes separate human news-article review, the 500-label release gate,
and label-derived precision/recall thresholds. Article provenance is required
in the operating pipeline; publication alone does not prove commercial claims.
Even an all-green self-reported list needs an actual release decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math

from .source_share import SourceShareError

ALL_TASKS=tuple(f"{phase}_{task}" for phase in range(1,7) for task in range(1,7))
# Retained for the optional research/evaluation workflow, not a release gate.
REQUIRED_GOLD_CASES=500


@dataclass(frozen=True)
class ReadinessInputs:
    completed_tasks: tuple[str, ...] = ()
    labeled_news_cases: int = 0
    duplicate_precision: float | None = None
    important_detection_recall: float | None = None
    extracted_fact_accuracy: float | None = None
    beneficiary_relation_precision: float | None = None
    numeric_claim_source_linkage: float | None = None
    important_missed_count: int | None = None
    actual_ai_month_cost_krw: float | None = None
    real_ai_provider_calls: int = 0
    real_market_session_dates: tuple[str, ...] = ()
    market_calendar_independently_checked: bool = False
    independent_off_device_restore_verified: bool = False
    eraleader_readonly_consumer_verified: bool = False
    full_regression_tests_passed: int = 0
    full_regression_tests_failed: int | None = None
    unresolved_p0_p1: int | None = None


@dataclass(frozen=True)
class ReadinessReport:
    completed_tasks: int
    total_tasks: int
    missing_tasks: tuple[str, ...]
    blockers: tuple[str, ...]
    metrics_claim_mathematically_satisfied: bool
    independently_release_certified: bool = False
    permitted_to_tag_v1: bool = False
    status: str = "NOT_READY_REQUIRES_INDEPENDENT_RELEASE_REVIEW"


def _fraction(value: float | None, field: str) -> bool:
    if value is None:
        return False
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
        raise SourceShareError(f"invalid {field} metric")
    return True


def evaluate_v1_readiness(values: ReadinessInputs) -> ReadinessReport:
    if not isinstance(values,ReadinessInputs):
        raise SourceShareError("validated V1.0 release evidence required")
    if len(set(values.completed_tasks))!=len(values.completed_tasks):
        raise SourceShareError("duplicate task identifiers")
    if set(values.completed_tasks)-set(ALL_TASKS):
        raise SourceShareError("unknown or unapproved V1.0 task")
    for field in ("labeled_news_cases","real_ai_provider_calls",
                  "full_regression_tests_passed"):
        val=getattr(values,field)
        if type(val) is not int or val<0:
            raise SourceShareError(f"invalid {field}")
    for field in ("important_missed_count","full_regression_tests_failed","unresolved_p0_p1"):
        val=getattr(values,field)
        if val is not None and (type(val) is not int or val<0):
            raise SourceShareError(f"invalid {field}")
    for field in ("market_calendar_independently_checked",
                  "independent_off_device_restore_verified",
                  "eraleader_readonly_consumer_verified"):
        if type(getattr(values,field)) is not bool:
            raise SourceShareError(f"invalid {field}")
    if values.actual_ai_month_cost_krw is not None and (
        type(values.actual_ai_month_cost_krw) not in (int,float) or
        not math.isfinite(values.actual_ai_month_cost_krw) or
        values.actual_ai_month_cost_krw<0
    ):
        raise SourceShareError("invalid actual AI cost")
    rates={
        "DUPLICATE_PRECISION_95":values.duplicate_precision,
        "IMPORTANT_DETECTION_RECALL_90":values.important_detection_recall,
        "FACT_EXTRACTION_ACCURACY_95":values.extracted_fact_accuracy,
        "BENEFICIARY_RELATION_PRECISION_95":values.beneficiary_relation_precision,
        "NUMERIC_EVIDENCE_LINKAGE_100":values.numeric_claim_source_linkage,
    }
    for name,val in rates.items():
        _fraction(val,name)
    dates=[]
    for raw in values.real_market_session_dates:
        if not isinstance(raw,str):
            raise SourceShareError("invalid trading session label")
        try:
            dt=date.fromisoformat(raw)
        except ValueError as exc:
            raise SourceShareError("invalid trading session date") from exc
        if dt.isoformat()!=raw:
            raise SourceShareError("noncanonical market trading session")
        dates.append(dt)
    if len(set(dates))!=len(dates):
        raise SourceShareError("duplicate trading session day")
    missing=tuple(x for x in ALL_TASKS if x not in values.completed_tasks)
    blocks=[]
    if missing:
        blocks.append(f"MISSING_{len(missing)}_V1_TASKS")
    # User-directed release scope: news articles enter as attributed source
    # claims without human gold labels. These optional metrics remain visible
    # to research tools, but cannot be represented as measured if absent.
    # Explicit numeric assertions still need complete source linkage.
    if rates["NUMERIC_EVIDENCE_LINKAGE_100"] is None or rates["NUMERIC_EVIDENCE_LINKAGE_100"]<1.0:
        blocks.append("NUMERIC_EVIDENCE_LINKAGE_100")
    if values.actual_ai_month_cost_krw is None or values.actual_ai_month_cost_krw>50000:
        blocks.append("VERIFIED_AI_BUDGET_50000_KRW")
    if values.real_ai_provider_calls==0:
        blocks.append("REAL_AI_PROVIDER_CALLS_NOT_VERIFIED")
    if len(dates)<5 or not values.market_calendar_independently_checked:
        blocks.append("FIVE_TRADING_SESSIONS_NOT_VERIFIED")
    if not values.independent_off_device_restore_verified:
        blocks.append("INDEPENDENT_VOLUME_RESTORE_NOT_VERIFIED")
    if not values.eraleader_readonly_consumer_verified:
        blocks.append("ERALEADER_READONLY_CONSUMER_NOT_VERIFIED")
    if (values.full_regression_tests_passed<=0 or
            values.full_regression_tests_failed!=0):
        blocks.append("FULL_REGRESSION_EXIT_ZERO_REQUIRED")
    if values.unresolved_p0_p1!=0:
        blocks.append("P0_P1_UNRESOLVED")
    return ReadinessReport(
        completed_tasks=len(values.completed_tasks),total_tasks=len(ALL_TASKS),
        missing_tasks=missing,blockers=tuple(blocks),
        metrics_claim_mathematically_satisfied=not blocks,
    )
