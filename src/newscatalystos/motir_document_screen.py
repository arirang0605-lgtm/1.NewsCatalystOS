"""Conservative economic screen of a SHA-bound, licensed ministry article.

Concrete economic changes feed theme discovery independently of paid AI
routing. A prior plan mentioned again remains a follow-up source claim.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re

from .evidence_archive import _private_root, _read_once, _write_new, read_archived_evidence
from .fact_extraction import MONEY
from .economic_changes import extract_economic_changes
from .motir_article_binding import consume_motir_article_binding
from .provider_registry import MOTIR_PRESS_DOCUMENT
from .source_share import SourceShareError, _json, _must_sha, _when

LEGACY_SCHEMA = "newscatalyst.motir_document_economic_screen.v1"
PREVIOUS_SCHEMA = "newscatalyst.motir_document_economic_screen.v2"
SCHEMA = "newscatalyst.motir_document_economic_screen.v3"
STATUS = "SOURCE_DOCUMENT_SCREENED_NOT_FACT_VERIFIED"
SECTOR = re.compile(r"반도체|파운드리|메모리\s*칩|첨단전략산업|semiconductor|chip\s+fab", re.I)
INVESTMENT = re.compile(r"투자|investment|investing", re.I)
PRIOR = re.compile(
    r"지난.{0,50}(?:발표된|발표한|공개된|확정된)|기존.{0,40}(?:투자|계획)|"
    r"이미.{0,40}(?:발표|공개|확정)|(?:투자|계획).{0,35}(?:이행|점검)|"
    r"(?:previously|earlier|last\s+year).{0,50}(?:announced|planned)", re.I,
)
NEW = re.compile(
    r"(?:신규|새로|새로운).{0,30}투자|투자.{0,25}(?:결정|확정|발표)|"
    r"(?:new|fresh).{0,30}investment|announc(?:es|ed).{0,35}investment", re.I,
)
MIN_AI_CANDIDATE_KRW = Decimal("100000000000")
MAX_SCREEN_BYTES = 16384
MAX_FINDINGS = 50


def _krw(mention: str) -> Decimal | None:
    match = re.fullmatch(r"₩?\s*(\d+(?:[,.]\d+)*)\s*(조원|억원|만원|원)", mention)
    if not match:
        return None
    value = Decimal(match[1].replace(",", ""))
    return value * {
        "조원": Decimal(10)**12, "억원": Decimal(10)**8,
        "만원": Decimal(10)**4, "원": Decimal(1),
    }[match[2]]


def prepare_motir_document_screen(
    binding_path: Path, binding_sha256: str, archive_root: Path,
    *, now: datetime | None = None, company_names=(),
) -> bytes:
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "screen time")
    binding_sha = _must_sha(binding_sha256, "article binding")
    binding = consume_motir_article_binding(binding_path, binding_sha, now=at)
    body, archived = read_archived_evidence(
        archive_root, binding["archive_version"], now=at,
    )
    if (archived.content_scope != "LICENSED_SOURCE_BYTES"
            or archived.provider_id != binding["article_provider_id"]
            or archived.document_id != binding["source_url"].split("/")[-2]
            or archived.receipt_sha256 != binding["archive_receipt_sha256"]
            or archived.payload_sha256 != binding["document_sha256"]
            or archived.archived_at.isoformat() != binding["article_archived_at"]):
        raise SourceShareError("screen article archive differs from RSS binding")
    try:
        lines = [line.strip() for line in body.decode("utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        raise SourceShareError("licensed article text must be UTF-8") from exc
    if len(lines) > 1000 or any(len(line) > 5000 for line in lines):
        raise SourceShareError("unbounded article paragraphs")
    findings = []
    for line in lines:
        amounts = [match.group().strip() for match in MONEY.finditer(line)]
        if not amounts or not INVESTMENT.search(line) or not SECTOR.search(line):
            continue
        prior, new = bool(PRIOR.search(line)), bool(NEW.search(line))
        category = (
            "MIXED_TEMPORAL_EVIDENCE_HOLD" if prior and new else
            "PRIOR_INVESTMENT_PLAN_MONITORING" if prior else
            "NEW_INVESTMENT_SOURCE_CANDIDATE" if new else
            "INVESTMENT_MENTION_UNRESOLVED"
        )
        eligible = bool(category == "NEW_INVESTMENT_SOURCE_CANDIDATE"
                        and any((amount := _krw(value)) is not None
                                and amount >= MIN_AI_CANDIDATE_KRW
                                for value in amounts))
        findings.append({
            "category": category,
            "source_paragraph_sha256": sha256(line.encode("utf-8")).hexdigest(),
            "source_amount_mentions": amounts[:5],
            "possible_new_investment_for_ai": eligible,
            "verified_new_economic_event": False,
        })
        if len(findings) > MAX_FINDINGS:
            raise SourceShareError("too many monetary investment paragraphs")
    changes = extract_economic_changes("\n".join(lines),company_names=company_names)
    # Retain concrete changes for theme discovery regardless of amount.
    # Only paid investment routing retains its monetary/temporal threshold.
    eligible_investments = {row["source_paragraph_sha256"] for row in findings
                            if row["possible_new_investment_for_ai"]}
    routed_changes = [row for row in changes if row["action"] != "INVESTMENT"
                      or row["source_paragraph_sha256"] in eligible_investments]
    result = {
        "schema": SCHEMA, "status": STATUS,
        "source_url": binding["source_url"],
        "source_event_sha256": binding["source_event_sha256"],
        "title_sha256": binding["title_sha256"],
        "binding_sha256": binding_sha,
        "document_sha256": binding["document_sha256"],
        "article_available_at": binding["binding_at"],
        "screened_at": at.isoformat(),
        "findings": findings,
        "economic_changes": changes,
        "ai_routing_candidate": bool(routed_changes) or any(row["possible_new_investment_for_ai"] for row in findings),
        "ai_provider_calls": 0,
        "verified_new_economic_event": False,
        "verified_real_transaction": False,
        "verified_real_benefit": False,
    }
    payload = (json.dumps(result, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > MAX_SCREEN_BYTES:
        raise SourceShareError("document screen exceeds private receipt limit")
    return payload


def publish_motir_document_screen(payload: bytes, out_root: Path) -> tuple[Path, str]:
    data = _json(payload, "ministry document screen")
    if data.get("schema") != SCHEMA or data.get("status") != STATUS:
        raise SourceShareError("document screen schema mismatch")
    digest = sha256(payload).hexdigest()
    root = _private_root(out_root)
    path = root / ("motir_document_screen_" + digest + ".json")
    if path.exists():
        if _read_once(path, MAX_SCREEN_BYTES) != payload:
            raise SourceShareError("document screen hash collision")
    else:
        _write_new(path, payload)
    return path, digest


def consume_motir_document_screen(path: Path, expected_sha256: str, *,
                                  now: datetime | None = None) -> dict:
    expected = _must_sha(expected_sha256, "document screen pin")
    payload = _read_once(path, MAX_SCREEN_BYTES)
    if sha256(payload).hexdigest() != expected:
        raise SourceShareError("document screen SHA mismatch")
    data = _json(payload, "document screen")
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "consumer time")
    required = {"schema", "status", "source_url", "source_event_sha256",
                "title_sha256", "binding_sha256", "document_sha256",
                "article_available_at", "screened_at", "findings",
                "ai_routing_candidate", "ai_provider_calls",
                "verified_new_economic_event", "verified_real_transaction",
                "verified_real_benefit"}
    if data.get("schema") in {SCHEMA, PREVIOUS_SCHEMA}:
        required.add("economic_changes")
    if (set(data) != required or data["schema"] not in {SCHEMA, PREVIOUS_SCHEMA, LEGACY_SCHEMA} or data["status"] != STATUS
            or not isinstance(data["source_url"], str)
            or MOTIR_PRESS_DOCUMENT.fullmatch(data["source_url"]) is None
            or type(data["ai_provider_calls"]) is not int or data["ai_provider_calls"] != 0
            or any(data[key] is not False for key in (
                "verified_new_economic_event", "verified_real_transaction",
                "verified_real_benefit"))
            or not _when(data["article_available_at"], "article available")
                <= _when(data["screened_at"], "screen time") <= at
            or not isinstance(data["findings"], list)
            or len(data["findings"]) > MAX_FINDINGS):
        raise SourceShareError("unavailable or overstated document screen")
    for key in ("source_event_sha256", "title_sha256", "binding_sha256",
                "document_sha256"):
        _must_sha(data[key], key)
    for row in data["findings"]:
        if (not isinstance(row, dict) or set(row) != {
                "category", "source_paragraph_sha256", "source_amount_mentions",
                "possible_new_investment_for_ai", "verified_new_economic_event"}
                or row["category"] not in {
                    "MIXED_TEMPORAL_EVIDENCE_HOLD", "PRIOR_INVESTMENT_PLAN_MONITORING",
                    "NEW_INVESTMENT_SOURCE_CANDIDATE", "INVESTMENT_MENTION_UNRESOLVED"}
                or row["verified_new_economic_event"] is not False
                or type(row["possible_new_investment_for_ai"]) is not bool
                or (row["possible_new_investment_for_ai"] and
                    row["category"] != "NEW_INVESTMENT_SOURCE_CANDIDATE")
                or not isinstance(row["source_amount_mentions"], list)
                or len(row["source_amount_mentions"]) > 5
                or any(not isinstance(value, str) or len(value) > 64
                       or MONEY.fullmatch(value) is None
                       for value in row["source_amount_mentions"])):
            raise SourceShareError("invalid document screen finding")
        _must_sha(row["source_paragraph_sha256"], "paragraph evidence")
    changes = data.get("economic_changes", [])
    from .theme_emergence import validate_change
    if not isinstance(changes, list) or len(changes) > 30:
        raise SourceShareError("invalid economic changes")
    for change in changes:
        validate_change(change)
    routed=changes
    if data['schema']==SCHEMA:
        eligible={row['source_paragraph_sha256'] for row in data['findings'] if row['possible_new_investment_for_ai']}
        routed=[c for c in changes if c['action']!='INVESTMENT' or c['source_paragraph_sha256'] in eligible]
    if data["ai_routing_candidate"] is not (bool(routed) or any(
        row["possible_new_investment_for_ai"] for row in data["findings"]
    )):
        raise SourceShareError("document AI routing contradicts findings")
    return data
