"""Bounded automatic collection of ministry press text from committed RSS.

Only the fixed official board and article family are contacted. The board's
Type 1 notice is checked automatically; attachments and other hosts are excluded.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import fcntl
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.error import HTTPError
from urllib.request import Request, HTTPRedirectHandler, build_opener

from .evidence_archive import _private_root, _write_new, archive_evidence
from .feed_triage import _matched_terms
from .motir_article_binding import FEED_ID, FEED_URL, prepare_motir_article_binding, publish_motir_article_binding
from .motir_press_document import MAX_HTML_BYTES, extract_motir_press_text
from .news_search import read_completed_title_snapshots
from .provider_registry import Provider, ProviderRegistry, MOTIR_PRESS_RIGHTS, MOTIR_PRESS_DOCUMENT, SCHEMA
from .source_share import SourceShareError, _when

MAX_PER_TICK = 2
HOURLY_REQUESTS = 3


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise SourceShareError("ministry document redirect refused")


def _fetch(url, opener=None):
    if url != MOTIR_PRESS_RIGHTS and MOTIR_PRESS_DOCUMENT.fullmatch(url) is None:
        raise SourceShareError("unsupported ministry document URL")
    request = Request(url, headers={"User-Agent": "NewsCatalystOS/1.0 (public press text research)",
                                   "Accept": "text/html"})
    connection = opener if opener is not None else build_opener(_NoRedirect())
    with connection.open(request, timeout=15) as response:
        if response.status != 200 or response.geturl() != url:
            raise SourceShareError("unexpected ministry document response")
        raw = response.read(MAX_HTML_BYTES + 1)
    if not 0 < len(raw) <= MAX_HTML_BYTES:
        raise SourceShareError("unbounded ministry HTML")
    return raw


class _LicenseNotice(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.icon = False
        self.text = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "img" and not self.skip and dict(attrs).get("src") == "/images/contents/sub/mark_license01.png":
            self.icon = True
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)


def _registry_bytes(provider):
    row = asdict(provider)
    for key in ("reviewed_at", "expires_at"):
        row[key] = row[key].isoformat() if row[key] else None
    return (json.dumps({"schema": SCHEMA, "providers": [row]}, ensure_ascii=False,
                       sort_keys=True) + "\n").encode()


def collect_motir_documents(registry: ProviderRegistry, inbox_root: Path, poll_state: Path,
                            root: Path, *, replay_only=False, opener=None, now=None):
    at = _when((now or datetime.now(timezone.utc)).isoformat(), "collection time")
    feed = registry.active(FEED_ID, at=at)
    if feed.endpoint != FEED_URL or feed.method != "RSS_POST":
        raise SourceShareError("exact ministry feed required")
    if type(replay_only) is not bool:
        raise SourceShareError("boolean replay policy required")
    # Only persisted, acknowledged RSS records may seed article requests.
    selected = {}
    for _, snapshot, _ in read_completed_title_snapshots(inbox_root, poll_state, registry, now=at):
        for item in snapshot["items"]:
            if (item["provider_id"] != FEED_ID or not _matched_terms(item["headline"])
                    or MOTIR_PRESS_DOCUMENT.fullmatch(item["canonical_url"]) is None
                    or item["document_id"] != item["canonical_url"]):
                continue
            key = item["event_id"]
            if key not in selected or item["available_at"] > selected[key]["available_at"]:
                selected[key] = item
    items = sorted(selected.values(), key=lambda x: (x["available_at"], x["event_id"]), reverse=True)[:20]
    root = _private_root(root)
    for path in (Path(inbox_root).resolve(), Path(poll_state).resolve()):
        if root == path or root in path.parents or path in root.parents:
            raise SourceShareError("collection state must be separate from RSS inputs")
    fd = os.open(root / ".collection.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "DOCUMENT_COLLECTION_BUSY", "source_fetch_calls": 0, "jobs": []}
        return _collect_locked(registry, inbox_root, poll_state, root, items,
                               at, replay_only, opener, now)
    finally:
        os.close(fd)


def _collect_locked(registry, inbox, poll, root, items, at, replay, opener, clock):
    from .incremental_ingest import _check_state_path
    db = sqlite3.connect(str(_check_state_path(root / "collection.sqlite3")))
    calls = 0
    outcomes = []
    def stamp():
        return at if clock else datetime.now(timezone.utc)
    def request(url):
        nonlocal calls
        current = stamp()
        count = db.execute("SELECT count(*) FROM requests WHERE at>?", ((current-timedelta(hours=1)).isoformat(),)).fetchone()[0]
        if count >= HOURLY_REQUESTS:
            raise SourceShareError("document hourly request budget exhausted")
        db.execute("INSERT INTO requests VALUES(?)", (current.isoformat(),));db.commit()
        calls += 1
        return _fetch(url, opener)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS requests(at TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY,sha TEXT,checked TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS documents(identity TEXT PRIMARY KEY,job TEXT,retry_at TEXT,status TEXT)")
        db.commit()
        policy = db.execute("SELECT sha,checked FROM policy WHERE id=1").fetchone()
        policy_ok = bool(policy and at-timedelta(days=1) <= _when(policy[1], "license checked") <= at)
        if items and not policy_ok and not replay:
            try:
                raw = request(MOTIR_PRESS_RIGHTS)
                notice = _LicenseNotice()
                notice.feed(raw.decode("utf-8"));notice.close()
                if (not notice.icon or re.search(r"공공누리\s*1유형\s*\(출처표시\)",
                                                " ".join(notice.text)) is None):
                    raise SourceShareError("ministry Type 1 notice unavailable")
                policy = (sha256(raw).hexdigest(), stamp().isoformat())
                db.execute("INSERT OR REPLACE INTO policy VALUES(1,?,?)", policy);db.commit()
                policy_ok = True
            except (SourceShareError, OSError, ValueError):
                return {"status": "DOCUMENT_LICENSE_UNAVAILABLE", "source_fetch_calls": calls, "jobs": []}
        processed = 0
        for item in items:
            identity = sha256((item["event_id"]+'\0'+item["title_sha256"]).encode()).hexdigest()
            row = db.execute("SELECT job,retry_at,status FROM documents WHERE identity=?", (identity,)).fetchone()
            if row and row[0]:
                continue
            if replay or not policy_ok or processed >= MAX_PER_TICK:
                continue
            if row and row[1] and _when(row[1], "retry at") > at:
                continue
            processed += 1
            try:
                url = item["canonical_url"];article_id = url.split('/')[-2]
                html = request(url)
                verified = stamp()
                provider = Provider('motir-press-'+article_id, 'GOVERNMENT_POLICY', 'DOCUMENT', url,
                    'PUBLIC_LICENSE_KOGL_1', MOTIR_PRESS_RIGHTS, verified, None, True, True, 1)
                body = extract_motir_press_text(provider, html)
                folder = _private_root(root / identity)
                provider_bytes = _registry_bytes(provider)
                # Registry identity is pinned once. Crash recovery retains its
                # original availability time and checks the same source again.
                registry_path = folder / 'registry.json'
                if registry_path.exists():
                    from .provider_registry import parse_provider_registry
                    from .evidence_archive import _read_once
                    providers = parse_provider_registry(_read_once(registry_path, 32768), now=stamp())
                    provider = providers.active(provider.provider_id, at=stamp())
                    if provider.endpoint != url:
                        raise SourceShareError('document registry collision')
                else:
                    _write_new(registry_path, provider_bytes)
                    providers = ProviderRegistry((provider,))
                archived = archive_evidence(folder/'archive', provider, article_id, body,
                                            scope='LICENSED_SOURCE_BYTES', now=stamp())
                payload = prepare_motir_article_binding(registry, inbox, poll, providers,
                    provider.provider_id, folder/'archive', archived.version_id,
                    archived.receipt_sha256, archived.payload_sha256,
                    item['event_id'], item['title_sha256'], now=stamp())
                binding, pin = publish_motir_article_binding(payload, folder/'bindings')
                job = {"binding_path":str(binding),"binding_sha256":pin,
                       "archive_root":str(folder/'archive'),"article_registry":str(registry_path)}
                db.execute("INSERT OR REPLACE INTO documents VALUES(?,?,NULL,'COLLECTED')", (identity,json.dumps(job)))
                outcomes.append({"status":"COLLECTED", "source_event_sha256":item['event_id']})
            except (SourceShareError, OSError, ValueError) as exc:
                wait = 24 if isinstance(exc, HTTPError) and exc.code in (401,403) else 1
                db.execute("INSERT OR REPLACE INTO documents VALUES(?,NULL,?,'RETRY_PENDING')",
                           (identity,(stamp()+timedelta(hours=wait)).isoformat()))
                outcomes.append({"status":"RETRY_PENDING", "error_type":type(exc).__name__})
            db.commit()
        jobs = []
        pending = 0
        if policy_ok:
            for item in items:
                identity = sha256((item['event_id']+'\0'+item['title_sha256']).encode()).hexdigest()
                row = db.execute("SELECT job FROM documents WHERE identity=?", (identity,)).fetchone()
                if row and row[0]:
                    jobs.append(json.loads(row[0]))
                else:
                    pending += 1
        return {"status":("DOCUMENT_COLLECTION_PARTIAL" if pending
                          else "DOCUMENT_COLLECTION_READY"), "source_fetch_calls":calls,
                "registered_documents":len(jobs), "pending_documents":pending,
                "outcomes":outcomes, "jobs":jobs}
    finally:
        db.close()
