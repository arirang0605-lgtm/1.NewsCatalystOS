"""NewsCatalystOS: fail-closed, read-only official evidence contracts."""
from .source_share import (ReadBatch, RawEvent, SourceManifest, SourceShareError,
                           read_verified_bundle)
from .era_capture_share import (OfficialCapture, OfficialRecord,
                                read_official_capture)
from .verified_reference import (VerifiedOfficialSources,
                                 verify_official_research_reference)
from .release_claim import ReleaseClaim, inspect_release_claim
from .signed_publication import SignedPublication, authenticate_publication
from .official_promotion import (AnchoredOfficialPublication,
                                  authenticate_anchored_official_record,
                                  authenticate_from_era_readonly)
from .observed_batch import (ObservedOfficialBatch, ObservedOfficialSource,
                             build_observed_official_batch)
from .published_observations import (PublishedResearchObservations,
                                     read_published_observations)
from .operational_observations import (
    OperationalObservation, OperationalObservationSet,
    load_operational_observations, project_operational_observations,
)
from .provider_registry import Provider, ProviderRegistry, parse_provider_registry
from .new_source_adapter import FeedObservation, parse_authorized_feed
from .feed_transport import FeedTransportError, fetch_authorized_once
from .incremental_ingest import (
    IncrementalResult, incremental_poll,
    state_snapshot,
)
from .event_identity import (
    CompanyBinding, RevisionEvidence, NormalizedEvent,
    normalize_observed_event,
)
from .evidence_archive import ArchivedEvidence, archive_evidence, read_archived_evidence
from .quality_watch import SourceQuality, check_sources, unresolved_count
from .text_normalization import NormalizedText, normalize_feed_metadata, normalize_text, canonicalize_url
from .exact_dedup import DedupDecision, register_exact
from .event_cluster import EventCluster, Story, group_event_stories
from .claim_filter import FilterDecision, classify_claim
from .origin_provenance import Citation, OriginAssessment, assess_origins
from .filter_evaluation import LabeledDecision, FilterEvaluation, evaluate_labeled_decisions
from .prior_fact_state import FactInput, FactVersion, PriorState, record_prior_fact, prior_state_as_of
from .novelty_detection import EconomicChange, detect_new_economic_claim
from .barrier_changes import BarrierAssessment, detect_barrier_relief
from .change_followup import FollowupChange, assess_followup
from .impact_triage import ImpactInputs, PreliminaryImportance, triage_importance
from .detection_history import (
    DetectionInput, DetectionRecord, DetectionRecall,
    record_detection, detection_history_as_of, evaluate_important_detection_recall,
)
from .ai_provider import AIModel, AIRequest, AIResult, run_ai_analysis
from .fact_extraction import FactProposal, ExtractedFacts, verify_extracted_facts
from .claim_boundaries import ClaimBoundary, classify_evidence_claim
from .economic_path import ImpactHypothesis, AnalysisEvent, build_impact_analysis
from .analysis_validation import AnalysisValidation, validate_analysis_lineage
from .ai_cost_ledger import AIReservation, reserve_ai_call, settle_ai_call
from .semiconductor_profile import SemiconductorProfile, build_semiconductor_profile
from .supply_chain_graph import SupplyChainEdge, observed_supply_edge
from .semiconductor_impact import SemiconductorTransmission, propagate_semiconductor_claim
from .beneficiary_classification import BeneficiaryCandidate, classify_semiconductor_beneficiary
from .beneficiary_graph_contract import BeneficiaryGraph, build_beneficiary_graph
from .event_lifecycle import LifecycleVersion, LifecycleState, append_lifecycle, lifecycle_as_of
from .analysis_cache import CachedAnalysis, cache_analysis_once, get_cached_analysis
from .catalyst_audit import AuditInput, AuditVersion, append_catalyst_audit, audit_as_of
from .standard_delivery import StandardBundle, build_standard_bundle, read_standard_bundle, to_parquet_bytes
from .backup_recovery import BackupReceipt, backup_sqlite, restore_to_new_dir
from .release_readiness import ReadinessInputs, ReadinessReport, evaluate_v1_readiness

__all__ = [
    "ReadBatch", "RawEvent", "SourceManifest", "SourceShareError",
    "read_verified_bundle", "OfficialCapture", "OfficialRecord",
    "read_official_capture", "VerifiedOfficialSources",
    "verify_official_research_reference", "ReleaseClaim",
    "inspect_release_claim", "SignedPublication", "authenticate_publication",
    "AnchoredOfficialPublication", "authenticate_anchored_official_record",
    "authenticate_from_era_readonly",
    "ObservedOfficialBatch", "ObservedOfficialSource",
    "build_observed_official_batch",
    "PublishedResearchObservations", "read_published_observations",
    "OperationalObservation", "OperationalObservationSet",
    "load_operational_observations", "project_operational_observations",
    "Provider", "ProviderRegistry", "parse_provider_registry",
    "FeedObservation", "parse_authorized_feed", "fetch_authorized_once",
    "FeedTransportError", "IncrementalResult", "incremental_poll",
    "state_snapshot",
    "CompanyBinding", "RevisionEvidence", "NormalizedEvent",
    "normalize_observed_event", "ArchivedEvidence", "archive_evidence",
    "read_archived_evidence", "SourceQuality", "check_sources",
    "unresolved_count", "NormalizedText", "normalize_feed_metadata",
    "normalize_text", "canonicalize_url", "DedupDecision",
    "register_exact",
    "EventCluster", "Story", "group_event_stories",
    "FilterDecision", "classify_claim",
    "Citation", "OriginAssessment", "assess_origins",
    "LabeledDecision", "FilterEvaluation", "evaluate_labeled_decisions",
    "FactInput", "FactVersion", "PriorState", "record_prior_fact",
    "prior_state_as_of", "EconomicChange", "detect_new_economic_claim",
    "BarrierAssessment", "detect_barrier_relief", "FollowupChange", "assess_followup",
    "ImpactInputs", "PreliminaryImportance", "triage_importance",
    "DetectionInput", "DetectionRecord", "DetectionRecall", "record_detection",
    "detection_history_as_of", "evaluate_important_detection_recall",
    "AIModel", "AIRequest", "AIResult", "run_ai_analysis",
    "FactProposal", "ExtractedFacts", "verify_extracted_facts",
    "ClaimBoundary", "classify_evidence_claim",
    "ImpactHypothesis", "AnalysisEvent", "build_impact_analysis",
    "AnalysisValidation", "validate_analysis_lineage",
    "AIReservation", "reserve_ai_call", "settle_ai_call",
    "SemiconductorProfile", "build_semiconductor_profile",
    "SupplyChainEdge", "observed_supply_edge",
    "SemiconductorTransmission", "propagate_semiconductor_claim",
    "BeneficiaryCandidate", "classify_semiconductor_beneficiary",
    "BeneficiaryGraph", "build_beneficiary_graph",
    "LifecycleVersion", "LifecycleState", "append_lifecycle", "lifecycle_as_of",
    "CachedAnalysis", "cache_analysis_once", "get_cached_analysis",
    "AuditInput", "AuditVersion", "append_catalyst_audit", "audit_as_of",
    "StandardBundle", "build_standard_bundle", "read_standard_bundle",
    "to_parquet_bytes", "BackupReceipt", "backup_sqlite", "restore_to_new_dir",
    "ReadinessInputs", "ReadinessReport", "evaluate_v1_readiness",
]
