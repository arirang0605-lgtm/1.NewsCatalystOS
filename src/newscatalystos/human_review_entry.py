"""Operator-driven blind gold review entry; never invent human labels.

Works only with existing independently pinned batches and precreated private
reviewer slots. A reviewer must manually write a source/rationale evidence note
before submitting a single decision. No RSS, DART, SEC, KRX or AI calls.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile

from .evidence_archive import _private_root, _read_once, _write_new
from .gold_review_intake import REVIEWER_PATTERN
from .live_gold_samples import (
    BLIND_SCHEMA, MAX_FILE, _encoded, _load_pinned_predictions,
)
from .source_share import SourceShareError, _json, _must_sha, _read_regular, _when

SLOTS = ("UNASSIGNED_A", "UNASSIGNED_B")
REVIEW_FIELDS = frozenset({
    "case_sha256", "source_sha256", "true_duplicate", "important_event",
    "review_evidence_sha256", "reviewed_at",
})
MAX_NOTE_BYTES = 16384


def _existing_private_dir(path: Path) -> Path:
    path = Path(path)
    if (not path.is_absolute() or ".." in path.parts or path.is_symlink()
            or any(part.casefold() == "eraleader" for part in path.parts)):
        raise SourceShareError("private existing reviewer directory required")
    try:
        info = path.lstat()
    except OSError as exc:
        raise SourceShareError("existing reviewer workspace unavailable") from exc
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or path.resolve(strict=True) != path):
        raise SourceShareError("unsafe reviewer workspace")
    return path


def _verified_slot(out_root: Path, pin_root: Path, workspace_root: Path,
                   digest: str, slot: str, now: datetime):
    digest = _must_sha(digest, "frozen review batch SHA")
    if slot not in SLOTS:
        raise SourceShareError("only distinct precreated reviewer slots allowed")
    folder = Path(out_root) / ("gold_batch_" + digest)
    pin = Path(pin_root) / ("gold_batch_" + digest + ".pin.json")
    predictions, frozen_at = _load_pinned_predictions(
        folder, out_root, digest, pin, pin_root, now,
    )
    root = _existing_private_dir(workspace_root)
    batch = _existing_private_dir(root / folder.name)
    directory = _existing_private_dir(batch / slot)
    answers = directory / "answers.json"
    content = _read_once(answers, MAX_FILE)
    document = _json(content, "reviewer answers")
    if (set(document) != {"schema", "reviewer_code", "labels"}
            or document["schema"] != BLIND_SCHEMA
            or not isinstance(document["labels"], list)
            or len(document["labels"]) != len(predictions)):
        raise SourceShareError("reviewer worksheet does not match pinned batch")
    prediction_by_id = {x.case_sha256: x for x in predictions}
    seen = set()
    for entry in document["labels"]:
        if not isinstance(entry, dict) or set(entry) != REVIEW_FIELDS:
            raise SourceShareError("unexpected answer row")
        case = _must_sha(entry["case_sha256"], "answer case")
        if case in seen or case not in prediction_by_id:
            raise SourceShareError("duplicate or missing review case")
        seen.add(case)
        if entry["source_sha256"] != prediction_by_id[case].source_sha256:
            raise SourceShareError("answer source SHA mismatch")
    if seen != set(prediction_by_id):
        raise SourceShareError("review answer list incomplete")
    blind = _json(
        _read_regular(folder / "blind_cases.json", MAX_FILE),
        "pinned blind case list",
    )
    return directory, answers, content, document, prediction_by_id, blind, frozen_at


def list_review_cases(out_root: Path, pin_root: Path, workspace_root: Path,
                      digest: str, slot: str, *, offset: int = 0,
                      limit: int = 10, now: datetime | None = None,
                      case_sha256: str | None = None) -> dict:
    """Show local titles + links, never model predictions, to real reviewers."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "review browse time")
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 25:
        raise SourceShareError("invalid review page")
    _, _, _, document, _, blind, pinned = _verified_slot(
        out_root, pin_root, workspace_root, digest, slot, at,
    )
    labels = {x["case_sha256"]: x for x in document["labels"]}
    selected = None
    if case_sha256 is not None:
        selected = _must_sha(case_sha256, "selected review case SHA")
        if selected not in labels:
            raise SourceShareError("selected case not in pinned review batch")
        target = labels[selected]
        values = [target[k] for k in (
            "true_duplicate", "important_event", "review_evidence_sha256", "reviewed_at"
        )]
        if not all(value is None for value in values):
            # A partial/corrupt answer must not masquerade as a submitted review.
            if (type(target["true_duplicate"]) is not bool
                    or type(target["important_event"]) is not bool):
                raise SourceShareError("selected case has incomplete human answers")
            _must_sha(target["review_evidence_sha256"], "selected review evidence")
            reviewed = _when(target["reviewed_at"], "selected human review time")
            code = document["reviewer_code"]
            if (not isinstance(code, str) or not REVIEWER_PATTERN.fullmatch(code)
                    or code.startswith("UNASSIGNED") or not pinned <= reviewed <= at):
                raise SourceShareError("selected human submission identity/time invalid")
    eligible = []
    for entry in blind["cases"]:
        item = labels[entry["case_sha256"]]
        if item["true_duplicate"] is None:
            eligible.append({
                "case_sha256": entry["case_sha256"],
                "source_sha256": entry["source_sha256"],
                "headline": entry["headline"],
                "source_url": entry["source_url"],
            })
    return {
        "status": "BLIND_HUMAN_REVIEW_LOCAL_ONLY",
        "unreviewed_count": len(eligible),
        "cases": ([row for row in eligible if row["case_sha256"] == selected]
                  if selected is not None else eligible)[offset:offset + limit],
        "model_predictions_exposed": False,
        "human_labels_added": 0,
        "release_gate_verified": False,
    }


