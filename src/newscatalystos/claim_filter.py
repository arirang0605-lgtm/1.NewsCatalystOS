"""2_4 conservative ads/rumors/source-type filter; never declares facts true.

No online reputation calls or generated facts. Provider roles are configured
separately from a headline; promotional and anonymous claims remain unverified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from .source_share import SourceShareError, _when
from .text_normalization import NormalizedText

KINDS = frozenset({"OFFICIAL_AGENCY", "COMPANY_IR", "PRESS_RELEASE",
                   "INDEPENDENT_NEWS", "SOCIAL", "ANONYMOUS"})
ADS = re.compile(r"(?i)(?:^|\W)(광고|유료광고|협찬|sponsored|advertisement|paid\s+promotion)(?:$|\W)")
RUMORS = re.compile(r"(?i)(?:소문|루머|카더라|익명\s*제보|확인되지\s*않|rumou?r|unconfirmed|anonymous\s+tip)")
SPAM = re.compile(r"(?i)(?:무료\s*수익|수익률\s*보장|100%\s*수익|무료\s*리딩|guaranteed\s+profit)")
SCHEMA = "newscatalyst.claim_filter.v1"


@dataclass(frozen=True)
class FilterDecision:
    event_id: str
    provider_id: str
    source_kind: str
    classification: str
    is_verified_fact: bool
    eligible_for_review: bool
    available_at: datetime
    reason_codes: tuple[str, ...]
    schema_version: str = SCHEMA

    def as_of(self, at: datetime, *, now: datetime | None = None) -> "FilterDecision":
        decision = _when(at.isoformat(), "decision_at")
        current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.available_at <= decision <= current:
            raise SourceShareError("claim filter result unavailable at decision")
        return self


def classify_claim(
    item: NormalizedText, source_kind: str,
    *, decision_at: datetime, now: datetime | None = None,
    is_advertisement: bool = False,
) -> FilterDecision:
    if not isinstance(item, NormalizedText) or source_kind not in KINDS:
        raise SourceShareError("validated normalized text/source role required")
    decision = _when(decision_at.isoformat(), "decision_at")
    current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    ready = _when(item.available_at.isoformat(), "available_at")
    if not ready <= decision <= current or type(is_advertisement) is not bool:
        raise SourceShareError("future or invalid claim classification")
    text = item.text
    reasons = []
    if is_advertisement or ADS.search(text):
        reasons.append("AD_OR_SPONSORED")
    if SPAM.search(text):
        reasons.append("SPAM_CLAIM")
    if RUMORS.search(text):
        reasons.append("RUMOR_CLAIM")
    if source_kind in ("SOCIAL", "ANONYMOUS"):
        reasons.append("UNVERIFIED_SOURCE")
    if reasons:
        return FilterDecision(
            item.event_id, item.source_id, source_kind,
            "BLOCK_AD_SPAM" if "AD_OR_SPONSORED" in reasons or "SPAM_CLAIM" in reasons
            else "UNVERIFIED_RUMOR",
            False, False, ready, tuple(sorted(set(reasons))),
        )
    if source_kind == "PRESS_RELEASE":
        label = "DISTRIBUTED_CLAIM_NOT_INDEPENDENT"
    elif source_kind in ("OFFICIAL_AGENCY", "COMPANY_IR"):
        label = "OFFICIAL_CHANNEL_OBSERVED_NOT_FACT_ATTESTED"
    else:
        label = "NEWS_REPORT_OBSERVED_NOT_FACT_ATTESTED"
    return FilterDecision(item.event_id, item.source_id, source_kind, label,
                          False, True, ready, ("FACT_NOT_EXTERNALLY_VERIFIED",))
