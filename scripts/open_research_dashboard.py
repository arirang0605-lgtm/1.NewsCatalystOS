"""Open the private daily/weekly/monthly research dashboard on this Mac only."""
from __future__ import annotations

import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit
import webbrowser

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT / "src"))

from newscatalystos.research_dashboard import KST, NoteStore, build_period, scan_saved_analysis
from newscatalystos.source_share import SourceShareError

ASSETS = Path(__file__).resolve().parent / "dashboard_assets"


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, port: int, reports: Path, notes: Path):
        super().__init__(("127.0.0.1", port), Handler)
        self.reports = reports
        self.notes = NoteStore(notes)


class Handler(BaseHTTPRequestHandler):
    def _origin_ok(self) -> bool:
        host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != host:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{host}"

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'self'; script-src 'self'; "
                         "connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if not self._origin_ok():
            self._json(403, {"error": "local browser origin required"})
            return
        url = urlsplit(self.path)
        if url.path == "/api/period":
            query = parse_qs(url.query)
            view = query.get("view", ["day"])[0]
            selected = query.get("date", [datetime.now(KST).date().isoformat()])[0]
            try:
                records, source_info = scan_saved_analysis(self.server.reports)
                data = build_period(records, self.server.notes.read(), view, selected,
                                    source_info=source_info)
                self._json(200, data)
            except (SourceShareError, OSError, ValueError, KeyError, TypeError) as exc:
                self._json(400, {"error": type(exc).__name__})
            return
        files = {"/": ("index.html", "text/html; charset=utf-8"),
                 "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                 "/style.css": ("style.css", "text/css; charset=utf-8")}
        if url.path not in files:
            self._json(404, {"error": "not found"})
            return
        name, kind = files[url.path]
        self._send(200, (ASSETS / name).read_bytes(), kind)

    def do_POST(self) -> None:
        if not self._origin_ok() or self.path != "/api/notes":
            self._json(403, {"error": "local browser origin required"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._json(415, {"error": "JSON required"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 8192:
                raise ValueError("invalid note request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("invalid note request")
            note = self.server.notes.add(data.get("view"), data.get("date"), data.get("text"))
            self._json(201, {"note": note})
        except (SourceShareError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": type(exc).__name__})

    def log_message(self, format: str, *args: object) -> None:
        # Paths and free-text notes must not enter persistent shell logs.
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--reports-root", type=Path,
                        default=PROJECT / "output" / "feed_analysis")
    parser.add_argument("--notes-root", type=Path,
                        default=Path.home() / "Library/Application Support/NewsCatalystOS/dashboard")
    parser.add_argument("--no-browser", action="store_true")
    options = parser.parse_args(argv)
    server = DashboardServer(options.port, options.reports_root, options.notes_root)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"NewsCatalystOS dashboard: {url}", flush=True)
    if not options.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