def record_review_once(
    out_root: Path, pin_root: Path, workspace_root: Path,
    digest: str, slot: str, reviewer_code: str, case_sha256: str,
    true_duplicate: bool, important_event: bool, evidence_file: Path,
    *, now: datetime | None = None,
) -> dict:
    """Record one *explicitly human-supplied* decision, with private evidence.

    A durable prior worksheet + receipt are created before atomic replacement.
    Already labeled cases and evidence notes cannot be overwritten.
    """
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "review submitted")
    case = _must_sha(case_sha256, "review case SHA")
    if (not isinstance(reviewer_code, str)
            or REVIEWER_PATTERN.fullmatch(reviewer_code) is None
            or reviewer_code.startswith("UNASSIGNED")
            or type(true_duplicate) is not bool
            or type(important_event) is not bool):
        raise SourceShareError("explicit human reviewer code and boolean decisions required")
    directory, answers, old_body, document, predictions, _, pin_time = _verified_slot(
        out_root, pin_root, workspace_root, digest, slot, at,
    )
    if not pin_time <= at or case not in predictions:
        raise SourceShareError("case not independently pinned before human review")
    old_code = document["reviewer_code"]
    if old_code not in (slot, reviewer_code):
        raise SourceShareError("reviewer identity already fixed for this slot")
    if (not isinstance(evidence_file, Path)
            or evidence_file.parent != directory
            or evidence_file.name != "evidence_" + case + ".txt"
            or evidence_file.is_symlink()):
        raise SourceShareError("reviewer-authored evidence note must be in private slot")
    evidence = _read_once(evidence_file, MAX_NOTE_BYTES)
    if not 16 <= len(evidence) <= MAX_NOTE_BYTES or not evidence.strip():
        raise SourceShareError("substantive reviewer evidence note required")
    note_sha = sha256(evidence).hexdigest()
    target = next(x for x in document["labels"] if x["case_sha256"] == case)
    if any(target[x] is not None for x in (
        "true_duplicate", "important_event", "review_evidence_sha256", "reviewed_at"
    )):
        raise SourceShareError("completed human review cannot be replaced")
    document["reviewer_code"] = reviewer_code
    target.update({
        "true_duplicate": true_duplicate,
        "important_event": important_event,
        "review_evidence_sha256": note_sha,
        "reviewed_at": at.isoformat(),
    })
    next_body = _encoded(document)
    if len(next_body) > MAX_FILE:
        raise SourceShareError("review answers exceed private limit")
    receipt_dir = _private_root(directory / "review_history")
    original_path = receipt_dir / (case + ".before.json")
    receipt_path = receipt_dir / (case + ".receipt.json")
    proposal_path = receipt_dir / (case + ".proposed.json")
    if original_path.exists() or receipt_path.exists() or proposal_path.exists():
        raise SourceShareError("existing review audit record; no overwrite")
    _write_new(original_path, old_body)
    _write_new(proposal_path, next_body)
    _write_new(receipt_path, _encoded({
        "schema": "newscatalyst.human_review_entry.v1",
        "case_sha256": case, "source_sha256": predictions[case].source_sha256,
        "reviewer_code": reviewer_code,
        "reviewed_at": at.isoformat(),
        "evidence_sha256": note_sha,
        "prior_answers_sha256": sha256(old_body).hexdigest(),
        "new_answers_sha256": sha256(next_body).hexdigest(),
        "human_independence_certified": False,
    }))
    # All durable audit artifacts precede the mutable answers replacement.
    audit_dir_fd = os.open(receipt_dir, os.O_RDONLY)
    try:
        os.fsync(audit_dir_fd)
    finally:
        os.close(audit_dir_fd)
    temp_path = None
    try:
        fd, name = tempfile.mkstemp(prefix=".review_pending_", dir=directory)
        temp_path = Path(name)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(next_body)
            out.flush()
            os.fsync(out.fileno())
        # Fail if another process updated the answer sheet mid-review.
        if sha256(_read_once(answers, MAX_FILE)).digest() != sha256(old_body).digest():
            raise SourceShareError("concurrent reviewer update refused")
        os.replace(temp_path, answers)
        dirfd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return {
        "status": "HUMAN_SUPPLIED_REVIEW_RECORDED_NOT_CERTIFIED",
        "case_sha256": case,
        "reviewer_slot": slot,
        "reviewed_at": at.isoformat(),
        "human_independence_certified": False,
        "release_gate_verified": False,
        "external_api_calls": 0,
    }


