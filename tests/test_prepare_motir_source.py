"""One-time operator-reviewed official ministry source, NO existing RSS changes."""
from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import json

import pytest

from scripts import prepare_motir_source as source
from newscatalystos.provider_registry import parse_provider_registry
from newscatalystos.source_share import SourceShareError

NOW = datetime(2026, 10, 14, 8, 0, tzinfo=timezone.utc)


def test_ministry_registry_is_exact_scoped_only_one_source():
    data = source.create_document(NOW)
    obj = parse_provider_registry(data, now=NOW)
    assert obj.approved_ids(at=NOW) == (source.SOURCE,)
    entry = obj.active(source.SOURCE, at=NOW)
    assert entry.method == "RSS_POST"
    assert entry.endpoint == source.ENDPOINT
    assert entry.hourly_limit == 1 and not entry.allow_full_text_storage
    assert entry.grant == "OFFICIAL_TERMS_REVIEWED"


def test_write_only_new_private_file_does_not_touch_general_registry(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    folder.chmod(0o700)
    general = folder / "authorized_sources.json"
    general.write_text('{"existing":"unchanged"}')
    path = folder / "motir_authorized_sources.json"
    result = source.write_private_registry(path, now=NOW)
    assert result == path and stat.S_IMODE(path.stat().st_mode) == 0o600
    assert general.read_text() == '{"existing":"unchanged"}'
    first = path.read_bytes()
    with pytest.raises(FileExistsError):
        source.write_private_registry(path, now=NOW)
    assert path.read_bytes() == first
    assert len(parse_provider_registry(first, now=NOW).providers) == 1


def test_unprotected_dir_or_wrong_name_denied(tmp_path):
    unsafe = tmp_path / "world"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o755)
    with pytest.raises(SourceShareError):
        source.write_private_registry(unsafe / "motir_authorized_sources.json", now=NOW)
    safe = tmp_path / "private"
    safe.mkdir(mode=0o700)
    safe.chmod(0o700)
    with pytest.raises(SourceShareError, match="cannot modify existing"):
        source.write_private_registry(safe / "authorized_sources.json", now=NOW)
    assert list(safe.iterdir()) == []


def test_no_operator_confirmation_means_no_registry_write(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    path = private / "motir_authorized_sources.json"
    code = source.main(["--out", str(path), "--write"])
    assert code == 4 and not path.exists()
    code = source.main(["--out", str(path)])
    assert code == 0 and not path.exists()
