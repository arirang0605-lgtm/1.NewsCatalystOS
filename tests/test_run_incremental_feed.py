"""1_3 CLI uses private allowlist and isolates per-provider failures."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from scripts import run_incremental_feed as cli
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import registry, NOW


def args(tmp_path, *, all_sources=False):
    argv = ["--registry", str(tmp_path / "private.json"),
            "--state", str(tmp_path / "state" / "feed.sqlite3")]
    argv += ["--all-approved"] if all_sources else ["--provider-id", "synthetic-government-feed"]
    return cli.parser().parse_args(argv)


def test_single_provider_returns_only_aggregate_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_registry", lambda path: registry())
    calls = []
    def poll(reg, provider, state):
        calls.append(provider)
        return SimpleNamespace(status="SUCCESS_NEW", new_count=3,
                               duplicate_count=1, usable_from=NOW)
    monkeypatch.setattr(cli, "incremental_poll", poll)
    code, result = cli.run(args(tmp_path))
    assert code == 0
    assert calls == ["synthetic-government-feed"]
    assert result["providers"][0]["new_count"] == 3
    assert result["stored_article_body_count"] == 0


def test_backoff_not_due_does_not_fail_scheduler(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_registry", lambda _: registry())
    def denied(*_):
        raise SourceShareError("provider rate or backoff window not elapsed")
    monkeypatch.setattr(cli, "incremental_poll", denied)
    code, summary = cli.run(args(tmp_path))
    assert code == 0
    assert summary["providers"][0]["status"] == "NOT_DUE"


def test_all_approved_continues_after_provider_failure(monkeypatch, tmp_path):
    from dataclasses import replace
    first = registry().providers[0]
    second = replace(first, provider_id="other-approved-government")
    monkeypatch.setattr(
        cli, "_registry", lambda _: ProviderRegistry((first, second)))
    calls = []
    def poll(r, provider, path):
        calls.append(provider)
        if provider == first.provider_id:
            raise SourceShareError("private secret must not be printed")
        return SimpleNamespace(status="SUCCESS_NEW", new_count=2,
                               duplicate_count=0, usable_from=NOW)
    monkeypatch.setattr(cli, "incremental_poll", poll)
    code, summary = cli.run(args(tmp_path, all_sources=True))
    assert code == 4
    assert len(calls) == 2
    assert "secret" not in json.dumps(summary)
    assert [r["status"] for r in summary["providers"]] == [
        "DATA_UNAVAILABLE", "SUCCESS_NEW",
    ]


def test_unreadable_registry_fails_before_fetch(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "incremental_poll",
                        lambda *_: (_ for _ in ()).throw(AssertionError("must not call")))
    code = cli.main([
        "--registry", str(tmp_path / "does_not_exist.json"),
        "--provider-id", "synthetic-government-feed",
    ])
    assert code == 4
    result = capsys.readouterr().out
    assert json.loads(result)["status"] == "DATA_UNAVAILABLE"
    assert str(tmp_path) not in result


def test_both_modes_or_no_modes_denied(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_registry",
                        lambda *_: (_ for _ in ()).throw(AssertionError("must not read")))
    opt = args(tmp_path)
    opt.all_approved = True
    with pytest.raises(SourceShareError, match="exactly one"):
        cli.run(opt)
    opt.provider_id = None
    opt.all_approved = False
    with pytest.raises(SourceShareError, match="exactly one"):
        cli.run(opt)


def test_resume_does_not_contact_provider_and_needs_single_selection(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_registry", lambda _: registry())
    calls = []
    def resume(reg, name, path, *, now):
        calls.append((name, path))
        return True
    monkeypatch.setattr(cli, "resume_after_rights_review", resume)
    monkeypatch.setattr(cli, "incremental_poll",
                        lambda *_: (_ for _ in ()).throw(AssertionError("should not fetch")))
    selection = args(tmp_path)
    selection.resume_after_review = True
    status, report = cli.run(selection)
    assert status == 0 and report["status"] == "REVIEW_RESUMED"
    assert len(calls) == 1
    selection.all_approved = True
    with pytest.raises(SourceShareError, match="exactly one|resume"):
        cli.run(selection)
