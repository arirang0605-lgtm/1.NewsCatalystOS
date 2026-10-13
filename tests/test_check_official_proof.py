"""Operational 1_1 proof CLI: smoke and fail-closed behaviors only."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_official_proof as cli
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 13, 16, 0, tzinfo=timezone.utc)


def args(tmp_path, *additional):
    return cli.parser().parse_args([
        "--era-root", str(tmp_path / "era"),
        "--reference", str(tmp_path / "reference"),
        "--anchor", str(tmp_path / "anchor"),
        *additional,
    ])


def _known_sources(monkeypatch):
    seen = []
    def load(era, ref, anchor, decision):
        seen.append((era, ref, anchor, decision))
        return SimpleNamespace(captures=(1, 2, 3, 4, 5))
    monkeypatch.setattr(cli, "verify_with_local_anchor", load)
    return seen


def test_missing_real_witness_reports_unavailable_not_fake_completion(tmp_path, monkeypatch):
    calls = _known_sources(monkeypatch)
    status, report = cli.evaluate(args(tmp_path), now=NOW)
    assert status == 4
    assert report["status"] == "DATA_UNAVAILABLE"
    assert report["verified_capture_count"] == 5
    assert report["certified_raw_event_count"] == 0
    assert report["reason"] == "INDEPENDENT_RELEASE_ATTESTATION_NOT_PROVIDED"
    assert len(calls) == 1


def test_partial_witness_stays_blocked(tmp_path, monkeypatch):
    _known_sources(monkeypatch)
    status, report = cli.evaluate(
        args(tmp_path, "--source-id", "sec-submissions"), now=NOW
    )
    assert status == 4 and report["certified_raw_event_count"] == 0
    assert report["reason"] == "INCOMPLETE_INDEPENDENT_WITNESS_INPUT"


def test_pin_verifier_failure_stops_before_claims(tmp_path, monkeypatch):
    def fail(*_args):
        raise SourceShareError("pin cannot be trusted")
    monkeypatch.setattr(cli, "verify_with_local_anchor", fail)
    with pytest.raises(SourceShareError, match="pin cannot be trusted"):
        cli.evaluate(args(tmp_path), now=NOW)


def test_future_decision_rejected_before_any_source_reads(tmp_path, monkeypatch):
    def should_not_run(*_args):
        raise AssertionError("source was read despite future decision")
    monkeypatch.setattr(cli, "verify_with_local_anchor", should_not_run)
    opts = args(tmp_path, "--decision-at", "2026-10-13T16:00:01Z")
    with pytest.raises(SourceShareError, match="future decision"):
        cli.evaluate(opts, now=NOW)


def test_real_script_error_redacts_private_file_paths(tmp_path, monkeypatch, capsys):
    def fail(*_args):
        raise SourceShareError("private secret /path/long_hidden")
    monkeypatch.setattr(cli, "verify_with_local_anchor", fail)
    opts = [
        "--era-root", str(tmp_path / "era"),
        "--reference", str(tmp_path / "reference"),
        "--anchor", str(tmp_path / "anchor"),
    ]
    assert cli.main(opts) == 4
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["error_type"] == "SourceShareError"
    assert result["certified_raw_event_count"] == 0
    assert "long_hidden" not in output


def test_explicit_witness_files_call_existing_pipeline_only(tmp_path, monkeypatch):
    called = _known_sources(monkeypatch)
    paths = {
        "claim": b"{}",
        "attestation": b"{}",
        "signature": b"x" * 64,
        "witness-key": b"-----BEGIN PUBLIC KEY-----\nFAKE\n",
    }
    argv = ["--source-id", "sec-submissions", "--document-id", "doc123",
            "--claim-sha256", "a" * 64, "--witness-key-sha256", "b" * 64,
            "--witness-id", "independent-witness"]
    for field, content in paths.items():
        path = tmp_path / field
        path.write_bytes(content)
        argv += ["--" + field, str(path)]
    received = []
    class FakeProof:
        usable_from = NOW
        def as_of(self, decision, *, now):
            return SimpleNamespace(provider_id="SEC")
    def bridge(*values, **kw):
        received.append((values, kw))
        return FakeProof()
    monkeypatch.setattr(cli, "authenticate_from_era_readonly", bridge)
    code, report = cli.evaluate(args(tmp_path, *argv), now=NOW)
    assert code == 0 and report["status"] == "SIGNED_PROOF_GATE_PASS"
    assert len(received) == 1
    assert called == []  # the production wrapper owns the single read pass
    values, kwargs = received[0]
    assert values[5] == b"{}"
    assert values[7] == b"{}"
    assert values[8] == b"x" * 64
    assert report["note"].startswith("Witness authority")


def test_unsafe_symlink_proof_file_cannot_be_read(tmp_path, monkeypatch):
    called = _known_sources(monkeypatch)
    argv = ["--source-id", "sec-submissions", "--document-id", "doc123",
            "--claim-sha256", "a" * 64, "--witness-key-sha256", "b" * 64,
            "--witness-id", "independent-witness"]
    for field in ("claim", "attestation", "signature", "witness-key"):
        path = tmp_path / field
        if field == "claim":
            target = tmp_path / "payload"
            target.write_bytes(b"{}")
            path.symlink_to(target)
        else:
            path.write_bytes(b"{}")
        argv += ["--" + field, str(path)]
    with pytest.raises(SourceShareError, match="evidence unavailable"):
        cli.evaluate(args(tmp_path, *argv), now=NOW)
