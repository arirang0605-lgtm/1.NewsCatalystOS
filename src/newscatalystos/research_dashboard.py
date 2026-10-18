"""Local dashboard over saved, unverified research results and separate owner notes."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import fcntl
import json
import os
import re

from .feed_analysis_delivery import MAX_REPORT_BYTES, _validate_report
from .motir_document_analysis import consume_motir_document_analysis
from .official_relation_intake import _private_input
from .source_share import SourceShareError, _json

KST = timezone(timedelta(hours=9))
VIEWS = frozenset({"day", "week", "month"})
SHA_NAME = re.compile(r"feed_analysis_([0-9a-f]{64})\.json\Z")
MAX_REPORTS = 1000
MAX_NOTES_BYTES = 1_000_000


def _day(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid calendar date")
    return date.fromisoformat(value)


def _instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return result.astimezone(timezone.utc)


def _bounds(view: str, selected: date) -> tuple[date, date]:
    if view not in VIEWS:
        raise ValueError("invalid dashboard view")
    if view == "day":
        return selected, selected
    if view == "week":
        start = selected - timedelta(days=selected.weekday())
        return start, start + timedelta(days=6)
    start = selected.replace(day=1)
    next_month = (start.replace(year=start.year + 1, month=1) if start.month == 12
                  else start.replace(month=start.month + 1))
    return start, next_month - timedelta(days=1)


def period_as_of(view: str, selected: str, *, now: datetime | None = None) -> datetime:
    """One KST period boundary for findings, themes and company evidence."""
    _, end = _bounds(view, _day(selected))
    finish = datetime.combine(end, datetime.min.time(), tzinfo=KST) + timedelta(days=1, microseconds=-1)
    current = _instant((now or datetime.now(timezone.utc)).isoformat())
    return min(finish, current).astimezone(timezone.utc)


def _available_as_of(row: dict, at: datetime) -> bool:
    # Includes provenance of a retained prior AI summary/directory enrichment.
    return all(_instant(row[k]) <= at for k in (
        'available_at', 'analysis_available_at', 'source_available_at',
        'ai_summary_available_at', 'company_identity_analysis_available_at') if row.get(k))


def scan_saved_analysis(root: Path, *, document_root: Path | None = None, now: datetime | None = None,
                        as_of: datetime | None = None,
                        additional_roots: tuple[tuple[str, Path], ...] = ()) -> tuple[list[dict], dict]:
    """Read SHA/PIT-checked reports across isolated approved source workspaces.

    Extra source roots contribute existing core reports under their unique
    workspace scope. No source DB, producer registry, or report is rewritten.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    at = min(now, _instant(as_of.isoformat())) if as_of is not None else now
    records: dict[tuple[str, str], dict] = {}
    seen_reports = 0
    skipped = 0
    folders = [("core", Path(root) / "core" / "reports"),
               ("motir", Path(root) / "motir" / "reports")]
    seen_scopes = {"core", "motir"}
    for scope, source in additional_roots:
        location = Path(source)
        if (not isinstance(scope, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", scope)
                or scope in seen_scopes or not location.is_absolute()
                or ".." in location.parts or location.resolve() != location
                or location.is_symlink()
                or any(part.casefold() == "eraleader" for part in location.parts)):
            raise SourceShareError("invalid separate approved report workspace")
        seen_scopes.add(scope)
        folders.append((scope, location / "core" / "reports"))
    for scope, folder in folders:
        if folder.is_symlink() or not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            match = SHA_NAME.fullmatch(path.name)
            if not match:
                continue
            seen_reports += 1
            if seen_reports > MAX_REPORTS:
                raise SourceShareError("too many saved analysis reports")
            try:
                if path.is_symlink():
                    raise SourceShareError("symlink report")
                raw = _private_input(path, MAX_REPORT_BYTES)
                if sha256(raw).hexdigest() != match.group(1):
                    raise SourceShareError("saved report digest mismatch")
                data = _json(raw, "saved feed analysis")
                checked = _validate_report(data, now)
                if checked is None or checked > at:
                    continue
                for row in data["results"]:
                    available = _instant(row["analysis_available_at"])
                    if available > at or _instant(row['source_available_at']) > at:
                        continue
                    # A saved report can only establish availability at its own
                    # producer check time; never place a later found row earlier.
                    observed = max(available, checked)
                    key = (scope, row["analysis_event_sha256"])
                    item = {
                        "scope": scope, "event_id": row["analysis_event_sha256"],
                        "source_event_sha256": row["source_event_sha256"],
                        "content_scope": "RSS_TITLE_METADATA",
                        "day": observed.astimezone(KST).date().isoformat(),
                        "available_at": observed.isoformat(),
                        "analysis_available_at": available.isoformat(),
                        "headline": row["headline"], "provider": row["provider_id"],
                        "source_url": row["source_url"],
                        "source_kind": row["source_kind"],
                        "source_available_at": row["source_available_at"],
                        "category": row.get("category_candidate"),
                        "priority": row.get("routing_priority"),
                        "ai_status": row["ai_status"],
                        "analysis_purpose": row.get("analysis_purpose", "NEW_EVENT"),
                        "ai_summary": (row.get("ai_analysis") or {}).get("summary"),
                        "ai_claims": (row.get("ai_analysis") or {}).get("claims", []),
                        "ai_uncertainties": (row.get("ai_analysis") or {}).get("uncertainties", []),
                        "uncertainty_count": len(row["uncertainties"]),
                        "reported_plan_only": row["reported_plan_only"],
                        "source_products": list(dict.fromkeys(x["value"]
                            for x in row["source_matched_fields"] if x["field"] == "PRODUCT")),
                        "economic_changes": row.get("economic_changes", []),
                        "semantic_analysis": row.get("semantic_analysis"),
                        "company_identity": row.get("company_identity"),
                        "company_identity_status": row.get("company_identity_status", "NOT_CONFIGURED"),
                        "report_sha256": match.group(1),
                        "evidence_status": "LOCAL_DIGEST_AND_SAVED_SCHEMA_CHECKED",
                    }
                    if row.get("analysis_industry")=="ECONOMIC_DISCOVERY":
                        item["economic_discovery"]=row["economic_discovery"]
                        item["analysis_industry"]="ECONOMIC_DISCOVERY"
                        item["source_title_sha256"]=row["source_title_sha256"]
                    # The same source version can be reanalyzed. The dashboard places it
                    # on its earliest available analysis day, rather than inflating trends.
                    old = records.get(key)
                    if old is None:
                        records[key] = item
                    else:
                        first_day = min(old["day"], item["day"])
                        # Show current event interpretation, while retaining a
                        # prior summary with its own report provenance.
                        records[key] = max((old,item),key=lambda r:r["available_at"])
                        ai_owner=max((old,item),key=lambda r:(bool(r.get("ai_summary")),r.get("ai_summary_available_at",r["available_at"])))
                        if ai_owner.get("ai_summary"):
                            for field in ("ai_summary","ai_claims","ai_uncertainties","ai_status","analysis_purpose"):
                                records[key][field]=ai_owner[field]
                            records[key]["ai_summary_available_at"]=ai_owner.get("ai_summary_available_at",ai_owner["available_at"])
                            records[key]["ai_summary_report_sha256"]=ai_owner.get("ai_summary_report_sha256",ai_owner["report_sha256"])
                        records[key]["day"] = first_day
                        # AI selection must not hide newer directory enrichment.
                        # Retain its own report/time, rather than backdating it to AI.
                        identity_owner = max((old, item), key=lambda r: r.get(
                            "company_identity_analysis_available_at", r["analysis_available_at"]))
                        for field in ("company_identity", "company_identity_status"):
                            records[key][field] = identity_owner.get(field)
                        records[key]["company_identity_analysis_available_at"] = identity_owner.get(
                            "company_identity_analysis_available_at", identity_owner["analysis_available_at"])
                        records[key]["company_identity_report_sha256"] = identity_owner.get(
                            "company_identity_report_sha256", identity_owner["report_sha256"])
            except (SourceShareError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                skipped += 1
    if document_root is not None:
        body_records, body_info = scan_saved_documents(document_root, list(records.values()), now=now, as_of=at)
        for row in body_records:
            records[("motir_document", row["event_id"])] = row
        seen_reports += body_info["saved_reports_seen"]
        skipped += body_info["saved_reports_skipped"]
    return list(records.values()), {
        "saved_reports_seen": seen_reports, "saved_reports_skipped": skipped,
        "unique_analysis_versions": len(records),
        "evidence_limit": "LOCAL_FILE_DIGEST_NOT_INDEPENDENT_PRODUCER_PIN",
    }



def saved_title_analysis(source: dict, reports_root: Path, *, as_of=None, now=None,
                         additional_roots: tuple[tuple[str, Path], ...] = ()) -> dict:
    """Show economic changes in the SAME approved saved RSS title version.

    The caller first resolves the exact source through completed workspaces.
    Reuse the dashboard's SHA-checked, PIT-aware report reader; absence of a
    linked ThemeStore entry must not hide an already-saved article analysis.
    """
    at = _instant((as_of or now or datetime.now(timezone.utc)).isoformat())
    present = _instant((now or datetime.now(timezone.utc)).isoformat())
    if at > present:
        raise SourceShareError("future saved article analysis")
    required = ("provider_id", "event_id", "title_sha256", "headline",
                "source_url", "source_available_at", "search_scope")
    if (not isinstance(source, dict)
            or any(not isinstance(source.get(k), str) for k in required)
            or any(re.fullmatch(r"[0-9a-f]{64}", source[k]) is None
                   for k in ("event_id", "title_sha256"))
            or source["search_scope"] not in (
                {"core", "motir"} | {s for s, _ in additional_roots})):
        raise SourceShareError("exact completed article identity required")
    output = {
        "schema": "newscatalyst.saved_title_economic_analysis.v1",
        "status": "N/A", "reason_code": "NO_EXACT_SAVED_TITLE_ANALYSIS",
        "as_of": at.isoformat(), "analysis_available_at": None,
        "source_available_at": source["source_available_at"],
        "content_scope": "RSS_TITLE_METADATA",
        "economic_changes": [], "economic_change_status": "N/A",
        "verified_economic_fact": False, "verified_real_transaction": False,
        "confirmed_beneficiary": False,
    }
    if _instant(source["source_available_at"]) > at:
        output["reason_code"] = "SOURCE_NOT_AVAILABLE_AS_OF"
        return output
    expected = sha256(("\0".join((source["provider_id"], source["event_id"],
                                      source["title_sha256"]))).encode()).hexdigest()
    rows, info = scan_saved_analysis(reports_root, as_of=at, now=present,
                                      additional_roots=additional_roots)
    matches = [row for row in rows if (
        row["scope"] == source["search_scope"]
        and row["event_id"] == expected
        and row["source_event_sha256"] == source["event_id"]
        and row["provider"] == source["provider_id"]
        and row["headline"] == source["headline"]
        and row["source_url"] == source["source_url"]
        and row["source_available_at"] == source["source_available_at"]
        and row["content_scope"] == "RSS_TITLE_METADATA"
    )]
    if len(matches) != 1:
        output["reason_code"] = ("PARTIAL_SAVED_ANALYSIS_COVERAGE"
                                 if info["saved_reports_skipped"] else "NO_EXACT_SAVED_TITLE_ANALYSIS")
        return output
    row = matches[0]
    changes = [{
        "topic": change["topic"], "action": change["action"],
        "economic_driver": change["economic_driver"],
        "phase": change["phase"], "entity_ids": change["entity_ids"],
        "evidence_level": change["evidence_level"],
        "source_paragraph_sha256": change["source_paragraph_sha256"],
        "industry_tags": change["industry_tags"],
        "extraction_method": change.get("extraction_method"),
    } for change in row["economic_changes"]]
    output.update(
        status="READY", reason_code=None,
        analysis_available_at=row["analysis_available_at"],
        report_sha256=row["report_sha256"],
        category=row["category"], routing_priority=row["priority"],
        ai_status=row["ai_status"], source_products=row["source_products"],
        reported_plan_only=row["reported_plan_only"],
        economic_changes=changes,
        economic_change_status="READY" if changes else "NO_EXPLICIT_TITLE_CHANGE",
    )
    return output

def scan_saved_documents(root: Path, headlines: list[dict], *, now: datetime,
                         as_of: datetime | None = None) -> tuple[list[dict], dict]:
    records = {}
    at = min(now, _instant(as_of.isoformat())) if as_of is not None else now
    seen = skipped = 0
    root = Path(root)
    if not root.exists():
        return [], {"saved_reports_seen": 0, "saved_reports_skipped": 0}
    if root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise SourceShareError("unsafe document dashboard root")
    titles = {row.get("source_event_sha256"): row["headline"] for row in headlines
              if _available_as_of(row, at) and (as_of is None or row.get('available_at'))}
    for folder in sorted(root.iterdir()):
        if re.fullmatch(r"[0-9a-f]{64}", folder.name) is None or folder.is_symlink():
            continue
        reports = folder / "reports"
        if reports.is_symlink() or not reports.is_dir():
            continue
        for path in sorted(reports.iterdir()):
            match = re.fullmatch(r"motir_document_analysis_([0-9a-f]{64})\.json", path.name)
            if match is None:
                continue
            seen += 1
            if seen > MAX_REPORTS:
                raise SourceShareError("too many document analysis reports")
            try:
                data = consume_motir_document_analysis(path, match.group(1), now=now)
                ai = data.get("ai_analysis") or {}
                available = _instant(data["analysis_available_at"])
                if available > at or _instant(data['source_available_at']) > at:
                    continue
                row = {"scope": "motir_document", "event_id": data["analysis_event_sha256"],
                    "source_event_sha256": data["source_event_sha256"],
                    "content_scope": data["content_scope"],
                    "day": available.astimezone(KST).date().isoformat(), "available_at": available.isoformat(),
                    "analysis_available_at": available.isoformat(), "source_available_at": data["source_available_at"],
                    "headline": titles.get(data["source_event_sha256"]) or "산업부 보도자료 본문 · " + data["source_url"].split("/")[-2],
                    "provider": "motir-official-press", "source_url": data["source_url"], "source_kind": "OFFICIAL_AGENCY",
                    "category": "LICENSED_ARTICLE_ANALYSIS", "priority": "HIGH_PRIORITY_CANDIDATE" if data["ai_eligible"] else "PARTIAL_EVIDENCE_ONLY",
                    "ai_status": data["ai_status"], "analysis_purpose": data["analysis_purpose"],
                    "ai_summary": ai.get("summary"), "ai_claims": [] if data.get('semantic_analysis') else ai.get("claims", []),
                    "semantic_analysis": data.get('semantic_analysis'),
                    "bound_title": titles.get(data['source_event_sha256']),
                    "economic_changes": data.get("economic_changes", []),
                    "company_identity": data.get("company_identity"),
                    "ai_uncertainties": ai.get("uncertainties", []), "uncertainty_count": len(ai.get("uncertainties", [])),
                    "reported_plan_only": any(x["category"] == "PRIOR_INVESTMENT_PLAN_MONITORING" for x in data["screen_findings"]),
                    "report_sha256": match.group(1), "document_sha256": data["document_sha256"],
                    "evidence_status": "LOCAL_DIGEST_AND_SAVED_SCHEMA_CHECKED"}
                key = row["event_id"]
                old = records.get(key)
                if old is None:
                    records[key] = row
                else:
                    first_day = min(old["day"], row["day"])
                    if (bool(row["ai_summary"]), row["available_at"]) > (bool(old["ai_summary"]), old["available_at"]):
                        records[key] = row
                    records[key]["day"] = first_day
            except (SourceShareError, OSError, ValueError, TypeError, KeyError):
                skipped += 1
    return list(records.values()), {"saved_reports_seen": seen, "saved_reports_skipped": skipped}


def _count(items: list[dict]) -> dict:
    priorities = Counter(x["priority"] for x in items)
    return {
        "items": len(items),
        "review": priorities.get("HIGH_REVIEW", 0) + priorities.get("HIGH_PRIORITY_CANDIDATE", 0),
        "held": sum(x["priority"] == "PARTIAL_EVIDENCE_ONLY" for x in items),
        "ai_analyzed": sum(x["ai_status"] in ("ANALYZED_UNVERIFIED", "CACHE_HIT") for x in items),
        "uncertainties": sum(x["uncertainty_count"] for x in items),
    }


def _period_key(view: str, selected: date) -> str:
    start, _ = _bounds(view, selected)
    return start.isoformat()


def build_period(records: list[dict], notes: list[dict], view: str, selected: str,
                 *, source_info: dict | None = None, now: datetime | None = None) -> dict:
    start, end = _bounds(view, _day(selected))
    at = period_as_of(view, selected, now=now)
    chosen = [x for x in records if start.isoformat() <= x["day"] <= end.isoformat()
              and _available_as_of(x, at)]
    chosen.sort(key=lambda x: (x["available_at"], x["event_id"]), reverse=True)
    counts = _count(chosen)
    children = []
    if view == "week":
        days = [start + timedelta(days=n) for n in range(7)]
        for day in days:
            subset = [x for x in chosen if x["day"] == day.isoformat()]
            children.append({"key": day.isoformat(), "label": day.isoformat(),
                             **_count(subset)})
    elif view == "month":
        cursor = start - timedelta(days=start.weekday())
        while cursor <= end:
            finish = cursor + timedelta(days=6)
            subset = [x for x in chosen if cursor.isoformat() <= x["day"] <= finish.isoformat()]
            children.append({"key": cursor.isoformat(),
                             "label": f"{max(cursor, start)} ~ {min(finish, end)}",
                             **_count(subset)})
            cursor += timedelta(days=7)
    key = start.isoformat()
    own = [x for x in notes if x["view"] == view and x["period"] == key]
    lower = "day" if view == "week" else "week" if view == "month" else None
    child_keys = {c["key"] for c in children}
    inherited = [x for x in notes if lower and x["view"] == lower
                 and x["period"] in child_keys]
    feedback = []
    if view == "day":
        feedback.append(f"분석 기록 {counts['items']}건, 분석 우선 {counts['review']}건, 근거 보류 {counts['held']}건.")
    else:
        active = sum(c["items"] > 0 for c in children)
        unit = "일" if view == "week" else "주"
        feedback.append(f"{unit}별 기록 {active}/{len(children)}개 구간, 고유 분석 {counts['items']}건.")
        active_children = [c for c in children if c["items"]]
        if len(active_children) > 1:
            first, last = active_children[0], active_children[-1]
            feedback.append(
                f"기록 있는 첫 {unit} {first['items']}건 → 마지막 {unit} {last['items']}건. "
                "기록량 비교이며 성과 확정은 아닙니다.")
        elif len(active_children) == 1:
            feedback.append("기록된 하위 기간이 1개여서 기간 간 변화 판단은 보류합니다.")
    feedback.append(f"미확인 항목 {counts['uncertainties']}개, AI 해석 포함 {counts['ai_analyzed']}건. 사실 검증·수혜 확정은 별도입니다.")
    if inherited:
        feedback.append(f"하위 기간 직접 메모 {len(inherited)}건을 검토 목록에 포함했습니다.")
    if not chosen:
        feedback.append("이 기간에 저장된 분석 기록이 없습니다.")
    return {
        "view": view, "period": key, "start": start.isoformat(), "end": end.isoformat(),
        "as_of": at.isoformat(),
        "counts": counts, "feedback": feedback, "children": children,
        "items": chosen, "notes": own, "inherited_notes": inherited,
        "source": source_info or {},
    }


class NoteStore:
    """Owner-only append log, separate from source reports and Git."""
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "notes.jsonl"

    def _prepare(self) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise SourceShareError("private note folder permissions required")

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        if self.path.is_symlink() or self.path.stat().st_mode & 0o077:
            raise SourceShareError("private note file permissions required")
        if self.path.stat().st_size > MAX_NOTES_BYTES:
            raise SourceShareError("note log exceeds local bound")
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("view") not in VIEWS or not isinstance(item.get("period"), str):
                raise SourceShareError("invalid saved note")
            rows.append(item)
        return rows

    def add(self, view: str, selected: str, text: str) -> dict:
        if view not in VIEWS or not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("invalid note")
        key = _period_key(view, _day(selected))
        self._prepare()
        row = {"view": view, "period": key, "text": text.strip(),
               "created_at": datetime.now(timezone.utc).isoformat()}
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if os.fstat(fd).st_mode & 0o077 or os.fstat(fd).st_size > MAX_NOTES_BYTES - 4096:
                raise SourceShareError("private note file unavailable")
            os.write(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return row
