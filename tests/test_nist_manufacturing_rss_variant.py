"""NIST's two official RSS categories share one provider budget and event IDs.

The public manufacturing feed is NOT a second independent witness. Reuse the
existing ACK, private state and title search; source body is never saved.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newscatalystos.incremental_ingest import state_snapshot
from newscatalystos.federated_news_search import search_completed_workspaces
from newscatalystos.provider_registry import ProviderRegistry, parse_provider_registry
from newscatalystos.economic_changes import official_us_chips_award_change
from scripts.run_feed_triage import _registry
from scripts.run_scheduled_triage import _approved_feed_variant, parser
from test_federated_news_search import collect, setup_workspace, write_registry

ROOT=Path(__file__).resolve().parent.parent
PROVIDER="nist-official-electronics"
MAIN=ROOT/"config/nist_electronics_rss_metadata_registry.json"
ALT=ROOT/"config/nist_manufacturing_rss_same_provider_registry.json"


def test_two_nist_official_feeds_have_one_valid_permitted_owner():
    primary=parse_provider_registry(MAIN.read_bytes())
    manufacturing=parse_provider_registry(ALT.read_bytes())
    assert primary.approved_ids()==manufacturing.approved_ids()==(PROVIDER,)
    a,b=primary.providers[0],manufacturing.providers[0]
    assert a.endpoint=="https://www.nist.gov/news-events/electronics/rss.xml"
    assert b.endpoint=="https://www.nist.gov/news-events/manufacturing/rss.xml"
    assert a.rights_reference==b.rights_reference=="https://www.nist.gov/copyrights-disclaimers"
    for field in ("method","kind","grant","hourly_limit","approved","allow_full_text_storage","expires_at"):
        assert getattr(a,field)==getattr(b,field)
    assert a.hourly_limit==1 and a.method=="RSS"
    assert not a.allow_full_text_storage
    # MEP program events are NOT semiconductor finance facts.
    assert not official_us_chips_award_change(
        "NIST Awards More Than $30 Million for MEP Centers in 11 States and Puerto Rico")


def test_one_nist_publisher_receipt_rotates_and_deduplicates_overlap(tmp_path):
    first,last=(parse_provider_registry(p.read_bytes()).providers[0] for p in (MAIN,ALT))
    now=datetime.now(timezone.utc)
    reviewed=now-timedelta(days=1)
    a=ProviderRegistry((replace(first,reviewed_at=reviewed),))
    b=ProviderRegistry((replace(last,reviewed_at=reviewed),))
    w=setup_workspace(tmp_path,"nist",a)
    next_registry=w.registry_path.with_name("manufacturing.json")
    write_registry(next_registry,b)
    opts=parser().parse_args([
      "--once","--registry",str(w.registry_path),
      "--alternate-registry",str(next_registry),
      "--provider-id",PROVIDER,
      "--state",str(w.poll_state),
      "--inbox-root",str(w.inbox_root),
      "--skip-analysis"
    ])
    root="https://www.nist.gov/news-events/news/2026/10/"
    t1=now-timedelta(hours=3)
    collect(w,a,PROVIDER,[("same","Second Semiconductor Traceability Workshop",
                          root+"semiconductor-traceability")],at=t1)
    target,variant=_approved_feed_variant(
        opts,(PROVIDER,),_registry(w.registry_path),
        datetime.now(timezone.utc),_registry)
    assert target==next_registry and variant=="alternate"
    collect(w,b,PROVIDER,[
        ("same","Second Semiconductor Traceability Workshop",
         root+"semiconductor-traceability"),
        ("new-me","NIST Joins White House Effort to Drive Science",
         root+"science-new")
    ],at=t1+timedelta(hours=1,seconds=3))
    target,variant=_approved_feed_variant(
        opts,(PROVIDER,),_registry(w.registry_path),
        datetime.now(timezone.utc),_registry)
    assert target==w.registry_path and variant=="primary"
    assert state_snapshot(w.poll_state,PROVIDER)["seen_count"]==2
    out=search_completed_workspaces((w,),"Semiconductor",registry_reader=_registry)
    assert out["coverage_complete"] and out["searched_document_versions"]==2
    assert len(out["results"])==1
    assert out["results"][0]["article_body_included"] is False
