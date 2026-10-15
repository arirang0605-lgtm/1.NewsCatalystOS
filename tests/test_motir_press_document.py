"""The reviewed public-license path archives text, never a completed deal."""
from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from newscatalystos.evidence_archive import archive_evidence, read_archived_evidence
from newscatalystos.motir_press_document import extract_motir_press_text
from newscatalystos.provider_registry import MOTIR_PRESS_RIGHTS, SCHEMA, parse_provider_registry
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
ARTICLE = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/171178/view"


def provider():
    raw = json.dumps({"schema": SCHEMA, "providers": [{
        "provider_id": "motir-press-171178", "kind": "GOVERNMENT_POLICY",
        "method": "DOCUMENT", "endpoint": ARTICLE,
        "grant": "PUBLIC_LICENSE_KOGL_1", "rights_reference": MOTIR_PRESS_RIGHTS,
        "reviewed_at": NOW.isoformat(), "expires_at": None, "approved": True,
        "allow_full_text_storage": True, "hourly_limit": 1,
    }]}).encode()
    return parse_provider_registry(raw, now=NOW).active("motir-press-171178", at=NOW)


def page(sequence="171178", body=""):
    body = body or ("산업통상부는 반도체 공급망을 설명하였다. "
                    "ASML은 삼성전자에 EUV 노광장비를 공급하고 있다. " * 3)
    return (f'<html><body><p>navigation secret</p>'
            f'<input name="bbsSeqN" value="{sequence}">'
            f'<div class="detail-cont mViewerContents"><p>{body}</p></div>'
            f'<p>unlicensed attachment</p></body></html>').encode()


def test_real_public_license_path_extracts_and_archives_only_press_text(tmp_path):
    source = provider()
    text = extract_motir_press_text(source, page())
    assert "ASML은 삼성전자에" in text.decode()
    assert b"navigation secret" not in text
    assert b"unlicensed attachment" not in text
    archived = archive_evidence(tmp_path / "private", source, "171178", text,
                                scope="LICENSED_SOURCE_BYTES", now=NOW)
    stored, receipt = read_archived_evidence(tmp_path / "private", archived.version_id,
                                              now=NOW)
    assert stored == text and receipt.payload_sha256 == sha256(text).hexdigest()


@pytest.mark.parametrize("bad", [
    page(sequence="171179"),
    page().replace(b"detail-cont mViewerContents", b"detail-cont"),
    page() + b'<div class="detail-cont mViewerContents">duplicate</div>',
    b"not an official article",
])
def test_wrong_or_missing_article_body_cannot_be_archived(bad):
    with pytest.raises(SourceShareError):
        extract_motir_press_text(provider(), bad)
