"""4_6 persistent cap and cache: no duplicate token charges on unchanged event."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.ai_cost_ledger import reserve_ai_call,settle_ai_call
from newscatalystos.ai_provider import run_ai_analysis
from newscatalystos.source_share import SourceShareError
from test_ai_provider import config,request,stub
from test_new_source_adapter import NOW


def path(tmp_path):
    return tmp_path/"private"/"ai_cost.sqlite3"


def test_reservation_settlement_and_cache_skip_without_second_call(tmp_path):
    db=path(tmp_path)
    reservation=reserve_ai_call(db,config(),request(),now=NOW)
    assert reservation.status=="RESERVED"
    assert reservation.reserved_cost_krw==pytest.approx(.4)
    result=run_ai_analysis(config(),request(),transport=stub,now=NOW)
    settle_ai_call(db,reservation,result,now=NOW)
    cached=reserve_ai_call(db,config(),request(),now=NOW)
    assert cached.status=="CACHED"
    assert cached.monthly_total_krw==pytest.approx(.08)
    assert db.stat().st_mode & 0o777 == 0o600


def test_unsettled_same_request_prevents_duplicate_parallel_call(tmp_path):
    db=path(tmp_path)
    first=reserve_ai_call(db,config(),request(),now=NOW)
    second=reserve_ai_call(db,config(),request(),now=NOW)
    assert first.status=="RESERVED"
    assert second.status=="IN_FLIGHT_OR_UNSETTLED"
    assert second.monthly_total_krw==first.monthly_total_krw


def test_hard_cap_denies_before_second_budget_reservation(tmp_path):
    db=path(tmp_path)
    high=replace(config(),input_krw_per_million=2_000_000,
                 max_input_tokens=100,max_output_tokens=100,
                 output_krw_per_million=2_000_000)
    with pytest.raises(SourceShareError,match="hard budget"):
        reserve_ai_call(db,high,request(),now=NOW,hard_budget_krw=5)


def test_many_distinct_events_cannot_bypass_monthly_limit(tmp_path):
    db=path(tmp_path)
    model=replace(config(),input_krw_per_million=1_000_000,
                  output_krw_per_million=0,max_input_tokens=100,
                  max_output_tokens=1)
    initial=reserve_ai_call(db,model,request(),now=NOW,hard_budget_krw=150)
    assert initial.reserved_cost_krw==100
    with pytest.raises(SourceShareError,match="hard budget"):
        reserve_ai_call(db,model,replace(request(),event_sha256="b"*64),
                        now=NOW,hard_budget_krw=150)


def test_old_event_is_not_eligible_for_budget_on_future_decision():
    with pytest.raises(SourceShareError,match="future"):
        reserve_ai_call("/tmp/do-not-create.sqlite3",config(),
                        replace(request(),decision_at=NOW+timedelta(seconds=2)),now=NOW)


def test_invalid_model_cost_or_existing_future_cache_rejected(tmp_path):
    with pytest.raises(SourceShareError):
        reserve_ai_call(path(tmp_path),config(),request(),
                        now=NOW,hard_budget_krw=50001)


def test_settle_wrong_model_result_never_rewrites_ledger(tmp_path):
    db=path(tmp_path)
    reservation=reserve_ai_call(db,config(),request(),now=NOW)
    result=run_ai_analysis(config(),request(),transport=stub,now=NOW)
    with pytest.raises(SourceShareError,match="differs"):
        settle_ai_call(db,reservation,replace(result,provider="ANTHROPIC"),now=NOW)
    assert reserve_ai_call(db,config(),request(),now=NOW).status=="IN_FLIGHT_OR_UNSETTLED"


def test_model_budget_soft_warning_with_high_reserved_cost(tmp_path):
    db=path(tmp_path)
    expensive=replace(config(),input_krw_per_million=80_000_000,
                      max_input_tokens=400,max_output_tokens=1,
                      output_krw_per_million=0)
    reservation=reserve_ai_call(db,expensive,request(),now=NOW)
    assert reservation.soft_limit_warning
    assert reservation.monthly_total_krw==32000


def test_negative_or_nan_settlement_cannot_credit_fake_budget(tmp_path):
    db=path(tmp_path)
    reservation=reserve_ai_call(db,config(),request(),now=NOW)
    result=run_ai_analysis(config(),request(),transport=stub,now=NOW)
    for value in (-1.0,float("nan")):
        with pytest.raises(SourceShareError,match="invalid settlement"):
            settle_ai_call(db,reservation,
                           replace(result,estimated_cost_krw=value),now=NOW)
    assert reserve_ai_call(db,config(),request(),now=NOW).status=="IN_FLIGHT_OR_UNSETTLED"
