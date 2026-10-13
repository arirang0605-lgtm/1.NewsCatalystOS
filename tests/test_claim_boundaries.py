"""4_3 only prior authenticated evidence can claim signed official status."""
from datetime import timedelta
from dataclasses import replace

import pytest

from newscatalystos.claim_boundaries import classify_evidence_claim
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def classify(kind="OFFICIAL_CHANNEL", **kw):
    return classify_evidence_claim(
        event_sha256="a"*64,
        claim_text="HBM contract 320억원; first article unverified",
        kind=kind, source_url="https://gov.example.org/news/123",
        evidence_quote="320억원", first_usable_at=NOW,
        reviewed_at=NOW, now=NOW, **kw,
    )


def test_observed_official_channel_is_not_issuer_certified():
    value=classify()
    assert value.evidence_status=="OFFICIAL_CHANNEL_OBSERVED_UNCERTIFIED"
    assert not value.issuer_verified
    assert not value.verified_economic_fact
    assert value.source_url.startswith("https://")


@pytest.mark.parametrize("kind,expected", [
    ("SOCIAL_RUMOR", "RUMOR_UNVERIFIED"),
    ("DISTRIBUTED_RELEASE", "DISTRIBUTED_UNVERIFIED_CLAIM"),
    ("AI_HYPOTHESIS", "AI_INFERENCE_UNVERIFIED"),
    ("INDEPENDENT_NEWS", "REPORT_SOURCE_UNVERIFIED"),
])
def test_rumor_distributed_news_and_ai_not_promoted(kind, expected):
    result=classify(kind)
    assert result.evidence_status==expected
    assert not result.issuer_verified
    assert not result.verified_economic_fact
    assert result.inference_only == (kind=="AI_HYPOTHESIS")


def test_model_may_not_supply_fake_issuer_attestation():
    with pytest.raises(SourceShareError,match="verified anchored publication"):
        classify("SOCIAL_RUMOR", anchored_publication="FAKE")
    with pytest.raises(SourceShareError,match="verified anchored publication"):
        classify(anchored_publication={"signed":True})


def test_unanchored_independent_report_is_not_verified_fact():
    review=classify("INDEPENDENT_NEWS",independent_source_reviewed=True)
    assert review.independent_confirmation
    assert review.evidence_status=="INDEPENDENT_REPORT_REVIEWED_NOT_FACT_ATTESTED"
    assert not review.verified_economic_fact


def test_bad_claim_quote_and_credential_url_rejected():
    with pytest.raises(SourceShareError,match="quote"):
        classify_evidence_claim(
            "a"*64, "HBM contract 320억원", "OFFICIAL_CHANNEL",
            source_url="https://gov.example.org/news",
            evidence_quote="1000억원",first_usable_at=NOW,
            reviewed_at=NOW,now=NOW,
        )
    with pytest.raises(SourceShareError):
        classify_evidence_claim(
            "a"*64, "HBM contract 320억원", "OFFICIAL_CHANNEL",
            source_url="https://gov.example.org/news?api_key=secret",
            evidence_quote="320억원",first_usable_at=NOW,
            reviewed_at=NOW,now=NOW,
        )


def test_source_available_after_decision_fails():
    with pytest.raises(SourceShareError,match="future"):
        classify_evidence_claim(
            "a"*64,"HBM contract 320억원","OFFICIAL_CHANNEL",
            source_url="https://gov.example.org/news",
            evidence_quote="320억원",
            first_usable_at=NOW+timedelta(seconds=1),
            reviewed_at=NOW,now=NOW,
        )


def test_old_classification_does_not_appear_before_review():
    at=NOW+timedelta(seconds=2)
    value=classify_evidence_claim(
        "a"*64,"HBM 320억원","OFFICIAL_CHANNEL",
        source_url="https://gov.example.org/news",
        evidence_quote="320억원",
        first_usable_at=NOW,reviewed_at=at,now=at,
    )
    with pytest.raises(SourceShareError,match="not available"):
        value.as_of(NOW,now=at)
