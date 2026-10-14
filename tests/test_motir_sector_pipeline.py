"""Reviewed government RSS sector delivery reuses existing metadata triage/gold."""
from argparse import Namespace
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import run_motir_policy_once as sector
from scripts import run_gold_capture_once as auto
from test_motir_rss_post import registry as official
from newscatalystos import live_gold_samples as gold
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
    )


def test_explicit_motir_sector_uses_existing_feed_then_gold_without_mixing_source(tmp_path):
    opts = config(tmp_path)
    records = []
    def fake_feed(args):
        records.append(("feed", args.provider_id, args.inbox_root))
        return 0, {"status": "NOT_DUE", "new_provider_ids": 0}
    def fake_gold(args):
        records.append(("gold", args.motir_policy_only, args.inbox_root))
        return 0, {"status": "NEW_VERIFIED_RSS_CANDIDATES_FROZEN",
                   "newly_frozen_cases": 10, "total_pinned_unique_cases": 10}
    code, output = sector.run_once(
        opts, registry_reader=lambda _: official(),
        feed_runner=fake_feed, gold_runner=fake_gold,
    )
    assert code == 0
    assert records == [("feed", "motir-official-press", opts.inbox_root),
                       ("gold", True, opts.inbox_root)]
    assert output["newly_frozen_gold_candidates"] == 10
    assert output["human_gold_labeled_cases"] == 0
    assert output["era_api_calls"] == output["ai_calls"] == 0
    assert output["release_gate_verified"] is False


def test_failing_feed_still_attempts_safe_completed_gold_replay(tmp_path):
    opts = config(tmp_path)
    called=[]
    def fake_gold(args):
        called.append(True)
        return 0, {"status":"NO_NEW_VERIFIED_RSS_CANDIDATES",
                   "newly_frozen_cases":0, "total_pinned_unique_cases":10}
    code, output = sector.run_once(
        opts, registry_reader=lambda _: official(),
        feed_runner=lambda _: (4,{"status":"DATA_UNAVAILABLE"}),
        gold_runner=fake_gold,
    )
    assert code == 4 and called
    assert output["status"] == "MOTIR_SECTOR_REQUIRES_REVIEW"
    assert output["release_gate_verified"] is False


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


def test_dedicated_capture_requires_motir_only_flag_and_approved_source(tmp_path, monkeypatch):
    opts = config(tmp_path)
    monkeypatch.setattr(gold, "_different_disk", lambda *_: True)
    params = Namespace(
        registry=opts.registry, state=opts.state,
        inbox_root=opts.inbox_root, out_root=opts.gold_root,
        pin_root=opts.pin_root, workspace_root=opts.workspace_root,
        lock_root=opts.lock_root, motir_policy_only=True,
    )
    code, summary = auto.capture(
        params, registry_reader=lambda _: official(),
    )
    assert code == 0
    assert summary["newly_frozen_cases"] == 0
    assert summary["total_pinned_unique_cases"] == 0
    assert summary["release_gate_verified"] is False
    params.motir_policy_only = False
    code, summary = auto.capture(
        params, registry_reader=lambda _: official(),
    )
    assert code == 4 and summary["release_gate_verified"] is False
