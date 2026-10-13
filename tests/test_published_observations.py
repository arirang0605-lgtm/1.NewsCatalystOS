"""Synthetic tests for fail-closed research-only publication consumption."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from newscatalystos.observed_batch import build_observed_official_batch, STATUS
from newscatalystos.published_observations import read_published_observations
from newscatalystos.source_share import SourceShareError
from scripts.inspect_official_observations import _private_output
from test_observed_batch import ANCHOR, NOW, sources


def published(tmp_path, source="sec-submissions"):
    verified, original_folder, before = sources(tmp_path / "captures", source)
    batch = build_observed_official_batch(verified, ANCHOR, NOW, now=NOW)
    root = tmp_path / "local-private"
    publication = _private_output("research.json", batch.to_json_bytes(), root=root)
    marker = json.loads((publication / "publication.json").read_bytes())
    at = datetime.fromisoformat(marker["first_local_published_at"])
    decision = at + timedelta(seconds=2)
    pin = sha256((publication / "observations.json").read_bytes()).hexdigest()
    return publication, root, pin, decision, original_folder, before


def read(published_tuple):
    folder, root, pin, decision, _, _ = published_tuple
    return read_published_observations(folder, root, pin, decision, now=decision)


def tamper_json(pub, name, modifier):
    path = pub / name
    value = json.loads(path.read_bytes())
    modifier(value)
    path.write_bytes((json.dumps(value, sort_keys=True) + "\n").encode())


@pytest.mark.parametrize("source,count", [
    ("krx-kospi", 1), ("krx-kosdaq", 1), ("dart-disclosures", 1),
    ("sec-submissions", 1), ("sec-companyfacts", 0),
])
def test_verified_publication_retains_unknown_release_and_origins(tmp_path, source, count):
    info = published(tmp_path, source)
    result = read(info)
    assert result.research_only is True
    assert len(result.as_of(info[3], now=info[3])) == count
    assert result.source_count == 1
    assert result.local_published_at <= info[3]
    for row in result.rows:
        assert row.classification == STATUS
        assert row.published_at is None
        assert row.issuer_verified is False
        assert row.usable_from < result.local_published_at
        assert row.original_sha256 and row.receipt_sha256
    folder, _, _, _, original, before = info
    assert {f.name: sha256(f.read_bytes()).hexdigest() for f in original.iterdir()} == before


def test_future_or_backdated_research_publication_rejected(tmp_path):
    info = published(tmp_path)
    folder, root, pin, decision, _, _ = info
    result = read(info)
    with pytest.raises(SourceShareError, match="unavailable"):
        result.as_of(result.local_published_at - timedelta(microseconds=1), now=decision)
    with pytest.raises(SourceShareError, match="unavailable"):
        result.as_of(decision + timedelta(seconds=1), now=decision)
    with pytest.raises(SourceShareError, match="did not exist"):
        read_published_observations(folder, root, pin,
                                    result.local_published_at - timedelta(microseconds=1),
                                    now=decision)


def test_wrong_independent_payload_pin_rejected(tmp_path):
    info = published(tmp_path)
    folder, root, _, decision, _, _ = info
    with pytest.raises(SourceShareError, match="unverified or incomplete"):
        read_published_observations(folder, root, "0" * 64, decision, now=decision)


def test_mutated_payload_rejected(tmp_path):
    info = published(tmp_path)
    p = info[0] / "observations.json"
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(SourceShareError, match="SHA or length mismatch"):
        read(info)


@pytest.mark.parametrize("field,value", [
    ("status", "COMPLETE"),
    ("certified_raw_event_count", 1),
    ("payload_file", "../forged"),
    ("first_local_published_at", "2099-01-01T00:00:00Z"),
])
def test_forged_or_future_publication_marker_rejected(tmp_path, field, value):
    info = published(tmp_path)
    tamper_json(info[0], "publication.json", lambda m: m.__setitem__(field, value))
    with pytest.raises(SourceShareError):
        read(info)


@pytest.mark.parametrize("field,value", [
    ("published_at", "2026-10-01T00:00:00Z"),
    ("issuer_verified", True),
    ("classification", "OFFICIAL_CONFIRMED"),
    ("usable_from", "2026-10-01T00:00:00Z"),
    ("provider_id", "DART"),
    ("evidence_id", "A" * 64),
    ("source_quality", "CERTIFIED"),
    ("source_quality", ["malformed"]),
    ("provider_acceptance_at", None),
])
def test_forged_row_rejected_even_if_local_digest_recomputed(tmp_path, field, value):
    info = published(tmp_path)
    folder, root, _, decision, _, _ = info
    tamper_json(folder, "observations.json",
                lambda b: b["rows"][0].__setitem__(field, value))
    raw = (folder / "observations.json").read_bytes()
    new_pin = sha256(raw).hexdigest()
    tamper_json(folder, "publication.json",
                lambda m: m.update(payload_sha256=new_pin,
                                   payload_size_bytes=len(raw)))
    with pytest.raises(SourceShareError):
        read_published_observations(folder, root, new_pin, decision, now=decision)


def test_duplicate_evidence_records_rejected(tmp_path):
    info = published(tmp_path)
    folder, root, _, decision, _, _ = info
    tamper_json(folder, "observations.json",
                lambda b: (b["rows"].append(dict(b["rows"][0])),
                           b.update(row_count=2)))
    raw = (folder / "observations.json").read_bytes()
    pin = sha256(raw).hexdigest()
    tamper_json(folder, "publication.json",
                lambda m: m.update(payload_sha256=pin,
                                   payload_size_bytes=len(raw)))
    with pytest.raises(SourceShareError, match="duplicate research observation"):
        read_published_observations(folder, root, pin, decision, now=decision)


def test_partial_publication_and_symlink_root_rejected(tmp_path):
    info = published(tmp_path)
    folder, root, pin, decision, _, _ = info
    (folder / "publication.json").unlink()
    with pytest.raises(SourceShareError, match="unavailable"):
        read(info)
    other = tmp_path / "alias"
    other.symlink_to(root, target_is_directory=True)
    with pytest.raises(SourceShareError, match="owner-private"):
        read_published_observations(other / folder.name, other, pin, decision, now=decision)


def test_malformed_old_marker_without_publish_time_fails_closed(tmp_path):
    info = published(tmp_path)
    tamper_json(info[0], "publication.json",
                lambda m: m.pop("first_local_published_at"))
    with pytest.raises(SourceShareError, match="unverified or incomplete"):
        read(info)


def test_outside_root_access_rejected(tmp_path):
    info = published(tmp_path)
    folder, root, pin, decision, _, _ = info
    with pytest.raises(SourceShareError, match="outside approved"):
        read_published_observations(folder, root / "other",
                                    pin, decision, now=decision)
