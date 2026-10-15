"""Incremental, rate-limited RSS metadata -> conservative semiconductor analysis queue.

Reuses the observations from an already committed 1_3 poll: no second HTTP GET,
no article bodies, no AI call, no assertion that keyword overlap proves relevance.
A private versioned JSON queue supplies automatic analysis candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile
import re

from .claim_filter import classify_claim
from .event_cluster import Story, group_event_stories
from .evidence_archive import _private_root, _write_new
from .exact_dedup import register_exact
from .impact_triage import ImpactInputs, triage_importance
from .incremental_ingest import IncrementalResult
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _must_sha, _when
from .text_normalization import normalize_feed_metadata

SCHEMA = "newscatalyst.feed_triage.v2"
MARKER_SCHEMA = "newscatalyst.feed_triage_publication.v1"
# These are screening hints, NEVER evidence that a report is about a semiconductor.
SEMICONDUCTOR_TERMS = (
    "반도체", "하이닉스", "파운드리", "웨이퍼", "후공정", "디램", "낸드",
    "hbm", "dram", "nand", "semiconductor", "chipmaking",
    "wafer", "foundry", "lithography",
)
SOURCE_ROLES = {
    "GOVERNMENT_POLICY": "OFFICIAL_AGENCY",
    "COMPANY_IR": "COMPANY_IR",
    # A licensed wire distribution service is NOT an independent newsroom.
    "LICENSED_NEWS": "PRESS_RELEASE",
}


@dataclass(frozen=True)
class FeedTriage:
    provider_id: str
    observed_count: int
    newly_seen_count: int
    keyword_candidate_count: int
    payload: bytes
    payload_sha256: str
    decision_at: datetime


def _matched_terms(text: str) -> tuple[str, ...]:
    lower = text.casefold()
    # Whole-token boundaries for English/Latin: not "hbm" inside a brand.
    terms = []
    for term in SEMICONDUCTOR_TERMS:
        if term[0].isascii() and term[0].isalpha():
            if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", lower):
                terms.append(term)
        elif term in lower:
            terms.append(term)
    return tuple(terms)


def triage_committed_feed(
    registry: ProviderRegistry, poll: IncrementalResult, dedup_state: Path, *,
    decision_at: datetime | None = None,
    now: datetime | None = None,
    replayed_from_checkpoint: bool = False,
) -> FeedTriage:
    """Only reports possible relevance. Does not create economic fact/novelty."""
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "now")
    decision = _when((decision_at or present).isoformat(), "decision_at")
    if (type(replayed_from_checkpoint) is not bool
            or not isinstance(poll, IncrementalResult)
            or poll.status not in ("SUCCESS_NEW", "SUCCESS_UNCHANGED")
            or not poll.observations or decision < poll.usable_from
            or decision > present or len(poll.observations) > 100):
        raise SourceShareError("committed bounded feed poll is required")
    provider = registry.active(poll.provider_id, at=decision)
    source_role = SOURCE_ROLES.get(provider.kind)
    if source_role is None:
        raise SourceShareError("unsupported source role for trusted screening")
    fresh_ids = tuple(poll.newly_observed_event_ids)
    if (len(fresh_ids) != poll.new_count or len(set(fresh_ids)) != len(fresh_ids)
            or poll.new_count + poll.duplicate_count != len(poll.observations)):
        raise SourceShareError("poll record count and new identities disagree")
    source_ids = tuple(row.event_id for row in poll.observations)
    if len(set(source_ids)) != len(source_ids) or not set(fresh_ids).issubset(source_ids):
        raise SourceShareError("duplicate or ungrounded source identities")
    entries = []
    stories = []
    for item in poll.observations:
        if (item.provider_id != poll.provider_id
                or item.first_seen_at > poll.usable_from
                or item.reported_published_at is not None):
            raise SourceShareError("feed observation source/timing mismatch")
        _must_sha(item.event_id, "feed event id")
        normalized = normalize_feed_metadata(
            item, verified_at=poll.usable_from, now=present,
        )
        reviewed = classify_claim(
            normalized, source_role, decision_at=decision, now=present,
        )
        dedup = register_exact(dedup_state, normalized, item.document_id, now=decision)
        matches = _matched_terms(normalized.text)
        candidate = bool(matches and reviewed.eligible_for_review)
        if reviewed.eligible_for_review:
            stories.append(Story(normalized))
        importance = triage_importance(ImpactInputs(
            event_sha256=item.event_id, available_at=poll.usable_from,
            scale="UNKNOWN", affected_scope="UNKNOWN", repeatability="UNKNOWN",
            novelty="UNKNOWN", market_expectation="UNKNOWN",
        ), decision, now=present)
        entries.append({
            "provider_id": item.provider_id,
            "event_id": item.event_id,
            "document_id": item.document_id,
            "headline": normalized.text,  # authorized RSS/JSON metadata only
            "canonical_url": normalized.canonical_url,
            "title_sha256": normalized.raw_title_sha256,
            "available_at": normalized.available_at.isoformat(),
            "source_kind": source_role,
            "claim_classification": reviewed.classification,
            "verified_fact": False,
            "reported_relevance_only": "KEYWORD_CANDIDATE" if matches else "UNKNOWN",
            "matching_tokens": list(matches),
            "source_new_identity": item.event_id in fresh_ids,
            "exact_index_status": (
                "INDEX_BOOTSTRAP_PRIOR_SEEN_ID"
                if dedup.status == "NEW" and item.event_id not in fresh_ids
                else dedup.status
            ),
            "analysis_candidate": candidate,
            "importance_priority": importance.priority,
            "economic_fact_verified": False,
            "ai_called": False,
            "verified_real_benefit": False,
        })
    # Explicit origin_reference and reviewed_subject are absent, so no
    # cross-provider/same-event merge or assumed source independence.
    groups = group_event_stories(stories, decision, now=present)
    output = {
        "schema": SCHEMA, "status": "FEED_METADATA_SCREENED_NOT_FACT_VERIFIED",
        "provider_id": poll.provider_id, "source_kind": source_role,
        "decision_at": decision.isoformat(),
        "source_poll_status": poll.status,
        "replayed_from_checkpoint": replayed_from_checkpoint,
        "observed_count": len(entries),
        "new_identity_count": len(fresh_ids),
        "keyword_candidate_count": sum(x["analysis_candidate"] for x in entries),
        "conservative_cluster_count": len(groups),
        "verified_new_economic_fact_count": 0,
        "confirmed_supply_relationship_count": 0,
        "ai_call_count": 0,
        "source_body_count": 0,
        "items": entries,
    }
    payload = (json.dumps(output, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False) + "\n").encode()
    if len(payload) > 100_000:
        raise SourceShareError("triage output too large")
    return FeedTriage(
        poll.provider_id, len(entries), len(fresh_ids),
        output["keyword_candidate_count"], payload, sha256(payload).hexdigest(), decision,
    )


def publish_feed_triage(triage: FeedTriage, root: Path) -> Path:
    """Private atomic JSON delivery; earliest verified consumption is current."""
    if not isinstance(triage, FeedTriage):
        raise SourceShareError("typed feed triage required")
    current = datetime.now(timezone.utc)
    if (triage.decision_at > current
            or sha256(triage.payload).hexdigest() != triage.payload_sha256):
        raise SourceShareError("future or invalid feed triage payload")
    private = _private_root(root)
    staging = Path(tempfile.mkdtemp(prefix=".triage_staging_", dir=private))
    final = private / ("feed_triage_" + triage.payload_sha256)
    if final.exists():
        raise SourceShareError("existing triage publication must remain immutable")
    try:
        staging.chmod(0o700)
        marker = {
            "schema": MARKER_SCHEMA, "status": "COMPLETE_METADATA_ONLY",
            "payload_sha256": triage.payload_sha256,
            "payload_file": "triage.json",
            "item_count": triage.observed_count,
            "verified_fact_count": 0,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }
        body = (json.dumps(marker, sort_keys=True, separators=(",", ":"))+"\n").encode()
        _write_new(staging / "triage.json", triage.payload)
        _write_new(staging / "publication.json", body)
        fd = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(staging, final)
        fd = os.open(private, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return final
    except OSError as exc:
        raise SourceShareError("private feed triage publication failed") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)
