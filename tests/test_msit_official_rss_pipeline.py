"""New public MSIT RSS: one existing collector -> screen -> theme -> saved search.

Uses a large synthetic publisher-shaped feed, with no network/AI or real article
bodies. The original private collector/database are never loaded or changed.
"""
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from hashlib import sha256
import json

from newscatalystos.new_source_adapter import MAX_FEED_BYTES, parse_authorized_feed
from newscatalystos.provider_registry import parse_provider_registry
from newscatalystos.federated_news_search import TitleSearchWorkspace, search_completed_workspaces
from newscatalystos.theme_emergence import ThemeStore
from scripts.run_feed_triage import _registry
from scripts import run_scheduled_triage
from test_federated_news_search import fingerprint

CONFIG = Path(__file__).resolve().parent.parent / "config/msit_rss_metadata_registry.json"


def official_shape_feed():
    # The real official press RSS is ~823KB, with a large content:encoded
    # body per item. Its body is NEVER used in the committed metadata pipeline.
    chunks = ['<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0"><channel>']
    for i in range(50):
        title = ("가온반도체, HBM 수요 증가로 1조원 공급계약 체결"
                 if i == 0 else f"정부 연구정책 발표 {i}")
        url = f"https://www.msit.go.kr/bbs/view.do?sCode=user&amp;bbsSeqNo=94&amp;nttSeqNo={3100000+i}"
        chunks.append("<item><title>"+escape(title)+"</title><link>"+url+"</link>"+
                      "<pubDate>2026.10.17</pubDate>"+
                      "<content:encoded>"+("NONPERSISTED_BODY_MARKER_"+"x"*15800)+
                      "</content:encoded></item>")
    chunks.append("</channel></rss>")
    raw="".join(chunks).encode()
    assert 128*1024 < len(raw) < MAX_FEED_BYTES
    return raw


def test_official_msit_press_large_rss_to_saved_economic_theme_and_search(tmp_path, monkeypatch):
    from newscatalystos import incremental_ingest

    config = CONFIG.read_bytes()
    reg = parse_provider_registry(config)
    assert reg.approved_ids() == ("msit-official-press","msit-official-rnd-policy")
    assert all(not r.allow_full_text_storage for r in reg.providers)
    raw = official_shape_feed()
    source = "msit-official-press"
    current = datetime.now(timezone.utc)
    parsed = parse_authorized_feed(reg, source, raw, observed_at=current)
    assert len(parsed)==50
    assert parsed[0].headline.startswith("가온반도체")
    assert all(x.reported_published_at is None for x in parsed)
    assert "NONPERSISTED_BODY_MARKER_" not in repr(parsed)

    root = tmp_path / "isolated"
    private = root / "providers"
    private.mkdir(mode=0o700,parents=True)
    registry=private / "authorized_sources.json"
    registry.write_bytes(config);registry.chmod(0o600)
    payload=official_shape_feed()
    calls=[]
    def approved_transport(registry_obj,provider_id,*,at=None):
        assert provider_id == source
        assert registry_obj.active(provider_id).endpoint.endswith("bbsSeqNo=94")
        calls.append(provider_id)
        return parse_authorized_feed(registry_obj,provider_id,payload,
                                     observed_at=datetime.now(timezone.utc))
    monkeypatch.setattr(incremental_ingest,"fetch_authorized_once",approved_transport)
    args=[
        "--registry",str(registry),"--provider-id",source,
        "--state",str(root/"state/incremental_feeds.sqlite3"),
        "--dedup-state",str(root/"state/dedup.sqlite3"),
        "--inbox-root",str(root/"inbox/feed_triage"),
        "--output-root",str(root/"triage"),
        "--analysis-root",str(root/"feed_analysis/core"),
        "--analysis-theme-root",str(root/"document_analysis/theme_history"),
        "--once",
    ]
    options=run_scheduled_triage.parser().parse_args(args)
    code,report=run_scheduled_triage.execute(options)
    assert code==0 and report["providers_failed"]==report["analysis_providers_failed"]==0
    assert report["analyzed_rows"]==50 and report["ai_call_count"]==0
    outcome=report["providers"][0]
    assert outcome["status"]=="FEED_METADATA_TRIAGE_READY"
    assert outcome["semiconductor_keyword_candidates"]==1
    assert outcome["analysis"]["status"]=="FEED_ECONOMIC_ANALYSIS_READY"
    assert calls==[source]
    saved=Path(outcome["analysis"]["private_report_file"])
    raw_report=saved.read_bytes()
    assert sha256(raw_report).hexdigest()==outcome["analysis"]["report_sha256"]
    assert b"NONPERSISTED_BODY_MARKER_" not in raw_report
    report_rows=json.loads(raw_report)["results"]
    assert len(report_rows)==50
    assert not any(row["verified_beneficiary"] for row in report_rows)
    assert sum(bool(row["economic_changes"]) for row in report_rows)>=1
    themes=ThemeStore(root/"document_analysis/theme_history").search(now=datetime.now(timezone.utc))
    assert any("SEMICONDUCTOR" in theme["industry_tags"] for theme in themes)
    workspace=TitleSearchWorkspace("msit",registry,root/"state/incremental_feeds.sqlite3",
                                   root/"inbox/feed_triage")
    found=search_completed_workspaces((workspace,),"HBM",registry_reader=_registry)
    assert len(found["results"])==1
    # R&D is also approved but has not yet completed a fixture poll.
    # One missing provider is explicit partial coverage, not fabricated full search.
    assert not found["coverage_complete"]
    assert "msit-official-rnd-policy" in found["scopes"][0]["missing_approved_provider_ids"]
    assert found["results"][0]["headline"].startswith("가온반도체")
    assert found["results"][0]["article_body_included"] is False
    for path in root.rglob("*"):
        if path.is_file():
            assert b"NONPERSISTED_BODY_MARKER_" not in path.read_bytes()

    first=ThemeStore(root/"document_analysis/theme_history").search(now=datetime.now(timezone.utc))
    code,again=run_scheduled_triage.execute(options)
    assert code==0 and again["providers"][0]["status"]=="NOT_DUE"
    assert calls==[source]  # Once-per-hour budget, no inline or second network call.
    second=ThemeStore(root/"document_analysis/theme_history").search(now=datetime.now(timezone.utc))
    assert len(first)==len(second)
