#!/usr/bin/env python3
"""One-time loopback Gemini API key setup for this Mac.

The user enters the credential in a local browser form. No key is accepted in
command arguments, printed, sent to ChatGPT, or written inside the Git repo.
"""
from __future__ import annotations

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from newscatalystos.ai_gemini_credentials import (  # noqa: E402
    credential_path, read_private_api_key, save_private_api_key,
)
from newscatalystos.source_share import SourceShareError  # noqa: E402

MAX_FORM = 2048


def render(path: Path, token: str, *, message: str = "", success: bool = False) -> bytes:
    try:
        read_private_api_key(path)
        status = "● 저장됨"
    except SourceShareError:
        status = "○ 미등록"
    notice = (f'<p class="notice {"ok" if success else "err"}">{escape(message)}</p>'
              if message else "")
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NewsCatalystOS · Gemini 키 설정</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}
body{{margin:0;background:#0d1420;color:#eef3fa;font:16px -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif}}
main{{max-width:600px;margin:8vh auto;padding:20px}}
h1{{font-size:26px;margin:0 0 10px}}p{{line-height:1.6;color:#b8c7d9}}
section{{background:#192333;border:1px solid #34445a;border-radius:14px;padding:25px}}
label{{display:block;font-weight:700;margin:0 0 12px}}
.status{{float:right;color:#9bb2c7;font-size:13px;font-weight:400}}
input[type=password]{{width:100%;padding:14px;border:1px solid #52637b;border-radius:8px;
background:#0d1420;color:#fff;font-size:17px}}
button{{width:100%;border:0;border-radius:8px;padding:14px;margin-top:22px;
background:#64d6c1;color:#09201d;font-weight:700;font-size:16px;cursor:pointer}}
.notice{{padding:12px 14px;border-radius:8px}}
.ok{{background:#13382f;color:#d3fff2}}.err{{background:#4b262d;color:#ffe5e8}}
small{{display:block;color:#96a9c1;line-height:1.6;margin-top:15px}}
</style></head><body><main><h1>Gemini API 키 등록</h1>
<p>이 화면은 이 Mac의 127.0.0.1에서만 열립니다. 키는 Mac 내부의 사용자 전용 파일에 저장되며 ChatGPT, GitHub, EraLeader로 전송되지 않습니다.</p>
{notice}<section><form action="/save" method="post" autocomplete="off">
<input type="hidden" name="csrf" value="{escape(token, quote=True)}">
<label for="gemini_key">Gemini API 키 <span class="status">{status}</span></label>
<input id="gemini_key" name="gemini_key" type="password" autocomplete="off"
required minlength="20" maxlength="256" spellcheck="false" autofocus>
<button type="submit">이 Mac에 안전하게 저장</button>
<small>등록된 키는 화면에 다시 표시되지 않습니다. 재등록하면 기존 NewsCatalystOS Gemini 키 파일을 교체합니다.</small>
</form></section></main></body></html>"""
    return html.encode("utf-8")


class UI(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, path: Path, port: int = 0):
        super().__init__(("127.0.0.1", port), Handler)
        self.path = path
        self.token = secrets.token_urlsafe(36)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _valid_host(self) -> bool:
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def _valid_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None or origin == "null":
            return True
        try:
            parsed = urlsplit(origin)
            return (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                    and parsed.port == self.server.server_port
                    and not parsed.username and not parsed.password
                    and not parsed.path and not parsed.query and not parsed.fragment)
        except ValueError:
            return False

    def _send(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; "
                         "form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._valid_host() or self.path != "/":
            return self._send(404, b"Not found")
        self._send(200, render(self.server.path, self.server.token))

    def do_POST(self):
        if not self._valid_host() or self.path != "/save" or not self._valid_origin():
            return self._send(403, b"Access denied")
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            return self._send(415, b"Wrong form encoding")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, b"Invalid form size")
        if not 0 < length <= MAX_FORM:
            return self._send(413, b"Form too large")
        try:
            fields = parse_qs(self.rfile.read(length).decode("utf-8"),
                              keep_blank_values=True, strict_parsing=True,
                              max_num_fields=2)
            if (set(fields) != {"csrf", "gemini_key"}
                    or any(len(values) != 1 for values in fields.values())
                    or fields["csrf"][0] != self.server.token):
                return self._send(403, b"Access denied")
            save_private_api_key(fields["gemini_key"][0], self.server.path)
            self.server.token = secrets.token_urlsafe(36)
            self._send(200, render(self.server.path, self.server.token,
                                   message="저장했습니다. 키 값은 다시 표시하지 않습니다.",
                                   success=True))
        except (SourceShareError, OSError, UnicodeError, ValueError):
            self._send(400, render(self.server.path, self.server.token,
                                   message="저장하지 못했습니다. 키 형식과 Mac 저장 권한을 확인하세요."))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Local Gemini key setup window")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    server = UI(credential_path(), args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print("NEWSCATALYSTOS_LOCAL_GEMINI_SETUP=" + url, flush=True)
    if not args.no_browser:
        subprocess.Popen(["open", url], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    watchdog = threading.Timer(900, server.shutdown)
    watchdog.daemon = True
    watchdog.start()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        watchdog.cancel()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
