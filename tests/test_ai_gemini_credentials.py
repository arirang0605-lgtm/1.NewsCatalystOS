"""Local Gemini credential registration, offline only."""
from __future__ import annotations

from html.parser import HTMLParser
import os
from pathlib import Path
import stat
from threading import Thread
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from newscatalystos.ai_gemini_credentials import (
    read_private_api_key, save_private_api_key,
)
from newscatalystos.source_share import SourceShareError
from scripts.open_gemini_setup import UI


class _Token(HTMLParser):
    def __init__(self):
        super().__init__()
        self.value = None

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "input" and fields.get("name") == "csrf":
            self.value = fields.get("value")


def test_owner_only_file_round_trip_and_replace(tmp_path):
    path = tmp_path / "private" / "gemini_api.env"
    first = "synthetic-gemini-key-first-value-12345"
    second = "synthetic-gemini-key-second-value-67890"
    save_private_api_key(first, path)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert read_private_api_key(path) == first
    save_private_api_key(second, path)
    assert read_private_api_key(path) == second


def test_rejects_shared_file_and_symlink(tmp_path):
    path = tmp_path / "private" / "gemini_api.env"
    save_private_api_key("synthetic-gemini-key-for-permission-test", path)
    os.chmod(path, 0o644)
    with pytest.raises(SourceShareError, match="unsafe"):
        read_private_api_key(path)
    with pytest.raises(SourceShareError, match="unsafe"):
        save_private_api_key("synthetic-gemini-key-for-permission-test", path)
    path.unlink()
    target = tmp_path / "outside"
    target.write_text("not a credential")
    path.symlink_to(target)
    with pytest.raises(SourceShareError, match="unsafe"):
        read_private_api_key(path)
    with pytest.raises(SourceShareError, match="unsafe"):
        save_private_api_key("synthetic-gemini-key-for-permission-test", path)


def test_loopback_form_saves_without_echoing_key(tmp_path):
    path = tmp_path / "private" / "gemini_api.env"
    secret = "synthetic-gemini-key-for-local-form-12345"
    with UI(path, 0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/", timeout=3) as response:
                page = response.read().decode()
                assert response.status == 200
                assert response.headers["Cache-Control"].startswith("no-store")
            parser = _Token()
            parser.feed(page)
            assert parser.value
            payload = urlencode({"csrf": parser.value, "gemini_key": secret}).encode()
            request = Request(base + "/save", data=payload, method="POST",
                              headers={"Content-Type": "application/x-www-form-urlencoded",
                                       "Origin": base})
            with urlopen(request, timeout=3) as response:
                result = response.read().decode()
                assert response.status == 200
            assert secret not in result
            assert "저장했습니다" in result
            assert read_private_api_key(path) == secret
        finally:
            server.shutdown()
            thread.join(timeout=3)
