"""4_1 OpenAI Responses offline wire tests; NO paid endpoint accessed."""
from dataclasses import replace
from datetime import timedelta
from io import BytesIO
import json

import pytest

from newscatalystos.ai_openai_transport import (
    openai_responses_transport, run_budgeted_openai_analysis,
    _normal_response, API,
)
from newscatalystos.ai_cost_ledger import reserve_ai_call
from newscatalystos.ai_provider import run_ai_analysis
from newscatalystos.source_share import SourceShareError
from test_ai_provider import config, request
from test_new_source_adapter import NOW


class LocalResponse(BytesIO):
    def __init__(self, payload, *, target=API, status=200):
        super().__init__(payload)
        self.target, self.status = target, status

    def geturl(self):
        return self.target


class LocalOpener:
    def __init__(self, data):
        self.calls, self.requests, self.data = 0, [], data

    def open(self, request, *, timeout):
        self.calls += 1
        self.requests.append(request)
        assert timeout <= 30
        return LocalResponse(self.data)


def packet(*, text=None, usage=None, status="completed", model="synthetic-model-not-live"):
    if text is None:
        text = json.dumps({"summary": "Potential event", "claims": ["Unverified proposal"],
                           "uncertainties": ["Contract not confirmed"]})
    if usage is None:
        usage = {"input_tokens": 50, "output_tokens": 20}
    return json.dumps({
        "status": status, "model": model,
        "error": None, "incomplete_details": None, "usage": usage,
        "output": [{"type": "message", "role": "assistant",
                    "status": "completed", "content": [
                        {"type": "output_text", "text": text}]}],
    }).encode()


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-material-not-real-abcdef0123456789")


def test_real_http_shape_stays_explicit_metadata_only_and_not_stored(key):
    stub = LocalOpener(packet())
    model = config()
    result = run_ai_analysis(
        model, request(), now=NOW,
        transport=lambda m,p: openai_responses_transport(
            m,p,allow_paid=True,opener=stub),
    )
    assert result.provider == "OPENAI"
    assert result.estimated_cost_krw == pytest.approx(.09)
    assert not result.is_verified_market_fact
    assert stub.calls == 1
    sent = stub.requests[0]
    assert sent.full_url == API
    assert sent.get_method() == "POST"
    data = json.loads(sent.data)
    assert data["store"] is False
    assert data["text"]["format"]["strict"] is True
    assert data["text"]["format"]["name"] == "news_catalyst"
    assert data["model"] == model.model
    assert data["max_output_tokens"] == model.max_output_tokens
    assert "HBM investment news" in data["input"]
    assert "password" not in data["input"].lower()


def test_no_authorization_or_env_key_never_opens_socket(monkeypatch):
    stub = LocalOpener(packet())
    payload = {
        "schema": "newscatalyst.ai_analysis.v1",
        "event_sha256": "a"*64,
        "metadata": "A short item", "source_kind": "OFFICIAL_METADATA",
        "decision_at": NOW.isoformat(),
        "require_uncertainty": True, "unverified_market_fact": True,
    }
    with pytest.raises(SourceShareError, match="explicit paid"):
        openai_responses_transport(config(), payload, opener=stub)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SourceShareError, match="credential unavailable"):
        openai_responses_transport(config(),payload,allow_paid=True,opener=stub)
    assert stub.calls == 0


@pytest.mark.parametrize("bad", [
    packet(status="incomplete"), packet(model="another-model"),
    packet(usage={"input_tokens": 201, "output_tokens": 20}),
    packet(text="not-json"),
    packet(text=json.dumps({"summary": "x", "claims": [], "uncertainties": [],
                            "verified_market_fact": True})),
    packet(text=json.dumps({"summary": "x", "claims": "bad", "uncertainties": []})),
    b'not a JSON document',
])
def test_malformed_api_results_rejected_without_false_fact_status(key,bad):
    opener=LocalOpener(bad)
    with pytest.raises(SourceShareError):
        run_ai_analysis(
            config(),request(),now=NOW,
            transport=lambda m,p: openai_responses_transport(
                m,p,allow_paid=True,opener=opener))
    assert opener.calls == 1


def test_monthly_ledger_reservation_before_network_and_cached_call_never_rebilled(
    key,tmp_path
):
    state=tmp_path/"private"/"real_ai.sqlite3"
    opener=LocalOpener(packet())
    first=run_budgeted_openai_analysis(
        config(),request(),state,allow_paid=True,opener=opener,now=NOW)
    assert first.estimated_cost_krw==pytest.approx(.09)
    assert opener.calls==1
    with pytest.raises(SourceShareError,match="already reserved"):
        run_budgeted_openai_analysis(
            config(),request(),state,allow_paid=True,opener=opener,now=NOW)
    assert opener.calls==1


def test_failed_http_holds_reservation_and_prevents_double_charge(key,tmp_path):
    class ErrorOpener:
        calls=0
        def open(self, *args, **kwargs):
            self.calls+=1
            raise OSError("test offline connection failed: redacted credential sk-SHOULDNOTLOG")
    state=tmp_path/"private"/"real_ai.sqlite3"
    bad=ErrorOpener()
    with pytest.raises(SourceShareError, match="provider unavailable"):
        run_budgeted_openai_analysis(
            config(),request(),state,allow_paid=True,opener=bad,now=NOW)
    assert bad.calls==1
    assert reserve_ai_call(state,config(),request(),now=NOW).status=="IN_FLIGHT_OR_UNSETTLED"
    with pytest.raises(SourceShareError,match="already reserved"):
        run_budgeted_openai_analysis(
            config(),request(),state,allow_paid=True,opener=bad,now=NOW)
    assert bad.calls==1


def test_unapproved_no_key_and_nonimportant_do_not_create_budget_reservation(
    monkeypatch,tmp_path
):
    state=tmp_path/"private"/"real_ai.sqlite3"
    opener=LocalOpener(packet())
    with pytest.raises(SourceShareError,match="explicit paid"):
        run_budgeted_openai_analysis(config(),request(),state,opener=opener,now=NOW)
    assert not state.exists()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SourceShareError,match="credential unavailable"):
        run_budgeted_openai_analysis(
            config(),request(),state,allow_paid=True,opener=opener,now=NOW)
    assert not state.exists()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-material-not-real-abcdef0123456789")
    with pytest.raises(SourceShareError,match="important novel"):
        run_budgeted_openai_analysis(
            config(),replace(request(),important=False),
            state,allow_paid=True,opener=opener,now=NOW)
    assert opener.calls==0


def test_model_swap_or_future_request_does_not_leave_ledger(key,tmp_path):
    state=tmp_path/"private"/"real_ai.sqlite3"
    stub=LocalOpener(packet())
    with pytest.raises(SourceShareError,match="OpenAI model"):
        run_budgeted_openai_analysis(
            config("GEMINI"),request(),state,allow_paid=True,opener=stub,now=NOW)
    with pytest.raises(SourceShareError,match="future"):
        run_budgeted_openai_analysis(
            config(),replace(request(),decision_at=NOW+timedelta(seconds=1)),
            state,allow_paid=True,opener=stub,now=NOW)
    assert stub.calls==0 and not state.exists()
