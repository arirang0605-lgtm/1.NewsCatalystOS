"""2_5 source-root attribution: citations are not independent fact proofs.

Ten news pages quoting one original press release count as ONE *claimed*
root, not ten independent confirmations. Unknown roots count as zero.
Official contradiction/correction suspends promotion pending review.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from .source_share import SourceShareError, _when, _must_sha

SCHEMA = "newscatalyst.claim_origins.v1"
ROLES = frozenset({"OFFICIAL_PRIMARY", "CORPORATE_RELEASE", "DISTRIBUTOR",
                   "INDEPENDENT_NEWS", "SOCIAL", "UNKNOWN"})
STANCES = frozenset({"SUPPORT", "REFUTE", "CORRECT", "UNCERTAIN"})
ROOT_PATTERN = re.compile(r"[A-Za-z0-9_.:/-]{3,200}\Z")


@dataclass(frozen=True)
class Citation:
    source_id: str
    event_id: str
    observed_at: datetime
    publisher_role: str
    stance: str
    attributed_origin_id: str | None = None
    origin_reference_sha256: str | None = None


@dataclass(frozen=True)
class OriginAssessment:
    event_group_id: str
    citation_count: int
    claimed_root_count: int
    unknown_origin_count: int
    independently_verified_fact_count: int
    claimed_roots: tuple[str, ...]
    statuses: tuple[str, ...]
    hold_reason: str | None
    decision_at: datetime
    schema_version: str = SCHEMA
    fact_verified: bool = False

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> "OriginAssessment":
        at = _when(decision_at.isoformat(), "decision_at")
        current = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.decision_at <= at <= current:
            raise SourceShareError("origin assessment not available at decision")
        return self


def assess_origins(
    group_id: str, citations: tuple[Citation, ...] | list[Citation],
    decision_at: datetime, *, now: datetime | None = None,
) -> OriginAssessment:
    """Only evidence observed at decision may influence provenance assessment."""
    group_id = _must_sha(group_id, "event group ID")
    decision = _when(decision_at.isoformat(), "decision_at")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if decision > present or not 0 < len(citations) <= 2000:
        raise SourceShareError("future or empty/unbounded citation set")
    roots = set()
    status = set()
    unknown = 0
    distinct = {}
    for item in citations:
        if not isinstance(item, Citation) or not isinstance(item.source_id,str) or not item.source_id:
            raise SourceShareError("invalid citation source")
        if item.publisher_role not in ROLES or item.stance not in STANCES:
            raise SourceShareError("unknown citation role/stance")
        _must_sha(item.event_id, "citation event ID")
        seen_at = _when(item.observed_at.isoformat(), "citation observed")
        if seen_at > decision:
            raise SourceShareError("future citation cannot prove historical claim")
        key=(item.source_id,item.event_id)
        if key in distinct:
            if distinct[key] != item:
                raise SourceShareError("conflicting duplicate citation record")
            continue
        distinct[key]=item
        status.add(item.stance)
        if item.attributed_origin_id is None:
            if item.origin_reference_sha256 is not None:
                raise SourceShareError("orphan origin reference SHA")
            unknown += 1
        else:
            origin=item.attributed_origin_id
            if not ROOT_PATTERN.fullmatch(origin) or ".." in origin:
                raise SourceShareError("invalid cited origin reference")
            if item.origin_reference_sha256 is not None:
                _must_sha(item.origin_reference_sha256, "origin evidence SHA")
            # Repeating a root URL through distributors never adds fact proof.
            roots.add(origin)
    hold = None
    if "CORRECT" in status:
        hold = "CORRECTION_PENDING_PRIMARY_REVIEW"
    elif "SUPPORT" in status and "REFUTE" in status:
        hold = "CONTRADICTORY_SOURCES_HOLD"
    elif unknown:
        hold = "UNTRACED_ORIGIN_NEEDS_REVIEW"
    return OriginAssessment(
        event_group_id=group_id, citation_count=len(distinct),
        claimed_root_count=len(roots), unknown_origin_count=unknown,
        independently_verified_fact_count=0,
        claimed_roots=tuple(sorted(roots)), statuses=tuple(sorted(status)),
        hold_reason=hold, decision_at=decision,
    )
