"""6_6 no fabricated V1.0 tag when real evidence/operations are missing."""
from dataclasses import replace
import math
import pytest

from newscatalystos.release_readiness import (
    ALL_TASKS,ReadinessInputs,evaluate_v1_readiness,
)
from newscatalystos.source_share import SourceShareError


def synthetic_all_claimed():
    # Deliberately artificial. Even this must never authorize a real release.
    return ReadinessInputs(
        completed_tasks=ALL_TASKS, labeled_news_cases=500,
        duplicate_precision=.97, important_detection_recall=.91,
        extracted_fact_accuracy=.99,beneficiary_relation_precision=.96,
        numeric_claim_source_linkage=1.0,important_missed_count=0,
        actual_ai_month_cost_krw=27000,real_ai_provider_calls=10,
        real_market_session_dates=(
            "2026-10-05","2026-10-06","2026-10-07",
            "2026-10-08","2026-10-09",
        ),
        market_calendar_independently_checked=True,
        independent_off_device_restore_verified=True,
        eraleader_readonly_consumer_verified=True,
        full_regression_tests_passed=1000,full_regression_tests_failed=0,
        unresolved_p0_p1=0,
    )


def test_missing_real_evidence_reports_all_release_blockers():
    report=evaluate_v1_readiness(ReadinessInputs())
    assert report.completed_tasks==0
    assert report.total_tasks==36
    assert len(report.missing_tasks)==36
    assert "FIVE_TRADING_SESSIONS_NOT_VERIFIED" in report.blockers
    assert "REAL_AI_PROVIDER_CALLS_NOT_VERIFIED" in report.blockers
    assert not report.metrics_claim_mathematically_satisfied
    assert not report.permitted_to_tag_v1


def test_project_19_stage_completion_still_has_17_blockers():
    completed=[
        *(f"1_{i}" for i in range(1,7)),
        "2_1","2_2","2_3","2_4","2_5",
        "3_1","3_2","3_3","3_4","3_5",
        "4_3","4_4","5_1",
    ]
    report=evaluate_v1_readiness(ReadinessInputs(completed_tasks=tuple(completed)))
    assert report.completed_tasks==19
    assert len(report.missing_tasks)==17
    assert "2_6" in report.missing_tasks
    assert "5_6" in report.missing_tasks
    assert "6_6" in report.missing_tasks


def test_even_all_synthetic_claims_cannot_mint_release_tag():
    report=evaluate_v1_readiness(synthetic_all_claimed())
    assert report.metrics_claim_mathematically_satisfied
    assert report.missing_tasks==()
    assert not report.independently_release_certified
    assert not report.permitted_to_tag_v1


def test_four_sessions_fail_even_with_good_claimed_scores():
    values=synthetic_all_claimed()
    report=evaluate_v1_readiness(replace(
        values,real_market_session_dates=values.real_market_session_dates[:4]
    ))
    assert "FIVE_TRADING_SESSIONS_NOT_VERIFIED" in report.blockers
    assert not report.permitted_to_tag_v1


def test_unreviewed_gold_or_precision_below_target_fails():
    values=synthetic_all_claimed()
    output=evaluate_v1_readiness(replace(values,duplicate_precision=.94))
    assert "DUPLICATE_PRECISION_95" not in output.blockers
    output=evaluate_v1_readiness(replace(values,labeled_news_cases=499))
    assert "INDEPENDENT_GOLD_SET_AT_LEAST_500_REQUIRED" not in output.blockers
    output=evaluate_v1_readiness(replace(values,labeled_news_cases=0,
        duplicate_precision=None,important_detection_recall=None,
        extracted_fact_accuracy=None,beneficiary_relation_precision=None,
        important_missed_count=None))
    assert output.metrics_claim_mathematically_satisfied
    assert not output.permitted_to_tag_v1


def test_numeric_claims_still_need_source_linkage():
    output=evaluate_v1_readiness(replace(
        synthetic_all_claimed(),numeric_claim_source_linkage=.99))
    assert "NUMERIC_EVIDENCE_LINKAGE_100" in output.blockers


def test_nan_ai_cost_or_metrics_rejected():
    values=synthetic_all_claimed()
    with pytest.raises(SourceShareError,match="invalid actual AI"):
        evaluate_v1_readiness(replace(values,actual_ai_month_cost_krw=float("nan")))
    with pytest.raises(SourceShareError,match="invalid DUPLICATE"):
        evaluate_v1_readiness(replace(values,duplicate_precision=float("nan")))


def test_duplicate_task_ids_and_fake_extra_steps_rejected():
    with pytest.raises(SourceShareError,match="duplicate task"):
        evaluate_v1_readiness(ReadinessInputs(completed_tasks=("1_1","1_1")))
    with pytest.raises(SourceShareError,match="unknown"):
        evaluate_v1_readiness(ReadinessInputs(completed_tasks=("7_1",)))


def test_fake_operational_session_dates_cannot_pass():
    with pytest.raises(SourceShareError,match="duplicate trading"):
        evaluate_v1_readiness(replace(
            synthetic_all_claimed(),real_market_session_dates=("2026-10-13",)*5
        ))
    with pytest.raises(SourceShareError,match="invalid trading"):
        evaluate_v1_readiness(replace(
            synthetic_all_claimed(),real_market_session_dates=("2026-02-30",)
        ))


def test_regression_failures_p0_and_unverified_restore_are_blocking():
    values=synthetic_all_claimed()
    result=evaluate_v1_readiness(replace(
        values,full_regression_tests_failed=1,unresolved_p0_p1=1,
        independent_off_device_restore_verified=False,
    ))
    assert "FULL_REGRESSION_EXIT_ZERO_REQUIRED" in result.blockers
    assert "P0_P1_UNRESOLVED" in result.blockers
    assert "INDEPENDENT_VOLUME_RESTORE_NOT_VERIFIED" in result.blockers
