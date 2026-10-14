"""2_6/3_6: prospective blind human-review queue from real approved RSS receipts.

A case here is an already SHA-checked provider+event+title VERSION.
Predictions are frozen only NOW, not at the older news publication/triage time.
Two humans must later independently review. No labels/accuracy are invented.
Neither full articles nor any EraLeader data/API are read or stored.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import stat
import tempfile

from .evidence_archive import _private_root, _write_new
from .gold_review_intake import (
    FrozenCasePrediction, HumanGoldReview, prediction_digest,
    prepare_gold_review_metrics,
)
from .news_search import _trusted_snapshot
from .physical_recovery import _different_disk
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _json, _must_sha, _read_regular, _when

SCHEMA = "newscatalyst.live_gold_candidate_batch.v1"
PREDICTIONS_SCHEMA = "newscatalyst.live_gold_predictions.v1"
BLIND_SCHEMA = "newscatalyst.live_gold_blind_review.v1"
PIN_SCHEMA = "newscatalyst.live_gold_independent_local_pin.v1"
MAX_CASES = 10_000
MAX_RECEIPTS = 5_000
MAX_FILE = 4 * 1024 * 1024
BATCH = re.compile(r"gold_batch_([a-f0-9]{64})\Z")


def _encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


@dataclass(frozen=True)
class GoldBatch:
    folder: Path
    pin_file: Path
    payload_sha256: str
    sample_count: int
    first_available_at: datetime
    independently_labeled_cases: int = 0
    release_certified: bool = False


def _rows(registry: ProviderRegistry, inbox: Path, state: Path, at: datetime):
    if not isinstance(registry, ProviderRegistry):
        raise SourceShareError("approved source registry required for gold cases")
    root = _private_root(inbox)
    acknowledgments = root / "acked"
    if not acknowledgments.exists():
        return ()
    ack_root = _private_root(acknowledgments)
    receipts = sorted(ack_root.iterdir())
    if len(receipts) > MAX_RECEIPTS:
        raise SourceShareError("too many receipts in one freeze")
    records = []
    for path in receipts:
        if (path.is_symlink() or not path.is_file()
                or not re.fullmatch(r"[0-9a-f]{64}\.json", path.name)):
            raise SourceShareError("untrusted live gold acknowledgment")
        receipt = _json(_read_regular(path, 4096), "gold source acknowledgment")
        if receipt.get("checkpoint_sha256") != path.name[:-5]:
            raise SourceShareError("gold source acknowledgment identity invalid")
        document, verified_sha = _trusted_snapshot(receipt, root, state, registry, at)
        acknowledged = _when(receipt["confirmed_at"], "gold source completed")
        for item in document["items"]:
            records.append((acknowledged, verified_sha, item))
    records.sort(key=lambda x:(x[0],x[1],x[2]["event_id"]))
    return tuple(records)


def freeze_real_gold_review_cases(
    registry: ProviderRegistry, inbox: Path, state: Path, out_root: Path,
    pin_root: Path, *, now: datetime | None = None,
) -> GoldBatch:
    """Freeze first-observed approved title/version decisions; no human truth."""
    prepared = _when((now or datetime.now(timezone.utc)).isoformat(), "freeze prepared")
    root = _private_root(out_root)
    pin_dir = _private_root(pin_root)
    if not _different_disk(root, pin_dir):
        raise SourceShareError("human gold pin must use independent local device")
    rows = _rows(registry, inbox, state, prepared)
    by_case = {}
    for ack_time, triage_sha, item in rows:
        provider = item["provider_id"]
        event = _must_sha(item["event_id"], "RSS event")
        title_sha = _must_sha(item["title_sha256"], "RSS title SHA")
        unique = sha256((provider + "\0" + event + "\0" + title_sha).encode()).hexdigest()
        if unique in by_case:
            continue
        source_at = _when(item["available_at"], "RSS first available")
        if source_at > prepared or ack_time > prepared:
            raise SourceShareError("future feed used as historic gold source")
        predicted = FrozenCasePrediction(
            case_sha256=unique, source_sha256=event,
            source_available_at=source_at, predicted_at=prepared,
            pin_first_observed_at=prepared,
            predicted_duplicate=(item["exact_index_status"] == "DUPLICATE"),
            predicted_excluded=item["claim_classification"] in (
                "BLOCK_AD_SPAM", "UNVERIFIED_RUMOR"),
            predicted_important=(item["importance_priority"] == "HIGH_PRIORITY_REVIEW"),
            prediction_sha256="0" * 64,
        )
        predicted = replace(predicted, prediction_sha256=prediction_digest(predicted))
        by_case[unique] = (
            predicted,
            {"case_sha256": unique, "source_sha256": event,
             "provider_id": provider,
             "source_role": item["source_kind"],
             "headline": item["headline"],
             "source_url": item["canonical_url"],
             "source_available_at": source_at.isoformat(),
             "first_acknowledged_at": ack_time.isoformat(),
             "source_triage_sha256": triage_sha,
             "review_status": "PENDING_TWO_INDEPENDENT_HUMANS",
             "economic_fact_verified": False},
        )
    if not 0 < len(by_case) <= MAX_CASES:
        raise SourceShareError("no verified approved RSS cases available")
    ordered = sorted(by_case, key=lambda case: sha256(case.encode()).hexdigest())
    predictions = [by_case[k][0] for k in ordered]
    prediction_file = _encoded({
        "schema": PREDICTIONS_SCHEMA,
        "frozen_at": prepared.isoformat(),
        "local_pin_first_observed_at": prepared.isoformat(),
        "realtime_detection_proof": False,
        "independent_gold_review_count": 0,
        "cases": [{
            **{k:(v.isoformat() if isinstance(v,datetime) else v)
               for k,v in asdict(row).items()},
        } for row in predictions],
    })
    if len(prediction_file) > MAX_FILE:
        raise SourceShareError("gold predictions too large")
    digest = sha256(prediction_file).hexdigest()
    blind = {
        "schema": BLIND_SCHEMA,
        "predictions_visible_to_reviewer": False,
        "source_body_included": False,
        "research_labels_filled": 0,
        "cases": [by_case[k][1] for k in ordered],
    }
    blind_file = _encoded(blind)
    template = {
        "schema": BLIND_SCHEMA,
        "reviewer_code": "UNASSIGNED",
        "labels": [{
            "case_sha256":k,"source_sha256":by_case[k][0].source_sha256,
            "true_duplicate":None,"important_event":None,
            "review_evidence_sha256":None,"reviewed_at":None,
        } for k in ordered],
    }
    template_file = _encoded(template)
    dest = root / ("gold_batch_" + digest)
    if dest.exists() or dest.is_symlink():
        raise SourceShareError("frozen gold batch already exists; no overwrite")
    stage = Path(tempfile.mkdtemp(prefix=".gold_staging_", dir=root))
    try:
        stage.chmod(0o700)
        for filename, body in (
            ("predictions.json",prediction_file),
            ("blind_cases.json",blind_file),
            ("human_review_template.json",template_file),
            ("publication.json",_encoded({
                "schema": SCHEMA,"status": "FROZEN_PREDICTIONS_AWAIT_HUMAN_REVIEW",
                "payload_sha256":digest,"prediction_file":"predictions.json",
                "blind_sha256":sha256(blind_file).hexdigest(),
                "template_sha256":sha256(template_file).hexdigest(),
                "case_count":len(ordered),
                "source_body_stored":False,"verified_accuracy":False,
                "prepared_at":prepared.isoformat(),
            })),
        ):
            if len(body) > MAX_FILE:
                raise SourceShareError("gold review component too large")
            _write_new(stage / filename, body)
        fd = os.open(stage, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(stage, dest)
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise SourceShareError("durable private gold sample export failed") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    # Locally independent trust record stamped AFTER durable SSD publication.
    pinned = _when((now or datetime.now(timezone.utc)).isoformat(),
                   "independent gold anchor observed")
    pin_file = pin_dir / ("gold_batch_" + digest + ".pin.json")
    pin_body = _encoded({
        "schema": PIN_SCHEMA, "payload_sha256": digest,
        "batch_name": dest.name, "source_batch_case_count":len(ordered),
        "blind_sha256":sha256(blind_file).hexdigest(),
        "template_sha256":sha256(template_file).hexdigest(),
        "first_local_observed_at":pinned.isoformat(),
        "trust_level":"LOCAL_OTHER_DISK_SHA_NOT_EXTERNAL_NOTARY",
    })
    try:
        _write_new(pin_file, pin_body)
        fd = os.open(pin_dir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        # Unpinned SSD batch remains diagnostic; cannot evaluate as frozen.
        raise SourceShareError("independent gold SHA pin missing") from exc
    return GoldBatch(dest,pin_file,digest,len(ordered),pinned)


def _load_pinned_predictions(batch_folder: Path, out_root: Path,
                             expected_sha: str, pin_file: Path, pin_root: Path,
                             at: datetime):
    digest = _must_sha(expected_sha,"trusted gold batch SHA")
    root = _private_root(out_root)
    pin_root = _private_root(pin_root)
    if not _different_disk(root, pin_root):
        raise SourceShareError("gold review pin not on independent device")
    folder = Path(batch_folder)
    if folder.parent != root or folder.name != "gold_batch_"+digest or folder.is_symlink():
        raise SourceShareError("untrusted frozen gold batch location")
    info=folder.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("unsafe frozen gold batch directory")
    if Path(pin_file) != pin_root / ("gold_batch_"+digest+".pin.json"):
        raise SourceShareError("independent SHA pin location mismatch")
    anchor = _json(_read_regular(pin_file, 4096),"gold pin")
    if (set(anchor) != {"schema","payload_sha256","batch_name",
                        "source_batch_case_count","blind_sha256","template_sha256",
                        "first_local_observed_at","trust_level"}
            or anchor.get("schema") != PIN_SCHEMA
            or anchor.get("trust_level") != "LOCAL_OTHER_DISK_SHA_NOT_EXTERNAL_NOTARY"
            or anchor.get("payload_sha256") != digest
            or anchor.get("batch_name") != folder.name):
        raise SourceShareError("gold pin trust/identity mismatch")
    pinned_at = _when(anchor["first_local_observed_at"], "gold first pinned")
    if pinned_at > at:
        raise SourceShareError("independent gold pin unavailable at evaluation")
    document = _read_regular(folder / "predictions.json", MAX_FILE)
    if sha256(document).hexdigest() != digest:
        raise SourceShareError("frozen prediction SHA differs from independent pin")
    manifest = _json(_read_regular(folder / "publication.json", 8192),
                     "gold frozen publication")
    if (manifest.get("schema") != SCHEMA
            or manifest.get("blind_sha256") != anchor.get("blind_sha256")
            or manifest.get("template_sha256") != anchor.get("template_sha256")
            or manifest.get("status") != "FROZEN_PREDICTIONS_AWAIT_HUMAN_REVIEW"
            or manifest.get("payload_sha256") != digest
            or manifest.get("source_body_stored") is not False):
        raise SourceShareError("frozen gold publication incomplete")
    payload = _json(document, "frozen gold predictions")
    if (payload.get("schema") != PREDICTIONS_SCHEMA
            or payload.get("independent_gold_review_count") != 0
            or not isinstance(payload.get("cases"),list)
            or len(payload["cases"]) != manifest.get("case_count")
            or len(payload["cases"]) != anchor.get("source_batch_case_count")):
        raise SourceShareError("frozen gold source count/shape invalid")
    predictions=[]
    for row in payload["cases"]:
        if not isinstance(row,dict) or set(row) != set(FrozenCasePrediction.__dataclass_fields__):
            raise SourceShareError("unexpected frozen prediction fields")
        updated = {k:(_when(v,k) if k in (
            "source_available_at","predicted_at","pin_first_observed_at") else v)
            for k,v in row.items()}
        predicted=FrozenCasePrediction(**updated)
        if prediction_digest(predicted)!=predicted.prediction_sha256:
            raise SourceShareError("frozen gold prediction changed")
        predictions.append(predicted)
    # Both original blind queue and marker must remain unchanged within private batch.
    blind_bytes = _read_regular(folder / "blind_cases.json",MAX_FILE)
    if sha256(blind_bytes).hexdigest() != _must_sha(anchor["blind_sha256"],"blind SHA"):
        raise SourceShareError("gold blind case sheet differs from independent pin")
    template_bytes = _read_regular(folder / "human_review_template.json",MAX_FILE)
    if sha256(template_bytes).hexdigest() != _must_sha(anchor["template_sha256"],"template SHA"):
        raise SourceShareError("gold review template differs from independent pin")
    blind = _json(blind_bytes, "gold blind review queue")
    if (blind.get("schema") != BLIND_SCHEMA
            or blind.get("predictions_visible_to_reviewer") is not False
            or blind.get("research_labels_filled") != 0
            or len(blind.get("cases",[])) != len(predictions)
            or {x["case_sha256"] for x in blind["cases"]} !=
               {p.case_sha256 for p in predictions}):
        raise SourceShareError("gold blind queue changed or incomplete")
    return tuple(predictions), pinned_at


def evaluate_live_gold_reviews(
    batch_folder: Path, out_root: Path, expected_sha: str,
    pin_file: Path, pin_root: Path,
    filled_reviews: tuple[Path,Path], *, now: datetime | None = None,
) -> dict:
    """Only operator-supplied two separate review files may produce metrics."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(),"now")
    if not isinstance(filled_reviews,tuple) or len(filled_reviews)!=2 or (
            filled_reviews[0] == filled_reviews[1]):
        raise SourceShareError("two independent human review files required")
    predictions,pinned_at=_load_pinned_predictions(
        batch_folder,out_root,expected_sha,pin_file,pin_root,at
    )
    case_by_id={p.case_sha256:p for p in predictions}
    reviews=[]
    codes=set()
    for filename in filled_reviews:
        filename=Path(filename)
        if not filename.is_absolute() or filename.is_symlink():
            raise SourceShareError("private reviewer file required")
        parent=_private_root(filename.parent)
        if filename.parent != parent:
            raise SourceShareError("unsafe reviewer location")
        entry=filename.lstat()
        if (not stat.S_ISREG(entry.st_mode) or entry.st_uid!=os.geteuid()
                or stat.S_IMODE(entry.st_mode)&0o077):
            raise SourceShareError("owner-only actual human review file required")
        sheet=_json(_read_regular(filename,MAX_FILE),"human review answers")
        reviewer=sheet.get("reviewer_code")
        from .gold_review_intake import REVIEWER_PATTERN
        if (sheet.get("schema") != BLIND_SCHEMA
                or not isinstance(reviewer,str)
                or REVIEWER_PATTERN.fullmatch(reviewer) is None
                or reviewer in codes
                or not isinstance(sheet.get("labels"),list)):
            raise SourceShareError("independent reviewer identity/list required")
        codes.add(reviewer)
        observed=set()
        for row in sheet["labels"]:
            if not isinstance(row,dict) or set(row) != {
                "case_sha256","source_sha256","true_duplicate","important_event",
                "review_evidence_sha256","reviewed_at"
            }:
                raise SourceShareError("unexpected blind review answer field")
            case=_must_sha(row["case_sha256"],"review case")
            if case in observed or case not in case_by_id:
                raise SourceShareError("duplicate or unknown review case")
            observed.add(case)
            predicted=case_by_id[case]
            if row["source_sha256"]!=predicted.source_sha256:
                raise SourceShareError("review source SHA differs from frozen source")
            truths=(row["true_duplicate"],row["important_event"])
            if truths==(None,None) and row["review_evidence_sha256"] is None and row["reviewed_at"] is None:
                continue
            if reviewer.startswith("UNASSIGNED"):
                raise SourceShareError("replace unassigned placeholder with actual reviewer code")
            if not all(type(v) is bool for v in truths):
                raise SourceShareError("partial or fabricated human gold label")
            ts=_when(row["reviewed_at"], "reviewed at")
            if not pinned_at <= ts <= at:
                raise SourceShareError("review is before independent SHA freeze")
            reviews.append(HumanGoldReview(
                case,predicted.source_sha256,reviewer,
                truths[0],truths[1],
                _must_sha(row["review_evidence_sha256"],"review evidence SHA"),ts
            ))
    report=prepare_gold_review_metrics(
        predictions,reviews,decision_at=at,now=at,
    )
    return {
        "status": "REAL_SOURCE_REVIEW_METRICS_PREVIEW_NOT_CERTIFIED",
        "sample_count":len(predictions),
        "reviewed_by_two_agreeing_humans":report.agreed_cases,
        "missing_or_partial_human_case_count":len(report.missing_case_ids),
        "disputed_case_count":len(report.disputed_case_ids),
        "required_gold_sample_count":500,
        "required_additional_cases":max(0,500-len(predictions)),
        "duplicate_precision":(
            report.duplicate_evaluation.precision
            if report.duplicate_evaluation else None),
        "important_event_recall":(
            report.important_recall.measured_recall
            if report.important_recall else None),
        "mathematical_threshold_met":report.sample_mathematically_eligible,
        "independent_provenance_certified":False,
        "release_gate_verified":False,
        "human_truth_invented":False,
    }


