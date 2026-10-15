"""Gemini REST and existing RSS pipeline with synthetic responses only."""
from dataclasses import asdict
from io import BytesIO
import json
from pathlib import Path

import pytest

from newscatalystos.ai_cost_ledger import reserve_ai_call
from newscatalystos.ai_gemini_transport import (
    API_ROOT, _normal_response, gemini_generate_content_transport,
    run_budgeted_gemini_analysis,
)
from newscatalystos.feed_analysis_delivery import consume_feed_analysis
from newscatalystos.source_share import SourceShareError
from scripts import run_feed_analysis
from test_ai_provider import config, request
from test_feed_analysis import setup, run
from test_new_source_adapter import NOW


def packet(*, finish="STOP", usage=None, result=None):
    if result is None:
        result = {"summary": "Potential event", "claims": ["Unverified proposal"],
                  "uncertainties": ["Contract not confirmed"]}
    if usage is None:
        usage = {"promptTokenCount": 50, "candidatesTokenCount": 20,
                 "thoughtsTokenCount": 5, "totalTokenCount": 75}
    return json.dumps({
        "candidates": [{"content": {"role": "model", "parts": [
            {"text": json.dumps(result)}]}, "finishReason": finish}],
        "usageMetadata": usage,
    }).encode()


class LocalResponse(BytesIO):
    def __init__(self, payload, target):
        super().__init__(payload)
        self.status, self.target = 200, target

    def geturl(self):
        return self.target


class LocalOpener:
    def __init__(self, data):
        self.data, self.calls, self.requests = data, 0, []

    def open(self, request, *, timeout):
        self.calls += 1
        self.requests.append(request)
        assert timeout <= 30
        return LocalResponse(self.data, request.full_url)


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key-only-for-offline-tests")


def test_transport_sends_metadata_json_without_tools_or_storage(key):
    model = config("GEMINI")
    payload = {"schema": "newscatalyst.ai_analysis.v1", "event_sha256": "a" * 64,
               "metadata": "HBM investment news", "source_kind": "OFFICIAL_METADATA",
               "decision_at": NOW.isoformat(), "require_uncertainty": True,
               "unverified_market_fact": True}
    opener = LocalOpener(packet())
    response = gemini_generate_content_transport(
        model, payload, allow_paid=True, opener=opener)
    assert response["usage"] == {"input_tokens": 50, "output_tokens": 25}
    assert opener.calls == 1
    sent = opener.requests[0]
    assert sent.full_url == API_ROOT + model.model + ":generateContent"
    assert sent.get_method() == "POST"
    body = json.loads(sent.data)
    assert body["store"] is False and "tools" not in body
    assert body["generationConfig"]["responseFormat"]["text"]["mimeType"] == "application/json"
    assert body["generationConfig"]["maxOutputTokens"] == model.max_output_tokens
    assert "HBM investment news" in body["contents"][0]["parts"][0]["text"]


def test_missing_key_or_authorization_never_reserves_or_calls(monkeypatch, tmp_path):
    model, req = config("GEMINI"), request()
    ledger = tmp_path / "private" / "ai.sqlite3"
    opener = LocalOpener(packet())
    with pytest.raises(SourceShareError, match="explicit paid"):
        run_budgeted_gemini_analysis(model, req, ledger, opener=opener, now=NOW)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("newscatalystos.ai_gemini_transport._keychain_api_key", lambda: "")
    with pytest.raises(SourceShareError, match="credential unavailable"):
        run_budgeted_gemini_analysis(
            model, req, ledger, allow_paid=True, opener=opener, now=NOW)
    assert opener.calls == 0 and not ledger.exists()


