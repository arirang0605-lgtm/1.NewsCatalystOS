"""5_2 metadata worklist: no invented semiconductor or supply relationships."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import argparse
import json
import stat

import pytest

from newscatalystos.official_review_queue import (
    SCHEMA, MARKER_SCHEMA, build_official_review_queue,
    publish_official_review_queue,
)
from newscatalystos.operational_observations import load_operational_observations
from newscatalystos.source_share import SourceShareError
from scripts.build_official_review_queue import evaluate
from test_published_observations import published


def observed(tmp_path, kind="dart-disclosures"):
    pub, root, pin, at, *_ = published(tmp_path, kind)
    return pub, root, pin, at, load_operational_observations(
        pub, root, pin, now=at,
    )


def test_dart_queue_uses_verified_metadata_without_semiconductor_inference(tmp_path):
    pub, root, pin, at, observations = observed(tmp_path)
    queue = build_official_review_queue(
        observations, decision_at=at, now=at,
    )
    doc = json.loads(queue.payload)
    assert doc["schema"] == SCHEMA
    assert doc["status"] == "OFFICIAL_METADATA_ONLY_MANUAL_SCREENING_REQUIRED"
    assert doc["total_eligible"] == 1 == doc["selected_count"]
    assert queue.payload_sha256 == sha256(queue.payload).hexdigest()
    item = doc["items"][0]
    row = observations.observations[0]
    assert item["source_document_id"] == row.source_document_id
    assert item["source_evidence_id"] == row.evidence_id
    assert item["source_receipt_sha256"] == row.receipt_sha256
    assert item["source_available_at"] == row.available_at.isoformat()
    assert item["industry_relevance"] == "UNKNOWN_UNSCREENED"
    assert item["supply_relation_status"] == "UNREVIEWED"
    assert not item["official_document_text_available"]
    assert not item["verified_real_transaction"]
    assert doc["verified_supply_relationship_count"] == 0
    assert doc["semiconductor_relevance_verified_count"] == 0
    assert "Supplier Alpha" not in queue.payload.decode()
    assert "text" not in item
    selected = build_official_review_queue(
        observations, decision_at=at,
        document_id=row.source_document_id, now=at,
    )
    assert json.loads(selected.payload)["requested_document_id"] == row.source_document_id
    with pytest.raises(SourceShareError, match="absent from verified"):
        build_official_review_queue(
            observations, decision_at=at,
            document_id="19990101000000", now=at,
        )


def test_sec_worklist_is_distinct_from_dart_and_market_context(tmp_path):
    for source_id in ("sec-submissions", "dart-disclosures"):
        pub, root, pin, at, obs = observed(tmp_path / source_id, source_id)
        queue = build_official_review_queue(
            obs, decision_at=at, source_id=source_id, now=at,
        )
        assert json.loads(queue.payload)["items"][0]["source_id"] == source_id
    _, _, _, at, market = observed(tmp_path / "market", "krx-kospi")
    queue = build_official_review_queue(market, decision_at=at, now=at)
    assert queue.total_eligible == queue.selected_count == 0


def test_pagination_is_stable_but_not_a_recommendation_ranking(tmp_path):
    _, _, _, at, obs = observed(tmp_path)
    row = obs.observations[0]
    second = replace(row, source_document_id="20261013000011",
                     evidence_id="c" * 64)
    obs = replace(obs, observations=(second, row))
    page = build_official_review_queue(obs, decision_at=at,
                                       offset=1, limit=1, now=at)
    data = json.loads(page.payload)
    assert data["total_eligible"] == 2 and data["selected_count"] == 1
    assert not data["has_more"]
    assert data["sort"] == "SOURCE_AND_DOCUMENT_ID_NOT_IMPORTANCE"
    first = build_official_review_queue(obs, decision_at=at,
                                        offset=0, limit=1, now=at)
    assert json.loads(first.payload)["has_more"] is True
    assert json.loads(first.payload)["items"][0]["source_document_id"] != data["items"][0]["source_document_id"]


def test_future_metadata_and_duplicate_document_ids_fail_closed(tmp_path):
    _, _, _, at, obs = observed(tmp_path)
    with pytest.raises(SourceShareError, match="unavailable"):
        build_official_review_queue(obs, decision_at=at-timedelta(seconds=1),
                                    now=at)
    with pytest.raises(SourceShareError, match="unavailable"):
        build_official_review_queue(obs, decision_at=at+timedelta(seconds=1),
                                    now=at)
    row = obs.observations[0]
    dup = replace(row, evidence_id="a" * 64)
    with pytest.raises(SourceShareError, match="duplicate"):
        build_official_review_queue(replace(obs, observations=(row, dup)),
                                    decision_at=at, now=at)


@pytest.mark.parametrize("offset,limit,source", [
    (-1, 10, "ALL"), (0, 0, "ALL"), (0, 2001, "ALL"),
    (True, 1, "ALL"), (0, 3, "UNKNOWN"),
])
def test_invalid_pagination_or_source_never_produces_queue(tmp_path, offset, limit, source):
    _, _, _, at, obs = observed(tmp_path)
    with pytest.raises(SourceShareError, match="invalid review queue"):
        build_official_review_queue(obs, decision_at=at,
                                    offset=offset, limit=limit,
                                    source_id=source, now=at)


def test_atomic_private_worklist_retains_evidence_shas_and_no_article_body(tmp_path):
    _, _, _, at, obs = observed(tmp_path)
    queue = build_official_review_queue(obs, decision_at=at, now=at)
    root = tmp_path / "owner-only-worklist"
    receipt = publish_official_review_queue(queue, root, now=at)
    assert receipt.payload_sha256 == queue.payload_sha256
    assert (receipt.location / "queue.json").read_bytes() == queue.payload
    marker = json.loads((receipt.location / "publication.json").read_bytes())
    assert marker["schema"] == MARKER_SCHEMA
    assert marker["status"] == "COMPLETE_METADATA_ONLY"
    assert marker["marker_prepared_at"] == at.isoformat()
    assert "first_local_published_at" not in marker
    assert receipt.published_at == at
    assert not marker["official_text_stored"]
    assert marker["verified_supply_relationship_count"] == 0
    assert marker["payload_sha256"] == queue.payload_sha256
    assert stat.S_IMODE(receipt.location.stat().st_mode) == 0o700
    assert stat.S_IMODE((receipt.location / "queue.json").stat().st_mode) == 0o600
    other = publish_official_review_queue(queue, root, now=at)
    assert other.location != receipt.location
    assert (receipt.location / "queue.json").read_bytes() == queue.payload
    assert not any(p.name.startswith(".review_staging") for p in root.iterdir())


def test_private_queue_rejects_public_directory_and_corrupted_payload(tmp_path):
    _, _, _, at, obs = observed(tmp_path)
    queue = build_official_review_queue(obs, decision_at=at, now=at)
    root = tmp_path / "world-readable"
    root.mkdir(mode=0o700)
    root.chmod(0o755)
    with pytest.raises(SourceShareError, match="owner-only"):
        publish_official_review_queue(queue, root, now=at)
    with pytest.raises(SourceShareError, match="corrupted"):
        publish_official_review_queue(replace(queue, payload=queue.payload+b"!"),
                                      tmp_path / "safe-output", now=at)


def test_cli_end_to_end_uses_completed_readonly_publication(tmp_path):
    pub, root, pin, at, obs = observed(tmp_path)
    args = argparse.Namespace(
        publication=pub, publication_root=root, payload_sha256=pin,
        source_id="ALL", document_id=None, limit=25, offset=0,
        output_root=tmp_path / "screened-output",
    )
    code, report = evaluate(args, now=at)
    assert code == 0 and report["status"] == "RESEARCH_METADATA_REVIEW_QUEUE_READY"
    assert report["item_count"] == report["total_eligible"] == 1
    assert report["verified_relation_count"] == 0
    assert json.loads((args.output_root /
                       next(args.output_root.iterdir()).name / "queue.json"
                       ).read_bytes())["selected_count"] == 1
    args.document_id = obs.observations[0].source_document_id
    code, selected = evaluate(args, now=at)
    assert code == 0 and selected["item_count"] == 1
    args.document_id = "19990101000000"
    code, absent = evaluate(args, now=at)
    assert code == 4 and absent["status"] == "DATA_UNAVAILABLE"
    args.document_id = None
    args.payload_sha256 = "0" * 64
    code, failed = evaluate(args, now=at)
    assert code == 4 and failed["status"] == "DATA_UNAVAILABLE"
