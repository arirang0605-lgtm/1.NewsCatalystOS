"""Exact article/firm quote, reusing saved SHA/PIT source extraction."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from newscatalystos.federated_news_search import search_completed_workspaces
from newscatalystos.news_search_evidence import saved_article_evidence
from newscatalystos.news_article_company_context import (
    article_company_context, article_company_excerpt,
)
from scripts.open_research_dashboard import DashboardServer
from scripts.run_feed_triage import _registry
from test_company_evidence import rss
from test_federated_news_search import fingerprint


def _context(tmp_path):
    theme, args, pub, report, info, store = rss(tmp_path)
    article = search_completed_workspaces(
        (info[0],), "HBM", registry_reader=_registry)["results"][0]
    detail = saved_article_evidence(article, store.root,
                                    as_of=args["as_of"], now=args["now"])
    detail["article_company_context"] = article_company_context(
        detail, store.root, as_of=args["as_of"], now=args["now"])
    candidates = [p for t in detail["article_company_context"]["themes"]
                  for p in t["direct_parties"] if p["entity_id"] == "가상전자"]
    assert len(candidates) == 1
    return detail, candidates[0], theme, args, info, store, article


def test_exact_article_quote_and_missing_other_company_are_read_only(tmp_path):
    detail, party, theme, args, info, store, article = _context(tmp_path)
    before = fingerprint(tmp_path)
    selected = dict(theme_id=theme["theme_id"], entity_id=party["entity_id"],
                    claim_event_id=party["event_id"],
                    evidence_sha256=party["evidence_sha256"],
                    theme_root=store.root, reports_root=args["reports_root"],
                    document_root=args["document_root"], feeds=args["feeds"],
                    jobs=[], now=args["now"], as_of=args["as_of"])
    out = article_company_excerpt(detail, **selected)
    assert out["status"] == "READY" and out["content_scope"] == "RSS_TITLE_METADATA"
    assert "가상전자" in out["excerpt"] and "새빛소재" not in out["excerpt"]
    assert "DRAM" not in out["excerpt"]
    assert out["excerpt_sha256"] == sha256(out["excerpt"].encode()).hexdigest()
    assert out["source_url"] == article["source_url"]
    assert not out["verified_real_transaction"] and not out["verified_real_benefit"]

    for change in (
        dict(evidence_sha256="f" * 64),
        dict(claim_event_id="f" * 64),
        dict(entity_id="다른기업"),
        dict(theme_id="f" * 64),
    ):
        result = article_company_excerpt(detail, **{**selected, **change})
        assert result["status"] == "N/A" and result["excerpt"] is None
    early = args["as_of"] - timedelta(seconds=1)
    assert article_company_excerpt(
        detail, **{**selected, "as_of": early})["status"] == "N/A"
    assert fingerprint(tmp_path) == before


def test_http_news_excerpt_expands_exact_company_only(tmp_path, monkeypatch):
    detail, party, theme, args, info, store, article = _context(tmp_path)
    import newscatalystos.company_evidence as module
    monkeypatch.setattr(module, "installed_sources", lambda _base: (args["feeds"], []))
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return args["now"]
    monkeypatch.setattr("scripts.open_research_dashboard.datetime", Clock)
    server = DashboardServer(0, args["reports_root"], tmp_path/"notes",
                             args["document_root"],
                             news_search_workspaces=(info[0],))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    before = fingerprint(tmp_path)
    query = dict(q="HBM", provider_id=article["provider_id"],
                 event_id=article["event_id"], title_sha256=article["title_sha256"],
                 excerpt_theme_id=theme["theme_id"],
                 excerpt_entity_id=party["entity_id"],
                 excerpt_claim_event_id=party["event_id"],
                 excerpt_evidence_sha256=party["evidence_sha256"])
    def get(params):
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/news-evidence?"
                     +urlencode(params), timeout=15) as response:
            return response.status, json.load(response)
    try:
        code, response = get(query)
        result = response["article_company_excerpt"]
        assert code == 200 and result["status"] == "READY"
        assert "가상전자" in result["excerpt"] and "새빛소재" not in result["excerpt"]
        assert response["article_company_context"]["status"] == "READY"
        _, wrong = get({**query, "excerpt_claim_event_id": "f"*64})
        assert wrong["article_company_excerpt"]["status"] == "N/A"
        assert wrong["article_company_excerpt"]["excerpt"] is None
        try:
            get({**query, "excerpt_evidence_sha256": "bad"})
            assert False, "tampered excerpt SHA accepted"
        except HTTPError as error:
            assert error.code == 400
    finally:
        server.shutdown();server.server_close();thread.join(2)
    assert fingerprint(tmp_path) == before


def test_licensed_motir_body_extracts_only_approved_company_quote(tmp_path):
    from test_company_evidence import body
    from newscatalystos.theme_emergence import ThemeStore

    theme, args, binding = body(tmp_path)
    ref = next(r for r in theme["source_refs"] if "가상전자" in r["entity_ids"])
    detail = {
        "source": {
            "provider_id": "motir-official-press",
            "event_id": binding["source_event_sha256"],
            "title_sha256": binding["title_sha256"],
            "source_url": binding["source_url"],
            "source_available_at": binding["rss_first_seen_at"],
        },
        "status": "N/A", "themes": [],
        "official_document_evidence": {
            "status": "READY", "document_sha256": binding["document_sha256"],
            "themes": [{
                "theme_id": theme["theme_id"], "name": theme["provisional_name"],
                "status": theme["status"], "decision_at": theme["decision_at"],
                "events": [{
                    "event_id": ref["event_id"], "source_url": ref["source_url"],
                    "source_available_at": ref["source_available_at"],
                    "recorded_at": ref["recorded_at"], "action": ref["action"],
                    "phase": ref["phase"], "evidence_level": ref["evidence_level"],
                    "polarity": ref["polarity"], "active_in_theme": True,
                    "content_scope": "LICENSED_ARTICLE_TEXT",
                }],
            }],
        },
    }
    theme_root = args["document_root"] / "theme_history"
    detail["article_company_context"] = article_company_context(
        detail, theme_root, as_of=args["as_of"], now=args["now"])
    group, = detail["article_company_context"]["themes"]
    actor, = group["direct_parties"]
    kwargs = dict(
        theme_id=group["theme_id"], entity_id=actor["entity_id"],
        claim_event_id=actor["event_id"],
        evidence_sha256=actor["evidence_sha256"],
        theme_root=theme_root, reports_root=args["reports_root"],
        document_root=args["document_root"], feeds=[], jobs=args["jobs"],
        as_of=args["as_of"], now=args["now"],
    )
    out = article_company_excerpt(detail, **kwargs)
    assert out["status"] == "READY"
    assert out["content_scope"] == "LICENSED_ARTICLE_TEXT"
    assert "가상전자" in out["excerpt"]
    assert "새빛소재" not in out["excerpt"]
    assert not out["verified_real_benefit"]
    # Current licensing always overrides an otherwise matching old SHA proof.
    registry = args["jobs"][0]["article_registry"]
    settings = json.loads(registry.read_bytes())
    settings["providers"][0]["approved"] = False
    registry.write_text(json.dumps(settings))
    unavailable = article_company_excerpt(detail, **kwargs)
    assert unavailable["status"] == "N/A" and unavailable["excerpt"] is None
