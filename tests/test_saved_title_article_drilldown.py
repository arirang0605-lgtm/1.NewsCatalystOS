"""Exact approved title -> already-published RSS economic changes -> search detail."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import threading
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

from newscatalystos.feed_analysis import analyze_completed_feed, publish_feed_analysis
from newscatalystos.research_dashboard import saved_title_analysis
from scripts.open_research_dashboard import DashboardServer
from scripts.run_feed_triage import _registry
from test_federated_news_search import sample, fingerprint
from test_saved_article_evidence import connected


def _saved_case(connected, tmp_path):
    workspaces, article, themes_root, _ = connected
    source = next(w for w in workspaces if w.scope == article["search_scope"])
    analysis = analyze_completed_feed(
        _registry(source.registry_path), source.inbox_root, source.poll_state,
        tmp_path / "derived",
        provider_id=article["provider_id"], limit=100, now=datetime.now(timezone.utc),
    )
    matched = [r for r in analysis["results"]
               if (r["source_event_sha256"], r["source_title_sha256"])
               == (article["event_id"], article["title_sha256"])]
    assert len(matched) == 1 and len(matched[0]["economic_changes"]) == 2
    pub, digest = publish_feed_analysis(analysis, tmp_path / "reports/core/reports")
    assert sha256(pub.read_bytes()).hexdigest() == digest
    return workspaces, article, themes_root, matched[0], digest


def test_article_click_shows_original_saved_economic_actions_not_only_theme(connected, tmp_path, monkeypatch):
    import newscatalystos.feed_transport as transport
    monkeypatch.setattr(transport, "fetch_authorized_once",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("fetch")))
    workspaces, article, themes_root, original, report_sha = _saved_case(connected, tmp_path)
    assert original["ai_status"] == "NOT_ELIGIBLE"
    assert saved_title_analysis(article, tmp_path / "reports")["status"] == "READY"
    server = DashboardServer(0, tmp_path / "reports", tmp_path / "notes",
                             themes_root.parent, news_search_workspaces=workspaces)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    before = fingerprint(tmp_path)
    try:
        qs = urlencode({"q": "가상전자", **{k: article[k]
                       for k in ("provider_id", "event_id", "title_sha256")}})
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/news-evidence?"+qs) as r:
            body = json.load(r)
            assert r.status == 200
        saved = body["saved_title_analysis"]
        assert saved["status"] == "READY" and saved["reason_code"] is None
        assert saved["report_sha256"] == report_sha
        assert saved["content_scope"] == "RSS_TITLE_METADATA"
        assert saved["economic_change_status"] == "READY"
        assert {x["action"] for x in saved["economic_changes"]} == {
            "DELIVERY_START", "MARKET_ENTRY"}
        assert all(x["source_paragraph_sha256"] == article["title_sha256"]
                   and x["evidence_level"] == "REPORTED"
                   for x in saved["economic_changes"])
        assert all(x["entity_ids"] == ["가상전자"] for x in saved["economic_changes"])
        assert not saved["verified_economic_fact"] and not saved["confirmed_beneficiary"]
        assert body["status"] == "READY" and body["themes"]
        assert not body.get("official_document_evidence")
    finally:
        server.shutdown(); server.server_close(); thread.join(3)
    assert fingerprint(tmp_path) == before


def test_pit_or_wrong_version_does_not_inherit_later_or_unrelated_report(connected, tmp_path):
    _, article, _, original, _ = _saved_case(connected, tmp_path)
    now = datetime.now(timezone.utc)
    assert saved_title_analysis(article, tmp_path / "reports", now=now)["status"] == "READY"
    before = datetime.fromisoformat(original["analysis_available_at"]) - timedelta(microseconds=1)
    prior = saved_title_analysis(article, tmp_path / "reports", as_of=before, now=now)
    assert prior["status"] == "N/A" and not prior["economic_changes"]
    forged = {**article, "headline": "같은 키워드의 다른 판본"}
    missing = saved_title_analysis(forged, tmp_path / "reports", now=now)
    assert missing["status"] == "N/A" and missing["reason_code"] == "NO_EXACT_SAVED_TITLE_ANALYSIS"
    forged = {**article, "title_sha256": "f" * 64}
    assert saved_title_analysis(forged, tmp_path / "reports", now=now)["status"] == "N/A"
    assert saved_title_analysis(article, tmp_path / "missing", now=now)["status"] == "N/A"
