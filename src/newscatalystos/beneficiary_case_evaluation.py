"""5_6 semiconductor candidate evaluation on SHA-checked private deliveries.

This measures supplied independent labels. It does not create human labels,
certify commercial benefits, or satisfy the real-case release gate by itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from .reviewed_beneficiary_delivery import consume_reviewed_beneficiary_graph
from .semiconductor_profile import STAGES
from .source_share import SourceShareError, _must_sha, _when

SCHEMA = "newscatalyst.semiconductor_case_evaluation.v1"
POSITIVE = "POTENTIAL_BENEFICIARY_UNVERIFIED"
TRUTHS = frozenset({"BENEFICIARY", "NOT_BENEFICIARY", "UNRESOLVED"})
KEY_FIELDS = ("event_sha256", "document_sha256", "supplier_namespace",
              "supplier_id", "customer_namespace", "customer_id", "product_stage")
LABEL_FIELDS = set(KEY_FIELDS) | {"truth", "source_available_at", "reviewed_at", "review_proof_sha256"}
PIN_FIELDS = {"folder", "out_root", "expected_sha256", "graph_version"}


def _case_id(row: dict) -> str:
    if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in KEY_FIELDS):
        raise SourceShareError("complete semiconductor case identity required")
    for key in ("event_sha256", "document_sha256"):
        _must_sha(row[key], key)
    namespace = row["supplier_namespace"]
    if (namespace not in {"DART_CORP", "SEC_CIK"}
            or row["customer_namespace"] != namespace
            or row["supplier_id"] == row["customer_id"]
            or row["product_stage"] not in STAGES):
        raise SourceShareError("invalid semiconductor relationship identity")
    pattern = r"[0-9]{8}" if namespace == "DART_CORP" else r"[0-9]{1,10}"
    if not all(re.fullmatch(pattern, row[k]) for k in ("supplier_id", "customer_id")):
        raise SourceShareError("invalid official company identifier")
    return sha256("\0".join(row[k] for k in KEY_FIELDS).encode()).hexdigest()


def evaluate_semiconductor_cases(
    pins: list[dict], labels: list[dict], *, now: datetime | None = None,
) -> dict:
    """Read verified outboxes, join independent cases, and report honest metrics."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "evaluation time")
    if (not isinstance(pins, list) or not isinstance(labels, list)
            or len(pins) > 10000 or not 1 <= len(labels) <= 10000):
        raise SourceShareError("bounded delivery pins and case labels required")
    gold = {}
    for row in labels:
        if not isinstance(row, dict) or set(row) != LABEL_FIELDS:
            raise SourceShareError("complete typed case label required")
        key = _case_id(row)
        if key in gold:
            raise SourceShareError("duplicate gold case")
        if row["truth"] not in TRUTHS:
            raise SourceShareError("unsupported case truth")
        _must_sha(row["review_proof_sha256"], "independent review proof")
        available = _when(row["source_available_at"], "case source available")
        reviewed = _when(row["reviewed_at"], "gold review time")
        if available > reviewed or reviewed > at:
            raise SourceShareError("future review unavailable")
        gold[key] = row["truth"]
    predicted = {}
    for pin in pins:
        if not isinstance(pin, dict) or set(pin) != PIN_FIELDS:
            raise SourceShareError("complete pinned delivery required")
        if pin["graph_version"] not in {"v1", "v2"}:
            raise SourceShareError("unsupported graph version")
        report = consume_reviewed_beneficiary_graph(
            Path(pin["folder"]), Path(pin["out_root"]), pin["expected_sha256"],
            graph_version=pin["graph_version"], now=at,
        )
        if report["industry_id"] != "SEMICONDUCTOR" or len(report["candidate_edges"]) != 1:
            raise SourceShareError("single semiconductor candidate expected")
        edge = report["candidate_edges"][0]
        key = _case_id(dict(edge, event_sha256=report["source_event_sha256"]))
        if key in predicted:
            raise SourceShareError("duplicate candidate case")
        predicted[key] = edge["candidate_category"] == POSITIVE
    tp = fp = fn = tn = 0
    false_positives, false_negatives, unresolved = [], [], []
    for key, truth in gold.items():
        if truth == "UNRESOLVED":
            unresolved.append(key)
            continue
        proposed = predicted.get(key, False)
        if truth == "BENEFICIARY" and proposed:
            tp += 1
        elif truth == "NOT_BENEFICIARY" and proposed:
            fp += 1
            false_positives.append(key)
        elif truth == "BENEFICIARY":
            fn += 1
            false_negatives.append(key)
        else:
            tn += 1
    reviewed = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    accuracy = (tp + tn) / reviewed if reviewed else None
    return {
        "schema": SCHEMA,
        "status": "METRICS_ONLY_INDEPENDENT_LABEL_PROVENANCE_NOT_CERTIFIED",
        "evaluated_at": at.isoformat(),
        "pinned_deliveries": len(pins),
        "reviewed_cases": reviewed,
        "unresolved_cases": len(unresolved),
        "unreviewed_predictions": len(set(predicted) - set(gold)),
        "true_positive": tp, "false_positive": fp,
        "false_negative": fn, "true_negative": tn,
        "precision": precision, "recall": recall, "accuracy": accuracy,
        "false_positive_case_ids": sorted(false_positives),
        "false_negative_case_ids": sorted(false_negatives),
        "unresolved_case_ids": sorted(unresolved),
        "precision_target_on_supplied_labels": precision is not None and precision >= .95,
        "independent_real_case_gate_verified": False,
        "verified_real_benefits": 0,
        "market_action": None,
    }
