"""6_5 scheduled tick reuses existing approved feed pipeline without new collectors."""
import argparse
from dataclasses import replace
from pathlib import Path

import pytest

from newscatalystos.provider_registry import ProviderRegistry
from scripts.run_scheduled_triage import execute, parser
from test_new_source_adapter import registry


def options(tmp_path, names=None, dry_run=False):
    return argparse.Namespace(
        registry=tmp_path / "private-registry.json",
        provider_id=names if names is not None else ["synthetic-government-feed"],
        state=tmp_path / "state" / "poll.sqlite3",
        dedup_state=tmp_path / "state" / "dedup.sqlite3",
        output_root=tmp_path / "output",
        inbox_root=tmp_path / "inbox",
        once=not dry_run, dry_run=dry_run,
        skip_analysis=True,  # legacy collection-only behavior tested in this file
    )


def test_dry_run_only_validates_approved_provider_no_network_or_file(tmp_path):
    params = options(tmp_path, dry_run=True)
    def no_network(_args):
        raise AssertionError("dry-run attempted feed poll")
    code, report = execute(params, registry_reader=lambda _: registry(),
                           feed_runner=no_network)
    assert code == 0
    assert report["status"] == "DRY_RUN_APPROVED_NO_REQUEST"
    assert report["providers"][0]["status"] == "AUTHORIZED_NO_REQUEST"
    assert report["official_era_api_request_count"] == 0
    assert report["ai_call_count"] == 0
    assert not params.state.exists()


def test_once_delegates_to_existing_rate_limited_feed_runner(tmp_path):
    params = options(tmp_path)
    called = []
    def callback(ns):
        called.append(ns)
        return 0, {
            "status": "FEED_METADATA_TRIAGE_READY",
            "new_provider_ids": 1,
            "semiconductor_keyword_candidates": 0,
        }
    code, report = execute(params, registry_reader=lambda _: registry(),
                           feed_runner=callback)
    assert code == 0
    assert report["status"] == "SCHEDULED_TICK_COMPLETE_OR_NOT_DUE"
    assert len(called) == 1 and called[0].replay_only is False
    assert called[0].state == params.state
    assert called[0].inbox_root == params.inbox_root
    assert report["providers"][0]["new_provider_ids"] == 1
    assert report["stored_article_body_count"] == 0


def test_not_due_is_normal_and_does_not_bypass_rate_limits(tmp_path):
    called = []
    def no_data(ns):
        called.append(ns.provider_id)
        return 0, {"status": "NOT_DUE", "new_provider_ids": 0}
    code, summary = execute(
        options(tmp_path), registry_reader=lambda _: registry(),
        feed_runner=no_data,
    )
    assert code == 0 and called == ["synthetic-government-feed"]
    assert summary["providers_failed"] == 0
    assert summary["providers"][0]["status"] == "NOT_DUE"


def test_one_provider_error_does_not_block_second(tmp_path):
    one = registry().providers[0]
    two = replace(one, provider_id="other-approved-source")
    approved = ProviderRegistry((one, two))
    called = []
    def feed(ns):
        called.append(ns.provider_id)
        if ns.provider_id == one.provider_id:
            return 4, {"status": "DATA_UNAVAILABLE"}
        return 0, {"status": "FEED_METADATA_TRIAGE_READY"}
    code, report = execute(
        options(tmp_path, names=[one.provider_id, two.provider_id]),
        registry_reader=lambda _: approved, feed_runner=feed,
    )
    assert code == 4
    assert called == [one.provider_id, two.provider_id]
    assert report["providers_failed"] == 1
    assert len(report["providers"]) == 2


@pytest.mark.parametrize("names", [
    ["sec-submissions"], ["dart-disclosures"], ["krx-kospi"],
    ["synthetic-government-feed", "synthetic-government-feed"], [],
])
def test_official_sources_and_duplicate_selectors_fail_closed(tmp_path, names):
    attempted = []
    def reader(_):
        attempted.append("read")
        return registry()
    code, report = execute(options(tmp_path, names=names), registry_reader=reader)
    assert code == 4
    assert report["status"] == "INVALID_EXPLICIT_PROVIDER_SELECTION"
    assert not attempted


def test_unapproved_or_revoked_registry_blocks_provider_before_fetch(tmp_path):
    inactive = ProviderRegistry((
        replace(registry().providers[0], approved=False),
    ))
    def no_call(_opts):
        raise AssertionError("unapproved RSS was queried")
    code, report = execute(
        options(tmp_path), registry_reader=lambda _: inactive,
        feed_runner=no_call,
    )
    assert code == 4
    assert report["providers_failed"] == 1


def test_cli_enforces_explicit_once_or_dry_run(tmp_path):
    cli = parser()
    with pytest.raises(SystemExit):
        cli.parse_args(["--registry", str(tmp_path / "x"), "--provider-id", "y"])
    parsed = cli.parse_args([
        "--registry", str(tmp_path / "x"),
        "--provider-id", "synthetic-government-feed", "--dry-run",
    ])
    assert parsed.dry_run and not parsed.once
