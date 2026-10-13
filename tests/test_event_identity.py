"""1_4 time/issuer/correction normalization without guessed release facts."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from newscatalystos.event_identity import (
    SCHEMA, BINDING_STATUS, REVISION_STATUS, CompanyBinding,
    RevisionEvidence, normalize_observed_event,
)
from newscatalystos.operational_observations import load_operational_observations
from newscatalystos.source_share import SourceShareError
from test_published_observations import published
from test_new_source_adapter import registry, NOW as RSS_NOW, RSS
from test_signed_publication import witness
from newscatalystos.new_source_adapter import parse_authorized_feed

AT = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc)


def official(tmp_path, source="sec-submissions"):
    folder, root, pin, moment, *_ = published(tmp_path, source)
    collection = load_operational_observations(folder, root, pin, now=moment)
    return collection.observations[0], moment


def feed():
    return parse_authorized_feed(
        registry(), "synthetic-government-feed", RSS, observed_at=RSS_NOW
    )[0]


def mapping(row, at, company_id="320193", namespace="SEC_CIK"):
    return CompanyBinding(
        source_id=row.source_id,
        source_document_id=row.source_document_id,
        id_namespace=namespace,
        company_id=company_id, mapped_ticker=None,
        evidence_sha256="a" * 64,
        observed_at=at,
    )


def revision(row, at):
    return RevisionEvidence(
        source_id=row.source_id,
        source_document_id=row.source_document_id,
        revision_id="r2",
        supersedes_document_id="original123",
        evidence_sha256="b" * 64,
        observed_at=at,
    )


@pytest.mark.parametrize("source", ["sec-submissions", "dart-disclosures", "krx-kospi"])
def test_official_unknown_release_is_not_guessed(tmp_path, source):
    row, verified = official(tmp_path, source)
    at = verified + timedelta(seconds=3)
    normalized = normalize_observed_event(row, at, verified_at=at, now=at)
    assert normalized.schema_version == SCHEMA
    assert normalized.provider_id == row.provider_id
    assert normalized.published_at is None
    assert normalized.publication_status == "UNKNOWN"
    assert normalized.company_id is None
    assert normalized.identity_status == "UNKNOWN"
    assert normalized.revision_status == "UNKNOWN"
    assert normalized.source_sha256 == row.original_sha256
    assert normalized.source_receipt_sha256 == row.receipt_sha256
    assert normalized.available_at == at
    assert normalized.decision_at == at
    assert normalized.collected_at == row.first_seen_at
    with pytest.raises(SourceShareError, match="unavailable"):
        normalized.as_of(at - timedelta(microseconds=1), now=at)


def test_rss_first_seen_and_verification_are_different():
    row = feed()
    decision = RSS_NOW + timedelta(minutes=2)
    result = normalize_observed_event(row, decision,
                                       verified_at=decision, now=decision)
    assert result.first_seen_at == RSS_NOW
    assert result.available_at == decision
    assert result.provider_id == row.provider_id
    assert result.source_sha256 is None
    assert result.published_at is None
    assert result.company_namespace is None
    assert result.identity_status == "UNKNOWN"


def test_issuer_mapping_not_self_certification(tmp_path):
    row, verified = official(tmp_path)
    reviewed = verified + timedelta(seconds=1)
    decision = reviewed + timedelta(seconds=1)
    result = normalize_observed_event(row, decision, now=decision,
                     verified_at=verified, binding=mapping(row, reviewed))
    assert result.company_namespace == "SEC_CIK"
    assert result.company_id == "320193"
    assert result.identity_status == BINDING_STATUS
    assert result.published_at is None
    assert result.available_at == reviewed
    with pytest.raises(SourceShareError, match="unavailable"):
        result.as_of(verified, now=decision)


def test_mapping_future_or_wrong_document_rejected(tmp_path):
    row, verified = official(tmp_path)
    decision = verified + timedelta(seconds=2)
    with pytest.raises(SourceShareError, match="future company"):
        normalize_observed_event(row, decision, now=decision,
                                 binding=mapping(row, decision + timedelta(seconds=1)))
    with pytest.raises(SourceShareError, match="source/document mismatch"):
        normalize_observed_event(row, decision, now=decision,
                                 binding=replace(mapping(row, verified),
                                                 source_document_id="other-id"))


@pytest.mark.parametrize("namespace,company_id", [
    ("SEC_CIK", "XYZ"), ("SEC_CIK", "123456789012"),
    ("DART_CORP", "1234567"), ("KRX_STOCK", "A005930"),
    ("UNKNOWN", "320193"),
])
def test_invalid_company_ids_rejected(tmp_path, namespace, company_id):
    row, verified = official(tmp_path)
    with pytest.raises(SourceShareError):
        normalize_observed_event(row, verified, now=verified,
            binding=mapping(row, verified, namespace=namespace, company_id=company_id))


def test_correction_is_explicit_new_version_not_source_rewrite(tmp_path):
    row, verified = official(tmp_path)
    correction_seen = verified + timedelta(seconds=10)
    decision = correction_seen + timedelta(seconds=1)
    normalized = normalize_observed_event(
        row, decision, now=decision, verified_at=verified,
        correction=revision(row, correction_seen),
    )
    assert normalized.revision_id == "r2"
    assert normalized.supersedes_document_id == "original123"
    assert normalized.revision_status == REVISION_STATUS
    assert normalized.available_at == correction_seen
    assert normalized.publication_status == "UNKNOWN"
    assert row.published_at is None
    with pytest.raises(SourceShareError, match="unavailable"):
        normalized.as_of(verified, now=decision)


def test_correction_backdate_self_reference_or_other_source_rejected(tmp_path):
    row, verified = official(tmp_path)
    with pytest.raises(SourceShareError, match="future correction"):
        normalize_observed_event(
            row, verified, now=verified,
            correction=revision(row, verified + timedelta(seconds=1)),
        )
    with pytest.raises(SourceShareError, match="self-referential"):
        normalize_observed_event(
            row, verified, now=verified,
            correction=replace(revision(row, verified),
                               supersedes_document_id=row.source_document_id),
        )
    with pytest.raises(SourceShareError, match="source/document mismatch"):
        normalize_observed_event(
            row, verified, now=verified,
            correction=replace(revision(row, verified), source_id="wrong"),
        )


def test_unsigned_official_cannot_fake_published_at_or_issuer(tmp_path):
    row, verified = official(tmp_path)
    with pytest.raises(SourceShareError, match="certification"):
        normalize_observed_event(replace(row, published_at=verified), verified,
                                 now=verified)
    with pytest.raises(SourceShareError, match="certification"):
        normalize_observed_event(replace(row, issuer_verified=True), verified,
                                 now=verified)


def test_future_or_naive_time_never_succeeds(tmp_path):
    row, verified = official(tmp_path)
    with pytest.raises(SourceShareError):
        normalize_observed_event(row, verified.replace(tzinfo=None),
                                 now=verified)
    with pytest.raises(SourceShareError, match="future"):
        normalize_observed_event(row, verified + timedelta(seconds=1),
                                 verified_at=verified, now=verified)
    with pytest.raises(SourceShareError):
        normalize_observed_event(row, verified, now=verified,
                                 verified_at=verified.replace(tzinfo=None))


def test_rss_operator_binding_remains_unverified():
    row = feed()
    decision = RSS_NOW + timedelta(minutes=1)
    binding = CompanyBinding(
        source_id=row.provider_id, source_document_id=row.document_id,
        id_namespace="DART_CORP", company_id="00123456",
        mapped_ticker="005930", evidence_sha256="b" * 64,
        observed_at=decision,
    )
    value = normalize_observed_event(
        row, decision, now=decision, binding=binding,
    )
    assert value.company_id == "00123456"
    assert value.mapped_ticker == "005930"
    assert value.identity_status == BINDING_STATUS
    assert value.published_at is None


@pytest.mark.parametrize("provider", ["SEC", "DART"])
def test_existing_attested_boundary_normalizes_without_replacing_evidence(
    tmp_path, witness, provider,
):
    from newscatalystos.event_identity import normalize_attested_publication
    from newscatalystos.official_promotion import authenticate_anchored_official_record
    from test_official_promotion import scenario, NOW as PROOF_NOW

    values, folder, original = scenario(tmp_path, witness, provider)
    signed = authenticate_anchored_official_record(**values)
    normalized = normalize_attested_publication(signed, PROOF_NOW, now=PROOF_NOW)
    assert normalized.available_at == signed.usable_from
    assert normalized.published_at == signed.attestation._sealed_event.published_at
    assert normalized.source_sha256 == values["verified"].captures[0].raw_sha256
    assert normalized.publication_status == "EXTERNAL_WITNESS_SIGNED_CLAIM"
    assert normalized.identity_status == (
        "SIGNED_WITNESS_CLAIM_REQUIRES_AUTHORITY_AUDIT" if provider == "SEC"
        else "SIGNED_WITNESS_IDENTITY_UNMAPPED"
    )
    assert normalized.company_namespace == ("SEC_CIK" if provider == "SEC" else None)
    assert normalized.mapped_ticker is None
    assert normalized.collected_at == signed.attestation.source_capture_first_seen_at
    assert normalized.decision_at == PROOF_NOW
    assert (folder / "raw_response.json").read_bytes() == original
    with pytest.raises(SourceShareError, match="unavailable"):
        normalized.as_of(normalized.available_at - timedelta(microseconds=1),
                         now=PROOF_NOW)
    with pytest.raises(SourceShareError):
        normalize_attested_publication(
            signed, normalized.available_at - timedelta(microseconds=1),
            now=PROOF_NOW,
        )


def test_raw_event_alone_cannot_claim_authenticated_publication():
    from newscatalystos.event_identity import normalize_attested_publication
    with pytest.raises(SourceShareError, match="authenticated anchored"):
        normalize_attested_publication(feed(), RSS_NOW, now=RSS_NOW)


def test_official_source_cannot_attach_other_market_identity(tmp_path):
    row, verified = official(tmp_path, "sec-submissions")
    wrong = mapping(row, verified, namespace="DART_CORP", company_id="00123456")
    with pytest.raises(SourceShareError, match="namespace mismatch"):
        normalize_observed_event(row, verified, now=verified, binding=wrong)


def test_normalization_decision_time_is_not_retroactively_replayed():
    row = feed()
    first_check = RSS_NOW + timedelta(seconds=1)
    decision = RSS_NOW + timedelta(seconds=30)
    normalized = normalize_observed_event(
        row, decision, verified_at=first_check, now=decision
    )
    assert normalized.available_at == first_check
    assert normalized.decision_at == decision
    with pytest.raises(SourceShareError, match="unavailable"):
        normalized.as_of(first_check, now=decision)
    assert normalized.as_of(decision, now=decision) is normalized


def test_evidence_fingerprints_cannot_be_arbitrary(tmp_path):
    row, verified = official(tmp_path)
    with pytest.raises(SourceShareError, match="SHA"):
        normalize_observed_event(
            row, verified, now=verified,
            binding=replace(mapping(row, verified), evidence_sha256="wrong"),
        )
    with pytest.raises(SourceShareError, match="SHA"):
        normalize_observed_event(
            row, verified, now=verified,
            correction=replace(revision(row, verified), evidence_sha256="wrong"),
        )
