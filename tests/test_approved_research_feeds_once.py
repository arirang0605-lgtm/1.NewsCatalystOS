"""One existing approved-crawler tick across three private research workspaces.

Real committed ACK -> rules -> ThemeStore, only transport mocked. No new
collection engine, background daemon, paid AI, article body or EraLeader API.
"""
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from newscatalystos import incremental_ingest
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.feed_analysis import analyze_completed_feed
from newscatalystos.source_share import SourceShareError
from scripts.run_approved_research_feeds_once import (
    execute, parser, FEEDS, WORKSPACES
)
from test_federated_news_search import fingerprint

PROJECT=Path(__file__).resolve().parent.parent


def _setup(tmp_path):
    root=tmp_path/"approved"
    root.mkdir(mode=0o700)
    defs={
        "msit":("msit_rss_metadata_registry.json",None),
        "company":("semiconductor_company_rss_metadata_registry.json",
                   ("skhynix_press_rss_same_provider_registry.json",
                    "skhynix_press_variant_authorized_sources.json")),
        "nist":("nist_electronics_rss_metadata_registry.json",
                ("nist_manufacturing_rss_same_provider_registry.json",
                 "nist_manufacturing_variant_authorized_sources.json")),
    }
    for scope,(filename,other) in defs.items():
        workspace=root/WORKSPACES[scope]
        providers=workspace/"providers"
        providers.mkdir(parents=True,mode=0o700)
        providers.chmod(0o700)
        (providers/"authorized_sources.json").write_bytes(
            (PROJECT/"config"/filename).read_bytes())
        (providers/"authorized_sources.json").chmod(0o600)
        if other:
            source, name=other
            (providers/name).write_bytes((PROJECT/"config"/source).read_bytes())
            (providers/name).chmod(0o600)
        workspace.chmod(0o700)
    return root


def _sample(provider):
    title,link={
        "msit-official-press":(
            "반도체 신기술 정부 발표","https://www.msit.go.kr/news/report-1"),
        "msit-official-rnd-policy":(
            "국가 기술 연구 정책 발표","https://www.msit.go.kr/news/report-2"),
        "samsung-newsroom-korea":(
            "삼성전자, 신규 칩 기술 소개","https://news.samsung.com/kr/research-1"),
        "skhynix-newsroom-korea":(
            "SK하이닉스, 용인 Y2 청주 M17에 54조 원 투자... "
            "AI 메모리 수요 대응 생산 기반 확보",
            "https://news.skhynix.co.kr/production-investment"),
        "nist-official-electronics":(
            "Department of Commerce Announces Definitive Agreement with "
            "SandboxAQ for a $500 Million CHIPS R&D Award to Accelerate "
            "Al-Driven Semiconductor Materials Discovery",
            "https://www.nist.gov/news-events/news/2026/10/chips-award"),
    }[provider]
    return (f"<rss version='2.0'><channel>"
            f"<item><guid>{escape(provider)}-1</guid>"
            f"<title>{escape(title)}</title><link>{escape(link)}</link>"
            "<description>UNLICENSED_FULL_BODY_MARKER</description></item>"
            "</channel></rss>").encode()


def test_five_actual_approved_pipelines_run_then_not_due_with_one_budget(tmp_path,monkeypatch):
    root=_setup(tmp_path)
    calls=[]
    def read(registry,provider,*,at=None):
        calls.append(provider)
        return parse_authorized_feed(registry,provider,_sample(provider),
               observed_at=at or datetime.now(timezone.utc))
    monkeypatch.setattr(incremental_ingest,"fetch_authorized_once",read)
    before=fingerprint(root)
    flags=["--workspaces-root",str(root)]
    rc,dry=execute(parser().parse_args([*flags,"--dry-run"]))
    assert rc==0 and dry["sources_checked"]==5 and dry["sources_failed"]==0
    assert not calls and fingerprint(root)==before
    rc,one=execute(parser().parse_args([*flags,"--once"]))
    assert rc==0 and one["sources_failed"]==0
    assert one["sources_checked"]==len(FEEDS)==len(calls)==5
    assert len(set(calls))==5
    assert one["new_articles"]==5
    assert one["ai_calls"]==one["stored_article_bodies"]==0
    assert one["era_api_calls"]==0
    assert sum(x["economic_changes"] for x in one["providers"])>=1
    assert all(x["analysis_status"]=="FEED_ECONOMIC_ANALYSIS_READY"
               for x in one["providers"])
    assert all(x["status"]=="FEED_METADATA_TRIAGE_READY" for x in one["providers"])
    assert not any("UNLICENSED_FULL_BODY_MARKER" in x.read_text(errors="ignore")
                   for x in root.rglob("*.json"))
    rc,not_due=execute(parser().parse_args([*flags,"--once"]))
    assert rc==0 and not_due["new_articles"]==0 and len(calls)==5
    assert {x["status"] for x in not_due["providers"]}=={"NOT_DUE"}
    rc,replay=execute(parser().parse_args([*flags,"--replay-only"]))
    assert rc==0 and len(calls)==5
    assert replay["sources_failed"]==0 and replay["new_articles"]==0
    assert sum(x["analyzed_rows"] for x in replay["providers"])==5
    assert replay["ai_calls"]==0


def test_one_failed_source_cannot_stop_other_four(tmp_path,monkeypatch):
    root=_setup(tmp_path)
    calls=[]
    def read(registry,provider,*,at=None):
        calls.append(provider)
        if provider=="msit-official-press":
            raise SourceShareError("simulated single-source connection error")
        return parse_authorized_feed(registry,provider,_sample(provider),
               observed_at=at or datetime.now(timezone.utc))
    monkeypatch.setattr(incremental_ingest,"fetch_authorized_once",read)
    rc,summary=execute(parser().parse_args([
        "--workspaces-root",str(root),"--once"]))
    assert rc==4 and summary["sources_failed"]==1,",".join(x["provider_id"]+"/"+x.get("analysis_status","")+"/"+x.get("status","") for x in summary["providers"] if x["failed"])
    assert len(calls)==5 and summary["new_articles"]==4
    assert summary["providers"][0]["failed"] is True
    assert all(not x["failed"] for x in summary["providers"][1:])
    assert summary["ai_calls"]==0 and summary["era_api_calls"]==0
