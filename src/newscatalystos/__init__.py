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
    IncrementalResult, incremental_poll, resume_after_rights_review,
    state_snapshot,
)

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
    "resume_after_rights_review", "state_snapshot",
]
