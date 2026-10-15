"""4_1 vendor-neutral AI contract; injected provider transport, NO implicit network.

Only important new observations with verified PIT availability are eligible.
This module does not include an SDK, API endpoint, credentials, or content upload.
A trusted operator must explicitly inject an authorized transport for a live call.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable, Protocol

from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.ai_analysis.v1"
PROVIDERS = frozenset({"OPENAI", "GEMINI", "ANTHROPIC"})
ALLOW_KINDS = frozenset({"OFFICIAL_METADATA", "LICENSED_METADATA"})
AI_CLASS = "UNVERIFIED_AI_INTERPRETATION_NOT_MARKET_FACT"
OUTPUT_FIELDS = frozenset({"summary", "claims", "uncertainties"})
MAX_METADATA_CHARS = 512
MAX_CLAIMS = 12


class AITransportError(SourceShareError):
    """Safe operational status; never carries provider response bodies or keys."""
    def __init__(self, http_status: int):
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else 0
        super().__init__(f"AI provider unavailable (HTTP_{self.http_status})")


@dataclass(frozen=True)
class AIModel:
    provider: str
    model: str
    prompt_version: str
    temperature: float
    max_input_tokens: int
    max_output_tokens: int
    # Operator-entered accounting assumptions, not verified live pricing.
    input_krw_per_million: int
    output_krw_per_million: int

    def validate(self) -> None:
        if self.provider not in PROVIDERS:
            raise SourceShareError("unknown AI provider")
        if (not isinstance(self.model, str) or not 1 <= len(self.model) <= 80
                or not isinstance(self.prompt_version, str)
                or not 1 <= len(self.prompt_version) <= 40):
            raise SourceShareError("invalid model/prompt version")
        if (type(self.temperature) not in (float, int)
                or not 0 <= self.temperature <= 1):
            raise SourceShareError("invalid temperature")
        if (type(self.max_input_tokens) is not int
                or type(self.max_output_tokens) is not int
                or not 1 <= self.max_input_tokens <= 20000
                or not 1 <= self.max_output_tokens <= 5000):
            raise SourceShareError("invalid AI token limits")
        if (type(self.input_krw_per_million) is not int
                or type(self.output_krw_per_million) is not int
                or not 0 <= self.input_krw_per_million <= 100000000
                or not 0 <= self.output_krw_per_million <= 100000000):
            raise SourceShareError("invalid assumed AI price")


@dataclass(frozen=True)
class AIRequest:
    event_sha256: str
    metadata: str
    source_kind: str
    first_usable_at: datetime
    decision_at: datetime
    important: bool
    new_economic_event: bool
    externally_verified_fact: bool = False
    analysis_purpose: str = "NEW_EVENT"


@dataclass(frozen=True)
class AIResult:
    schema_version: str
    event_sha256: str
    provider: str
    model: str
    prompt_version: str
    content_sha256: str
    summary: str
    claims: tuple[str, ...]
    uncertainties: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    estimated_cost_krw: float
    available_at: datetime
    classification: str = AI_CLASS
    is_verified_market_fact: bool = False


def _check_request(request: AIRequest, now: datetime) -> None:
    if not isinstance(request, AIRequest):
        raise SourceShareError("structured AI request required")
    _must_sha(request.event_sha256, "AI event SHA")
    observed = _when(request.first_usable_at.isoformat(), "first usable")
    decision = _when(request.decision_at.isoformat(), "decision at")
    if observed > decision or decision > now:
        raise SourceShareError("future information cannot be sent to AI")
    if (request.source_kind not in ALLOW_KINDS or
            type(request.important) is not bool or
            type(request.new_economic_event) is not bool or
            type(request.externally_verified_fact) is not bool):
        raise SourceShareError("invalid or unauthorized AI source")
    if request.analysis_purpose not in ("NEW_EVENT", "EXISTING_ARTICLE"):
        raise SourceShareError("invalid AI analysis purpose")
    if request.analysis_purpose == "NEW_EVENT" and (not request.important or not request.new_economic_event):
        raise SourceShareError("AI only for important novel events")
    if (not isinstance(request.metadata, str)
            or not 0 < len(request.metadata) <= MAX_METADATA_CHARS
            or "\x00" in request.metadata or "\n" in request.metadata):
        raise SourceShareError("unsafe or oversized metadata-only AI input")
    # This is a metadata-only bridge; article body and credentials are never
    # arguments to an SDK or an automatically-created HTTP connection.


def _validate_result(value: object) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    if not isinstance(value, dict) or set(value) != OUTPUT_FIELDS:
        raise SourceShareError("AI output does not match normalized schema")
    summary = value["summary"]
    claims = value["claims"]
    unknown = value["uncertainties"]
    if (not isinstance(summary, str) or not 0 < len(summary) <= 1000
            or not isinstance(claims, list) or len(claims) > MAX_CLAIMS
            or not isinstance(unknown, list) or len(unknown) > MAX_CLAIMS):
        raise SourceShareError("invalid AI output bounds")
    if any(not isinstance(x, str) or not 0 < len(x) <= 500 for x in claims+unknown):
        raise SourceShareError("invalid AI claim/uncertainty")
    return summary, tuple(claims), tuple(unknown)


def run_ai_analysis(
    model: AIModel, request: AIRequest,
    *,
    transport: Callable[[AIModel, dict], dict] | None = None,
    now: datetime | None = None,
    hard_budget_krw: int = 50000,
    cost_already_spent_krw: float = 0.0,
) -> AIResult:
    """A strictly injected transport takes a minimal vendor-neutral payload.

    Not a production billing ledger: 4_6 must replace the caller-provided
    spending sum with an independently persisted verified monthly total.
    """
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if not isinstance(model, AIModel):
        raise SourceShareError("AI model configuration missing")
    model.validate()
    _check_request(request, current)
    if (type(hard_budget_krw) is not int or not 0 < hard_budget_krw <= 50000
            or type(cost_already_spent_krw) not in (int,float)
            or not 0 <= cost_already_spent_krw <= hard_budget_krw):
        raise SourceShareError("AI budget inputs invalid")
    ceiling = (
        model.max_input_tokens * model.input_krw_per_million +
        model.max_output_tokens * model.output_krw_per_million
    ) / 1_000_000
    if cost_already_spent_krw + ceiling > hard_budget_krw:
        raise SourceShareError("AI hard budget denied before network")
    if transport is None:
        raise SourceShareError("AI transport not configured, DATA_UNAVAILABLE")
    prompt = {
        "schema": SCHEMA, "event_sha256": request.event_sha256,
        "metadata": request.metadata, "source_kind": request.source_kind,
        "decision_at": request.decision_at.isoformat(),
        "require_uncertainty": True, "unverified_market_fact": True,
    }
    try:
        response = transport(model, prompt)
    except AITransportError:
        raise
    except Exception as exc:
        raise SourceShareError("AI provider unavailable, original evidence unchanged") from None
    if not isinstance(response, dict) or set(response) != {"result","usage"}:
        raise SourceShareError("AI provider returned invalid envelope")
    summary, claims, unknown = _validate_result(response["result"])
    usage = response["usage"]
    if not isinstance(usage,dict) or set(usage) != {"input_tokens","output_tokens"}:
        raise SourceShareError("AI usage accounting missing")
    inp, out = usage["input_tokens"], usage["output_tokens"]
    if (type(inp) is not int or type(out) is not int
            or not 0 <= inp <= model.max_input_tokens
            or not 0 <= out <= model.max_output_tokens):
        raise SourceShareError("AI usage exceeds planned bounds")
    actual = (inp*model.input_krw_per_million +
              out*model.output_krw_per_million) / 1_000_000
    if cost_already_spent_krw+actual > hard_budget_krw:
        raise SourceShareError("AI usage exceeds hard budget")
    sealed = json.dumps(response["result"], sort_keys=True,
                        ensure_ascii=False, separators=(",", ":")).encode()
    # The model's words are NOT usable at dispatch time. In production record
    # availability only AFTER the HTTP response has been fully validated.
    completed_at = _when((now or datetime.now(timezone.utc)).isoformat(),
                         "AI response completed")
    return AIResult(
        SCHEMA, request.event_sha256, model.provider, model.model,
        model.prompt_version, sha256(sealed).hexdigest(),
        summary, claims, unknown, inp, out, actual, completed_at,
    )
