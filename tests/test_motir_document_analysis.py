"""Licensed body lifecycle with synthetic Gemini responses; no paid network."""
from argparse import Namespace
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3

import pytest

from newscatalystos.ai_provider import DOCUMENT_SCHEMA, AIRequest, run_ai_analysis
from newscatalystos.motir_article_binding import publish_motir_article_binding
from newscatalystos.motir_document_analysis import (
    analyze_motir_document, publish_motir_document_analysis, consume_motir_document_analysis,
)
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from test_motir_article_binding import setup, prepare
from test_ai_provider import config
from test_ai_gemini_transport import LocalOpener, packet
from scripts import run_motir_policy_once as scheduler

NEW = "반도체 공장에 20조원을 신규 투자하기로 결정했다. 집행과 매출은 미확인이다. " * 3
PRIOR = "지난 7월 발표된 392조원 첨단전략산업 투자계획 이행을 점검했다. " * 3


def case(tmp_path, body=NEW):
    data = setup(tmp_path, body=body)
    binding, pin = publish_motir_article_binding(prepare(data), tmp_path / "bindings")
    return data, dict(binding_path=binding, binding_sha256=pin, archive_root=data[4],
        article_registry=data[1], analysis_root=tmp_path / "analysis",
        model=replace(config("GEMINI"), max_input_tokens=20000, prompt_version="motir-body-v1"),
        ai_ledger=tmp_path / "shared-ledger.sqlite3")


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-gemini-key-only-for-offline-tests")


def test_full_body_dispatch_cache_private_publication_and_readonly_consumption(tmp_path):
    source, args = case(tmp_path)
    opener = LocalOpener(packet())
    report = analyze_motir_document(**args, allow_paid=True, opener=opener)
    assert report["ai_status"] == "ANALYZED_UNVERIFIED"
    assert report["ai_analysis"]["schema_version"] == DOCUMENT_SCHEMA
    assert report["content_scope"] == "LICENSED_ARTICLE_TEXT"
    sent = json.loads(opener.requests[0].data)
    prompt = json.loads(sent["contents"][0]["parts"][0]["text"])
    content = json.loads(prompt["document"])
    assert "metadata" not in prompt and NEW.strip() in content["article_text"]
    assert not report["verified_new_economic_event"]
    assert report["source_available_at"] > source[5].archived_at.isoformat()
    assert "article_text" not in report
    second = analyze_motir_document(**args, allow_paid=True, opener=opener)
    assert second["ai_status"] == "CACHE_HIT" and opener.calls == 1
    assert second["ai_analysis"] == report["ai_analysis"]
    path, pin = publish_motir_document_analysis(second, tmp_path / "reports")
    assert consume_motir_document_analysis(path, pin) == second
    with sqlite3.connect(args["ai_ledger"]) as db:
        assert db.execute("SELECT count(*),count(settled_at) FROM ai_invocations").fetchone() == (1, 1)
    with pytest.raises(SourceShareError, match="SHA"):
        consume_motir_document_analysis(path, "0" * 64)
    with pytest.raises(SourceShareError):
        consume_motir_document_analysis(path, pin, now=datetime(2020, 1, 1, tzinfo=timezone.utc))


def test_prior_plan_no_automatic_call_but_existing_article_can_be_analyzed(tmp_path):
    _, args = case(tmp_path, PRIOR)
    opener = LocalOpener(packet())
    report = analyze_motir_document(**args, allow_paid=True, opener=opener)
    assert report["ai_status"] == "NOT_ELIGIBLE" and opener.calls == 0
    assert not args["ai_ledger"].exists()
    old = analyze_motir_document(**args, allow_paid=True, analyze_existing=True, opener=opener)
    assert old["ai_status"] == "ANALYZED_UNVERIFIED" and not old["ai_eligible"]
    assert not old["verified_new_economic_event"]


def test_revoked_rights_prevent_even_cached_result_access(tmp_path):
    _, args = case(tmp_path)
    opener = LocalOpener(packet())
    analyze_motir_document(**args, allow_paid=True, opener=opener)
    args["article_registry"] = ProviderRegistry(tuple(replace(p, approved=False) for p in args["article_registry"].providers))
    with pytest.raises(SourceShareError):
        analyze_motir_document(**args, allow_paid=True, opener=opener)
    assert opener.calls == 1


def test_wrong_binding_no_network_or_ledger(tmp_path):
    _, args = case(tmp_path)
    args["binding_sha256"] = "0" * 64
    opener = LocalOpener(packet())
    with pytest.raises(SourceShareError):
        analyze_motir_document(**args, allow_paid=True, opener=opener)
    assert opener.calls == 0 and not args["ai_ledger"].exists()


def test_long_body_not_silently_truncated_or_billed(tmp_path):
    _, args = case(tmp_path)
    args["model"] = replace(args["model"], max_input_tokens=1000)
    opener = LocalOpener(packet())
    result = analyze_motir_document(**args, allow_paid=True, opener=opener)
    assert result["ai_status"] == "DOCUMENT_INPUT_LIMIT_EXCEEDED"
    assert not result["article_text_truncated"]
    assert opener.calls == 0 and not args["ai_ledger"].exists()


