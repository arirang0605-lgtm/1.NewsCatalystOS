"""3_6 immutable version lineage, time-safe replay and honest recall metrics."""
from dataclasses import replace
from datetime import timedelta
import pytest

from newscatalystos.detection_history import (
    DetectionInput, record_detection, detection_history_as_of,
    evaluate_important_detection_recall,
)
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import NOW


def candidate(value="b"*64,category="NEW_FACT_CANDIDATE",**changes):
    fields=dict(event_sha256="a"*64,source_sha256="c"*64,
                claim_value_sha256=value,category=category,
                first_source_seen_at=NOW)
    fields.update(changes)
    return DetectionInput(**fields)


def db(tmp_path):
    return tmp_path/"private"/"detection.sqlite3"


def test_initial_record_idempotent_and_pit_protected(tmp_path):
    path=db(tmp_path)
    original=record_detection(path,candidate(),now=NOW)
    again=record_detection(path,candidate(),now=NOW)
    assert original==again
    assert original.published_at is None
    assert len(detection_history_as_of(path,NOW,now=NOW))==1
    assert not detection_history_as_of(path,NOW-timedelta(seconds=1),now=NOW)


def test_revisions_append_without_overwriting_before_asof(tmp_path):
    path=db(tmp_path)
    initial=record_detection(path,candidate(),now=NOW)
    later=NOW+timedelta(seconds=2)
    revised=record_detection(path,candidate(
        value="d"*64,category="STRENGTHENED_CANDIDATE",
        supersedes_version_sha256=initial.version_sha256),now=later)
    assert revised.version_sha256!=initial.version_sha256
    assert revised.supersedes_version_sha256==initial.version_sha256
    assert len(detection_history_as_of(path,NOW,now=later))==1
    assert len(detection_history_as_of(path,later,now=later))==2


def test_fake_parent_or_changed_lineage_rejected(tmp_path):
    path=db(tmp_path)
    initial=record_detection(path,candidate(),now=NOW)
    with pytest.raises(SourceShareError,match="lineage"):
        record_detection(path,candidate(value="d"*64,
                     supersedes_version_sha256="f"*64),now=NOW)
    with pytest.raises(SourceShareError,match="collision"):
        record_detection(path,candidate(
            supersedes_version_sha256=initial.version_sha256),now=NOW)


def test_future_capture_does_not_enter_history(tmp_path):
    path=db(tmp_path)
    with pytest.raises(SourceShareError,match="future"):
        record_detection(path,candidate(
            first_source_seen_at=NOW+timedelta(seconds=1)),now=NOW)
    with pytest.raises(SourceShareError,match="future"):
        detection_history_as_of(path,NOW+timedelta(days=1),now=NOW)


def test_perfect_synthetic_detection_metric_is_not_certified():
    expected=("a"*64,"b"*64,"c"*64)
    result=evaluate_important_detection_recall(expected,expected,target=.9)
    assert result.measured_recall==1.0
    assert result.target_met_on_supplied_labels
    assert not result.release_gate_verified


def test_missing_important_events_reported_separately():
    expected=("a"*64,"b"*64,"c"*64)
    result=evaluate_important_detection_recall(expected,("a"*64,),target=.9)
    assert result.measured_recall==pytest.approx(1/3)
    assert len(result.missed_important_ids)==2
    assert not result.target_met_on_supplied_labels


def test_no_gold_labels_never_count_as_100_recall():
    outcome=evaluate_important_detection_recall((),(),target=.9)
    assert outcome.measured_recall is None
    assert not outcome.target_met_on_supplied_labels
