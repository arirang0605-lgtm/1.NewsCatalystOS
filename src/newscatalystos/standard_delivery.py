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


THEME_SCHEMA = 'newscatalyst.theme_delivery.v1'
THEME_RELATION_SCHEMA = 'newscatalyst.theme_delivery.v2'
THEME_COMPANY_SCHEMA = 'newscatalyst.theme_delivery.v3'


def build_theme_bundle(themes: list[dict], *, decision_at: datetime, now=None,
                       include_company_candidates=False) -> bytes:
    """Read-only theme metadata envelope; v1 catalyst bundles stay unchanged."""
    from .theme_emergence import SCHEMA as theme_schema, RELATION_SCHEMA, _url
    from .theme_supply_chain import validate_theme_relations
    at=_when(decision_at.isoformat(),'theme delivery decision')
    present=_when((now or datetime.now(timezone.utc)).isoformat(),'now')
    if at>present or not isinstance(themes,list) or len(themes)>1000:
        raise SourceShareError('invalid theme delivery')
    for row in themes:
        if (row.get('schema_version') not in {theme_schema,RELATION_SCHEMA} or row.get('verified_beneficiary_count')!=0
                or row.get('verified_vs_inferred')!='THEME_HYPOTHESIS'
                or not _when(row['first_detected_at'],'first detection')<=_when(row['decision_at'],'theme decision')<=at):
            raise SourceShareError('invalid or future theme candidate')
        _must_sha(row['theme_id'],'theme identity')
        row_at=_when(row['decision_at'],'theme decision')
        for ref in row['source_refs']:
            if 'policy_cause' in ref:
                from .theme_emergence import validate_policy_cause
                validate_policy_cause(ref['policy_cause'],ref['topic'])
            if 'topic_alias_evidence' in ref:
                from .theme_emergence import validate_alias_evidence
                validate_alias_evidence(ref['topic_alias_evidence'],ref['topic'])
            if ('content_scope' in ref and (ref['content_scope'] not in
                    {'RSS_TITLE_METADATA','LICENSED_ARTICLE_TEXT'} or
                    (ref['content_scope']=='RSS_TITLE_METADATA' and ref['evidence_level']!='REPORTED'))):
                raise SourceShareError('invalid theme evidence scope')
            if (not _url(ref['source_url']) or not _url(ref['origin_reference'])
                    or not _when(ref['source_available_at'],'source')<=_when(ref['recorded_at'],'recorded')<=row_at):
                raise SourceShareError('future theme source')
        for entry in row['history']:
            if _when(entry['decision_at'],'history')>row_at:
                raise SourceShareError('future theme history')
        for link in row.get('event_followups',[]):
            if (link.get('status')!='SOURCE_REPORTED_REALIZATION'
                    or link.get('is_realization_confirmed') is not False
                    or not _when(link['decision_at'],'followup decision')<=row_at):
                raise SourceShareError('invalid service realization claim')
            plans=[ref for ref in row['source_refs'] if ref['event_id']==link.get('planned_event_id')
                   and ref['event_id'] in row['event_ids'] and ref['phase']=='PLANNED']
            starts=[ref for ref in row['source_refs'] if ref['event_id']==link.get('realization_event_id')
                    and ref['event_id'] in row['event_ids'] and ref['phase']=='SOURCE_REPORTED']
            from .theme_emergence import _service_pairs
            def observation(ref):
                return {'event_id':ref['event_id'],'polarity':ref['polarity'],
                    'supersedes_event_id':ref['supersedes_event_id'],
                    'source_available_at':ref['source_available_at'],
                    'change':{**ref,'source_paragraph_sha256':ref['evidence_sha256']}}
            if not any(_service_pairs([observation(plan),observation(start)])
                       and link.get('service_name')==start.get('service_name')
                       and link.get('entity_ids')==start['entity_ids']
                       and link.get('evidence_sha256')==[plan['evidence_sha256'],start['evidence_sha256']]
                       and max(_when(plan['recorded_at'],'plan recorded'),_when(start['recorded_at'],'start recorded'))
                           <=_when(link['decision_at'],'followup decision')
                       for plan in plans for start in starts):
                raise SourceShareError('service followup must retain both source claims')
        validate_theme_relations(row,at)
        allowed={'THEMATIC_ONLY','SOURCE_BACKED_CONTEXT'} if row['schema_version']==RELATION_SCHEMA else {'THEMATIC_ONLY'}
        if any(link.get('relation_kind') not in allowed or link.get('revenue_contribution') is not None
               for link in row['company_links']):
            raise SourceShareError('unsubstantiated direct theme benefit')
    schema=THEME_RELATION_SCHEMA if any(x['schema_version']==RELATION_SCHEMA for x in themes) else THEME_SCHEMA
    envelope={'schema':schema,'decision_at':at.isoformat(),
        'ThemeCandidates':themes,'original_content_included':False,'verified_beneficiary_count':0}
    if include_company_candidates:
        from .theme_company_candidates import company_candidates
        envelope.update(schema=THEME_COMPANY_SCHEMA,
                        CompanyCandidates=[c for theme in themes for c in company_candidates(theme)])
    payload=_json_bytes(envelope)
    if len(payload)>2_000_000:raise SourceShareError('oversized theme delivery')
    return payload


def read_theme_bundle(data: bytes, expected_sha256: str, *, decision_at: datetime, now=None) -> dict:
    if not isinstance(data,bytes) or len(data)>2_000_000 or sha256(data).hexdigest()!=_must_sha(expected_sha256,'theme pin'):
        raise SourceShareError('theme delivery SHA mismatch')
    value=json.loads(data)
    with_companies=value.get('schema')==THEME_COMPANY_SCHEMA
    expected={'schema','decision_at','ThemeCandidates','original_content_included','verified_beneficiary_count'}
    if with_companies:expected.add('CompanyCandidates')
    if (set(value)!=expected
            or value['schema'] not in {THEME_SCHEMA,THEME_RELATION_SCHEMA,THEME_COMPANY_SCHEMA} or value['original_content_included'] is not False
            or value['verified_beneficiary_count']!=0):
        raise SourceShareError('invalid theme delivery schema')
    created=_when(value['decision_at'],'bundle decision')
    if created>_when(decision_at.isoformat(),'consumer decision'):
        raise SourceShareError('theme bundle not yet available')
    rebuilt=build_theme_bundle(value['ThemeCandidates'],decision_at=created,now=now,
                               include_company_candidates=with_companies)
    if rebuilt!=data:raise SourceShareError('noncanonical theme delivery')
    if decision_at>(now or datetime.now(timezone.utc)):
        raise SourceShareError('future consumer decision')
    return value
