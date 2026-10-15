"""A newly published follow-up must not turn an older plan into fresh capex."""
from datetime import datetime, timezone
import json

import pytest

from newscatalystos.motir_article_binding import publish_motir_article_binding
from newscatalystos.motir_document_screen import (
    consume_motir_document_screen, prepare_motir_document_screen,
    publish_motir_document_screen,
)
from newscatalystos.source_share import SourceShareError
from test_motir_article_binding import prepare, setup


def screen_case(tmp_path, body):
    case = setup(tmp_path, body=body)
    binding, digest = publish_motir_article_binding(
        prepare(case), tmp_path / "bindings",
    )
    raw = prepare_motir_document_screen(binding, digest, case[4])
    path, screen_sha = publish_motir_document_screen(raw, tmp_path / "screens")
    return path, screen_sha, json.loads(raw)


def test_prior_plan_mentioned_in_current_article_is_not_new_investment(tmp_path):
    body = ("충전대 TF는 지난 7월 국민보고회에서 발표된 392조원 규모의 "
            "첨단전략산업 투자가 차질 없이 이행되도록 점검하였다. " * 2)
    path, digest, data = screen_case(tmp_path, body)
    assert data["findings"][0]["category"] == "PRIOR_INVESTMENT_PLAN_MONITORING"
    assert data["findings"][0]["source_amount_mentions"] == ["392조원", "392조원"]
    assert not data["ai_routing_candidate"]
    assert not data["verified_new_economic_event"]
    assert consume_motir_document_screen(path, digest)["ai_provider_calls"] == 0
    assert "국민보고회" not in path.read_text()


def test_explicit_large_new_semiconductor_investment_is_only_ai_candidate(tmp_path):
    body = ("한 기업은 충남 반도체 공장에 20조원을 신규 투자하기로 결정했다. "
            "구체적인 집행과 수익은 아직 확인되지 않았다. " * 2)
    path, digest, data = screen_case(tmp_path, body)
    assert data["findings"][0]["category"] == "NEW_INVESTMENT_SOURCE_CANDIDATE"
    assert data["ai_routing_candidate"]
    assert data["ai_provider_calls"] == 0
    assert not data["verified_real_transaction"]
    assert consume_motir_document_screen(path, digest)["ai_routing_candidate"]


def test_mixed_past_and_new_temporal_cues_are_held(tmp_path):
    body = ("지난 7월 발표된 392조원 첨단전략산업 투자계획을 신규 투자 결정으로 "
            "소개했지만 이행 점검만 진행했다. " * 2)
    _, _, data = screen_case(tmp_path, body)
    assert data["findings"][0]["category"] == "MIXED_TEMPORAL_EVIDENCE_HOLD"
    assert data["ai_routing_candidate"] is False


def test_document_screen_pin_and_future_time_fail_closed(tmp_path):
    path, digest, _ = screen_case(tmp_path,
        "반도체 사업 투자 3조원 관련 사항을 검토 중이다. " * 4)
    with pytest.raises(SourceShareError):
        consume_motir_document_screen(path, "0" * 64)
    with pytest.raises(SourceShareError):
        consume_motir_document_screen(path, digest,
                                      now=datetime(2026, 10, 14, tzinfo=timezone.utc))


def test_consumer_rejects_resealed_false_ai_routing(tmp_path):
    _, _, data = screen_case(tmp_path,
        "반도체 공장에 20조원을 신규 투자하기로 결정했다. " * 4)
    data["ai_routing_candidate"] = False
    payload = (json.dumps(data, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode()
    path, digest = publish_motir_document_screen(payload, tmp_path / "altered")
    with pytest.raises(SourceShareError, match="contradicts"):
        consume_motir_document_screen(path, digest)
