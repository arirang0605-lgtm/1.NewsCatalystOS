"""NIST's approved government RSS -> CHIP award actions -> firm and theme.

Use a synthetic feed shaped like the public NIST RSS. All publications retain
their first local observation time, not the issuer's pre-existing pubDate.
No article bodies, real network requests, paid AI or inferred cash receipt.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from xml.sax.saxutils import escape
import json

import pytest

from newscatalystos.economic_changes import official_us_chips_award_change
from newscatalystos.feed_triage import _matched_terms
from newscatalystos.federated_news_search import TitleSearchWorkspace, search_completed_workspaces
from newscatalystos.new_source_adapter import parse_authorized_feed
from newscatalystos.provider_registry import parse_provider_registry
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.news_search_evidence import saved_article_evidence
from newscatalystos.news_article_company_context import article_company_context, article_company_excerpt
from scripts.run_feed_triage import _registry
from scripts import run_scheduled_triage as scheduled

CONFIG = (Path(__file__).resolve().parent.parent /
          "config/nist_electronics_rss_metadata_registry.json")
PROVIDER = "nist-official-electronics"
AWARDS = (
    "Department of Commerce Announces Finalization of CHIPS Incentives with Powerex "
    "to Enhance Domestic Production Capacity of Key Components for U.S. Semiconductor Manufacturing",
    "Department of Commerce Announces Agreement with GlobalFoundries to Amend Its Existing "
    "CHIPS Program Award and Reallocate $955 Million to Accelerate Investments in Silicon "
    "Photonics, Silicon-Germanium, and Advanced Packaging",
    "Department of Commerce Announces Definitive Agreement with SandboxAQ for a $500 Million "
    "CHIPS R&D Award to Accelerate Al-Driven Semiconductor Materials Discovery",
    "Department of Commerce Announces Direct Funding Agreement with Bosch for a $225 Million "
    "CHIPS Program Award to Support Domestic Production of Silicon Carbide Semiconductors",
    "Department of Commerce Announces Definitive Agreement with I-Pulse for a $250 Million "
    "CHIPS R&D Award to Develop Novel Silicon-Carbide Semiconductors",
)
REJECT = (
    "Department of Commerce Announces Finalization of CHIPS R&D Award with D-Wave",
    "Department of Commerce Announces Letters of Intent With 7 Companies for $874 Million "
    "to Accelerate Semiconductor R&D for the Compute Supply Chain",
    "Department of Commerce Announces Agreement with GlobalFoundries to Amend CHIPS "
    "Program Award for Quantum Technology",
    "University Announces Definitive Agreement with Bosch for CHIPS Semiconductor Award",
    "Department of Commerce Denies Definitive Agreement with Bosch for Semiconductor CHIPS Award",
)


def _rss():
    lines=["<rss version='2.0'><channel>"]
    for n,title in enumerate((*AWARDS,*REJECT)):
        lines.append(
            f"<item><guid>https://www.nist.gov/node/{n+5000}</guid>"
            f"<title>{escape(title)}</title>"
            f"<link>https://www.nist.gov/news-events/news/2026/10/nist-source-{n}</link>"
            "<description>NO_SAVED_BODY_PAYLOAD_MARKER</description>"
            "<pubDate>Wed, 14 Oct 2026 12:00:00 +0000</pubDate></item>")
    lines.append("</channel></rss>")
    return "".join(lines).encode()


def test_narrow_nist_chips_financing_phases_and_no_false_sector_claims():
    assert all(len(s)<=256 for s in AWARDS + REJECT)
    for title in AWARDS:
        changes=official_us_chips_award_change(title)
        assert len(changes)==1, title
        change=changes[0]
        assert change["action"]=="POLICY_CHANGE"
        assert change["economic_driver"]=="POLICY_ENABLEMENT"
        assert change["industry_tags"]==["SEMICONDUCTOR"]
        assert len(change["entity_ids"])==1
        assert change["verified_economic_effect"] is False
        assert change["source_paragraph_sha256"]==sha256(title.encode()).hexdigest()
    # Legacy keyword receipts are immutable: an official, explicit policy
    # action must still be detected when a generic title tokenizer missed it.
    assert not _matched_terms(AWARDS[1])
    assert official_us_chips_award_change(AWARDS[1])[0]["phase"]=="PLANNED"
    assert all(official_us_chips_award_change(title)[0]["phase"]=="SOURCE_REPORTED"
               for i,title in enumerate(AWARDS) if i!=1)
    assert all(not official_us_chips_award_change(title) for title in REJECT)
    assert not official_us_chips_award_change(
        "Department of Commerce Announces Letter of Intent with Company "
        "for Semiconductor CHIPS Award")  # future commitment, but no approved template
    assert not official_us_chips_award_change("CHIPS Program Award with GlobalFoundries")


def test_approved_official_nist_feed_reaches_saved_policy_and_actor(tmp_path,monkeypatch):
    from newscatalystos import incremental_ingest
    reg=parse_provider_registry(CONFIG.read_bytes())
    assert reg.approved_ids()==(PROVIDER,)
    assert not reg.providers[0].allow_full_text_storage
    raw=_rss()
    received=[]
    def fetch(current, name, *, at=None):
        assert current.active(name).endpoint=="https://www.nist.gov/news-events/electronics/rss.xml"
        received.append(name)
        return parse_authorized_feed(current,name,raw,
                                     observed_at=at or datetime.now(timezone.utc))
    monkeypatch.setattr(incremental_ingest,"fetch_authorized_once",fetch)
    base=tmp_path/"nist"
    for folder in (base/"providers",base/"state"):
        folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    registry=base/"providers/authorized_sources.json"
    registry.write_bytes(CONFIG.read_bytes())
    registry.chmod(0o600)
    opts=scheduled.parser().parse_args([
       "--once","--registry",str(registry),"--provider-id",PROVIDER,
       "--state",str(base/"state/incremental_feeds.sqlite3"),
       "--dedup-state",str(base/"state/dedup.sqlite3"),
       "--inbox-root",str(base/"inbox/feed_triage"),
       "--output-root",str(base/"triage"),
       "--analysis-root",str(base/"feed_analysis/core"),
       "--analysis-theme-root",str(base/"document_analysis/theme_history"),
       "--analysis-limit","100",
    ])
    code,report=scheduled.execute(opts)
    assert code==0 and received==[PROVIDER]
    assert not report["providers_failed"] and not report["analysis_providers_failed"]
    assert report["analyzed_rows"]==len(AWARDS+REJECT)
    assert report["ai_call_count"]==report["stored_article_body_count"]==0
    done=report["providers"][0]["analysis"]
    assert done["economic_changes_count"]==len(AWARDS)
    assert done["theme_versions_created"]>=2
    saved=Path(done["private_report_file"])
    assert sha256(saved.read_bytes()).hexdigest()==done["report_sha256"]
    assert "NO_SAVED_BODY_PAYLOAD_MARKER" not in saved.read_text()
    rows,_=scan_saved_analysis(tmp_path/"other",additional_roots=(("nist",base/"feed_analysis"),))
    assert len(rows)==len(AWARDS+REJECT)
    assert sum(bool(x["economic_changes"]) for x in rows)==len(AWARDS)
    assert sum(x["priority"]=="HIGH_PRIORITY_CANDIDATE" for x in rows)==len(AWARDS)
    assert all(not x["verified_beneficiary"]
               for x in json.loads(saved.read_bytes())["results"])
    assert all(x["scope"]=="nist" for x in rows)
    themes=ThemeStore(base/"document_analysis/theme_history").search(now=datetime.now(timezone.utc))
    assert len(themes)>=2
    assert any("GlobalFoundries" in t["entity_ids"] for t in themes)

    w=TitleSearchWorkspace("nist",registry,base/"state/incremental_feeds.sqlite3",
                           base/"inbox/feed_triage")
    found=search_completed_workspaces((w,),"GlobalFoundries",registry_reader=_registry)
    assert found["coverage_complete"] and len(found["results"])==2  # one award, one rejected
    award=next(x for x in found["results"] if "Silicon Photonics" in x["headline"])
    result=saved_article_evidence(award,base/"document_analysis/theme_history",
                                  now=datetime.now(timezone.utc))
    assert result["status"]=="READY"
    context=article_company_context(result,base/"document_analysis/theme_history",
                                    now=datetime.now(timezone.utc))
    assert context["status"]=="READY"
    people=[c for t in context["themes"] for c in t["direct_parties"]]
    assert len(people)==1 and people[0]["source_name"]=="GlobalFoundries"
    assert people[0]["benefit_status"]=="UNVERIFIED"
    selected=next(group for group in context["themes"] if group["direct_parties"])
    party=people[0]
    exact=dict(theme_id=selected["theme_id"],entity_id=party["entity_id"],
               claim_event_id=party["event_id"],evidence_sha256=party["evidence_sha256"],
               theme_root=base/"document_analysis/theme_history",
               reports_root=base/"feed_analysis",document_root=base/"document_analysis",
               feeds=[{"registry":registry,"inbox":w.inbox_root,"state":w.poll_state}],
               jobs=[],now=datetime.now(timezone.utc))
    citation=article_company_excerpt({**result,"article_company_context":context},**exact)
    assert citation["status"]=="READY"
    assert "GlobalFoundries" in citation["excerpt"]
    assert citation["content_scope"]=="RSS_TITLE_METADATA"
    assert not citation["verified_real_transaction"]
    assert not citation["verified_real_benefit"]
    forged=article_company_excerpt({**result,"article_company_context":context},
                                  **{**exact,"evidence_sha256":"f"*64})
    assert forged["status"]=="N/A" and forged["excerpt"] is None

    code,again=scheduled.execute(opts)
    assert code==0 and again["providers"][0]["status"]=="NOT_DUE"
    assert received==[PROVIDER]  # no second official request within an hour
    for file in base.rglob("*"):
        if file.is_file():
            assert b"NO_SAVED_BODY_PAYLOAD_MARKER" not in file.read_bytes()


# These titles already exist as completed, version-pinned NIST RSS metadata.
# The agency reports a commitment or intent; completion/payments are NOT facts.
ADDITIONAL_REPORTS = (
    ("TSMC", "INVESTMENT", "Semiconductor",
     "Trump Administration Secures an Additional $100 Billion U.S. Semiconductor "
     "Manufacturing Investment for a Total of $265 Billion from TSMC"),
    ("Coherent", "POLICY_CHANGE", "Indium Phosphide",
     "The Department of Commerce’s CHIPS Program Announces a Letter of Intent "
     "with Coherent for up to $50 Million to Expand Indium Phosphide Production"),
    ("xLight", "POLICY_CHANGE", "Extreme Ultraviolet Lithography",
     "Department of Commerce and NIST Announce CHIPS Research and Development "
     "Letter of Intent with xLight, Inc. for Extreme Ultraviolet Lithography"),
)


def test_exact_federal_semiconductor_commitments_not_realized_revenue():
    from newscatalystos.economic_changes import official_us_semiconductor_news_change
    assert len(ADDITIONAL_REPORTS)==3
    for actor, action, product, title in ADDITIONAL_REPORTS:
        rows=official_us_semiconductor_news_change(title)
        assert len(rows)==1
        row=rows[0]
        assert row["topic"]==product
        assert row["action"]==action and row["phase"]=="PLANNED"
        assert row["economic_driver"]==(
            "CAPACITY_EXPANSION" if action=="INVESTMENT" else "POLICY_ENABLEMENT")
        assert row["entity_ids"]==[actor]
        assert row["industry_tags"]==["SEMICONDUCTOR"]
        assert row["source_paragraph_sha256"]==sha256(title.encode()).hexdigest()
        assert row["verified_economic_effect"] is False
    tsmc=ADDITIONAL_REPORTS[0][3]
    for bad in (
        tsmc.replace("from TSMC","from Unknown"),
        tsmc.replace("Total of $265 Billion","Total of $50 Billion"),
        tsmc.replace("Trump Administration Secures","Investors Speculate"),
        tsmc+" - unconfirmed rumor",
        ADDITIONAL_REPORTS[1][3].replace("to Expand Indium Phosphide Production",
                                          "for Quantum Computing"),
        ADDITIONAL_REPORTS[2][3].replace("xLight, Inc.","7 Companies"),
    ):
        assert not official_us_semiconductor_news_change(bad),bad


def test_nist_saved_titles_produce_three_real_source_shaped_actions_and_exact_company_evidence(tmp_path):
    from test_federated_news_search import setup_workspace,collect
    from newscatalystos.economic_changes import official_us_semiconductor_news_change

    now=datetime.now(timezone.utc)
    reg=parse_provider_registry(CONFIG.read_bytes())
    w=setup_workspace(tmp_path,"nist",reg)
    pairs=[]
    for n,(actor,action,topic,title) in enumerate(ADDITIONAL_REPORTS):
        pairs.append((f"nist-semiconductor-news-{n}",title,
                      f"https://www.nist.gov/news-events/news/2026/07/approved-news-{n}"))
    collect(w,reg,PROVIDER,pairs,at=now)
    root=w.registry_path.parent.parent
    opts=scheduled.parser().parse_args([
        "--replay-only","--registry",str(w.registry_path),
        "--provider-id",PROVIDER,"--state",str(w.poll_state),
        "--inbox-root",str(w.inbox_root),
        "--dedup-state",str(root/"state/dedup.sqlite3"),
        "--output-root",str(root/"triage"),
        "--analysis-root",str(root/"feed_analysis/core"),
        "--analysis-theme-root",str(root/"document_analysis/theme_history"),
        "--analysis-limit","100",
    ])
    code,summary=scheduled.execute(opts)
    assert code==0
    a=summary["providers"][0]["analysis"]
    assert summary["ai_call_count"]==summary["stored_article_body_count"]==0
    assert a["analyzed_rows"]==a["economic_changes_count"]==3
    assert a["theme_versions_created"]==3
    report_bytes=Path(a["private_report_file"]).read_bytes()
    assert sha256(report_bytes).hexdigest()==a["report_sha256"]
    assert b"FULL ARTICLE BODY NOT FOR STORAGE" not in report_bytes
    data=json.loads(report_bytes)
    assert all(not x["ai_eligible"] and x["ai_status"]=="NOT_ELIGIBLE"
               and not x["verified_beneficiary"] and not x["verified_economic_fact"]
               for x in data["results"])
    assert all(x["routing_priority"]=="HIGH_PRIORITY_CANDIDATE"
               and x["economic_changes"][0]["phase"]=="PLANNED"
               for x in data["results"])
    theme_root=root/"document_analysis/theme_history"
    themes=ThemeStore(theme_root).search(now=datetime.now(timezone.utc))
    assert len(themes)==3
    assert {r["entity_id"] for t in themes for r in t["company_links"]}=={
        "TSMC","Coherent","xLight"}

    for actor,action,topic,title in ADDITIONAL_REPORTS:
        found=search_completed_workspaces((w,),actor,registry_reader=_registry)
        assert found["coverage_complete"]
        assert len(found["results"])==1
        article=found["results"][0]
        assert article["headline"]==title
        assert article["article_body_included"] is False
        details=saved_article_evidence(article,theme_root,now=datetime.now(timezone.utc))
        assert details["status"]=="READY"
        parties=article_company_context(details,theme_root,now=datetime.now(timezone.utc))
        assert parties["status"]=="READY"
        group,party=next((g,c) for g in parties["themes"] for c in g["direct_parties"])
        assert party["source_name"]==actor and party["benefit_status"]=="UNVERIFIED"
        proof=article_company_excerpt({**details,"article_company_context":parties},
             theme_id=group["theme_id"],entity_id=party["entity_id"],
             claim_event_id=party["event_id"],evidence_sha256=party["evidence_sha256"],
             theme_root=theme_root,reports_root=root/"feed_analysis",
             feeds=[{"registry":w.registry_path,"inbox":w.inbox_root,"state":w.poll_state}],
             jobs=[],now=datetime.now(timezone.utc))
        assert proof["status"]=="READY",(actor, proof.get("reason_code"),proof)
        assert actor in proof["excerpt"] and proof["content_scope"]=="RSS_TITLE_METADATA"
        assert proof["verified_real_transaction"] is proof["verified_real_benefit"] is False

    code,again=scheduled.execute(opts)
    assert code==0 and again["providers"][0]["status"]=="NO_PENDING_REPLAY"
    assert again["ai_call_count"]==0
