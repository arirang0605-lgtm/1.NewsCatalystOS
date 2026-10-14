"""Completed RSS metadata -> economic screening -> existing budgeted AI/cache.

This is a downstream consumer, not a collector or a human-label producer.
Rules propose claims from exact title strings. Novelty is local/source-scoped,
importance is a review heuristic, and every AI statement remains unverified.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
import fcntl
import os
import re
import sqlite3
import tempfile

from .ai_provider import AIModel, AIRequest
from .ai_openai_transport import run_budgeted_openai_analysis
from .analysis_cache import cache_analysis_once, get_cached_analysis, _result_bytes
from .evidence_archive import _private_root, _write_new
from .fact_extraction import FactProposal, MONEY, verify_extracted_facts
from .feed_triage import _matched_terms
from .impact_triage import ImpactInputs, triage_importance, SCALE, SCOPE, REPEAT, NOVELTY
from .news_search import read_completed_title_snapshots
from .novelty_detection import detect_new_economic_claim
from .prior_fact_state import FactInput, PriorState, prior_state_as_of, record_prior_fact
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.feed_economic_analysis.v1"
RULE_VERSION = "rss-title-economic-v1"
# Screening assumptions, NOT release criteria or a verified economic scale.
MEDIUM_KRW = Decimal("1000000000")
LARGE_KRW = Decimal("100000000000")
HIGH_REVIEW_SCORE = 8  # same threshold as the existing importance triage
ACTION_RULES = (
    ("NEW_CONTRACT", r"(?:공급|납품)\s*계약.{0,30}(?:체결|수주|계획)|수주|(?:signs?|signed|awarded).{0,50}(?:supply|contract)|supply\s+contract"),
    ("NEW_INVESTMENT", r"(?:설비|시설|공장|반도체).{0,40}투자.{0,20}(?:결정|발표|계획)|투자.{0,20}(?:결정|발표)|(?:announce|announced).{0,40}investment"),
    ("COMMERCIALIZATION", r"상용화|commercialization"),
    ("PRODUCT_LAUNCH", r"신제품.{0,20}출시|(?:launch|launches|launched).{0,30}(?:chip|memory|semiconductor)"),
    ("REGULATORY_APPROVAL", r"인허가.{0,15}승인|regulatory\s+approval"),
    ("NEW_FACILITY", r"신규.{0,15}공장.{0,15}(?:가동|착공)|new\s+fab.{0,20}(?:opens|construction)"),
)
NEGATED = re.compile(r"취소|철회|해지|무산|체결하지\s*않|계약\s*없|부인|not\s+(?:signed|awarded)|(?:no|not).{0,15}(?:supply|contract|deal)|cancelled|canceled|denies", re.I)
PLANNED = re.compile(r"계획|예정|추진|검토|\b(?:plan\w*|will|proposed|potential)\b", re.I)
GLOBAL = re.compile(r"전\s*세계|글로벌|\bglobal\b", re.I)
INDUSTRY = re.compile(r"업계|산업\s*전반|\bindustry.wide\b", re.I)
RECURRING = re.compile(r"(?:[2-9]|[1-9][0-9]+)\s*년간.{0,20}공급|장기\s*공급|multi.year\s+supply|recurring\s+supply", re.I)
BLOCKED = frozenset({"BLOCK_AD_SPAM", "UNVERIFIED_RUMOR"})


def _stamp(now: datetime | None) -> datetime:
    return _when((now or datetime.now(timezone.utc)).isoformat(), "analysis time")


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _version(item: dict) -> str:
    return _digest("\0".join(item[k] for k in ("provider_id", "event_id", "title_sha256")))


def _subject(item: dict) -> str:
    # A source/document scope, NEVER a guessed company or globally merged event.
    return "RSS_DOC:" + _digest(item["provider_id"] + "\0" + item["canonical_url"])


def _category(title: str) -> str | None:
    if NEGATED.search(title):
        return None  # cancellation/refutation is not a NEW contract
    matches = [kind for kind, pattern in ACTION_RULES if re.search(pattern, title, re.I)]
    return matches[0] if len(matches) == 1 else None


def _claim(item: dict, at: datetime) -> FactInput:
    return FactInput(_subject(item), "ECONOMIC_HEADLINE", _version(item),
                     _digest(item["headline"].casefold()), at,
                     "OFFICIAL_CHANNEL_OBSERVED" if item["source_kind"] in
                     ("OFFICIAL_AGENCY", "COMPANY_IR") else "UNVERIFIED_CLAIM")


def _krw(mention: str) -> Decimal | None:
    match = re.fullmatch(r"₩?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(조원|억원|만원|원)", mention)
    if not match:
        return None  # no inferred FX conversion
    return Decimal(match[1].replace(",", "")) * {
        "조원": Decimal(10)**12, "억원": Decimal(10)**8,
        "만원": Decimal(10)**4, "원": Decimal(1),
    }[match[2]]


def _screen(item: dict, prior: PriorState, at: datetime) -> tuple[dict, FactInput | None]:
    title, event = item["headline"], _version(item)
    category = _category(title)
    permitted = item["claim_classification"] not in BLOCKED
    terms = _matched_terms(title)
    proposals = []
    for term in terms:
        start = title.casefold().find(term.casefold())
        proposals.append(FactProposal("PRODUCT", title[start:start + len(term)], title))
    amounts = [match.group().strip() for match in MONEY.finditer(title)]
    if category == "NEW_CONTRACT":
        proposals.extend(FactProposal("CONTRACT_AMOUNT", value, title) for value in amounts)
    extracted = verify_extracted_facts(event, title, proposals,
        observed_at=_when(item["available_at"], "source seen"), checked_at=at, now=at)
    fact = _claim(item, at) if category and permitted and terms else None
    own = [x for x in prior.facts if x.source_event_sha256 == event]
    baseline = PriorState(prior.reviewed_subject_id, at,
                          tuple(x for x in prior.facts if x.source_event_sha256 != event))
    change = (detect_new_economic_claim(baseline, fact, category, at, now=at)
              if fact else None)
    novelty = change.novelty if change else "UNCLASSIFIED_SOURCE_CLAIM"
    novelty_dim = {
        "NEW_FACT_CANDIDATE_NEEDS_EVIDENCE": "NEW_FACT_CANDIDATE",
        "CHANGED_ECONOMIC_CLAIM_REVIEW": "MATERIAL_REVISION",
        "EXISTING_ECONOMIC_CLAIM": "ALREADY_KNOWN",
    }.get(novelty, "UNKNOWN")
    numeric = _krw(amounts[0]) if len(amounts) == 1 and category else None
    scale = ("UNKNOWN" if numeric is None else "LARGE" if numeric >= LARGE_KRW
             else "MEDIUM" if numeric >= MEDIUM_KRW else "SMALL")
    dimensions = dict(scale=scale,
        affected_scope="GLOBAL" if GLOBAL.search(title) else "INDUSTRY" if INDUSTRY.search(title) else "UNKNOWN",
        repeatability="RECURRING" if RECURRING.search(title) else "UNKNOWN",
        novelty=novelty_dim, market_expectation="UNKNOWN")
    importance = triage_importance(ImpactInputs(event, at, **dimensions), at, now=at)
    known_score = sum((mapping[dimensions[key]] or 0) for key, mapping in (
        ("scale", SCALE), ("affected_scope", SCOPE), ("repeatability", REPEAT), ("novelty", NOVELTY)))
    eligible = bool(fact and known_score >= HIGH_REVIEW_SCORE and novelty_dim in
                    ("NEW_FACT_CANDIDATE", "MATERIAL_REVISION"))
    report = {
        "analysis_event_sha256": event, "source_event_sha256": item["event_id"],
        "source_title_sha256": item["title_sha256"], "provider_id": item["provider_id"],
        "document_id": item["document_id"], "source_url": item["canonical_url"],
        "headline": title, "source_kind": item["source_kind"],
        "source_available_at": item["available_at"],
        "source_triage_sha256": item["triage_sha256"],
        "source_claim_classification": item["claim_classification"],
        "category_candidate": category, "novelty": novelty,
        "novelty_scope": "CURRENT_LOCAL_HISTORY_SAME_PROVIDER_AND_DOCUMENT_URL",
        "already_recorded_source_version": bool(own),
        "reported_plan_only": bool(PLANNED.search(title)),
        "dimensions": dimensions, "legacy_importance_priority": importance.priority,
        "complete_importance_score": importance.numeric_score,
        "known_dimension_score_lower_bound": known_score,
        "known_dimensions": list(importance.known_dimensions),
        "unknown_dimensions": list(importance.unknown_dimensions),
        "routing_priority": "HIGH_PRIORITY_CANDIDATE" if eligible else "PARTIAL_EVIDENCE_ONLY",
        "routing_rule_version": RULE_VERSION,
        "source_amount_mentions": amounts,
        "source_matched_fields": [{"field": v.field, "value": v.value,
            "evidence_quote_sha256": v.evidence_quote_sha256, "status": v.status}
            for v in extracted.supported],
        "ai_eligible": eligible,
        "uncertainties": ["Title metadata only; event date and full context unverified",
            "Local novelty does not prove a globally new economic event",
            "Scale/scope/recurrence are screening estimates, not verified economic effects",
            "Supply relationships, realized revenue and market expectations are unverified"],
        "verified_economic_fact": False, "verified_supply_transaction": False,
        "verified_beneficiary": False, "revenue_estimate_krw": None,
    }
    return report, fact


def _sources(inbox: Path, state: Path, registry: ProviderRegistry, at: datetime) -> list[dict]:
    versions = {}
    for ack, document, digest in read_completed_title_snapshots(inbox, state, registry, now=at):
        for original in document["items"]:
            key = (original["provider_id"], original["event_id"], original["title_sha256"])
            item = dict(original, triage_sha256=digest, last_observed_at=ack["confirmed_at"])
            old = versions.get(key)
            if old is None:
                versions[key] = item
            else:
                last = max(old["last_observed_at"], item["last_observed_at"])
                if item["available_at"] < old["available_at"]:
                    versions[key] = item
                versions[key]["last_observed_at"] = last
    return list(versions.values())


def analyze_completed_feed(
    registry: ProviderRegistry, inbox_root: Path, poll_state: Path, analysis_root: Path, *,
    provider_id: str | None = None, event_id: str | None = None,
    title_sha256: str | None = None, limit: int = 20,
    model: AIModel | None = None, allow_paid: bool = False,
    opener=None, now: datetime | None = None,
) -> dict:
    """Reuse committed sources and separate analysis state; paid execution is opt-in.

    An injected opener is for offline tests of the EXISTING HTTP adapter only.
    Failed AI leaves source-backed fields visible and its cost reservation held.
    """
    at = _stamp(now)
    if (type(limit) is not int or not 1 <= limit <= 100 or type(allow_paid) is not bool
            or not isinstance(registry, ProviderRegistry)):
        raise SourceShareError("invalid feed analysis inputs")
    if event_id is not None:
        _must_sha(event_id, "selected event")
    if title_sha256 is not None:
        _must_sha(title_sha256, "selected title")
        if event_id is None:
            raise SourceShareError("title version selection requires an event")
    if model is not None:
        model.validate()
        if model.provider != "OPENAI":
            raise SourceShareError("this pipeline uses the existing OpenAI adapter")
    elif allow_paid:
        raise SourceShareError("explicit model and rates required before paid execution")
    if provider_id is not None:
        registry.active(provider_id, at=at)
    # Validate original evidence BEFORE initializing downstream analysis state.
    rows = _sources(inbox_root, poll_state, registry, at)
    root = Path(analysis_root)
    for source in (Path(inbox_root), Path(poll_state)):
        if root == source or root in source.parents or source in root.parents:
            raise SourceShareError("analysis writes must be separate from source inputs")
    selected = [x for x in rows if (provider_id is None or x["provider_id"] == provider_id)
                and (event_id is None or x["event_id"] == event_id)
                and (title_sha256 is None or x["title_sha256"] == title_sha256)]
    if title_sha256 is None:
        latest = {}
        for item in selected:
            key = (item["provider_id"], item["event_id"])
            if key not in latest or item["last_observed_at"] > latest[key]["last_observed_at"]:
                latest[key] = item
        selected = list(latest.values())
    selected.sort(key=lambda x: (x["available_at"], x["provider_id"], x["event_id"]), reverse=True)
    matched = len(selected)
    if event_id is not None and not selected:
        raise SourceShareError("selected committed source version unavailable")
    if not selected:
        return {"schema": SCHEMA, "status": "NO_COMPLETED_FEED_INPUT", "results": [],
                "source_versions_checked": len(rows), "new_ai_results": 0, "cache_hits": 0,
                "source_fetch_calls": 0, "human_labels_added": 0}
    root = _private_root(root)
    facts, cache, ledger = (root / n for n in ("facts.sqlite3", "ai_cache.sqlite3", "ai_costs.sqlite3"))
    reports = []
    for item in selected[:limit]:
        decision = _stamp(now)
        registry.active(item["provider_id"], at=decision)
        # Earlier title revisions are known NOW, never backfilled to an old decision.
        for previous in rows:
            if (_subject(previous) == _subject(item)
                    and previous["available_at"] < item["available_at"]
                    and _category(previous["headline"])
                    and previous["claim_classification"] not in BLOCKED):
                record_prior_fact(facts, _claim(previous, decision), now=decision)
        prior = prior_state_as_of(facts, _subject(item), decision, now=decision)
        report, fact = _screen(item, prior, decision)
        report.update(ai_status="NOT_ELIGIBLE", ai_analysis=None, ai_adapter_attempted=False)
        if fact:
            record_prior_fact(facts, fact, now=decision)
        cached = None
        metadata = "Unverified RSS title: " + item["headline"]
        metadata_sha = _digest(metadata)
        cache_unavailable = False
        if fact and model is not None and cache.exists():
            try:
                cached = get_cached_analysis(cache, event_sha256=report["analysis_event_sha256"],
                    source_version_sha256=item["title_sha256"], metadata_sha256=metadata_sha,
                    provider=model.provider, model=model.model, prompt_version=model.prompt_version,
                    decision_at=decision, now=decision)
            except (SourceShareError, OSError, sqlite3.Error):
                cache_unavailable = True
                report["ai_status"] = "AI_CACHE_UNAVAILABLE"
        if cached is not None:
            report.update(ai_status="CACHE_HIT", ai_analysis=json.loads(_result_bytes(cached.result)))
        elif report["ai_eligible"] and not cache_unavailable:
            if not allow_paid:
                report["ai_status"] = "AWAITING_EXPLICIT_AI_AUTHORIZATION"
            else:
                request = AIRequest(report["analysis_event_sha256"], metadata,
                    "OFFICIAL_METADATA" if item["source_kind"] in ("OFFICIAL_AGENCY", "COMPANY_IR")
                    else "LICENSED_METADATA", decision, decision, True, True)
                try:
                    report["ai_adapter_attempted"] = True
                    result = run_budgeted_openai_analysis(model, request, ledger,
                        allow_paid=True, opener=opener, now=now)
                    stored = cache_analysis_once(cache, result,
                        source_version_sha256=item["title_sha256"],
                        metadata_sha256=metadata_sha, recorded_at=_stamp(now))
                    report.update(ai_status="ANALYZED_UNVERIFIED",
                                  ai_analysis=json.loads(_result_bytes(stored.result)))
                except (SourceShareError, OSError, sqlite3.Error) as exc:
                    # Only fixed reason codes leave the adapter; no key/body/path leaks.
                    message = str(exc)
                    reason = ("AI_CREDENTIAL_UNAVAILABLE" if "credential" in message
                        else "AI_BUDGET_UNAVAILABLE" if "budget" in message
                        else "AI_ALREADY_RESERVED_OR_RESULT_UNAVAILABLE" if "already reserved" in message
                        else "AI_PROVIDER_OR_CACHE_UNAVAILABLE")
                    report.update(ai_status=reason)
        report["analysis_available_at"] = _stamp(now).isoformat()
        reports.append(report)
    return {"schema": SCHEMA, "status": "FEED_ECONOMIC_ANALYSIS_READY",
        "checked_at": _stamp(now).isoformat(), "rule_version": RULE_VERSION,
        "routing_assumptions_not_acceptance_criteria": {
            "medium_krw": str(MEDIUM_KRW), "large_krw": str(LARGE_KRW),
            "minimum_known_score": HIGH_REVIEW_SCORE},
        "source_versions_checked": len(rows), "matched_versions": matched,
        "has_more_results": matched > len(reports), "results": reports,
        "ai_eligible_candidates": sum(x["ai_eligible"] for x in reports),
        "new_ai_results": sum(x["ai_status"] == "ANALYZED_UNVERIFIED" for x in reports),
        "cache_hits": sum(x["ai_status"] == "CACHE_HIT" for x in reports),
        "source_fetch_calls": 0, "human_labels_added": 0,
        "source_inputs_modified": False, "article_body_included": False,
        "verified_economic_facts": 0, "market_action": None,
        "release_gate_verified": False}


def publish_feed_analysis(report: dict, output_root: Path) -> tuple[Path, str]:
    """Atomically save a private analysis result, not the official graph outbox."""
    if report.get("schema") != SCHEMA:
        raise SourceShareError("feed analysis report required")
    raw = _encoded(report)
    if len(raw) > 2_000_000:
        raise SourceShareError("bounded feed analysis report required")
    root = _private_root(output_root)
    digest = sha256(raw).hexdigest()
    dest = root / ("feed_analysis_" + digest + ".json")
    with tempfile.TemporaryDirectory(prefix=".analysis_", dir=root) as temporary:
        staged = Path(temporary) / "report.json"
        _write_new(staged, raw)
        # External SSD filesystems may not implement hard links (Mac errno 45).
        # Serialize the existence check and atomic rename, preserving old bytes.
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        lock = os.open(root / ".publish.lock", flags, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if dest.exists() or dest.is_symlink():
                if dest.is_symlink() or dest.read_bytes() != raw:
                    raise SourceShareError("existing analysis publication differs")
            else:
                os.rename(staged, dest)
            fd = os.open(root, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            os.close(lock)
    return dest, digest
