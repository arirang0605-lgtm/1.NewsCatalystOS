"""5_2 document proofs cannot manufacture supply contracts from filing indexes."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from newscatalystos.event_identity import CompanyBinding
from newscatalystos.official_relation_review import (
    OfficialRelationReview, RELATION_STATUS, review_official_supply_relation,
)
from newscatalystos.operational_observations import (
    OperationalObservation, OperationalObservationSet, SCHEMA,
)
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
DOC = "20261013000001"
STATEMENT = (
    "Supplier Alpha agrees to supply advanced packaging components to "
    "Customer Beta pursuant to a direct supply contract."
)
BODY = ("Official disclosed agreement: " + STATEMENT).encode()
DIGEST = sha256(BODY).hexdigest()
EVIDENCE = sha256(("dart-disclosures\0" + DOC).encode()).hexdigest()
RECEIPT = "a" * 64


def setup():
    old = NOW - timedelta(hours=2)
    row = OperationalObservation(
        SCHEMA, "dart-disclosures", "DART", EVIDENCE, DOC,
        old, NOW-timedelta(hours=1), NOW-timedelta(hours=1),
        "f"*64, RECEIPT, "INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY",
        "DISCLOSURE_OBSERVED",
    )
    observed = OperationalObservationSet(
        NOW-timedelta(hours=1), 5, True, (row,),
    )
    supplier = CompanyBinding(
        row.source_id, DOC, "DART_CORP", "00000001",
        None, "b"*64, old,
    )
    customer = replace(supplier, company_id="00000002")
    review = OfficialRelationReview(
        row.source_id, DOC, EVIDENCE, RECEIPT, DIGEST,
        NOW-timedelta(minutes=35), NOW-timedelta(minutes=30),
        NOW-timedelta(minutes=10), "REVIEWER_1",
        "Supplier Alpha", "Customer Beta", STATEMENT,
        "ADVANCED_PACKAGING",
    )
    return observed, supplier, customer, review


def run(obs=None, supplier=None, customer=None, review=None,
        body=BODY, pin=DIGEST, decision=NOW, now=NOW):
    default_obs, a, b, r = setup()
    return review_official_supply_relation(
        obs if obs is not None else default_obs,
        supplier if supplier is not None else a,
        customer if customer is not None else b,
        review if review is not None else r,
        body, trusted_document_sha256=pin,
        decision_at=decision, now=now,
    )


def test_official_text_and_independent_pin_generate_only_reviewed_claim():
    result=run()
    assert result.evidence_status == RELATION_STATUS
    assert result.evidence_sha256 == DIGEST
    assert result.document_sha256 == DIGEST
    assert len(result.review_proof_sha256) == 64
    assert result.verified_real_transaction is False
    assert result.supplier_namespace == result.customer_namespace == "DART_CORP"
    assert result.available_at == NOW-timedelta(minutes=10)
    assert result.as_of(NOW, now=NOW) == result
    with pytest.raises(SourceShareError,match="unavailable"):
        result.as_of(NOW-timedelta(minutes=11), now=NOW)


@pytest.mark.parametrize("changed, message", [
    ({"body":BODY+b"tampered"}, "SHA untrusted"),
    ({"body":b""}, "SHA untrusted"),
    ({"body":b"bad \xff UTF8"}, "SHA untrusted"),
    ({"pin":"0"*64}, "SHA untrusted"),
])
def test_untrusted_document_rejected(changed, message):
    with pytest.raises(SourceShareError, match=message):
        run(**changed)


def test_invalid_utf8_and_too_large_document_rejected():
    bad=b"\xff"*80
    with pytest.raises(SourceShareError,match="UTF-8"):
        run(body=bad,pin=sha256(bad).hexdigest(),
            review=replace(setup()[3],document_sha256=sha256(bad).hexdigest()))
    large=b"a"*(1024*1024+1)
    with pytest.raises(SourceShareError,match="SHA untrusted"):
        run(body=large)


def test_document_must_explicitly_name_both_parties_and_supply_relation():
    review=setup()[3]
    for statement in [
        "Supplier Alpha only mentions packaging capacity.",
        "Customer Beta only mentions packaging capacity.",
        "Supplier Alpha and Customer Beta mentioned jointly with no business deal.",
    ]:
        with pytest.raises(SourceShareError,match="explicit supplier/customer"):
            run(review=replace(review,evidence_statement=statement))
    with pytest.raises(SourceShareError,match="explicit supplier/customer"):
        run(review=replace(review,supplier_name="Anonymous Vendor"))


def test_source_receipt_document_and_coverage_cannot_be_spoofed():
    observed,a,b,review=setup()
    with pytest.raises(SourceShareError,match="coverage"):
        run(obs=replace(observed,coverage_verified=False))
    with pytest.raises(SourceShareError,match="uniquely verified"):
        run(obs=replace(observed,observations=()))
    with pytest.raises(SourceShareError,match="uniquely verified"):
        run(obs=replace(observed,observations=observed.observations*2))
    with pytest.raises(SourceShareError,match="evidence/receipt"):
        run(review=replace(review,source_receipt_sha256="c"*64))
    with pytest.raises(SourceShareError,match="evidence/receipt"):
        run(review=replace(review,source_evidence_id="c"*64))
    with pytest.raises(SourceShareError,match="source-document mismatch"):
        run(customer=replace(b,source_document_id="20261013000002"))


def test_no_krx_context_or_forged_issuer_certification():
    observed, *_=setup()
    row=observed.observations[0]
    with pytest.raises(SourceShareError,match="uncertified disclosure"):
        run(obs=replace(observed,observations=(replace(
            row,data_kind="MARKET_CONTEXT_NOT_NEWS",provider_id="KRX"
        ),)))
    with pytest.raises(SourceShareError,match="uncertified disclosure"):
        run(obs=replace(observed,observations=(replace(
            row,issuer_verified=True
        ),)))


def test_late_pins_reviews_and_company_bindings_cannot_backdate():
    observed,supplier,customer,review=setup()
    with pytest.raises(SourceShareError,match="unavailable"):
        run(review=replace(review,pin_observed_at=NOW))
    with pytest.raises(SourceShareError,match="unavailable"):
        run(review=replace(review,document_observed_at=NOW))
    with pytest.raises(SourceShareError,match="unavailable"):
        run(decision=NOW-timedelta(minutes=11))
    with pytest.raises(SourceShareError,match="review predates"):
        run(supplier=replace(supplier,observed_at=NOW))
    with pytest.raises(SourceShareError,match="future supply-chain decision"):
        run(decision=NOW+timedelta(minutes=1))
    result=run(review=replace(review,reviewed_at=NOW))
    assert result.available_at==NOW


def test_review_cannot_be_replaced_with_self_certification():
    review=setup()[3]
    with pytest.raises(SourceShareError,match="reviewer code"):
        run(review=replace(review,reviewer_code=""))
    with pytest.raises(SourceShareError,match="invalid stage"):
        run(review=replace(review,product_stage="BIOTECH"))
    assert run().verified_real_transaction is False

def test_review_proof_survives_readonly_beneficiary_json_without_false_sales():
    import json
    from newscatalystos.beneficiary_classification import classify_semiconductor_beneficiary
    from newscatalystos.beneficiary_graph_contract import build_beneficiary_graph
    from newscatalystos.semiconductor_impact import propagate_semiconductor_claim
    from newscatalystos.semiconductor_profile import build_semiconductor_profile

    linked = run()
    profile = build_semiconductor_profile()
    economic = propagate_semiconductor_claim(
        profile, "d"*64, "PACKAGING_CAPACITY",
        direction="POSITIVE", evidence_note="Hypothetical capacity change only",
        source_available_at=linked.available_at, reviewed_at=NOW, now=NOW,
    )
    candidate = classify_semiconductor_beneficiary(
        linked, economic, reviewed_at=NOW, now=NOW,
    )
    graph = build_beneficiary_graph(
        profile, economic, [linked], [candidate], NOW, now=NOW,
    )
    node = json.loads(graph.JSON_bytes)["edges"][0]
    assert node["relation_evidence_status"] == RELATION_STATUS
    assert node["document_sha256"] == DIGEST
    assert node["review_proof_sha256"] == linked.review_proof_sha256
    assert node["verified_real_benefit"] is False
    assert node["revenue_contribution_krw"] is None
    with pytest.raises(SourceShareError,match="inconsistent official relation"):
        build_beneficiary_graph(
            profile, economic, [replace(linked, document_sha256="a"*64)],
            [candidate], NOW, now=NOW,
        )
