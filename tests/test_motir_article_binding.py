"""Completed RSS metadata and licensed article text stay separately timed."""
from datetime import datetime, timezone
from hashlib import sha256
import json

import pytest

from newscatalystos.evidence_archive import archive_evidence
from newscatalystos.motir_article_binding import (
    consume_motir_article_binding, prepare_motir_article_binding,
    publish_motir_article_binding,
)
from newscatalystos.motir_press_document import extract_motir_press_text
from newscatalystos.provider_registry import (
    MOTIR_PRESS_RIGHTS, SCHEMA, parse_provider_registry,
)
from newscatalystos.source_share import SourceShareError
from test_federated_news_search import collect, setup_workspace
from test_motir_rss_post import registry as feed_registry

ARTICLE = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172295/view"
TITLE = "산업부, 기존 반도체 투자계획 이행상황 점검"
ID = "motir-press-172295"


def article_registry():
    data = {"schema": SCHEMA, "providers": [{
        "provider_id": ID, "kind": "GOVERNMENT_POLICY", "method": "DOCUMENT",
        "endpoint": ARTICLE, "grant": "PUBLIC_LICENSE_KOGL_1",
        "rights_reference": MOTIR_PRESS_RIGHTS,
        "reviewed_at": "2026-10-14T00:00:00+00:00", "expires_at": None,
        "approved": True, "allow_full_text_storage": True, "hourly_limit": 1,
    }]}
    return parse_provider_registry(json.dumps(data).encode())


def setup(tmp_path, *, rss_url=ARTICLE, body=None):
    feed, article = feed_registry(), article_registry()
    workspace = setup_workspace(tmp_path, "motir", feed)
    observed = datetime.now(timezone.utc)
    folder, _ = collect(workspace, feed, "motir-official-press",
                        [(ARTICLE, TITLE, rss_url)], at=observed)
    item = json.loads((folder / "triage.json").read_bytes())["items"][0]
    body = body or ("산업부는 기존 반도체 투자계획의 이행 상황을 점검했다. " * 4)
    html = (b'<input name="bbsSeqN" value="172295">'
            b'<div class="detail-cont mViewerContents"><p>'
            + body.encode()
            + b'</p></div>')
    text = extract_motir_press_text(article.active(ID), html)
    archive_root = tmp_path / "article_archive"
    archived = archive_evidence(archive_root, article.active(ID), "172295",
                                text, scope="LICENSED_SOURCE_BYTES")
    return feed, article, workspace, item, archive_root, archived


def prepare(case, **changes):
    feed, article, workspace, item, root, archived = case
    values = dict(
        feed_registry=feed, inbox_root=workspace.inbox_root,
        poll_state=workspace.poll_state, article_registry=article,
        article_provider_id=ID, archive_root=root,
        archive_version=archived.version_id,
        archive_receipt_sha256=archived.receipt_sha256,
        document_sha256=archived.payload_sha256,
        source_event_sha256=item["event_id"],
        title_sha256=item["title_sha256"],
    )
    values.update(changes)
    return prepare_motir_article_binding(**values)


def test_exact_rss_article_binding_can_be_independently_consumed(tmp_path):
    case = setup(tmp_path)
    payload = prepare(case)
    path, digest = publish_motir_article_binding(payload, tmp_path / "bindings")
    assert digest == sha256(payload).hexdigest()
    assert publish_motir_article_binding(payload, tmp_path / "bindings") == (path, digest)
    record = consume_motir_article_binding(path, digest)
    assert record["source_url"] == ARTICLE
    assert record["source_event_sha256"] == case[3]["event_id"]
    assert record["new_economic_event_verified"] is False
    assert record["verified_real_transaction"] is False
    assert record["rss_first_seen_at"] != record["article_archived_at"]
    assert "기존 반도체 투자계획" not in payload.decode()


@pytest.mark.parametrize("change", [
    {"source_event_sha256": "0" * 64},
    {"title_sha256": "0" * 64},
    {"archive_receipt_sha256": "0" * 64},
    {"document_sha256": "0" * 64},
])
def test_wrong_rss_or_archive_pin_fails_closed(tmp_path, change):
    with pytest.raises(SourceShareError):
        prepare(setup(tmp_path), **change)


def test_binding_consumer_rejects_wrong_digest_or_future_receipt(tmp_path):
    payload = prepare(setup(tmp_path))
    path, digest = publish_motir_article_binding(payload, tmp_path / "bindings")
    with pytest.raises(SourceShareError):
        consume_motir_article_binding(path, "0" * 64)
    past = datetime(2026, 10, 14, tzinfo=timezone.utc)
    with pytest.raises(SourceShareError):
        consume_motir_article_binding(path, digest, now=past)


def test_same_rss_id_and_title_cannot_bind_another_article_url(tmp_path):
    other = "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172296/view"
    with pytest.raises(SourceShareError, match="exact committed RSS identity"):
        prepare(setup(tmp_path, rss_url=other))


def test_consumer_rejects_resealed_claim_of_new_event(tmp_path):
    data = json.loads(prepare(setup(tmp_path)))
    data["new_economic_event_verified"] = True
    altered = (json.dumps(data, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode()
    path, digest = publish_motir_article_binding(altered, tmp_path / "bindings")
    with pytest.raises(SourceShareError, match="overstated"):
        consume_motir_article_binding(path, digest)
