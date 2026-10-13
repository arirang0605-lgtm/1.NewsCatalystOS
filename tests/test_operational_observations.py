"""Operational observations are usable after verified receipt, not release claims."""
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.operational_observations import (
    SCHEMA, STATUS, load_operational_observations, project_operational_observations,
)
from newscatalystos.published_observations import read_published_observations
from newscatalystos.source_share import SourceShareError
from test_published_observations import published


@pytest.mark.parametrize("source,expected,kind", [
    ("sec-submissions", 1, "DISCLOSURE_OBSERVED"),
    ("dart-disclosures", 1, "DISCLOSURE_OBSERVED"),
    ("krx-kospi", 1, "MARKET_CONTEXT_NOT_NEWS"),
    ("krx-kosdaq", 1, "MARKET_CONTEXT_NOT_NEWS"),
    ("sec-companyfacts", 0, "MARKET_CONTEXT_NOT_NEWS"),
])
def test_verified_source_metadata_operational_but_release_unknown(
    tmp_path, source, expected, kind,
):
    info = published(tmp_path, source)
    folder, root, digest, moment, original, before = info
    collection = load_operational_observations(folder, root, digest, now=moment)
    assert collection.coverage_verified
    assert collection.source_count == 1
    assert len(collection.as_of(moment, now=moment)) == expected
    for row in collection.observations:
        assert row.schema_version == SCHEMA and row.status == STATUS
        assert row.data_kind == kind
        assert row.published_at is None
        assert row.issuer_verified is False and row.release_certified is False
        assert row.available_at >= moment
        assert row.first_seen_at <= row.available_at
        assert row.original_sha256 and row.receipt_sha256
        with pytest.raises(SourceShareError, match="not independently certified"):
            row.to_raw_event()
    assert {p.name: sha256(p.read_bytes()).hexdigest()
            for p in original.iterdir()} == before


def test_late_validation_never_backfills_historical_decision(tmp_path):
    folder, root, digest, moment, *_ = published(tmp_path)
    collection = load_operational_observations(folder, root, digest, now=moment)
    earlier = moment - timedelta(microseconds=1)
    with pytest.raises(SourceShareError, match="unavailable"):
        collection.as_of(earlier, now=moment)
    earlier_verified = read_published_observations(
        folder, root, digest, moment, now=moment
    )
    with pytest.raises(SourceShareError, match="backdate"):
        project_operational_observations(
            earlier_verified, earlier, now=moment
        )
    assert all(row.available_at == moment for row in collection.observations)


def test_legacy_v1_cannot_be_operationally_promoted(tmp_path):
    folder, root, digest, moment, *_ = published(tmp_path)
    pub = read_published_observations(folder, root, digest, moment, now=moment)
    from dataclasses import replace
    with pytest.raises(SourceShareError, match="v2 source coverage"):
        project_operational_observations(
            replace(pub, coverage_verified=False), moment, now=moment
        )


def test_bad_pin_or_missing_atomic_marker_not_usable(tmp_path):
    folder, root, digest, moment, *_ = published(tmp_path)
    with pytest.raises(SourceShareError):
        load_operational_observations(folder, root, "0" * 64, now=moment)
    (folder / "publication.json").unlink()
    with pytest.raises(SourceShareError):
        load_operational_observations(folder, root, digest, now=moment)


def test_false_certification_and_unverified_source_coverage_rejected(tmp_path):
    from dataclasses import replace
    folder, root, digest, moment, *_ = published(tmp_path)
    pub = read_published_observations(folder, root, digest, moment, now=moment)
    with pytest.raises(SourceShareError, match="masquerading"):
        project_operational_observations(
            replace(pub, rows=(replace(pub.rows[0], published_at=moment),)),
            moment, now=moment,
        )
    with pytest.raises(SourceShareError, match="coverage"):
        project_operational_observations(
            replace(pub, source_count=2), moment, now=moment
        )
