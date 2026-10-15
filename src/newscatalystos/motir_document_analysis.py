"""Licensed, RSS-bound ministry text -> budgeted Gemini -> private result.

No collection, source mutation, implicit model, or human review queue. The full
extracted press text is sent only after current document rights and SHA checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from .ai_provider import AIModel, AIRequest, DOCUMENT_SCHEMA, MAX_DOCUMENT_CHARS
from .ai_gemini_transport import run_budgeted_gemini_analysis
from .analysis_cache import cache_analysis_once, get_cached_analysis, _result_bytes, _decode
from .evidence_archive import _private_root, _read_once, _write_new, read_archived_evidence
from .motir_article_binding import consume_motir_article_binding
from .motir_document_screen import prepare_motir_document_screen
from .provider_registry import ProviderRegistry, permits_document_storage, MOTIR_PRESS_DOCUMENT
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA = "newscatalyst.motir_document_analysis.v1"
MAX_REPORT = 65536


def _stamp(now):
    return _when((now or datetime.now(timezone.utc)).isoformat(), "document analysis time")


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def analyze_motir_document(
    binding_path: Path, binding_sha256: str, archive_root: Path,
    article_registry: ProviderRegistry, analysis_root: Path, *,
    model: AIModel | None = None, ai_ledger: Path | None = None,
    allow_paid: bool = False, analyze_existing: bool = False,
    opener=None, now: datetime | None = None,
) -> dict:
    at = _stamp(now)
    if type(allow_paid) is not bool or type(analyze_existing) is not bool:
        raise SourceShareError("boolean document execution policy required")
    if model is not None:
        model.validate()
        if model.provider != "GEMINI":
            raise SourceShareError("licensed document adapter requires Gemini")
    elif allow_paid or analyze_existing:
        raise SourceShareError("configured document model required")
    binding = consume_motir_article_binding(binding_path, binding_sha256, now=at)
    provider = article_registry.active(binding["article_provider_id"], at=at)
    if (not permits_document_storage(provider) or provider.method != "DOCUMENT"
            or provider.endpoint != binding["source_url"]):
        raise SourceShareError("current licensed article authorization required")
    # Recompute screening from the archive; a caller-provided eligibility bit is
    # never sufficient to dispatch paid analysis or to upgrade a prior plan.
    screen = _json(prepare_motir_document_screen(
        binding_path, binding_sha256, archive_root, now=at), "document screen")
    body, archived = read_archived_evidence(archive_root, binding["archive_version"], now=at)
    if (sha256(body).hexdigest() != binding["document_sha256"]
            or archived.receipt_sha256 != binding["archive_receipt_sha256"]):
        raise SourceShareError("document changed after screening")
    text = body.decode("utf-8")
    purpose = "EXISTING_ARTICLE" if analyze_existing else "NEW_EVENT"
    content = json.dumps({"article_text": text, "source_url": binding["source_url"],
        "analysis_purpose": purpose, "screen_findings": screen["findings"],
        "verified_new_economic_event": False}, ensure_ascii=False, sort_keys=True)
    event = sha256(("licensed-motir-body-v1\0" + binding["source_event_sha256"]
                    + "\0" + binding["document_sha256"]).encode()).hexdigest()
    content_sha = sha256(content.encode()).hexdigest()
    root = Path(analysis_root).resolve()
    archive = Path(archive_root).resolve()
    if root == archive or root in archive.parents or archive in root.parents:
        raise SourceShareError("document analysis must be separate from source archive")
    root = _private_root(Path(analysis_root))
    cache = root / "document_ai_cache.sqlite3"
    ledger = Path(ai_ledger) if ai_ledger else root / "ai_costs.sqlite3"
    if (ledger.resolve() == cache.resolve() or ledger.resolve() == Path(binding_path).resolve()
            or archive in ledger.resolve().parents):
        raise SourceShareError("separate document AI cost ledger required")
    report = {
        "schema": SCHEMA, "status": "MOTIR_DOCUMENT_ANALYSIS_READY",
        "content_scope": "LICENSED_ARTICLE_TEXT", "article_text_truncated": False,
        "source_url": binding["source_url"], "source_event_sha256": binding["source_event_sha256"],
        "title_sha256": binding["title_sha256"], "binding_sha256": binding_sha256,
        "document_sha256": binding["document_sha256"],
        "archive_receipt_sha256": binding["archive_receipt_sha256"],
        "analysis_event_sha256": event, "input_sha256": content_sha,
        "source_available_at": binding["binding_at"],
        "analysis_purpose": purpose, "screen_findings": screen["findings"],
        "ai_eligible": screen["ai_routing_candidate"],
        "ai_status": "NOT_ELIGIBLE", "ai_analysis": None,
        "ai_adapter_attempted": False, "new_ai_results": 0, "cache_hits": 0,
        "source_fetch_calls": 0, "verified_new_economic_event": False,
        "verified_real_transaction": False, "verified_real_benefit": False,
    }
    cached = None
    if model and cache.exists():
        cached = get_cached_analysis(cache, event_sha256=event,
            source_version_sha256=binding["document_sha256"], metadata_sha256=content_sha,
            provider=model.provider, model=model.model, prompt_version=model.prompt_version,
            decision_at=at, now=at)
    if cached:
        report.update(ai_status="CACHE_HIT", cache_hits=1,
                      ai_analysis=json.loads(_result_bytes(cached.result)))
    elif screen["ai_routing_candidate"] or analyze_existing:
        if not allow_paid or model is None:
            report["ai_status"] = "AI_DISABLED_BY_CONFIGURATION"
        elif len(content) > MAX_DOCUMENT_CHARS or len(content.encode("utf-8")) + 2048 > model.max_input_tokens:
            # Conservative byte-based preflight, including instruction overhead.
            # Never silently truncate temporal context or dispatch beyond budget.
            report["ai_status"] = "DOCUMENT_INPUT_LIMIT_EXCEEDED"
        else:
            request = AIRequest(event, content, "LICENSED_DOCUMENT",
                _when(binding["binding_at"], "body available"), at,
                screen["ai_routing_candidate"], screen["ai_routing_candidate"],
                analysis_purpose=purpose)
            try:
                report["ai_adapter_attempted"] = True
                result = run_budgeted_gemini_analysis(model, request, ledger,
                    allow_paid=True, opener=opener, now=now)
                stored = cache_analysis_once(cache, result,
                    source_version_sha256=binding["document_sha256"],
                    metadata_sha256=content_sha, recorded_at=_stamp(now))
                report.update(ai_status="ANALYZED_UNVERIFIED", new_ai_results=1,
                              ai_analysis=json.loads(_result_bytes(stored.result)))
            except (SourceShareError, OSError, sqlite3.Error) as exc:
                message = str(exc)
                report["ai_status"] = (
                    "AI_CREDENTIAL_UNAVAILABLE" if "credential" in message else
                    "AI_BUDGET_UNAVAILABLE" if "budget" in message else
                    "AI_ALREADY_RESERVED_OR_RESULT_UNAVAILABLE" if "already reserved" in message else
                    "AI_PROVIDER_OR_CACHE_UNAVAILABLE")
    report["analysis_available_at"] = _stamp(now).isoformat()
    return report


def publish_motir_document_analysis(report: dict, root: Path) -> tuple[Path, str]:
    if report.get("schema") != SCHEMA:
        raise SourceShareError("document analysis report required")
    raw = _bytes(report)
    if len(raw) > MAX_REPORT:
        raise SourceShareError("oversized document analysis report")
    digest = sha256(raw).hexdigest()
    path = _private_root(root) / ("motir_document_analysis_" + digest + ".json")
    try:
        _write_new(path, raw)
    except FileExistsError:
        if _read_once(path, MAX_REPORT) != raw:
            raise SourceShareError("document analysis publication conflict") from None
    return path, digest


def consume_motir_document_analysis(path: Path, expected_sha256: str, *, now=None) -> dict:
    raw = _read_once(path, MAX_REPORT)
    if sha256(raw).hexdigest() != _must_sha(expected_sha256, "document analysis pin"):
        raise SourceShareError("document analysis SHA mismatch")
    report = _json(raw, "document analysis")
    if (report.get("schema") != SCHEMA or report.get("status") != "MOTIR_DOCUMENT_ANALYSIS_READY"
            or report.get("content_scope") != "LICENSED_ARTICLE_TEXT"
            or report.get("article_text_truncated") is not False
            or not isinstance(report.get("source_url"), str)
            or MOTIR_PRESS_DOCUMENT.fullmatch(report["source_url"]) is None
            or any(report.get(k) is not False for k in (
                "verified_new_economic_event", "verified_real_transaction", "verified_real_benefit"))
            or not _when(report["source_available_at"], "source available")
                <= _when(report["analysis_available_at"], "analysis available") <= _stamp(now)):
        raise SourceShareError("invalid or future document analysis")
    for key in ("source_event_sha256", "title_sha256", "binding_sha256", "document_sha256",
                "archive_receipt_sha256", "analysis_event_sha256", "input_sha256"):
        _must_sha(report[key], key)
    result = report.get("ai_analysis")
    if result is not None:
        decoded = _decode(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode())
        if (decoded.schema_version != DOCUMENT_SCHEMA
                or decoded.event_sha256 != report["analysis_event_sha256"]
                or decoded.available_at > _when(report["analysis_available_at"], "analysis available")):
            raise SourceShareError("document analysis result identity mismatch")
    return report
