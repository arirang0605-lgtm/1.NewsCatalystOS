"""4_5 fail-closed evidence lineage across vendor output, numeric quotes, impacts.

No unsupported number or unaudited source claim is allowed to become a
confirmed economic fact. This check never repairs malformed inputs with
model hallucinations or rewrites original publisher evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .ai_provider import AIResult
from .economic_path import AnalysisEvent
from .fact_extraction import ExtractedFacts
from .source_share import SourceShareError, _when

SCHEMA="newscatalyst.analysis_validation.v1"


@dataclass(frozen=True)
class AnalysisValidation:
    schema_version: str
    event_sha256: str
    status: str
    supported_numbers: int
    unsupported_number_fields: tuple[str, ...]
    linked_impact_count: int
    reviewed_at: datetime
    certified_fact_count: int = 0
    analysis_replaced_source: bool = False


def validate_analysis_lineage(
    ai: AIResult, extracted: ExtractedFacts, impacts: AnalysisEvent,
    *, reviewed_at: datetime, now: datetime | None = None,
) -> AnalysisValidation:
    at=_when(reviewed_at.isoformat(),"reviewed_at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not at<=current:
        raise SourceShareError("future analysis verification")
    if (not isinstance(ai,AIResult) or not isinstance(extracted,ExtractedFacts)
            or not isinstance(impacts,AnalysisEvent)):
        raise SourceShareError("typed evidence, model output and impact required")
    event=extracted.source_event_sha256
    if not (ai.event_sha256==impacts.event_sha256==event):
        raise SourceShareError("analysis event/source ID mismatch")
    if (ai.available_at>at or extracted.available_at>at
            or impacts.analyzed_at>at or impacts.source_available_at>at):
        raise SourceShareError("future evidence may not validate current analysis")
    proof_ids={x.evidence_quote_sha256 for x in extracted.supported}
    orphaned=[
        v for v in impacts.impact_hypotheses
        if v.source_claim_sha256 not in proof_ids
    ]
    unsupported=tuple(sorted(set(extracted.rejected_fields)))
    if orphaned or unsupported or not proof_ids:
        return AnalysisValidation(
            SCHEMA,event,"UNKNOWN_HOLD_SOURCE_EVIDENCE_MISSING",
            len(extracted.supported),unsupported,len(impacts.impact_hypotheses),
            at,
        )
    # All numbers and impact links are traceable to exact quotes but may still
    # lack publisher/independent verification. Never mark as verified fact.
    return AnalysisValidation(
        SCHEMA,event,"EVIDENCE_LINKED_CANDIDATE_NOT_VERIFIED_FACT",
        len(extracted.supported),(),len(impacts.impact_hypotheses),at,
    )
