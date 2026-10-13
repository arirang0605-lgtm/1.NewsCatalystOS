"""Synthetic, strict as-of contract for research-only official observations."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from newscatalystos.era_capture_share import read_official_capture
from newscatalystos.observed_batch import (
    SCHEMA, STATUS, build_observed_official_batch,
)
from newscatalystos.source_share import SourceShareError
from newscatalystos.verified_reference import VerifiedOfficialSources
from test_era_capture_share import NOW, fixture

ANCHOR = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


def sources(tmp_path, provider="dart-disclosures"):
    era, folder, pin = fixture(tmp_path, provider)
    before = {
        f.name: sha256(f.read_bytes()).hexdigest()
        for f in folder.iterdir()
    }
    capture = read_official_capture(folder, era, pin, NOW, now=NOW)
    return VerifiedOfficialSources(report_sha256="a" * 64,
                                   captures=(capture,)), folder, before


@pytest.mark.parametrize("source,count", [
    ("krx-kospi", 1), ("krx-kosdaq", 1), ("dart-disclosures", 1),
    ("sec-submissions", 1), ("sec-companyfacts", 0),
])
def test_safe_real_format_metadata_output(tmp_path, source, count):
    verified, folder, before = sources(tmp_path, source)
    batch = build_observed_official_batch(verified, ANCHOR, NOW, now=NOW)
    assert batch.schema_version == SCHEMA
    assert batch.source_count == 1
    assert len(batch.rows) == count
    assert batch.research_only
    assert batch.as_of(NOW, now=NOW) == batch.rows
    payload = json.loads(batch.to_json_bytes())
    assert payload["certified_raw_event_count"] == 0
    assert payload["research_only"] is True
    assert payload["row_count"] == count
    assert all(row["classification"] == STATUS and
               row["published_at"] is None and
               row["issuer_verified"] is False and
               row["usable_from"] == ANCHOR.isoformat()
               for row in payload["rows"])
    assert before == {f.name: sha256(f.read_bytes()).hexdigest()
                      for f in folder.iterdir()}


def test_deterministic_output_and_sha_lineage(tmp_path):
    verified, folder, _ = sources(tmp_path, "sec-submissions")
    batch = build_observed_official_batch(verified, ANCHOR, NOW, now=NOW)
    batch_again = build_observed_official_batch(verified, ANCHOR, NOW, now=NOW)
    assert batch.to_json_bytes() == batch_again.to_json_bytes()
    record = batch.rows[0]
    assert record.receipt_sha256 == verified.captures[0].first_receipt_sha256
    assert record.original_sha256 == verified.captures[0].raw_sha256
    assert record.provider_acceptance_at is not None
    assert record.provider_acceptance_at != record.first_seen_at
    assert record.published_at is None


@pytest.mark.parametrize("offset", [-1, 1])
def test_anchor_or_decision_time_outside_window_rejected(tmp_path, offset):
    verified, _, _ = sources(tmp_path)
    with pytest.raises(SourceShareError, match="anchor unavailable"):
        build_observed_official_batch(
            verified, ANCHOR, ANCHOR + timedelta(seconds=offset),
            now=NOW if offset < 0 else ANCHOR,
        )


def test_prior_decision_cannot_use_later_anchor(tmp_path):
    verified, _, _ = sources(tmp_path)
    with pytest.raises(SourceShareError, match="anchor unavailable"):
        build_observed_official_batch(
            verified, ANCHOR, ANCHOR - timedelta(microseconds=1), now=NOW,
        )


def test_asof_cannot_backdate_research_batch(tmp_path):
    verified, _, _ = sources(tmp_path)
    batch = build_observed_official_batch(verified, ANCHOR, NOW, now=NOW)
    with pytest.raises(SourceShareError, match="not available"):
        batch.as_of(ANCHOR, now=NOW)
    with pytest.raises(SourceShareError, match="not available"):
        batch.as_of(NOW + timedelta(seconds=1), now=NOW)


def test_invalid_source_research_claims_rejected(tmp_path):
    verified, _, _ = sources(tmp_path)
    capture = verified.captures[0]
    fake = replace(verified, captures=(replace(capture, release_time_verified=True),))
    with pytest.raises(SourceShareError, match="falsely certified"):
        build_observed_official_batch(fake, ANCHOR, NOW, now=NOW)
    fake_dup = replace(verified, captures=(capture, capture))
    with pytest.raises(SourceShareError, match="duplicate research source"):
        build_observed_official_batch(fake_dup, ANCHOR, NOW, now=NOW)
    fake_future = replace(verified, captures=(
        replace(capture, first_seen_at=ANCHOR + timedelta(hours=1)),))
    with pytest.raises(SourceShareError, match="after independent"):
        build_observed_official_batch(fake_future, ANCHOR, NOW, now=NOW)
    with pytest.raises(SourceShareError, match="verified research"):
        build_observed_official_batch(replace(verified, research_only=False),
                                      ANCHOR, NOW, now=NOW)


def test_private_research_publication_atomically_committed(tmp_path):
    from scripts.inspect_official_observations import _private_output
    verified, _, _ = sources(tmp_path / "captures", "dart-disclosures")
    batch = build_observed_official_batch(verified, ANCHOR, NOW, now=NOW)
    data = batch.to_json_bytes()
    target = _private_output("sample.json", data, root=tmp_path / "private-output")
    assert target.is_dir()
    assert (target / "observations.json").read_bytes() == data
    marker = json.loads((target / "publication.json").read_text())
    assert marker["status"] == "COMPLETE_RESEARCH_ONLY"
    assert marker["payload_sha256"] == sha256(data).hexdigest()
    assert marker["certified_raw_event_count"] == 0
    assert sorted(path.name for path in target.iterdir()) == [
        "observations.json", "publication.json"
    ]
    assert not list(target.parent.glob(".staging_*"))
    another = _private_output("sample.json", data, root=tmp_path / "private-output")
    assert another != target and target.is_dir()
    assert (target / "observations.json").read_bytes() == data


@pytest.mark.parametrize("bad", ["../escape.json", "file/escape.json", "../foo", ".hidden.json", "bad.txt"])
def test_private_publication_rejects_unsafe_filename(tmp_path, bad):
    from scripts.inspect_official_observations import _private_output
    with pytest.raises(SourceShareError, match="invalid private output"):
        _private_output(bad, b"{}", root=tmp_path / "private-output")
    assert not (tmp_path / "private-output").exists()


def test_private_publication_blocks_symlink_and_world_access(tmp_path):
    from scripts.inspect_official_observations import _private_output
    source = tmp_path / "external"
    source.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(source, target_is_directory=True)
    with pytest.raises(SourceShareError, match="owner-only"):
        _private_output("safe.json", b"{}", root=linked)
    open_directory = tmp_path / "unsafe"
    open_directory.mkdir(mode=0o755)
    open_directory.chmod(0o755)
    with pytest.raises(SourceShareError, match="owner-only"):
        _private_output("safe.json", b"{}", root=open_directory)


def test_source_coverage_tracks_zero_event_taxonomy_without_promotion(tmp_path):
    verified, _, _ = sources(tmp_path, "sec-companyfacts")
    batch = build_observed_official_batch(verified, ANCHOR, NOW, now=NOW)
    payload = json.loads(batch.to_json_bytes())
    assert payload["schema"] == SCHEMA
    assert payload["row_count"] == 0
    assert payload["source_count"] == 1
    assert len(payload["source_coverage"]) == 1
    item = payload["source_coverage"][0]
    assert item["source_id"] == "sec-companyfacts"
    assert item["observed_count"] == 2
    assert item["metadata_count"] == 0
    assert item["original_sha256"] == verified.captures[0].raw_sha256
    assert item["receipt_sha256"] == verified.captures[0].first_receipt_sha256


def test_multiple_source_summaries_cross_reference_rows(tmp_path):
    from newscatalystos.verified_reference import VerifiedOfficialSources
    captures = []
    for source in ("sec-companyfacts", "sec-submissions", "dart-disclosures"):
        verified, _, _ = sources(tmp_path / source, source)
        captures.extend(verified.captures)
    combined = VerifiedOfficialSources(
        report_sha256="a" * 64, captures=tuple(captures),
    )
    batch = build_observed_official_batch(combined, ANCHOR, NOW, now=NOW)
    p = json.loads(batch.to_json_bytes())
    assert p["source_count"] == 3
    assert p["row_count"] == 2
    assert sum(x["metadata_count"] for x in p["source_coverage"]) == 2
    assert p["source_coverage"][0]["source_id"] == "sec-companyfacts"
    assert p["source_coverage"][0]["metadata_count"] == 0
