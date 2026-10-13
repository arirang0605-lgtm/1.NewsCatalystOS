"""Explicit operator witness enrollment boundary: synthetic content tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from newscatalystos.source_share import SourceShareError
from newscatalystos.witness_registry import (
    SCHEMA, TRUST, parse_operator_witness_registry, load_operator_witness,
)
from scripts import check_official_proof as cli

NOW = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)
ENROLLED = datetime(2026, 10, 12, 9, tzinfo=timezone.utc)


def document():
    return {
        "schema": SCHEMA, "trust_level": TRUST,
        "witnesses": [{
            "witness_id": "independent-release-authority",
            "public_key_sha256": "a" * 64,
            "enrolled_at": ENROLLED.isoformat(),
            "allowed_sources": ["sec-submissions"],
        }]
    }


def parse(value, *, witness="independent-release-authority",
          source="sec-submissions", decision=NOW):
    return parse_operator_witness_registry(
        json.dumps(value).encode(), witness, source, decision, now=NOW,
    )


def test_independent_preapproved_fingerprint_and_scope():
    result = parse(document())
    assert result.public_key_sha256 == "a" * 64
    assert result.allowed_sources == frozenset({"sec-submissions"})
    assert result.enrolled_at == ENROLLED


def test_unregistered_witness_must_fail_closed():
    with pytest.raises(SourceShareError, match="not in independent"):
        parse(document(), witness="self-created-now")


def test_scope_restricted_not_valid_for_other_provider():
    with pytest.raises(SourceShareError, match="no provider authorization"):
        parse(document(), source="dart-disclosures")


def test_later_enrollment_not_retroactive():
    with pytest.raises(SourceShareError, match="not enrolled"):
        parse(document(), decision=ENROLLED - timedelta(seconds=1))


@pytest.mark.parametrize("mutation", [
    lambda v: v["witnesses"].append(v["witnesses"][0]),
    lambda v: v["witnesses"][0].update(witness_id="eraleader"),
    lambda v: v["witnesses"][0].update(enrolled_at="2099-01-01T00:00:00Z"),
    lambda v: v["witnesses"][0].update(allowed_sources=["sec-submissions", "sec-submissions"]),
    lambda v: v["witnesses"][0].update(allowed_sources=["unknown-provider"]),
    lambda v: v["witnesses"][0].update(public_key_sha256="not-a-sha"),
    lambda v: v.update(trust_level="USER_SUPPLIED_UNVERIFIED"),
    lambda v: v.update(extra_field="unexpected"),
])
def test_forged_invalid_enrollment_rejected(mutation):
    registry = document()
    mutation(registry)
    with pytest.raises(SourceShareError):
        parse(registry)


def test_missing_real_trust_registry_denied_before_proof(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "newscatalystos.witness_registry.private_registry_path",
        lambda: tmp_path / "missing_registry.json",
    )
    with pytest.raises(SourceShareError, match="registry missing"):
        load_operator_witness(tmp_path / "eraleader",
                              "independent-release-authority",
                              "sec-submissions", NOW, now=NOW)


def test_proof_CLI_never_accepts_inline_self_pinned_witness_key():
    options = cli.parser()
    with pytest.raises(SystemExit) as caught:
        options.parse_args([
            "--era-root", "/tmp/eraleader",
            "--reference", "/tmp/reference", "--anchor", "/tmp/anchor",
            "--witness-key-sha256", "a" * 64,
        ])
    assert caught.value.code == 2


def test_full_evidence_stops_before_reading_unregistered_claim(monkeypatch, tmp_path):
    def no_registry(*args, **kwargs):
        raise SourceShareError("external witness enrollment missing")
    monkeypatch.setattr(cli, "load_operator_witness", no_registry)
    args = cli.parser().parse_args([
        "--era-root", str(tmp_path),
        "--reference", str(tmp_path / "report"),
        "--anchor", str(tmp_path / "anchor"),
        "--source-id", "sec-submissions",
        "--document-id", "test-id",
        "--claim", str(tmp_path / "nonexistent-claim"),
        "--claim-sha256", "a" * 64,
        "--attestation", str(tmp_path / "nonexistent-statement"),
        "--signature", str(tmp_path / "nonexistent-signature"),
        "--witness-key", str(tmp_path / "nonexistent-key"),
        "--witness-id", "independent-release-authority",
    ])
    with pytest.raises(SourceShareError, match="enrollment missing"):
        cli.evaluate(args, now=NOW)
