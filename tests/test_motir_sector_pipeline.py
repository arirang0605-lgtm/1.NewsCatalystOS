"""Reviewed government RSS sector delivery reuses existing metadata triage/gold."""
from argparse import Namespace
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import run_motir_policy_once as sector
from test_motir_rss_post import registry as official
from newscatalystos.provider_registry import ProviderRegistry


def config(tmp_path):
    home = tmp_path / "private"
    return Namespace(
        registry=home / "providers" / "motir_authorized_sources.json",
        state=home / "state" / "motir_incremental_feeds.sqlite3",
        dedup_state=home / "state" / "motir_triage_exact_index.sqlite3",
        inbox_root=home / "inbox" / "motir_feed_triage",
        output_root=tmp_path / "project" / "output" / "motir_policy",
        gold_root=tmp_path / "project" / "output" / "motir_gold_review",
        pin_root=home / "pins" / "motir_gold",
        workspace_root=home / "motir_gold_review_workspace",
        lock_root=home / "state" / "motir_gold_lock",
        skip_analysis=True,  # existing source/Gold-only tests
    )








def test_wrong_issuer_or_rights_fails_before_feed_network(tmp_path):
    opts = config(tmp_path)
    called=[]
    wrong = official()
    bad = ProviderRegistry((replace(wrong.providers[0],method="RSS"),))
    code, result = sector.run_once(
        opts, registry_reader=lambda _: bad,
        feed_runner=lambda _: called.append(True),
    )
    assert code == 4 and not called and result["ai_calls"] == 0




def test_source_then_analysis_needs_no_review_workspace(tmp_path):
    opts = config(tmp_path)
    opts.skip_analysis = False
    calls = []
    def feed(args):
        calls.append("feed")
        return 0, {"status": "NOT_DUE"}
    def analysis(args):
        calls.append("analysis")
        return 0, {"status": "FEED_ECONOMIC_ANALYSIS_READY", "new_ai_results": 0}
    code, report = sector.run_once(opts, registry_reader=lambda _: official(),
        feed_runner=feed, analysis_runner=analysis)
    assert code == 0 and calls == ["feed", "analysis"]
    assert not any("gold" in k or "human" in k for k in report)
    assert not opts.workspace_root.exists()
