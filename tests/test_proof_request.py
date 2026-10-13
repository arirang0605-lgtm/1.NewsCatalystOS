"""No external publication proof is invented in an offline request."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from newscatalystos.proof_request import (
    SCHEMA, STATUS, build_official_proof_request, request_from_era_readonly,
)
from newscatalystos.source_share import SourceShareError
from scripts import request_official_proof as cli
from test_official_promotion import scenario, witness, NOW


@pytest.mark.parametrize("provider", ["SEC", "DART"])
def test_pinned_document_creates_metadata_request_not_certification(tmp_path, witness, provider):
    args, folder, original = scenario(tmp_path, witness, provider)
    result = build_official_proof_request(
        args["verified"], args["anchor"], args["source_id"],
        args["provider_document_id"], NOW, now=NOW,
    )
    capture = args["verified"].captures[0]
    assert result["schema"] == SCHEMA
    assert result["status"] == STATUS
    assert result["certified_raw_event_count"] == 0
    assert result["source_sha256"] == capture.raw_sha256
    assert result["source_receipt_sha256"] == capture.first_receipt_sha256
    assert result["source_document_id"] == args["provider_document_id"]
    assert result["publisher_released_at"] is None
    assert result["issuer_id"] is None
    assert result["revision_id"] is None
    assert result["supersedes_document_id"] is None
    assert len(result["missing_external_evidence"]) == 5
    assert "raw_response" not in json.dumps(result)
    assert (folder / "raw_response.json").read_bytes() == original


@pytest.mark.parametrize("wrong", [
    "wrong-document", "../sensitive", " ",
])
def test_non_pinned_document_rejected(tmp_path, witness, wrong):
    args, _, _ = scenario(tmp_path, witness)
    with pytest.raises(SourceShareError):
        build_official_proof_request(
            args["verified"], args["anchor"], args["source_id"], wrong,
            NOW, now=NOW,
        )


def test_untrusted_anchor_and_source_are_blocked(tmp_path, witness):
    args, _, _ = scenario(tmp_path, witness)
    supplied = [args["verified"], args["anchor"], args["source_id"],
                args["provider_document_id"], NOW]
    with pytest.raises(SourceShareError, match="anchor"):
        build_official_proof_request(
            supplied[0], replace(supplied[1], report_sha256="0" * 64),
            *supplied[2:], now=NOW,
        )
    with pytest.raises(SourceShareError, match="eligible"):
        build_official_proof_request(
            *supplied[:2], "sec-companyfacts", *supplied[3:], now=NOW,
        )
    with pytest.raises(SourceShareError, match="ambiguous|unavailable"):
        build_official_proof_request(
            replace(supplied[0], captures=tuple()), *supplied[1:], now=NOW
        )


def test_request_fails_closed_before_anchor_or_future_decision(tmp_path, witness):
    args, _, _ = scenario(tmp_path, witness)
    params = [args["verified"], args["anchor"], args["source_id"],
              args["provider_document_id"]]
    with pytest.raises(SourceShareError, match="anchor"):
        build_official_proof_request(
            *params, args["anchor"].observed_at - timedelta(seconds=1),
            now=NOW,
        )
    with pytest.raises(SourceShareError, match="future"):
        build_official_proof_request(
            *params, NOW + timedelta(minutes=1), now=NOW,
        )


def test_readonly_wrapper_uses_separately_pinned_reference(tmp_path, monkeypatch):
    calls = []
    fake_anchor = SimpleNamespace(report_sha256="a" * 64)
    def get_anchor(*values):
        calls.append(("anchor", values))
        return fake_anchor
    def get_reference(*values, **kwargs):
        calls.append(("reference", values, kwargs))
        return "VERIFIED"
    def build(*values, **kwargs):
        calls.append(("build", values, kwargs))
        return {"status": STATUS, "certified_raw_event_count": 0}
    from newscatalystos import proof_request as mod
    monkeypatch.setattr(mod, "read_local_reference_anchor", get_anchor)
    monkeypatch.setattr(mod, "verify_official_research_reference", get_reference)
    monkeypatch.setattr(mod, "build_official_proof_request", build)
    got = request_from_era_readonly(
        tmp_path, tmp_path / "ref", tmp_path / "anchor", "sec-submissions",
        "doc001", NOW, now=NOW,
    )
    assert got["certified_raw_event_count"] == 0
    assert [x[0] for x in calls] == ["anchor", "reference", "build"]
    assert calls[1][1][2] == fake_anchor.report_sha256


def test_cli_outputs_request_without_private_raw_bytes(tmp_path, monkeypatch, capsys):
    called = []
    def only_request(*values, **kw):
        called.append((values, kw))
        return {"status": STATUS, "certified_raw_event_count": 0}
    monkeypatch.setattr(cli, "request_from_era_readonly", only_request)
    argv = ["--era-root", str(tmp_path), "--reference", str(tmp_path / "r"),
            "--anchor", str(tmp_path / "a"), "--source-id", "sec-submissions",
            "--document-id", "doc001"]
    assert cli.main(argv) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == STATUS
    assert output["certified_raw_event_count"] == 0
    assert len(called) == 1


def test_cli_fail_closed_redacts_private_path(tmp_path, monkeypatch, capsys):
    def fail(*values, **kw):
        raise SourceShareError("secret location /private/my-raw-record")
    monkeypatch.setattr(cli, "request_from_era_readonly", fail)
    argv = ["--era-root", str(tmp_path), "--reference", str(tmp_path / "r"),
            "--anchor", str(tmp_path / "a"), "--source-id", "dart-disclosures",
            "--document-id", "doc001"]
    assert cli.main(argv) == 4
    result = capsys.readouterr().out
    assert "my-raw-record" not in result
    assert json.loads(result)["certified_raw_event_count"] == 0
