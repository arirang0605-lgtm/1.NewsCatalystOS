"""1_5 append-only license-gated local evidence receipts."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.evidence_archive import archive_evidence, read_archived_evidence
from newscatalystos.source_share import SourceShareError
from test_new_source_adapter import registry, NOW


def metadata(label="A new chip design"):
    return json.dumps({
        "source_id": "synthetic-government-feed",
        "event_id": "a" * 64,
        "source_url": "https://example.org/news?id=1",
        "headline": label,
    }, sort_keys=True).encode()


def test_archive_metadata_sha_idempotence_and_private_perms(tmp_path):
    root = tmp_path / "private"
    provider = registry().providers[0]
    payload = metadata()
    first = archive_evidence(root, provider, "a" * 64, payload, first_verified_at=NOW, now=NOW)
    assert len(first.payload_sha256) == 64
    assert first.payload_sha256 == sha256(payload).hexdigest()
    again = archive_evidence(
        root, provider, "a" * 64, payload, first_verified_at=NOW + timedelta(seconds=10), now=NOW + timedelta(seconds=10)
    )
    assert again.version_id == first.version_id
    assert again.receipt_sha256 == first.receipt_sha256
    assert again.first_verified_at == NOW
    assert len(list(root.iterdir())) == 1
    original, loaded = read_archived_evidence(root, first.version_id, decision_at=NOW)
    assert original == payload
    assert loaded == first
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / first.version_id / "payload.bin").stat().st_mode & 0o777 == 0o600
    assert (root / first.version_id / "receipt.json").stat().st_mode & 0o777 == 0o600


def test_correction_keeps_old_bytes_and_sha(tmp_path):
    root = tmp_path / "private"
    provider = registry().providers[0]
    one = metadata("first source")
    two = metadata("corrected facts")
    first_at = NOW + timedelta(seconds=2)
    first = archive_evidence(root, provider, "doc-1", one, first_verified_at=first_at, now=first_at)
    second = archive_evidence(
        root, provider, "doc-1", two,
        first_verified_at=first_at + timedelta(seconds=1),
        now=first_at + timedelta(seconds=1),
        supersedes_version_id=first.version_id,
    )
    assert first.version_id != second.version_id
    assert second.supersedes_version_id == first.version_id
    assert read_archived_evidence(root, first.version_id, decision_at=first_at)[0] == one
    assert read_archived_evidence(root, second.version_id,
                                  decision_at=first_at+timedelta(seconds=1))[0] == two
    assert len(list(root.iterdir())) == 2
    with pytest.raises(SourceShareError, match="earlier version"):
        archive_evidence(root, provider, "doc-1", metadata("backdated"),
                         first_verified_at=NOW + timedelta(seconds=1),
                         now=NOW + timedelta(seconds=1),
                         supersedes_version_id=first.version_id)


def test_raw_article_body_requires_written_license(tmp_path):
    provider = registry().providers[0]
    root = tmp_path / "safe"
    with pytest.raises(SourceShareError, match="licensed original"):
        archive_evidence(root, provider, "doc1", b"this is source body",
                         scope="LICENSED_SOURCE_BYTES", first_verified_at=NOW, now=NOW)
    assert not root.exists()
    licensed = replace(provider, grant="WRITTEN_LICENSE",
                       allow_full_text_storage=True)
    value = archive_evidence(root, licensed, "doc1", b"licensed fixture",
                             scope="LICENSED_SOURCE_BYTES", first_verified_at=NOW, now=NOW)
    assert read_archived_evidence(root, value.version_id, decision_at=NOW)[0] == b"licensed fixture"


@pytest.mark.parametrize("body", [
    b'{"source_id":"synthetic-government-feed","headline":"valid","body":"copyright text","event_id":"a"}',
    b"not JSON",
    b"{}",
])
def test_unapproved_metadata_structure_rejected(tmp_path, body):
    with pytest.raises(SourceShareError):
        archive_evidence(tmp_path / "safe", registry().providers[0], "doc1",
                         body, first_verified_at=NOW, now=NOW)


def test_unapproved_provider_denied_before_path_creation(tmp_path):
    root = tmp_path / "no-write"
    with pytest.raises(SourceShareError, match="permission"):
        archive_evidence(root, registry(False).providers[0], "doc1", metadata(),
                         first_verified_at=NOW, now=NOW)
    assert not root.exists()


def test_receipt_or_payload_tampering_fails_closed(tmp_path):
    root = tmp_path / "private"
    obj = archive_evidence(root, registry().providers[0], "doc1",
                           metadata(), first_verified_at=NOW, now=NOW)
    payload = root / obj.version_id / "payload.bin"
    payload.write_bytes(payload.read_bytes() + b"tamper")
    with pytest.raises(SourceShareError, match="SHA mismatch"):
        read_archived_evidence(root, obj.version_id, decision_at=NOW)
    payload.write_bytes(metadata())
    receipt = root / obj.version_id / "receipt.json"
    parsed = json.loads(receipt.read_bytes())
    parsed["first_verified_at"] = (NOW + timedelta(days=1)).isoformat()
    receipt.write_bytes(json.dumps(parsed).encode())
    with pytest.raises(SourceShareError, match="receipt SHA mismatch"):
        read_archived_evidence(root, obj.version_id, decision_at=NOW)


def test_symlink_or_unprivate_output_rejected(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    link = tmp_path / "alias"
    link.symlink_to(private, target_is_directory=True)
    with pytest.raises(SourceShareError, match="non-symlink"):
        archive_evidence(link, registry().providers[0], "doc1",
                         metadata(), first_verified_at=NOW, now=NOW)
    private.chmod(0o755)
    with pytest.raises(SourceShareError, match="owner-only"):
        archive_evidence(private, registry().providers[0], "doc1",
                         metadata(), first_verified_at=NOW, now=NOW)


def test_unknown_version_or_historical_lookup_unavailable(tmp_path):
    root = tmp_path / "private"
    obj = archive_evidence(root, registry().providers[0], "doc1",
                           metadata(), first_verified_at=NOW, now=NOW)
    with pytest.raises(SourceShareError, match="historical"):
        read_archived_evidence(root, obj.version_id,
                               decision_at=NOW-timedelta(microseconds=1))
    with pytest.raises(SourceShareError):
        read_archived_evidence(root, "f" * 64, decision_at=NOW)


def test_correction_other_document_must_fail(tmp_path):
    root = tmp_path / "private"
    obj = archive_evidence(root, registry().providers[0], "doc1",
                           metadata(), first_verified_at=NOW, now=NOW)
    with pytest.raises(SourceShareError, match="correction reference differs"):
        archive_evidence(root, registry().providers[0], "doc2",
                         metadata("change"), first_verified_at=NOW,
                         supersedes_version_id=obj.version_id)


def test_new_archive_does_not_backdate_historical_availability(tmp_path):
    root = tmp_path / "private"
    source = registry().providers[0]
    saved = archive_evidence(root, source, "doc1", metadata(),
                             first_verified_at=NOW)
    assert saved.archived_at >= saved.first_verified_at
    assert saved.archived_at > NOW
    with pytest.raises(SourceShareError, match="historical"):
        read_archived_evidence(root, saved.version_id, decision_at=NOW)
    assert read_archived_evidence(root, saved.version_id,
                                  decision_at=saved.archived_at)[0] == metadata()


def test_future_claim_not_archived(tmp_path):
    root = tmp_path / "private"
    with pytest.raises(SourceShareError, match="future"):
        archive_evidence(root, registry().providers[0], "doc1", metadata(),
                         first_verified_at=NOW + timedelta(days=3650))
    assert not root.exists()
