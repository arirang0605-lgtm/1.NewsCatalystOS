"""5_6 core evaluation path; every delivery and label is synthetic."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from newscatalystos.beneficiary_case_evaluation import evaluate_semiconductor_cases
from newscatalystos.reviewed_beneficiary_delivery import publish_reviewed_beneficiary_graph
from newscatalystos.source_share import SourceShareError
from test_official_relation_intake import fixture
from test_reviewed_beneficiary_delivery import prepare


def sample(tmp_path):
    info = fixture(tmp_path)
    graph = prepare(info, direction="POSITIVE")
    pub = publish_reviewed_beneficiary_graph(graph, tmp_path / "outbox", now=info[6])
    edge = json.loads(graph.graph.JSON_bytes)["edges"][0]
    label = {
        "event_sha256": graph.source_evidence_sha256,
        "document_sha256": edge["document_sha256"],
        "supplier_namespace": edge["supplier_namespace"],
        "supplier_id": edge["supplier_id"],
        "customer_namespace": edge["customer_namespace"],
        "customer_id": edge["customer_id"],
        "product_stage": edge["product_stage"],
        "source_available_at": edge["source_available_at"],
        "truth": "BENEFICIARY",
        "reviewed_at": info[6].isoformat(),
        "review_proof_sha256": sha256(b"synthetic-independent-review").hexdigest(),
    }
    pin = {"folder": str(pub.folder), "out_root": str(pub.folder.parent),
           "expected_sha256": pub.payload_sha256, "graph_version": "v1"}
    return info, pin, label


def test_pinned_graph_to_5_6_metrics_and_separate_cli(tmp_path):
    info, pin, label = sample(tmp_path)
    result = evaluate_semiconductor_cases([pin], [label], now=info[6])
    assert result["true_positive"] == result["reviewed_cases"] == 1
    assert result["precision"] == result["recall"] == result["accuracy"] == 1
    assert result["precision_target_on_supplied_labels"]
    assert not result["independent_real_case_gate_verified"]
    assert result["verified_real_benefits"] == 0 and result["market_action"] is None
    # The existing synthetic publication fixture records actual completion plus 2s.
    wait = (info[6] - datetime.now(timezone.utc)).total_seconds()
    if wait > 0:
        time.sleep(wait + .1)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    manifest = private / "pins.json"
    labels = private / "labels.json"
    manifest.write_text(json.dumps({
        "schema": "newscatalyst.semiconductor_evaluation_pins.v1", "pins": [pin]}))
    labels.write_text(json.dumps({
        "schema": "newscatalyst.semiconductor_case_labels.v1", "cases": [label]}))
    manifest.chmod(0o600)
    labels.chmod(0o600)
    project = Path(__file__).resolve().parent.parent
    child = subprocess.run([sys.executable,
        str(project / "scripts/evaluate_semiconductor_cases.py"),
        "--manifest", str(manifest), "--labels", str(labels)],
        cwd=tmp_path, env=dict(os.environ, PYTHONPATH=str(project / "src")),
        capture_output=True, text=True, timeout=15)
    assert child.returncode == 0, child.stderr
    output = json.loads(child.stdout)
    assert output["true_positive"] == 1
    assert not output["independent_real_case_gate_verified"]
    assert (Path(pin["folder"]) / "beneficiary_graph.json").is_file()


def test_false_positive_miss_and_unresolved_are_distinct(tmp_path):
    info, pin, label = sample(tmp_path)
    wrong = dict(label, truth="NOT_BENEFICIARY")
    missed = dict(label, customer_id="00000009", truth="BENEFICIARY")
    unresolved = dict(label, customer_id="00000008", truth="UNRESOLVED")
    result = evaluate_semiconductor_cases([pin], [wrong, missed, unresolved], now=info[6])
    assert (result["true_positive"], result["false_positive"],
            result["false_negative"], result["true_negative"]) == (0, 1, 1, 0)
    assert result["precision"] == result["recall"] == result["accuracy"] == 0
    assert result["unresolved_cases"] == 1
    assert len(result["false_positive_case_ids"]) == len(result["false_negative_case_ids"]) == 1
    assert not result["precision_target_on_supplied_labels"]


def test_invalid_pin_or_future_review_cannot_supply_metrics(tmp_path):
    info, pin, label = sample(tmp_path)
    with pytest.raises(SourceShareError):
        evaluate_semiconductor_cases([dict(pin, expected_sha256="f" * 64)],
                                     [label], now=info[6])
    with pytest.raises(SourceShareError, match="future review"):
        evaluate_semiconductor_cases([pin],
            [dict(label, reviewed_at=(info[6] + timedelta(days=1)).isoformat())],
            now=info[6])
    before_source = datetime.fromisoformat(label["source_available_at"]) - timedelta(seconds=1)
    with pytest.raises(SourceShareError, match="future review"):
        evaluate_semiconductor_cases([pin],
            [dict(label, reviewed_at=before_source.isoformat())], now=info[6])
