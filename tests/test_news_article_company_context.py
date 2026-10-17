"""One saved article -> current as-of company reasons, not entire theme exposure."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from newscatalystos.news_search_evidence import saved_article_evidence
from newscatalystos.news_article_company_context import article_company_context
from newscatalystos.theme_emergence import ThemeStore, economic_observation
from newscatalystos.source_share import SourceShareError
from test_saved_article_evidence import connected
from test_federated_news_search import sample
from test_theme_supply_chain import setup as relation_case, attach
from test_theme_emergence import T, event


def test_article_party_has_matching_source_inclusion_reason_but_not_benefit(connected):
    _, source, theme_root, present = connected
    detail = saved_article_evidence(source, theme_root, now=present)
    result = article_company_context(detail, theme_root, now=present)
    assert result["status"] == "READY"
    assert result["verified_real_benefit"] is False
    assert result["investment_merit"] == "NOT_ASSESSED"
    assert len(result["themes"]) == 1
    for theme in result["themes"]:
        assert len(theme["direct_parties"]) == 2
        for party in theme["direct_parties"]:
            assert party["source_name"] == "가상전자"
            assert party["official_entity_id"] is None
            assert party["identity_status"] == "SOURCE_NAME_ONLY"
            assert party["active_in_theme"]
            assert party["inclusion_status"] == "READY"
            assert len(party["inclusion_reasons"]) == 1
            assert party["source_url"] == source["source_url"]
            assert party["benefit_status"] == "UNVERIFIED"
            assert party["price_assessment"] == "NOT_EVALUATED_HERE"
        assert not theme["related_supply_context"]
    early = present - timedelta(microseconds=1)
    old = saved_article_evidence(source, theme_root, as_of=early, now=present)
    assert article_company_context(old, theme_root, as_of=early, now=present)["status"] == "N/A"
    forged = {**detail, "source": {**source, "title_sha256": "f" * 64}}
    assert article_company_context(forged, theme_root, now=present)["status"] == "N/A"


def test_exact_pinned_official_id_is_not_inferred_from_name(tmp_path):
    change = dict(event(company="가상전자", topic="HBM")["change"])
    change["source_paragraph_sha256"] = "b" * 64
    change["evidence_level"] = "REPORTED"
    pin = {"source_event_sha256": "a" * 64, "document_sha256": "b" * 64}
    kwargs = dict(origin_reference="https://gov.example.org/semiconductor/1",
                  source_url="https://gov.example.org/semiconductor/1",
                  source_id="synthetic-government-feed", source_available_at=T.isoformat(),
                  source_binding=pin, content_scope="RSS_TITLE_METADATA")
    mapped = economic_observation(change, **kwargs, company_mappings=[{
        "source_name": "가상전자", "entity_id": "DART_CORP:12345678",
        "evidence_sha256": "c" * 64}])
    store = ThemeStore(tmp_path / "themes")
    store.ingest([mapped], now=T)
    source = {
        "provider_id": kwargs["source_id"], "event_id": pin["source_event_sha256"],
        "title_sha256": pin["document_sha256"], "source_url": kwargs["source_url"],
        "source_available_at": T.isoformat(), "headline": "가상전자 HBM 근거"}
    detail = saved_article_evidence(source, store.root, now=T)
    context = article_company_context(detail, store.root, now=T)
    assert context["status"] == "READY"
    party = context["themes"][0]["direct_parties"][0]
    assert party["entity_id"] == "DART_CORP:12345678"
    assert party["source_name"] == "가상전자"
    assert party["official_entity_id"] == "DART_CORP:12345678"
    assert party["identity_status"] == "PINNED_OFFICIAL_ID"
    assert party["identity_evidence_sha256"] == "c" * 64
    assert party["inclusion_status"] == "READY"
    # The same economic source WITHOUT pinned identity cannot promote the name.
    other = economic_observation(change, **kwargs)
    plain = ThemeStore(tmp_path / "plain")
    plain.ingest([other], now=T)
    direct = article_company_context(saved_article_evidence(source, plain.root, now=T),
                                     plain.root, now=T)
    assert direct["themes"][0]["direct_parties"][0]["official_entity_id"] is None


def test_explicit_supply_relation_is_context_of_same_event_not_article_benefit(tmp_path):
    info, out, pub, store, original, _ = relation_case(tmp_path)
    present = info[-1] + timedelta(seconds=1)
    saved, = attach(store, out, pub, present)
    ref = next(r for r in saved["source_refs"] if r["polarity"] == "SUPPORT")
    detail = {
        "source": {
            "provider_id": ref["source_id"], "event_id": "f" * 64,
            "title_sha256": "e" * 64, "source_url": ref["source_url"],
            "source_available_at": ref["source_available_at"]},
        "status": "N/A",
        "official_document_evidence": {
            "status": "READY",
            "document_sha256": ref["source_binding"]["document_sha256"],
            "themes": [{
                "theme_id": saved["theme_id"], "name": saved["provisional_name"],
                "status": saved["status"], "decision_at": saved["decision_at"],
                "events": [{
                    "event_id": ref["event_id"], "action": ref["action"],
                    "phase": ref["phase"], "evidence_level": ref["evidence_level"],
                    "polarity": ref["polarity"], "recorded_at": ref["recorded_at"],
                    "source_url": ref["source_url"], "source_available_at": ref["source_available_at"],
                    "active_in_theme": True, "content_scope": "LICENSED_ARTICLE_TEXT"}]
            }]}
    }
    ctx = article_company_context(detail, store.root, as_of=present, now=present)
    assert ctx["status"] == "READY"
    linked = ctx["themes"][0]
    assert {p["entity_id"] for p in linked["direct_parties"]} == {"SEC_CIK:222222"}
    supplier = next(c for c in linked["related_supply_context"]
                    if c["entity_id"] == "SEC_CIK:111111")
    assert supplier["role"] == "supplier"
    assert supplier["linked_event_id"] == ref["event_id"]
    assert supplier["reported_in_selected_article"] is False
    customer = next(c for c in linked["related_supply_context"]
                    if c["entity_id"] == "SEC_CIK:222222")
    assert customer["reported_in_selected_article"] is True
    assert supplier["realized_benefit"] is False
    assert supplier["relation_kind"] == "REPORTED_DIRECT_TRANSACTION"
    assert supplier["source_urls"]
    # At the earlier time, this relation had not been attached yet.
    older = info[-1]
    prior = store.search(as_of=older, now=present)[0]
    previous = {**detail,
        "official_document_evidence": {**detail["official_document_evidence"],
        "themes": [{**detail["official_document_evidence"]["themes"][0],
                    "decision_at": prior["decision_at"], "status": prior["status"]}]}}
    old = article_company_context(previous, store.root, as_of=older, now=present)
    assert old["status"] == "READY"
    assert old["themes"][0]["related_supply_context"] == []


def test_empty_policy_only_has_no_invented_firms(tmp_path):
    original = event()
    original["change"]["entity_ids"] = []
    original["change"]["evidence_level"] = "REPORTED"
    original = economic_observation(original["change"],
        **{k:v for k,v in original.items() if k not in {"change","event_id"}},
        content_scope="RSS_TITLE_METADATA",
        source_binding={"source_event_sha256":"a"*64, "document_sha256":"b"*64})
    # Its paragraph SHA is deliberately not the selected title SHA,
    # so this article cannot inherit another event through a topic overlap.
    store = ThemeStore(tmp_path / "themes")
    saved, = store.ingest([original], now=T)
    detail = {"source": {"provider_id": original["source_id"], "event_id":"a"*64,
             "title_sha256":"b"*64, "source_url":original["source_url"],
             "source_available_at":original["source_available_at"]},
             "status":"N/A","themes":[]}
    assert article_company_context(detail,store.root,now=T)["status"] == "N/A"