def recover_interrupted_review(
    out_root: Path, pin_root: Path, workspace_root: Path,
    digest: str, slot: str, case_sha256: str,
    *, now: datetime | None = None,
) -> dict:
    """Finish a previously human-confirmed edit after a crash; no new labels.

    Uses the durable pre-change document, SHA-bound proposed document, and
    receipt created during the original HUMAN submission. Never guesses.
    Any changed worksheet, missing receipt, or mismatched note fails closed.
    """
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "review recovery")
    case = _must_sha(case_sha256, "recover case SHA")
    directory, answers, current, _, predictions, _, pinned = _verified_slot(
        out_root, pin_root, workspace_root, digest, slot, at,
    )
    if case not in predictions:
        raise SourceShareError("unknown pinned case recovery")
    history = _existing_private_dir(directory / "review_history")
    prefix = history / case
    original = _read_once(Path(str(prefix) + ".before.json"), MAX_FILE)
    proposed = _read_once(Path(str(prefix) + ".proposed.json"), MAX_FILE)
    receipt = _json(_read_once(Path(str(prefix) + ".receipt.json"), 4096),
                    "pending human review receipt")
    if (set(receipt) != {
            "schema", "case_sha256", "source_sha256", "reviewer_code",
            "reviewed_at", "evidence_sha256", "prior_answers_sha256",
            "new_answers_sha256", "human_independence_certified",
        } or receipt["schema"] != "newscatalyst.human_review_entry.v1"
            or receipt["case_sha256"] != case
            or receipt["source_sha256"] != predictions[case].source_sha256
            or receipt["human_independence_certified"] is not False
            or sha256(original).hexdigest() != receipt["prior_answers_sha256"]
            or sha256(proposed).hexdigest() != receipt["new_answers_sha256"]):
        raise SourceShareError("human review recovery receipt or SHA mismatch")
    reviewer = receipt["reviewer_code"]
    if (not isinstance(reviewer, str)
            or REVIEWER_PATTERN.fullmatch(reviewer) is None
            or reviewer.startswith("UNASSIGNED")):
        raise SourceShareError("human recovery reviewer not assigned")
    reviewed = _when(receipt["reviewed_at"], "review submitted at")
    if not pinned <= reviewed <= at:
        raise SourceShareError("human review recovery has future/pre-pin timestamp")
    note = _read_once(directory / ("evidence_" + case + ".txt"), MAX_NOTE_BYTES)
    if (len(note) < 16 or sha256(note).hexdigest()
            != _must_sha(receipt["evidence_sha256"], "review evidence SHA")):
        raise SourceShareError("review evidence note was changed")
    old_doc = _json(original, "prior review answers")
    next_doc = _json(proposed, "proposed human answers")
    if (set(old_doc) != {"schema", "reviewer_code", "labels"}
            or old_doc["schema"] != BLIND_SCHEMA
            or old_doc["reviewer_code"] not in (slot, reviewer)
            or not isinstance(old_doc["labels"], list)
            or not isinstance(next_doc.get("labels"), list)):
        raise SourceShareError("invalid pre-review answers")
    if next_doc.get("reviewer_code") != reviewer:
        raise SourceShareError("proposal changed reviewer identity")
    untouched = deepcopy(old_doc)
    matching = [row for row in untouched["labels"]
                if isinstance(row, dict) and row.get("case_sha256") == case]
    proposed = [row for row in next_doc["labels"]
                if isinstance(row, dict) and row.get("case_sha256") == case]
    if len(matching) != 1 or len(proposed) != 1:
        raise SourceShareError("review recovery case missing or duplicate")
    if any(matching[0].get(field) is not None for field in (
        "true_duplicate", "important_event", "review_evidence_sha256",
        "reviewed_at",
    )) or any(type(proposed[0].get(field)) is not bool
               for field in ("true_duplicate", "important_event")):
        raise SourceShareError("review recovery would replace existing label")
    if (proposed[0].get("review_evidence_sha256") != receipt["evidence_sha256"]
            or proposed[0].get("reviewed_at") != reviewed.isoformat()):
        raise SourceShareError("review recovery proposal does not match receipt")
    untouched["reviewer_code"] = reviewer
    matching[0].update({
        field: proposed[0][field]
        for field in ("true_duplicate", "important_event",
                      "review_evidence_sha256", "reviewed_at")
    })
    if next_doc != untouched:
        raise SourceShareError("review proposal changes another case or field")
    if sha256(current).hexdigest() == receipt["new_answers_sha256"]:
        return {"status": "HUMAN_REVIEW_ALREADY_APPLIED_NO_REWRITE",
                "case_sha256": case, "human_labels_added": 0,
                "release_gate_verified": False}
    if sha256(current).hexdigest() != receipt["prior_answers_sha256"]:
        raise SourceShareError("review sheet changed since interrupted submission")
    # Only one known, fully verified old->new state transition is allowed.
    temp_path = None
    try:
        fd, name = tempfile.mkstemp(prefix=".recover_review_", dir=directory)
        temp_path = Path(name)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(_encoded(next_doc))
            stream.flush()
            os.fsync(stream.fileno())
        if sha256(_read_once(answers, MAX_FILE)).hexdigest() != receipt["prior_answers_sha256"]:
            raise SourceShareError("concurrent review update during recovery")
        os.replace(temp_path, answers)
        dirfd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return {
        "status": "INTERRUPTED_HUMAN_REVIEW_RECOVERED_FROM_SHA_LOCAL_RECEIPT",
        "case_sha256": case, "human_labels_added": 0,
        "reviewed_at": reviewed.isoformat(),
        "human_independence_certified": False,
        "release_gate_verified": False,
        "external_api_calls": 0,
    }
