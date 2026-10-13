"""4_5 every impact's supporting number must be source-quote anchored."""
from dataclasses import replace
from datetime import timedelta

import pytest

from newscatalystos.ai_provider import run_ai_analysis
from newscatalystos.fact_extraction import FactProposal, verify_extracted_facts
from newscatalystos.economic_path import ImpactHypothesis, build_impact_analysis
from newscatalystos.analysis_validation import validate_analysis_lineage
from newscatalystos.source_share import SourceShareError
from test_ai_provider import config, request, stub
from test_new_source_adapter import NOW


def evidence():
    ai=run_ai_analysis(config(),request(),transport=stub,now=NOW)
    facts=verify_extracted_facts(
        "a"*64,"Equipment order reached 320억원",
        [FactProposal("CONTRACT_AMOUNT","320억원","order reached 320억원")],
        observed_at=NOW,checked_at=NOW,now=NOW,
    )
    impact=build_impact_analysis(
        "a"*64,[ImpactHypothesis(
            path="CAPEX",direction="INCREASE",affected_product="HBM equipment",
            source_claim_sha256=facts.supported[0].evidence_quote_sha256,
            premise="Equipment spending may expand",
            counter_type="MISSING_INFORMATION",
            counter_argument="Supplier award remains unknown",
        )],available_at=NOW,decision_at=NOW,now=NOW,
    )
    return ai,facts,impact


def test_only_fully_linked_analysis_is_candidate_not_factual_certification():
    result=validate_analysis_lineage(*evidence(),reviewed_at=NOW,now=NOW)
    assert result.status=="EVIDENCE_LINKED_CANDIDATE_NOT_VERIFIED_FACT"
    assert result.supported_numbers==1
    assert result.certified_fact_count==0
    assert not result.analysis_replaced_source


def test_unsupported_impact_claim_is_held_unknown():
    ai,facts,impact=evidence()
    bad=replace(impact,impact_hypotheses=(
        replace(impact.impact_hypotheses[0],source_claim_sha256="b"*64),
    ))
    result=validate_analysis_lineage(ai,facts,bad,reviewed_at=NOW,now=NOW)
    assert result.status=="UNKNOWN_HOLD_SOURCE_EVIDENCE_MISSING"


def test_rejected_ai_amount_keeps_unknown_instead_of_fact():
    ai,facts,impact=evidence()
    suspicious=replace(facts,rejected_fields=("CONTRACT_AMOUNT",))
    value=validate_analysis_lineage(ai,suspicious,impact,reviewed_at=NOW,now=NOW)
    assert value.status.startswith("UNKNOWN_HOLD")
    assert value.unsupported_number_fields==("CONTRACT_AMOUNT",)


def test_mixed_event_ids_rejected():
    ai,facts,impact=evidence()
    with pytest.raises(SourceShareError,match="source ID mismatch"):
        validate_analysis_lineage(replace(ai,event_sha256="c"*64),
                                  facts,impact,reviewed_at=NOW,now=NOW)


def test_later_model_result_cannot_validate_earlier_decision():
    ai,facts,impact=evidence()
    later=NOW+timedelta(seconds=3)
    with pytest.raises(SourceShareError,match="future evidence"):
        validate_analysis_lineage(replace(ai,available_at=later),
                                  facts,impact,reviewed_at=NOW,now=later)
