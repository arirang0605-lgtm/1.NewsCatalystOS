"""Research SHA local-first-observation anchor, synthetic only."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json

import pytest

from newscatalystos import pin_anchor as mod
from newscatalystos.source_share import SourceShareError
from test_verified_reference import report_fixture


def local_env(tmp_path, monkeypatch):
    era, report, pin, capture = report_fixture(tmp_path)
    target = tmp_path / "other_device" / mod.ANCHOR_FILENAME
    target.parent.mkdir(mode=0o700)
    actual_device = mod._device
    monkeypatch.setattr(mod, "_device",
        lambda p: 123 if p == target.parent else 456)
    return era, report, pin, target, capture


def test_anchor_once_and_verify_exact_preserved_digest(tmp_path, monkeypatch):
    era, report, expected, target, capture = local_env(tmp_path, monkeypatch)
    anchor = mod.create_local_reference_anchor(era, report, target)
    assert anchor.report_sha256 == expected
    assert anchor.trust_level == "LOCAL_TOFU_NOT_EXTERNAL_ATTESTATION"
    assert target.stat().st_mode & 0o077 == 0
    when = datetime.now(timezone.utc)
    result = mod.verify_with_local_anchor(era, report, target, when)
    assert result.research_only and len(result.captures) == 1
    assert result.report_sha256 == expected
    with pytest.raises(SourceShareError, match="already exists"):
        mod.create_local_reference_anchor(era, report, target)
    assert mod.read_local_reference_anchor(era, report, target, when) == anchor


def test_mutation_after_anchor_rejected(tmp_path, monkeypatch):
    era, report, _, target, capture = local_env(tmp_path, monkeypatch)
    mod.create_local_reference_anchor(era, report, target)
    data = json.loads(report.read_text())
    data["official_leaders"] = 99
    report.write_text(json.dumps(data))
    with pytest.raises(SourceShareError, match="reference SHA pin mismatch"):
        mod.verify_with_local_anchor(era, report, target, datetime.now(timezone.utc))


def test_no_backdating_local_pin(tmp_path, monkeypatch):
    era, report, _, target, capture = local_env(tmp_path, monkeypatch)
    mod.create_local_reference_anchor(era, report, target)
    early = datetime.now(timezone.utc) - timedelta(days=1)
    with pytest.raises(SourceShareError, match="unavailable at decision"):
        mod.read_local_reference_anchor(era, report, target, early)


def test_other_disk_is_required(tmp_path):
    era, report, _, _ = report_fixture(tmp_path)
    same_disk_dir = tmp_path / "same_disk"
    same_disk_dir.mkdir(mode=0o700)
    target = same_disk_dir / mod.ANCHOR_FILENAME
    with pytest.raises(SourceShareError, match="another disk"):
        mod.create_local_reference_anchor(era, report, target)
    assert not target.exists()


def test_unsafe_directory_or_symlink_blocked(tmp_path, monkeypatch):
    era, report, _, target, capture = local_env(tmp_path, monkeypatch)
    target.parent.chmod(0o755)
    with pytest.raises(SourceShareError, match="private owner-only"):
        mod.create_local_reference_anchor(era, report, target)
    target.parent.chmod(0o700)
    mod.create_local_reference_anchor(era, report, target)
    fake = target.parent / "other.txt"
    target.rename(fake)
    target.symlink_to(fake)
    with pytest.raises(SourceShareError, match="not private regular"):
        mod.read_local_reference_anchor(era, report, target,
                                        datetime.now(timezone.utc))


def test_pin_cannot_be_treated_as_external_notary(tmp_path, monkeypatch):
    era, report, _, target, capture = local_env(tmp_path, monkeypatch)
    mod.create_local_reference_anchor(era, report, target)
    obj = json.loads(target.read_text())
    obj["trust_level"] = "THIRD_PARTY_NOTARIZED"
    target.write_text(json.dumps(obj))
    with pytest.raises(SourceShareError, match="schema/trust"):
        mod.read_local_reference_anchor(era, report, target,
                                        datetime.now(timezone.utc))
