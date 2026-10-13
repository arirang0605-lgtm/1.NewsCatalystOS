"""4_2 evidence-bound extracted facts; model output cannot invent source values.

Only user-allowed short headline/metadata is accepted. Every extracted value
and supporting quote must occur verbatim in that supplied source. No inferred
currency conversion, corporate IDs, quantitative impact or date interpolation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import re
import unicodedata

from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.fact_extraction.v1"
FIELDS = frozenset({
    "CONTRACT_AMOUNT", "ANNOUNCEMENT_DATE", "COMPANY_NAME",
    "PRODUCT", "PROCESS", "POLICY_EFFECTIVE_DATE",
})
MONEY = re.compile(
    r"(?:\$|₩)?\s*\d+(?:[,.]\d+)*\s*(?:억원|조원|만원|원|KRW|USD|달러|million|billion)",
    re.I,
)
DATE = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}")
RAW_LIMIT = 2048


@dataclass(frozen=True)
class FactProposal:
    field: str
    value: str
    source_quote: str


@dataclass(frozen=True)
class ExtractedFact:
    field: str
    value: str
    evidence_quote_sha256: str
    source_event_sha256: str
    available_at: datetime
    status: str = "EXACT_SOURCE_MATCH_ISSUER_NOT_ATTESTED"


@dataclass(frozen=True)
class ExtractedFacts:
    source_event_sha256: str
    supported: tuple[ExtractedFact, ...]
    rejected_fields: tuple[str, ...]
    available_at: datetime
    schema_version: str = SCHEMA
    independently_certified_accuracy: bool = False

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> "ExtractedFacts":
        decision = _when(decision_at.isoformat(), "decision_at")
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.available_at <= decision <= present:
            raise SourceShareError("extracted claim unavailable at decision")
        return self


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def _supported(field: str, value: str, quote: str, source: str) -> bool:
    if not value or not quote or quote not in source or value not in quote:
        return False
    if field == "CONTRACT_AMOUNT":
        return any(_normalize(m.group()).replace(" ", "") == value.replace(" ", "")
                   for m in MONEY.finditer(quote))
    if field in ("ANNOUNCEMENT_DATE", "POLICY_EFFECTIVE_DATE"):
        if not DATE.fullmatch(value):
            return False
        try:
            y, mo, day = (int(x) for x in re.split(r"[-./]", value))
            date(y, mo, day)
        except ValueError:
            return False
    return True


def verify_extracted_facts(
    source_event_sha256: str, authorized_excerpt: str,
    proposals: tuple[FactProposal, ...] | list[FactProposal],
    *,
    observed_at: datetime,
    checked_at: datetime | None = None,
    now: datetime | None = None,
) -> ExtractedFacts:
    """Separates exact source-backed strings from unsupported AI suggestions."""
    event = _must_sha(source_event_sha256, "source event SHA")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    source_seen = _when(observed_at.isoformat(), "source observed_at")
    checked = _when((checked_at or present).isoformat(), "checked_at")
    if not source_seen <= checked <= present:
        raise SourceShareError("fact extraction cannot precede observed source")
    if (not isinstance(authorized_excerpt, str) or
            not 0 < len(authorized_excerpt) <= RAW_LIMIT or
            "\x00" in authorized_excerpt):
        raise SourceShareError("authorized short metadata required")
    if not isinstance(proposals, (list,tuple)) or len(proposals) > 30:
        raise SourceShareError("invalid bounded fact proposals")
    original = _normalize(authorized_excerpt)
    supported = []
    rejected = []
    keys = set()
    for proposal in proposals:
        if (not isinstance(proposal, FactProposal) or
                proposal.field not in FIELDS or
                not isinstance(proposal.value, str) or
                not isinstance(proposal.source_quote, str) or
                len(proposal.value) > 120 or len(proposal.source_quote) > 400):
            raise SourceShareError("unknown or malformed extracted field")
        value = _normalize(proposal.value)
        quote = _normalize(proposal.source_quote)
        if (proposal.field,value) in keys:
            continue
        keys.add((proposal.field,value))
        if not _supported(proposal.field,value,quote,original):
            rejected.append(proposal.field)
            continue
        supported.append(ExtractedFact(
            proposal.field,value,sha256(quote.encode()).hexdigest(),event,checked,
        ))
    return ExtractedFacts(
        event,tuple(supported),tuple(sorted(set(rejected))),checked
    )
