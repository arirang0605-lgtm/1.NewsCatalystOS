"""1_6 CLI summarizes only quality codes and never provider secrets."""
import json
from types import SimpleNamespace

from scripts import check_feed_quality as cli
from test_new_source_adapter import registry


def test_cli_reports_pending_without_private_failure_text(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "_registry", lambda _: registry())
    def issues(*args, **kwargs):
        return (SimpleNamespace(provider_id="synthetic-government-feed",
                                status="STALE", gap_seconds=18000,
                                queue_status="PENDING"),)
    monkeypatch.setattr(cli, "check_sources", issues)
    monkeypatch.setattr(cli, "unresolved_count", lambda _: 1)
    rc = cli.main(["--registry", str(tmp_path / "p.json"),
                   "--state", str(tmp_path / "s.sqlite3")])
    obj = json.loads(capsys.readouterr().out)
    assert rc == 4
    assert obj["status"] == "QUALITY_DEGRADED"
    assert obj["pending_count"] == 1
    assert "headline" not in obj


def test_cli_rejects_missing_private_registry_without_network(tmp_path, capsys):
    assert cli.main(["--registry", str(tmp_path / "missing.json"),
                     "--state", str(tmp_path / "s.sqlite3")]) == 4
    payload = capsys.readouterr().out
    assert "DATA_UNAVAILABLE" in payload
    assert str(tmp_path) not in payload
