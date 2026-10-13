"""4_1 identical normalized AI contract across model vendors, offline only."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.ai_provider import AIModel, AIRequest, run_ai_analysis, SCHEMA
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def config(provider="OPENAI"):
    return AIModel(
        provider=provider, model="synthetic-model-not-live",
        prompt_version="prompt-v1", temperature=0.0,
        max_input_tokens=200, max_output_tokens=100,
        input_krw_per_million=1000, output_krw_per_million=2000,
    )


def request():
    return AIRequest(
        event_sha256="a"*64, metadata="HBM investment news observed at official channel",
        source_kind="OFFICIAL_METADATA", first_usable_at=NOW,
        decision_at=NOW, important=True, new_economic_event=True,
    )


def stub(m, payload):
    assert payload["unverified_market_fact"] is True
    assert len(payload["metadata"]) <= 512
    assert m.prompt_version == "prompt-v1"
    return {
        "result": {
            "summary": "Candidate capital spending update",
            "claims": ["This is only a provider response"],
            "uncertainties": ["Economic outcome unverified"],
        },
        "usage": {"input_tokens": 40, "output_tokens": 20},
    }


@pytest.mark.parametrize("provider", ["OPENAI", "GEMINI", "ANTHROPIC"])
def test_vendor_swap_keeps_identical_schema(provider):
    result=run_ai_analysis(config(provider),request(),transport=stub,now=NOW)
    assert result.schema_version==SCHEMA
    assert result.provider==provider
    assert result.content_sha256
    assert result.estimated_cost_krw==pytest.approx(.08)
    assert not result.is_verified_market_fact
    assert result.classification.startswith("UNVERIFIED")
    assert result.available_at==NOW


def test_missing_real_provider_does_not_claim_success():
    with pytest.raises(SourceShareError,match="DATA_UNAVAILABLE"):
        run_ai_analysis(config(),request(),now=NOW)


def test_late_source_or_future_decision_cannot_leak_to_provider():
    called=[]
    def forbidden(*args):
        called.append(True)
        return stub(*args)
    with pytest.raises(SourceShareError,match="future"):
        run_ai_analysis(config(),replace(
            request(),first_usable_at=NOW+timedelta(seconds=2)),
            transport=forbidden,now=NOW)
    with pytest.raises(SourceShareError,match="future"):
        run_ai_analysis(config(),replace(
            request(),decision_at=NOW+timedelta(seconds=2)),
            transport=forbidden,now=NOW)
    assert not called


def test_repeated_not_novel_and_minor_not_sent_to_ai():
    for change in ({"important":False},{"new_economic_event":False}):
        with pytest.raises(SourceShareError,match="important novel"):
            run_ai_analysis(config(),replace(request(),**change),transport=stub,now=NOW)


def test_article_raw_and_unlicensed_input_are_blocked():
    with pytest.raises(SourceShareError,match="unauthorized"):
        run_ai_analysis(config(),replace(request(),source_kind="PAID_ARTICLE"),
                        transport=stub,now=NOW)
    with pytest.raises(SourceShareError,match="metadata-only"):
        run_ai_analysis(config(),replace(request(),metadata="x"*513),
                        transport=stub,now=NOW)


def test_preflight_budget_prevents_transport_call():
    called=[]
    def transport(*args):
        called.append(True)
        return stub(*args)
    with pytest.raises(SourceShareError,match="budget"):
        run_ai_analysis(config(),request(),transport=transport,now=NOW,
                        hard_budget_krw=1,cost_already_spent_krw=.8)
    assert called==[]


def test_malformed_schema_or_unaccounted_usage_fails_closed():
    cases=[
        {"result":{"summary":"x","claims":[],"uncertainties":[],"certified":True},
         "usage":{"input_tokens":1,"output_tokens":1}},
        {"result":{"summary":"x","claims":[],"uncertainties":[]},
         "usage":{"input_tokens":100000,"output_tokens":1}},
        {"result":{"summary":"x","claims":"not-array","uncertainties":[]},
         "usage":{"input_tokens":1,"output_tokens":1}},
    ]
    for result in cases:
        with pytest.raises(SourceShareError):
            run_ai_analysis(config(),request(),transport=lambda m,p:result,now=NOW)


def test_transport_failure_is_redacted():
    def fails(*_):
        raise Exception("SECRET_API_KEY_WRONG")
    with pytest.raises(SourceShareError,match="provider unavailable"):
        run_ai_analysis(config(),request(),transport=fails,now=NOW)


def test_no_arbitrary_provider_token_limits_or_krw_values():
    with pytest.raises(SourceShareError):
        run_ai_analysis(config("BAD"),request(),transport=stub,now=NOW)
    with pytest.raises(SourceShareError):
        run_ai_analysis(replace(config(),max_output_tokens=True),
                        request(),transport=stub,now=NOW)
    with pytest.raises(SourceShareError):
        run_ai_analysis(replace(config(),input_krw_per_million=-1),
                        request(),transport=stub,now=NOW)
