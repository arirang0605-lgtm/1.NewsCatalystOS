"""Source-backed article claims use no human labels or verified deal flags."""
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos.evidence_archive import archive_evidence
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.source_article_claim import (
    prepare_source_article_claim, publish_source_article_claim,
    consume_source_article_claim,
)
from newscatalystos.source_share import SourceShareError
from test_motir_press_document import NOW, provider


def setup(tmp_path, line=None):
    source = provider()
    line = line or "ASML은 삼성전자에 EUV 노광 장비를 공급하고 있다."
    text = ("공식 보도자료입니다.\n" + line + "\n").encode()
    archive = archive_evidence(tmp_path / "archive", source, "171178", text,
                               scope="LICENSED_SOURCE_BYTES", now=NOW)
    return source, archive, text


def prepare(tmp_path, source, archive, *, now=None):
    return prepare_source_article_claim(
        tmp_path / "archive", archive.version_id, archive.receipt_sha256,
        archive.payload_sha256, ProviderRegistry((source,)),
        supplier_name="ASML", customer_name="삼성전자",
        product_stage="FAB_EQUIPMENT", now=now or NOW,
    )


def test_article_claim_to_private_publication_to_separate_consumer(tmp_path):
    source, archive, text = setup(tmp_path)
    payload = prepare(tmp_path, source, archive)
    path, digest = publish_source_article_claim(payload, tmp_path / "outbox")
    loaded = consume_source_article_claim(path, digest, now=NOW)
    assert loaded["source_url"] == source.endpoint
    assert loaded["document_sha256"] == sha256(text).hexdigest()
    assert loaded["supplier_name"] == "ASML"
    assert loaded["customer_name"] == "삼성전자"
    assert loaded["company_ids_verified"] is False
    assert loaded["verified_real_transaction"] is False
    assert loaded["verified_real_benefit"] is False
    assert loaded["realized_revenue_krw"] is None
    assert text not in path.read_bytes()
    assert publish_source_article_claim(payload, tmp_path / "outbox")[0] == path


def test_wrong_pin_negated_or_missing_relation_stays_out(tmp_path):
    source, archive, _ = setup(tmp_path)
    with pytest.raises(SourceShareError, match="pins mismatch"):
        prepare_source_article_claim(
            tmp_path / "archive", archive.version_id, archive.receipt_sha256,
            "f" * 64, ProviderRegistry((source,)), supplier_name="ASML",
            customer_name="삼성전자", product_stage="FAB_EQUIPMENT", now=NOW)
    for line in ("ASML은 삼성전자에 장비를 공급하지 않는다.",
                 "ASML과 삼성전자가 공급망 행사에 참석했다.",
                 "삼성전자는 ASML에 장비를 공급하고 있다.",
                 "ASML과 삼성전자가 행사에 참석했다."):
        other = tmp_path / ("case" + str(len(list(tmp_path.iterdir()))))
        other.mkdir()
        src, ar, _ = setup(other, line)
        with pytest.raises(SourceShareError, match="explicit source-reported"):
            prepare(other, src, ar)


def test_claim_sha_and_future_pit_are_enforced(tmp_path):
    source, archive, _ = setup(tmp_path)
    payload = prepare(tmp_path, source, archive, now=NOW + timedelta(seconds=2))
    path, digest = publish_source_article_claim(payload, tmp_path / "outbox")
    with pytest.raises(SourceShareError, match="payload SHA"):
        consume_source_article_claim(path, "a" * 64, now=NOW + timedelta(seconds=2))
    with pytest.raises(SourceShareError, match="unavailable"):
        consume_source_article_claim(path, digest, now=NOW)
    altered = json.loads(payload)
    altered["verified_real_transaction"] = True
    changed = (json.dumps(altered) + "\n").encode()
    path.write_bytes(changed)
    with pytest.raises(SourceShareError, match="payload SHA"):
        consume_source_article_claim(path, digest, now=NOW + timedelta(seconds=2))
