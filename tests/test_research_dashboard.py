"""Dashboard aggregation, private notes, and loopback HTTP path."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from newscatalystos.research_dashboard import NoteStore, build_period
from scripts.open_research_dashboard import DashboardServer


def record(day: str, event: str, priority: str = "PARTIAL_EVIDENCE_ONLY") -> dict:
    return {"day": day, "available_at": day + "T00:00:00+00:00",
            "event_id": event, "priority": priority, "ai_status": "NOT_ELIGIBLE",
            "uncertainty_count": 2, "headline": event, "provider": "test",
            "source_url": "https://example.org/report", "category": "TEST"}


def test_week_reviews_days_and_month_reviews_weeks():
    rows = [record("2026-10-05", "a"), record("2026-10-07", "b", "HIGH_REVIEW"),
            record("2026-10-12", "c")]
    notes = [
        {"view": "day", "period": "2026-10-05", "text": "일간 확인", "created_at": "x"},
        {"view": "week", "period": "2026-10-05", "text": "주간 결론", "created_at": "x"},
    ]
    week = build_period(rows, notes, "week", "2026-10-07")
    assert (week["start"], week["end"]) == ("2026-10-05", "2026-10-11")
    assert week["counts"]["items"] == 2
    assert sum(x["items"] for x in week["children"]) == 2
    assert [x["text"] for x in week["inherited_notes"]] == ["일간 확인"]
    month = build_period(rows, notes, "month", "2026-10-15")
    assert month["counts"]["items"] == 3
    assert [x["text"] for x in month["inherited_notes"]] == ["주간 결론"]
    assert [x["items"] for x in month["children"] if x["items"]] == [2, 1]
    assert "성과 확정은 아닙니다" in " ".join(month["feedback"])
    assert "성과 확정은 아닙니다" in " ".join(week["feedback"])


def test_private_note_storage_and_period_normalization():
    with tempfile.TemporaryDirectory() as tmp:
        store = NoteStore(Path(tmp) / "private")
        first = store.add("week", "2026-10-07", "  확인할 것  ")
        assert first["period"] == "2026-10-05"
        assert first["text"] == "확인할 것"
        assert store.read() == [first]
        assert os.stat(store.root).st_mode & 0o077 == 0
        assert os.stat(store.path).st_mode & 0o077 == 0


def test_loopback_dashboard_reads_empty_and_saves_note():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        server = DashboardServer(0, base / "reports", base / "notes")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(url + "/api/period?view=day&date=2026-10-15") as response:
                data = json.load(response)
            assert data["counts"]["items"] == 0
            assert data["notes"] == []
            request = Request(url + "/api/notes", method="POST",
                              headers={"Content-Type": "application/json",
                                       "Origin": url},
                              data=json.dumps({"view": "day", "date": "2026-10-15",
                                               "text": "내 메모"}).encode())
            with urlopen(request) as response:
                assert response.status == 201
            with urlopen(url + "/api/period?view=day&date=2026-10-15") as response:
                assert json.load(response)["notes"][0]["text"] == "내 메모"
            bad = Request(url + "/api/notes", method="POST",
                          headers={"Content-Type": "application/json",
                                   "Origin": "https://other.example"},
                          data=b"{}")
            try:
                urlopen(bad)
                assert False, "cross-origin note write accepted"
            except HTTPError as exc:
                assert exc.code == 403
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
