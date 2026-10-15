"""1_4 PIT-safe common identity and timestamp normalization.

Bridge existing official observations and authorized feed metadata WITHOUT
implying a verified public release or issuer. Corrections and company mappings
require separately observed evidence. No collection, filesystem or Era writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re

from .new_source_adapter import FeedObservation
from .operational_observations import OperationalObservation
from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.normalized_event.v1"
BINDING_STATUS = "SOURCE_LINKED_MAPPING_NOT_ISSUER_ATTESTED"
REVISION_STATUS = "EXPLICIT_CORRECTION_REFERENCE_UNVERIFIED"
ID_KINDS = frozenset({"SEC_CIK", "DART_CORP", "KRX_STOCK"})
FULL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/?&=%-]{0,511}\Z")
REV_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


def _stamp(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise SourceShareError(f"missing {label}")
    return _when(value.isoformat(), label)


def _docid(value: str, label: str) -> str:
    if not isinstance(value, str) or not FULL_ID.fullmatch(value):
        raise SourceShareError(f"invalid {label}")
    return value


@dataclass(frozen=True)
class CompanyBinding:
    """Out-of-band reviewed identifier; issuer authority NOT attested."""
    source_id: str
    source_document_id: str
    id_namespace: str
    company_id: str
    mapped_ticker: str | None
    evidence_sha256: str
    observed_at: datetime

    def validate(self) -> datetime:
        if self.id_namespace not in ID_KINDS:
            raise SourceShareError("unknown company identity namespace")
        _docid(self.source_document_id, "binding document id")
        _docid(self.source_id, "binding source id")
        if self.id_namespace == "SEC_CIK":
            if not re.fullmatch(r"[0-9]{1,10}", self.company_id):
                raise SourceShareError("invalid SEC CIK")
        elif self.id_namespace == "DART_CORP":
            if not re.fullmatch(r"[0-9]{8}", self.company_id):
                raise SourceShareError("invalid DART corporation code")
        else:
            if not re.fullmatch(r"[0-9]{6}", self.company_id):
                raise SourceShareError("invalid KRX stock code")
        if self.mapped_ticker is not None and not re.fullmatch(
            r"[A-Za-z0-9.:-]{1,20}", self.mapped_ticker
        ):
            raise SourceShareError("invalid mapped ticker")
        _must_sha(self.evidence_sha256, "mapping evidence SHA")
        return _stamp(self.observed_at, "mapping observed_at")


@dataclass(frozen=True)
class RevisionEvidence:
    """Non-retroactive explicit correction lineage (not a signed authority)."""
    source_id: str
    source_document_id: str
    revision_id: str
    supersedes_document_id: str
    evidence_sha256: str
    observed_at: datetime

    def validate(self) -> datetime:
        _docid(self.source_document_id, "correction document id")
        _docid(self.supersedes_document_id, "superseded document id")
        _docid(self.source_id, "correction source id")
        if (self.supersedes_document_id == self.source_document_id
                or not isinstance(self.revision_id, str)
                or not REV_ID.fullmatch(self.revision_id)):
            raise SourceShareError("invalid or self-referential correction")
        _must_sha(self.evidence_sha256, "correction evidence SHA")
        return _stamp(self.observed_at, "correction observed_at")


@dataclass(frozen=True)
class NormalizedEvent:
    schema_version: str
    event_id: str
    source_id: str
    provider_id: str
    source_document_id: str
    data_kind: str
    first_seen_at: datetime
    collected_at: datetime
    verified_at: datetime
    decision_at: datetime
    available_at: datetime
    published_at: datetime | None
    publication_status: str
    company_namespace: str | None
    company_id: str | None
    mapped_ticker: str | None
    identity_status: str
    revision_id: str | None
    supersedes_document_id: str | None
    revision_status: str
    source_sha256: str | None
    source_receipt_sha256: str | None

    def as_of(self, decision_at: datetime, *, now: datetime | None = None) -> "NormalizedEvent":
        at = _stamp(decision_at, "decision_at")
        current = _stamp(now or datetime.now(timezone.utc), "now")
        if not max(self.available_at, self.decision_at) <= at <= current:
            raise SourceShareError("normalized event unavailable at decision")
        return self


def normalize_observed_event(
    observed: OperationalObservation | FeedObservation,
    decision_at: datetime,
    *,
    verified_at: datetime | None = None,
    now: datetime | None = None,
    binding: CompanyBinding | None = None,
    correction: RevisionEvidence | None = None,
) -> NormalizedEvent:
    """Build a conservative common record; never guess missing release/issuer.

    The optional binding/revision records are source-linked *metadata*
    observations, not proof of the original issuer's external publication.
    They cannot change an earlier decision retroactively.
    """
    decision = _stamp(decision_at, "decision_at")
    current = _stamp(now or datetime.now(timezone.utc), "now")
    check_at = _stamp(verified_at or current, "verified_at")
    if check_at > decision or decision > current:
        raise SourceShareError("future/unavailable verified decision")
    if isinstance(observed, OperationalObservation):
        if observed.published_at is not None or observed.issuer_verified or observed.release_certified:
            raise SourceShareError("unsigned official event cannot claim certification")
        provider_id = observed.provider_id
        source_id = observed.source_id
        document_id = observed.source_document_id
        event_id = _must_sha(observed.evidence_id, "official evidence ID")
        first = _stamp(observed.first_seen_at, "official first_seen_at")
        predecessor_available = max(
            _stamp(observed.available_at, "official available_at"),
            _stamp(observed.verified_at, "official verified_at"),
        )
        quality = observed.data_kind
        raw_sha = _must_sha(observed.original_sha256, "official original SHA")
        receipt_sha = _must_sha(observed.receipt_sha256, "official receipt SHA")
    elif isinstance(observed, FeedObservation):
        if observed.reported_published_at is not None:
            raise SourceShareError("feed release time not independently certified")
        provider_id = observed.provider_id
        source_id = observed.provider_id
        document_id = observed.document_id
        event_id = _must_sha(observed.event_id, "feed event ID")
        first = _stamp(observed.first_seen_at, "feed first_seen_at")
        predecessor_available = first
        quality = "FEED_METADATA_UNVERIFIED"
        raw_sha, receipt_sha = None, None
    else:
        raise SourceShareError("unsupported observation type")
    _docid(source_id, "source_id")
    _docid(document_id, "source document id")
    _docid(provider_id, "provider_id")
    if first > check_at or predecessor_available > decision:
        raise SourceShareError("source not available at verification/decision")
    available = max(first, predecessor_available, check_at)
    company_namespace = company_id = mapped_ticker = None
    identity_status = "UNKNOWN"
    revision_id = supersedes = None
    revision_status = "UNKNOWN"
    if binding is not None:
        if (not isinstance(binding, CompanyBinding)
                or binding.source_id != source_id
                or binding.source_document_id != document_id):
            raise SourceShareError("company mapping source/document mismatch")
        approved_at = binding.validate()
        if isinstance(observed, OperationalObservation):
            expected_namespaces = {
                "SEC": "SEC_CIK", "DART": "DART_CORP", "KRX": "KRX_STOCK",
            }
            if binding.id_namespace != expected_namespaces.get(observed.provider_id):
                raise SourceShareError("official provider and company ID namespace mismatch")
        if approved_at > decision:
            raise SourceShareError("future company identity evidence")
        available = max(available, approved_at)
        company_namespace = binding.id_namespace
        company_id = binding.company_id
        mapped_ticker = binding.mapped_ticker
        identity_status = BINDING_STATUS
    if correction is not None:
        if (not isinstance(correction, RevisionEvidence)
                or correction.source_id != source_id
                or correction.source_document_id != document_id):
            raise SourceShareError("correction source/document mismatch")
        revised_at = correction.validate()
        if revised_at > decision:
            raise SourceShareError("future correction evidence")
        available = max(available, revised_at)
        revision_id = correction.revision_id
        supersedes = correction.supersedes_document_id
        revision_status = REVISION_STATUS
    if available > decision:
        raise SourceShareError("future evidence at decision")
    normalized = NormalizedEvent(
        schema_version=SCHEMA, event_id=event_id,
        source_id=source_id, provider_id=provider_id,
        source_document_id=document_id, data_kind=quality,
        first_seen_at=first, collected_at=first,
        verified_at=check_at, decision_at=decision, available_at=available,
        published_at=None, publication_status="UNKNOWN",
        company_namespace=company_namespace, company_id=company_id,
        mapped_ticker=mapped_ticker, identity_status=identity_status,
        revision_id=revision_id, supersedes_document_id=supersedes,
        revision_status=revision_status,
        source_sha256=raw_sha, source_receipt_sha256=receipt_sha,
    )
    return normalized.as_of(decision, now=current)


def normalize_attested_publication(
    proof: object, decision_at: datetime, *, now: datetime | None = None,
) -> NormalizedEvent:
    """Normalize an already authenticated signed-proof object, not loose JSON.

    This intentionally accepts only the previous stage's immutable, anchored
    publication type. Calling this never creates witness trust or a real-world
    independent timestamp. Synthetic signed proofs remain synthetic.
    """
    from .official_promotion import AnchoredOfficialPublication

    decision = _stamp(decision_at, "decision_at")
    current = _stamp(now or datetime.now(timezone.utc), "now")
    if not isinstance(proof, AnchoredOfficialPublication):
        raise SourceShareError("authenticated anchored publication required")
    raw = proof.as_of(decision, now=current)
    seen = _stamp(proof.attestation.source_capture_first_seen_at,
                  "source capture first_seen_at")
    usable = _stamp(proof.usable_from, "signed proof usable_from")
    published = _stamp(raw.published_at, "signed publisher released at")
    if not published <= seen <= usable <= decision <= current:
        raise SourceShareError("signed publication timestamps violate PIT")
    _docid(raw.source_id, "signed source id")
    _docid(raw.source_document_id, "signed document id")
    _must_sha(raw.source_sha256, "signed source SHA")
    _must_sha(raw.source_receipt_sha256, "signed receipt SHA")
    if (raw.company_id is None or
            (raw.provider_id == "SEC" and not re.fullmatch(r"[0-9]{1,10}", raw.company_id))):
        raise SourceShareError("invalid signed issuer identifier")
    issuer_namespace = "SEC_CIK" if raw.provider_id == "SEC" else "DART_CORP"
    issuer_status = "SIGNED_WITNESS_CLAIM_REQUIRES_AUTHORITY_AUDIT"
    if raw.provider_id == "DART" and not re.fullmatch(r"[0-9]{8}", raw.company_id):
        # Synthetic/general issuer labels are not proof of DART corp codes.
        issuer_namespace = None
        issuer_status = "SIGNED_WITNESS_IDENTITY_UNMAPPED"
    signer = proof.attestation
    if signer.revision_kind not in ("ORIGINAL", "CORRECTION"):
        raise SourceShareError("invalid signed revision")
    if signer.revision_kind == "ORIGINAL" and signer.supersedes_document_id is not None:
        raise SourceShareError("original cannot supersede")
    if signer.revision_kind == "CORRECTION":
        _docid(signer.supersedes_document_id, "signed superseded document")
        if signer.supersedes_document_id == raw.source_document_id:
            raise SourceShareError("signed self-correction invalid")
    return NormalizedEvent(
        schema_version=SCHEMA,
        event_id=_must_sha(raw.event_id, "signed event ID"),
        source_id=raw.source_id,
        provider_id=raw.provider_id,
        source_document_id=raw.source_document_id,
        data_kind="ATTESTED_DISCLOSURE_CLAIM",
        first_seen_at=seen,
        collected_at=seen,
        verified_at=usable,
        decision_at=decision,
        available_at=usable,
        published_at=published,
        publication_status="EXTERNAL_WITNESS_SIGNED_CLAIM",
        company_namespace=issuer_namespace,
        company_id=raw.company_id,
        mapped_ticker=None,
        identity_status=issuer_status,
        revision_id=signer.revision_id,
        supersedes_document_id=signer.supersedes_document_id,
        revision_status="SIGNED_WITNESS_REVISION_CLAIM",
        source_sha256=raw.source_sha256,
        source_receipt_sha256=raw.source_receipt_sha256,
    )