def test_keychain_fallback_reads_once_before_reservation(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    lookups = []
    synthetic = "synthetic-keychain-key-for-offline-tests"
    def keychain_lookup():
        lookups.append(True)
        return synthetic
    monkeypatch.setattr("newscatalystos.ai_gemini_transport._keychain_api_key", keychain_lookup)
    model, req = config("GEMINI"), request()
    ledger = tmp_path / "private" / "ai.sqlite3"
    opener = LocalOpener(packet())
    result = run_budgeted_gemini_analysis(
        model, req, ledger, allow_paid=True, opener=opener, now=NOW)
    assert result.provider == "GEMINI"
    assert lookups == [True] and opener.calls == 1
    assert opener.requests[0].get_header("X-goog-api-key") == synthetic
    assert synthetic not in repr(result)


def test_budget_reservation_and_duplicate_call(key, tmp_path):
    model, req = config("GEMINI"), request()
    ledger = tmp_path / "private" / "ai.sqlite3"
    opener = LocalOpener(packet())
    first = run_budgeted_gemini_analysis(
        model, req, ledger, allow_paid=True, opener=opener, now=NOW)
    assert first.provider == "GEMINI"
    assert first.estimated_cost_krw == pytest.approx(0.1)
    assert not first.is_verified_market_fact
    with pytest.raises(SourceShareError, match="already reserved"):
        run_budgeted_gemini_analysis(
            model, req, ledger, allow_paid=True, opener=opener, now=NOW)
    assert opener.calls == 1


def test_failed_provider_keeps_reservation_and_never_retries(key, tmp_path):
    class Broken:
        calls = 0
        def open(self, *args, **kwargs):
            self.calls += 1
            raise OSError("synthetic connection failure")
    model, req = config("GEMINI"), request()
    ledger = tmp_path / "private" / "ai.sqlite3"
    opener = Broken()
    with pytest.raises(SourceShareError, match="provider unavailable"):
        run_budgeted_gemini_analysis(
            model, req, ledger, allow_paid=True, opener=opener, now=NOW)
    assert reserve_ai_call(ledger, model, req, now=NOW).status == "IN_FLIGHT_OR_UNSETTLED"
    with pytest.raises(SourceShareError, match="already reserved"):
        run_budgeted_gemini_analysis(
            model, req, ledger, allow_paid=True, opener=opener, now=NOW)
    assert opener.calls == 1


@pytest.mark.parametrize("data", [
    packet(finish="MAX_TOKENS"),
    packet(usage={"promptTokenCount": 50, "candidatesTokenCount": 20,
                  "totalTokenCount": 55}),
    packet(result={"summary": "x", "claims": [], "uncertainties": [],
                   "verified_market_fact": True}),
    b"not-json",
])
def test_incomplete_or_unaccounted_response_fails(data):
    with pytest.raises(SourceShareError):
        _normal_response(data, config("GEMINI"))


def test_existing_feed_cli_gemini_cache_and_private_consumer(key, tmp_path):
    info = setup(tmp_path)
    model = config("GEMINI")
    opener = LocalOpener(packet())
    path = tmp_path / "model.json"
    path.write_text(json.dumps(asdict(model)))
    path.chmod(0o600)
    opts = run_feed_analysis.parser().parse_args([
        "--registry", str(info[0].registry_path), "--inbox-root", str(info[0].inbox_root),
        "--state", str(info[0].poll_state), "--analysis-root", str(info[-1]),
        "--model-config", str(path), "--allow-paid"])
    code, first = run_feed_analysis.evaluate(opts, opener=opener)
    assert code == 0 and first["new_ai_results"] == 1 and opener.calls == 1
    row = first["results"][0]
    assert row["ai_analysis"]["provider"] == "GEMINI"
    assert not row["verified_economic_fact"]
    opts.allow_paid = False
    code, second = run_feed_analysis.evaluate(opts, opener=opener)
    assert code == 0 and second["cache_hits"] == 1 and opener.calls == 1
    saved = Path(second["private_report_file"])
    consumed = consume_feed_analysis(saved, saved.parent, second["report_sha256"])
    assert consumed["results"][0]["ai_analysis"]["provider"] == "GEMINI"
    assert consumed["ai_calls"] == 0


def test_gemini_is_not_called_for_blocked_feed_item(key, tmp_path):
    info = setup(tmp_path, "광고: HBM 반도체 공급 계약 체결")
    opener = LocalOpener(packet())
    report = run(info, model=config("GEMINI"), allow_paid=True, opener=opener)
    row = report["results"][0]
    assert not row["ai_eligible"] and row["ai_status"] == "NOT_ELIGIBLE"
    assert opener.calls == 0
    assert not (info[-1] / "ai_costs.sqlite3").exists()
