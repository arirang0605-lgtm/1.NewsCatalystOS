"""Synthetic-only contract tests: NEVER touch EraLeader real data or Git."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

import pytest

from newscatalystos.source_share import SourceShareError, read_verified_bundle

T0 = "2026-10-12T10:00:00+00:00"
T1 = "2026-10-12T10:01:00+00:00"
T2 = "2026-10-12T10:02:00+00:00"
T3 = "2026-10-12T11:00:00+00:00"
NOW = datetime.fromisoformat(T3)
SHA = "a" * 64


def raw_event(**changes):
    row = {
        "schema": "newscatalyst.raw_event.v1", "event_id": "event001",
        "source_id": "dart-disclosures", "provider_id": "DART",
        "source_document_id": "doc001", "company_id": "corp001",
        "published_at": T0, "first_seen_at": T1,
        "source_sha256": SHA, "source_receipt_sha256": SHA,
    }
    return dict(row, **changes)


def publish(tmp_path, *, rows=None, manifest_changes=None, marker_changes=None):
    era = tmp_path / "eraleader"
    bundle = era / "output" / "published" / "snapshot001"
    bundle.mkdir(parents=True)
    events = (b"".join(json.dumps(x, sort_keys=True).encode() + b"\n"
                       for x in (rows if rows is not None else [raw_event()])))
    (bundle / "events.jsonl").write_bytes(events)
    manifest = {
        "schema": "newscatalyst.source_manifest.v1", "status": "COMPLETE",
        "publisher_id": "eraleader", "quality_status": "PASS",
        "snapshot_id": "snapshot001", "provider_id": "DART",
        "source_id": "dart-disclosures", "source_schema_version": "eraleader.receipt.v1",
        "published_at": T2, "first_seen_at": T1, "first_receipt_sha256": SHA,
        "events_file": "events.jsonl", "events_sha256": sha256(events).hexdigest(),
        "events_size_bytes": len(events), "event_count": len(rows) if rows is not None else 1,
    }
    manifest.update(manifest_changes or {})
    content = json.dumps(manifest, sort_keys=True).encode()
    (bundle / "manifest.json").write_bytes(content)
    digest = sha256(content).hexdigest()
    marker = {
        "schema": "newscatalyst.publication.v1", "status": "COMPLETE",
        "publisher_id": "eraleader", "published_at": T2, "manifest_sha256": digest,
    }
    marker.update(marker_changes or {})
    (bundle / "publication.json").write_text(json.dumps(marker))
    return era, bundle, digest


def read(era, bundle, digest, at=NOW):
    return read_verified_bundle(bundle, era, digest, at, now=NOW)


def test_valid_bundle_preserves_provenance_and_raw_bytes(tmp_path):
    era, bundle, digest = publish(tmp_path)
    before = {p.name: sha256(p.read_bytes()).digest() for p in bundle.iterdir()}
    result = read(era, bundle, digest)
    assert result.manifest.provider_id == "DART"
    assert result.manifest.manifest_sha256 == digest
    assert result.manifest.first_receipt_sha256 == SHA
    assert len(result.events) == 1
    assert result.events[0].source_sha256 == SHA
    assert result.events[0].first_seen_at == datetime.fromisoformat(T1)
    assert before == {p.name: sha256(p.read_bytes()).digest() for p in bundle.iterdir()}
    assert read(era, bundle, digest) == result


def test_not_published_is_blocked(tmp_path):
    era, bundle, digest = publish(tmp_path)
    (bundle / "publication.json").unlink()
    with pytest.raises(SourceShareError):
        read(era, bundle, digest)


def test_marker_in_progress_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path, marker_changes={"status": "WRITING"})
    with pytest.raises(SourceShareError, match="COMPLETE"):
        read(era, bundle, digest)


def test_wrong_manifest_pin_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    with pytest.raises(SourceShareError, match="digest|COMPLETE"):
        read(era, bundle, "c" * 64)


def test_changed_events_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    (bundle / "events.jsonl").write_bytes(b'{"tampered":true}\n')
    with pytest.raises(SourceShareError, match="match"):
        read(era, bundle, digest)


@pytest.mark.parametrize("override", [
    {"quality_status": "FAIL"}, {"status": "WRITING"},
    {"provider_id": "TWITTER"}, {"events_file": "../secret.jsonl"},
    {"first_seen_at": "2026-10-12T14:00:00+00:00"},
    {"published_at": "2026-10-12T14:00:00+00:00"},
])
def test_bad_manifest_is_blocked(tmp_path, override):
    era, bundle, digest = publish(tmp_path, manifest_changes=override)
    with pytest.raises(SourceShareError):
        read(era, bundle, digest)


def test_future_decision_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    future = datetime.fromisoformat("2026-10-13T11:00:00+00:00")
    with pytest.raises(SourceShareError, match="future"):
        read(era, bundle, digest, future)


def test_pit_before_publication_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    early = datetime.fromisoformat(T1)
    with pytest.raises(SourceShareError, match="publication"):
        read(era, bundle, digest, early)


def test_future_event_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path, rows=[
        raw_event(published_at="2026-10-13T10:00:00+00:00",
                  first_seen_at="2026-10-13T10:01:00+00:00")])
    with pytest.raises(SourceShareError, match="future"):
        read(era, bundle, digest)


def test_duplicate_event_ids_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path, rows=[raw_event(), raw_event()])
    with pytest.raises(SourceShareError, match="duplicate event"):
        read(era, bundle, digest)


def test_event_provider_mismatch_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path, rows=[raw_event(provider_id="SEC")])
    with pytest.raises(SourceShareError, match="source mismatch"):
        read(era, bundle, digest)


def test_symlink_bundle_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    link = era / "output" / "linked"
    link.symlink_to(bundle, target_is_directory=True)
    with pytest.raises(SourceShareError, match="symlink"):
        read(era, link, digest)


def test_symlink_event_file_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    original = bundle / "events.jsonl"
    other = tmp_path / "other.jsonl"
    original.rename(other)
    original.symlink_to(other)
    with pytest.raises(SourceShareError, match="unsafe"):
        read(era, bundle, digest)


def test_outside_era_root_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    with pytest.raises(SourceShareError, match="outside"):
        read(tmp_path / "elsewhere", bundle, digest)


def test_unpinned_manifest_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    with pytest.raises(SourceShareError, match="expected_manifest_sha256"):
        read(era, bundle, "")


def test_naive_decision_rejected(tmp_path):
    era, bundle, digest = publish(tmp_path)
    with pytest.raises(SourceShareError, match="timezone"):
        read(era, bundle, digest, datetime(2026, 10, 12, 11))


def test_missing_real_publication_fails_closed(tmp_path):
    era = tmp_path / "eraleader"
    (era / "output" / "unfinished").mkdir(parents=True)
    with pytest.raises(SourceShareError):
        read(era, era / "output" / "unfinished", SHA)


def test_unrelated_receipt_cannot_be_spliced(tmp_path):
    era, bundle, digest = publish(tmp_path, rows=[raw_event(source_receipt_sha256="f" * 64)])
    with pytest.raises(SourceShareError, match="receipt not pinned"):
        read(era, bundle, digest)
