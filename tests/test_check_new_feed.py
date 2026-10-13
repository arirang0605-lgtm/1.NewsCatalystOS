"""One-shot CLI validation without external network or private files."""
from datetime import datetime, timezone
import json

import pytest

from scripts import check_new_feed as cli
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import registry, NOW


def _args(path):
    return cli.parser().parse_args([
        "--registry", str(path), "--provider-id", "synthetic-government-feed",
    ])


def _reg_file(path, approved=True):
    from newscatalystos.provider_registry import SCHEMA
    feed = registry(approved).providers[0]
    from dataclasses import asdict
    row = asdict(feed)
    for key in ("reviewed_at", "expires_at"):
        if row[key] is not None:
            row[key] = row[key].isoformat()
    path.write_text(json.dumps({"schema": SCHEMA, "providers": [row]}))
    path.chmod(0o600)
    return path


def test_cli_only_prints_metadata_not_fulltext(tmp_path, monkeypatch, capsys):
    p = _reg_file(tmp_path / "providers.json")
    calls = []
    def fetch(r, id):
        calls.append(id)
        from types import SimpleNamespace
        return (SimpleNamespace(first_seen_at=NOW),)
    monkeypatch.setattr(cli, "fetch_authorized_once", fetch)
    assert cli.main(["--registry", str(p), "--provider-id",
                     "synthetic-government-feed"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["metadata_count"] == 1
    assert output["stored_article_body_count"] == 0
    assert output["certified_raw_event_count"] == 0
    assert calls == ["synthetic-government-feed"]


def test_cli_rejects_world_readable_registry(tmp_path, monkeypatch, capsys):
    p = _reg_file(tmp_path / "providers.json")
    p.chmod(0o644)
    monkeypatch.setattr(cli, "fetch_authorized_once",
                        lambda *_: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert cli.main(["--registry", str(p), "--provider-id",
                     "synthetic-government-feed"]) == 4
    output = json.loads(capsys.readouterr().out)
    assert output["certified_raw_event_count"] == 0


def test_cli_redacts_permission_errors(tmp_path, monkeypatch, capsys):
    p = _reg_file(tmp_path / "providers.json")
    def forbidden(*_):
        raise SourceShareError("SECRET_DO_NOT_ECHO")
    monkeypatch.setattr(cli, "fetch_authorized_once", forbidden)
    assert cli.main(["--registry", str(p), "--provider-id",
                     "synthetic-government-feed"]) == 4
    text = capsys.readouterr().out
    assert "SECRET_DO_NOT_ECHO" not in text
    assert json.loads(text)["status"] == "DATA_UNAVAILABLE"