def prepare_blank_human_review_sheets(
    batch_folder: Path, out_root: Path, expected_sha: str, pin_file: Path,
    pin_root: Path, workspace_root: Path, *,
    now: datetime | None = None,
) -> tuple[Path, Path]:
    """Make two EMPTY owner-private editable copies; never assign real labels."""
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "review sheets prepared")
    originals, pinned = _load_pinned_predictions(
        batch_folder, out_root, expected_sha, pin_file, pin_root, at,
    )
    if pinned > at or not originals:
        raise SourceShareError("frozen real RSS candidates unavailable")
    protected = _private_root(workspace_root)
    batch = protected / ("gold_batch_" + _must_sha(expected_sha, "batch SHA"))
    if batch.exists() or batch.is_symlink():
        raise SourceShareError("reviewer workspace exists; existing answers are protected")
    template = _json(_read_regular(Path(batch_folder) / "human_review_template.json",
                                   MAX_FILE), "original blank human review template")
    if (template.get("schema") != BLIND_SCHEMA
            or template.get("reviewer_code") != "UNASSIGNED"
            or len(template.get("labels", [])) != len(originals)):
        raise SourceShareError("blind human review template invalid")
    if any(item.get("true_duplicate") is not None
           or item.get("important_event") is not None
           or item.get("review_evidence_sha256") is not None
           or item.get("reviewed_at") is not None
           for item in template["labels"]):
        raise SourceShareError("gold reviewer draft already contains labels")
    batch.mkdir(mode=0o700)
    paths = []
    try:
        for code in ("UNASSIGNED_A", "UNASSIGNED_B"):
            reviewer = batch / code
            reviewer.mkdir(mode=0o700)
            filled = dict(template)
            filled["reviewer_code"] = code
            target = reviewer / "answers.json"
            _write_new(target, _encoded(filled))
            paths.append(target)
        fd = os.open(batch, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        # No human answers predated this new workspace.
        shutil.rmtree(batch)
        raise
    return tuple(paths)
