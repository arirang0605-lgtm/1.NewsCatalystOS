"""6_4 versioned CatalystEvent + BeneficiaryGraph + EventHistory delivery.

Consumes ONLY NewsCatalystOS validated types; serializes aggregate metadata
for read-only downstream consumers (including EraLeader) without mutating their
repositories or databases. No article body, API secrets or auto publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json

from .economic_path import AnalysisEvent
from .beneficiary_graph_contract import BeneficiaryGraph
from .event_lifecycle import LifecycleState
from .catalyst_audit import AuditVersion
from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.delivery_bundle.v1"
KINDS = ("CatalystEvent", "BeneficiaryGraph", "EventHistory")


@dataclass(frozen=True)
class StandardBundle:
    event_sha256: str
    decision_at: datetime
    payload: bytes
    payload_sha256: str
    schema_version: str = SCHEMA
    fact_certified: bool = False


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,
                       separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")


def build_standard_bundle(
    analysis: AnalysisEvent,
    graph: BeneficiaryGraph,
    history: LifecycleState,
    *,
    decision_at: datetime,
    audited: tuple[AuditVersion, ...] | list[AuditVersion] = (),
    now: datetime | None = None,
) -> StandardBundle:
    at=_when(decision_at.isoformat(),"decision at")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not at<=current:
        raise SourceShareError("future delivery decision")
    if (not isinstance(analysis,AnalysisEvent) or
            not isinstance(graph,BeneficiaryGraph) or
            not isinstance(history,LifecycleState)):
        raise SourceShareError("validated analysis/graph/lifecycle required")
    event=_must_sha(analysis.event_sha256,"event id")
    if not (graph.source_event_sha256==history.event_sha256==event):
        raise SourceShareError("delivery event linkage differs")
    if (analysis.analyzed_at>at or graph.decision_at>at or
            history.decision_at>at):
        raise SourceShareError("future delivery component")
    if graph.payload_sha256!=sha256(graph.JSON_bytes).hexdigest():
        raise SourceShareError("beneficiary graph payload SHA mismatch")
    try:
        graph_dict=json.loads(graph.JSON_bytes)
    except (ValueError,UnicodeDecodeError) as exc:
        raise SourceShareError("invalid beneficiary graph JSON") from exc
    if (graph_dict.get("schema")!="newscatalyst.beneficiary_graph.v1"
            or graph_dict.get("event_sha256")!=event
            or graph_dict.get("industry_id")!="SEMICONDUCTOR"
            or graph_dict.get("certified_beneficiary_count")!=0):
        raise SourceShareError("unsupported beneficiary graph contract")
    if history.current_state not in (None,"DETECTED","CONFIRMED",
                                     "STRENGTHENED","WEAKENED","INVALIDATED"):
        raise SourceShareError("invalid catalyst lifecycle state")
    for item in history.versions:
        if item.event_sha256!=event or item.recorded_at>at or item.available_at>at:
            raise SourceShareError("future/mismatched lifecycle entry")
    for item in audited:
        if not isinstance(item,AuditVersion) or item.event_sha256!=event or (
            item.recorded_at>at or item.source_available_at>at
        ):
            raise SourceShareError("future or cross-event evidence in delivery")
    catalyst = {
        "schema":"newscatalyst.catalyst_event.v1",
        "event_sha256":event,"industry_id":"SEMICONDUCTOR",
        "first_analysis_at":analysis.analyzed_at.isoformat(),
        "source_available_at":analysis.source_available_at.isoformat(),
        "current_state":history.current_state,
        "impact_paths":[{"path":x.path,"direction":x.direction,
                         "product_stage":x.affected_product,
                         "source_evidence_sha256":x.source_claim_sha256,
                         "hypothesis_only":True}
                        for x in analysis.impact_hypotheses],
        "economic_effect_verified":False,
        "market_action":None,
    }
    lifecycle = {
        "schema":"newscatalyst.event_history.v1",
        "event_sha256":event,
        "versions":[{"version_sha256":x.version_sha256,
                     "parent_sha256":x.previous_version_sha256,
                     "state":x.state,"evidence_sha256":x.evidence_sha256,
                     "source_available_at":x.source_available_at.isoformat(),
                     "recorded_at":x.recorded_at.isoformat(),
                     "externally_verified_fact":False}
                    for x in history.versions],
        "audit_shas":[x.audit_sha256 for x in audited],
    }
    package={"schema":SCHEMA,"event_sha256":event,"decision_at":at.isoformat(),
             "CatalystEvent":catalyst,"BeneficiaryGraph":graph_dict,
             "EventHistory":lifecycle,"verified_beneficiary_count":0,
             "original_content_included":False}
    data=_json_bytes(package)
    if len(data)>512_000:
        raise SourceShareError("delivery payload exceeds bounded contract")
    return StandardBundle(event,at,data,sha256(data).hexdigest())


def read_standard_bundle(data: bytes, expected_sha256: str,
                         *, decision_at: datetime, now: datetime | None = None) -> dict:
    """Independent caller-provided expected SHA; re-hashing same file is not a pin."""
    pinned=_must_sha(expected_sha256,"expected bundle SHA")
    current=_when((now or datetime.now(timezone.utc)).isoformat(),"now")
    at=_when(decision_at.isoformat(),"decision at")
    if not isinstance(data,bytes) or not 0<len(data)<=512_000:
        raise SourceShareError("missing or oversized versioned bundle")
    if sha256(data).hexdigest()!=pinned:
        raise SourceShareError("bundle SHA differs from consumer pin")
    try:
        value=json.loads(data)
    except (ValueError,UnicodeDecodeError) as exc:
        raise SourceShareError("unreadable delivery JSON") from exc
    if (not isinstance(value,dict) or
            set(value)!={"schema","event_sha256","decision_at",
                        "CatalystEvent","BeneficiaryGraph","EventHistory",
                        "verified_beneficiary_count","original_content_included"}
            or value["schema"]!=SCHEMA or
            value["original_content_included"] is not False or
            value["verified_beneficiary_count"]!=0 or
            value["CatalystEvent"]["event_sha256"]!=value["event_sha256"] or
            value["BeneficiaryGraph"]["event_sha256"]!=value["event_sha256"] or
            value["EventHistory"]["event_sha256"]!=value["event_sha256"]):
        raise SourceShareError("delivery schema or event identity mismatch")
    created=_when(value["decision_at"],"bundle decision")
    if not created<=at<=current:
        raise SourceShareError("bundle not PIT available to consumer")
    if _json_bytes(value)!=data:
        raise SourceShareError("noncanonical delivery payload")
    return value


def to_parquet_bytes(bundle: StandardBundle) -> bytes:
    """Optional Arrow/Parquet one-file envelope with three versioned records.

    Parquet stores each independently named nested document as canonical JSON.
    No external file writes or background collection.
    """
    if not isinstance(bundle,StandardBundle):
        raise SourceShareError("versioned bundle required")
    read_standard_bundle(bundle.payload,bundle.payload_sha256,
                         decision_at=bundle.decision_at,now=bundle.decision_at)
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SourceShareError("Parquet export unavailable without pyarrow") from exc
    data=json.loads(bundle.payload)
    table=pa.table({
        "schema":[SCHEMA]*3,
        "event_sha256":[bundle.event_sha256]*3,
        "decision_at":[bundle.decision_at.isoformat()]*3,
        "kind":list(KINDS),
        "document_json":[_json_bytes(data[name]).decode() for name in KINDS],
    })
    buf=pa.BufferOutputStream()
    pq.write_table(table,buf,compression="zstd")
    return buf.getvalue().to_pybytes()
