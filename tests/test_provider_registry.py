"""1_2 source permissions: all URLs/rights here are synthetic fixtures."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from newscatalystos.provider_registry import (
    SCHEMA, MOTIR_PRESS_RIGHTS, parse_provider_registry,
)
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)


def sample(**changes):
    row = {
        "provider_id": "synthetic-company-ir",
        "kind": "COMPANY_IR",
        "method": "RSS",
        "endpoint": "https://ir.example.org/feed.xml",
        "grant": "NOT_REVIEWED",
        "rights_reference": None,
        "reviewed_at": None,
        "expires_at": None,
        "approved": False,
        "allow_full_text_storage": False,
        "hourly_limit": 6,
    }
    row.update(changes)
    return {"schema": SCHEMA, "providers": [row]}


def parse(data):
    return parse_provider_registry(json.dumps(data).encode(), now=NOW)


def test_empty_registry_disables_all_by_default():
    reg = parse({"schema": SCHEMA, "providers": []})
    assert reg.approved_ids(at=NOW) == ()
    with pytest.raises(SourceShareError, match="not approved"):
        reg.active("missing", at=NOW)


def test_unknown_legal_permission_disables_provider():
    reg = parse(sample())
    assert reg.approved_ids(at=NOW) == ()
    with pytest.raises(SourceShareError, match="not approved"):
        reg.active("synthetic-company-ir", at=NOW)


def test_explicitly_operator_reviewed_rss_is_metadata_only():
    reg = parse(sample(
        grant="OFFICIAL_TERMS_REVIEWED",
        rights_reference="operator-confirmed-rights-fixture-not-real",
        reviewed_at="2026-10-12T01:00:00Z",
        expires_at="2026-11-12T01:00:00Z",
        approved=True,
    ))
    active = reg.active("synthetic-company-ir", at=NOW)
    assert active.allow_full_text_storage is False
    assert active.method == "RSS"
    assert reg.approved_ids(at=NOW) == ("synthetic-company-ir",)
    with pytest.raises(SourceShareError, match="not approved"):
        reg.active("synthetic-company-ir", at=NOW + timedelta(days=100))


def test_explicit_written_license_may_enable_text_but_never_fetches(tmp_path):
    reg = parse(sample(
        grant="WRITTEN_LICENSE",
        rights_reference="synthetic-contract-reference",
        reviewed_at="2026-10-12T01:00:00Z",
        approved=True,
        allow_full_text_storage=True,
    ))
    assert reg.active("synthetic-company-ir", at=NOW).allow_full_text_storage
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("changed", [
    {"provider_id": "DART"},
    {"provider_id": "sec-submissions"},
    {"provider_id": "krx-kospi"},
    {"provider_id": "EraLeader-original"},
    {"endpoint": "http://ir.example.org/feed"},
    {"endpoint": "https://localhost/"},
    {"endpoint": "https://127.0.0.1/feed"},
    {"endpoint": "https://ir.example.org:444/feed"},
    {"endpoint": "https://user:secret@ir.example.org/feed"},
    {"endpoint": "https://ir.example.org/feed?token=hidden"},
    {"approved": True},
    {"hourly_limit": 0},
    {"hourly_limit": True},
    {"kind": "UNOFFICIAL_RUMOR"},
    {"allow_full_text_storage": True},
    {"reviewed_at": "2099-01-01T00:00:00Z"},
])
def test_unsafe_or_unapproved_provider_rejected(changed):
    with pytest.raises(SourceShareError):
        parse(sample(**changed))


def test_duplicate_provider_and_json_keys_fail():
    document = sample()
    document["providers"].append(dict(document["providers"][0]))
    with pytest.raises(SourceShareError, match="duplicate"):
        parse(document)
    with pytest.raises(SourceShareError, match="invalid JSON"):
        parse_provider_registry(
            b'{"schema":"newscatalyst.provider_registry.v1","schema":"evil","providers":[]}',
            now=NOW,
        )


def test_social_tip_cannot_become_a_verified_fact():
    with pytest.raises(SourceShareError, match="social"):
        parse(sample(kind="SNS_TIP", approved=True,
                     grant="OFFICIAL_TERMS_REVIEWED",
                     rights_reference="synthetic", reviewed_at=NOW.isoformat()))


def test_fulltext_needs_written_license_even_when_reviewed():
    with pytest.raises(SourceShareError, match="document license"):
        parse(sample(grant="OFFICIAL_TERMS_REVIEWED", approved=True,
                     rights_reference="synthetic", reviewed_at=NOW.isoformat(),
                     allow_full_text_storage=True))


def test_kogl_type1_is_limited_to_ministry_press_article_text():
    row = sample(provider_id="motir-press-171178", kind="GOVERNMENT_POLICY",
                 method="DOCUMENT",
                 endpoint="https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/171178/view",
                 grant="PUBLIC_LICENSE_KOGL_1", rights_reference=MOTIR_PRESS_RIGHTS,
                 reviewed_at=NOW.isoformat(), approved=True, allow_full_text_storage=True)
    assert parse(row).active("motir-press-171178", at=NOW).allow_full_text_storage
    for change in ({"endpoint": "https://www.motir.go.kr/kor/contents/1"},
                   {"endpoint": "https://evil.example.org/kor/article/ATCL3f49a5a8c/171178/view"},
                   {"rights_reference": "https://example.org/unknown"},
                   {"kind": "COMPANY_IR"}, {"method": "RSS"}):
        with pytest.raises(SourceShareError, match="public license"):
            parse(sample(**{**row["providers"][0], **change}))


def test_no_real_rights_are_inferred_from_source_url():
    registry = parse(sample())
    assert registry.providers[0].endpoint.startswith("https://")
    assert registry.approved_ids(at=NOW) == ()