def test_failed_billed_response_is_not_automatically_charged_again(tmp_path):
    _, args = case(tmp_path)
    opener = LocalOpener(b'not-json')
    first = analyze_motir_document(**args, allow_paid=True, opener=opener)
    second = analyze_motir_document(**args, allow_paid=True, opener=opener)
    assert first["ai_status"] == "AI_PROVIDER_OR_CACHE_UNAVAILABLE"
    assert second["ai_status"] == "AI_ALREADY_RESERVED_OR_RESULT_UNAVAILABLE"
    assert opener.calls == 1


def test_disabled_mode_has_no_provider_call(tmp_path):
    _, args = case(tmp_path)
    opener = LocalOpener(packet())
    assert analyze_motir_document(**args, opener=opener)["ai_status"] == "AI_DISABLED_BY_CONFIGURATION"
    assert opener.calls == 0


def test_metadata_contract_still_rejects_full_body(tmp_path):
    now = datetime.now(timezone.utc)
    req = AIRequest("a" * 64, "body\n" * 130, "OFFICIAL_METADATA", now, now, True, True)
    with pytest.raises(SourceShareError, match="metadata-only"):
        run_ai_analysis(config("GEMINI"), req)


def test_scheduler_document_failure_is_local_and_replay_never_pays(tmp_path):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"schema": "newscatalyst.motir_document_jobs.v1", "jobs": [
        {"bad": "row"}, {"binding_path": str(tmp_path / "binding.json"), "binding_sha256": "a" * 64,
            "archive_root": str(tmp_path / "archive"), "article_registry": str(tmp_path / "registry.json")}]}))
    tmp_path.chmod(0o700); jobs.chmod(0o600)
    opts = Namespace(document_jobs=jobs, analysis_root=tmp_path / "analysis",
        analysis_model_config=tmp_path / "model.json", allow_paid_ai=True, replay_only=True)
    seen = []
    def runner(args):
        seen.append(args)
        return 0, {"status": "MOTIR_DOCUMENT_ANALYSIS_READY", "new_ai_results": 0}
    code, result = scheduler._analyze_documents(opts, runner)
    assert code == 4 and len(result["results"]) == 2 and len(seen) == 1
    assert seen[0].allow_paid is False and seen[0].analyze_existing is False


def test_body_revision_gets_new_result_without_overwriting_first(tmp_path):
    first_root = tmp_path / "first"
    first_root.mkdir(mode=0o700)
    _, first = case(first_root)
    opener = LocalOpener(packet())
    old = analyze_motir_document(**first, allow_paid=True, opener=opener)
    second_root = tmp_path / "second"
    second_root.mkdir(mode=0o700)
    _, revised = case(second_root, NEW.replace("20조원", "21조원"))
    revised.update(analysis_root=first["analysis_root"], ai_ledger=first["ai_ledger"])
    new = analyze_motir_document(**revised, allow_paid=True, opener=opener)
    assert new["analysis_event_sha256"] != old["analysis_event_sha256"]
    assert opener.calls == 2
    assert analyze_motir_document(**first, allow_paid=True, opener=opener)["ai_analysis"] == old["ai_analysis"]
    assert opener.calls == 2


def test_direct_document_adapter_limits_checked_before_cost_reservation(tmp_path):
    from newscatalystos.ai_gemini_transport import run_budgeted_gemini_analysis
    now = datetime.now(timezone.utc)
    request = AIRequest("b" * 64, "허가된 본문" * 100, "LICENSED_DOCUMENT", now, now, True, True)
    ledger = tmp_path / "cost.sqlite3"
    opener = LocalOpener(packet())
    with pytest.raises(SourceShareError, match="token budget"):
        run_budgeted_gemini_analysis(replace(config("GEMINI"), max_input_tokens=1000),
            request, ledger, allow_paid=True, opener=opener)
    assert not ledger.exists() and opener.calls == 0


def test_scheduled_tick_runs_registered_document_after_title_analysis(tmp_path):
    from test_motir_sector_pipeline import config as options
    from test_motir_rss_post import registry
    opts = options(tmp_path)
    opts.skip_analysis = False
    opts.analysis_model_config = tmp_path / "model.json"
    opts.allow_paid_ai = True
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"schema": "newscatalyst.motir_document_jobs.v1", "jobs": [
        {"binding_path": str(tmp_path / "binding.json"), "binding_sha256": "a" * 64,
         "archive_root": str(tmp_path / "archive"), "article_registry": str(tmp_path / "registry.json")}]}))
    tmp_path.chmod(0o700); jobs.chmod(0o600); opts.document_jobs = jobs
    seen = []
    def document(args):
        seen.append(args)
        return 0, {"status": "MOTIR_DOCUMENT_ANALYSIS_READY", "new_ai_results": 1}
    code, result = scheduler.run_once(opts, registry_reader=lambda _: registry(),
        feed_runner=lambda _: (0, {"status": "NOT_DUE"}),
        analysis_runner=lambda _: (0, {"status": "FEED_ECONOMIC_ANALYSIS_READY"}),
        document_runner=document)
    assert code == 0 and result["new_ai_results"] == 1 and len(seen) == 1
    assert seen[0].allow_paid is True and seen[0].analyze_existing is False
