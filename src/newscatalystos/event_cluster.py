"""2_3 conservative same-event grouping; preserve every material revision.

Only explicitly reviewed claim origin + subject permit a cross-source merge.
Headline similarity never authenticates issuer, independence or publication.
All variants remain inspectable at their own PIT available times.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re
import unicodedata

from .source_share import SourceShareError, _must_sha, _when
from .text_normalization import NormalizedText

SCHEMA = "newscatalyst.event_cluster.v1"
TOKEN = re.compile(r"[\w가-힣]+", flags=re.UNICODE)
NUMERIC = re.compile(
    r"(?:[0-9]+(?:[.,][0-9]+)*(?:\s*(?:억원|조원|만원|원|%|개|대|억|조|년|월|일|"
    r"USD|KRW|달러|배|MW|GW|GWh))?)",
    flags=re.I,
)
CORRECTION = re.compile(r"(정정|수정|취소|철회|correction|revised|withdrawn)", re.I)
STOP = frozenset({"주식", "뉴스", "보도", "발표", "the", "and", "for", "new", "official"})

@dataclass(frozen=True)
class Story:
    observation: NormalizedText
    origin_reference: str | None = None
    reviewed_subject: str | None = None

@dataclass(frozen=True)
class StoryVariant:
    evidence_id: str
    source_id: str
    canonical_url: str
    observed_at: datetime
    tokens: tuple[str, ...]
    numeric_facts: tuple[str, ...]
    correction_flag: bool
    new_numeric_facts: tuple[str, ...]

@dataclass(frozen=True)
class EventCluster:
    cluster_id: str
    origin_reference: str | None
    reviewed_subject: str | None
    variants: tuple[StoryVariant, ...]
    first_usable_at: datetime
    grouped_at: datetime
    status: str = "GROUPED_CLAIMS_NOT_INDEPENDENTLY_VERIFIED"
    schema_version: str = SCHEMA

    def as_of(self, at: datetime, *, now: datetime | None = None) -> "EventCluster":
        decision = _when(at.isoformat(), "decision_at")
        present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
        if not self.grouped_at <= decision <= present:
            raise SourceShareError("event cluster did not exist at decision")
        return self


def _terms(title: str) -> frozenset[str]:
    value = unicodedata.normalize("NFKC", title).casefold()
    cleaned = NUMERIC.sub(" ", value)
    return frozenset(t for t in TOKEN.findall(cleaned) if len(t) >= 2 and t not in STOP)

def _numbers(text: str) -> tuple[str, ...]:
    return tuple(sorted(set("".join(raw.split()) for raw in NUMERIC.findall(text))))

def _overlap(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)

def group_event_stories(
    stories: tuple[Story, ...] | list[Story], decision_at: datetime,
    *, now: datetime | None = None, min_similarity: float = 0.52,
) -> tuple[EventCluster, ...]:
    """Conservative, deterministic cluster builder with lossless variants.

    A subject label without explicit origin-reference is NOT enough to declare
    two independent sources describe the same verifiable economic event.
    """
    decision = _when(decision_at.isoformat(), "decision_at")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    if decision > present or not 0.25 <= min_similarity <= 1.0:
        raise SourceShareError("invalid cluster decision/similarity")
    if len(stories) > 5000:
        raise SourceShareError("too many candidate stories")
    candidates = []
    seen = set()
    for item in stories:
        if not isinstance(item, Story) or not isinstance(item.observation, NormalizedText):
            raise SourceShareError("normalized observation required")
        row = item.observation
        available = _when(row.available_at.isoformat(), "available_at")
        if available > decision:
            raise SourceShareError("future source cannot join cluster")
        _must_sha(row.event_id, "source event id")
        if item.origin_reference is not None and (
            not isinstance(item.origin_reference, str) or
            not re.fullmatch(r"[A-Za-z0-9_.:/-]{3,200}", item.origin_reference)
            or ".." in item.origin_reference
        ):
            raise SourceShareError("invalid source origin reference")
        if item.reviewed_subject is not None and (
            not isinstance(item.reviewed_subject, str) or
            not re.fullmatch(r"[A-Za-z0-9_.:/가-힣-]{2,100}", item.reviewed_subject)
        ):
            raise SourceShareError("unreviewed or invalid event subject")
        unique = (row.source_id, row.event_id, row.raw_title_sha256)
        if unique in seen:
            continue
        seen.add(unique)
        candidates.append((item, available))
    candidates.sort(key=lambda x: (x[1], x[0].observation.source_id,
                                   x[0].observation.event_id,
                                   x[0].observation.raw_title_sha256))
    buckets: list[list[tuple[Story, datetime]]] = []
    for item, available in candidates:
        terms = _terms(item.observation.text)
        destination = None
        if item.origin_reference and item.reviewed_subject:
            for bucket in buckets:
                first = bucket[0][0]
                if (first.origin_reference == item.origin_reference and
                    first.reviewed_subject == item.reviewed_subject and
                    any(_overlap(_terms(other.observation.text), terms) >= min_similarity
                        for other, _ in bucket)):
                    destination = bucket
                    break
        if destination is None:
            destination = []
            buckets.append(destination)
        destination.append((item, available))
    groups = []
    for bucket in buckets:
        first = bucket[0][0]
        seed = first.observation
        seedid = sha256((seed.source_id + "\0" + seed.event_id +
                         "\0" + seed.raw_title_sha256).encode()).hexdigest()
        previous_numbers: set[str] = set()
        variants = []
        for item, available in bucket:
            row = item.observation
            facts = _numbers(row.text)
            new_facts = tuple(sorted(set(facts) - previous_numbers))
            previous_numbers.update(facts)
            versions = StoryVariant(
                evidence_id=row.event_id, source_id=row.source_id,
                canonical_url=row.canonical_url,
                observed_at=available, tokens=tuple(sorted(_terms(row.text))),
                numeric_facts=facts, correction_flag=bool(CORRECTION.search(row.text)),
                new_numeric_facts=new_facts,
            )
            variants.append(versions)
        groups.append(EventCluster(
            cluster_id=seedid,
            origin_reference=first.origin_reference,
            reviewed_subject=first.reviewed_subject,
            variants=tuple(variants), first_usable_at=bucket[0][1],
            grouped_at=decision,
        ))
    return tuple(groups)
