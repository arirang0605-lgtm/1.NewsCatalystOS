"""Exact, read-only bridge: approved MOTIR RSS -> archived licensed document -> theme.

The completed RSS title is authenticated by the caller's existing federated
reader. Body content is never returned, copied, indexed or inferred from a
matching title/URL. Missing rights, receipts or analysis remains item-level N/A.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from .evidence_archive import read_archived_evidence
from .motir_article_binding import consume_motir_article_binding, FEED_ID
from .motir_document_analysis import consume_motir_document_analysis
from .provider_registry import permits_document_storage
from .source_share import SourceShareError, _when
from .theme_emergence import ThemeStore, economic_observation

PIN = re.compile(r"[0-9a-f]{64}\Z")
BINDING = re.compile(r"motir_article_binding_([0-9a-f]{64})\.json\Z")
REPORT = re.compile(r"motir_document_analysis_([0-9a-f]{64})\.json\Z")


def _folders(root, *, limit=128):
    """Bounded directory discovery; never create an output or follow a link."""
    root = Path(root)
    if (not root.is_absolute() or ".." in root.parts or root.is_symlink()
            or root.resolve() != root):
        raise SourceShareError("invalid archived document root")
    if not root.exists():
        return []
    if not root.is_dir():
        raise SourceShareError("archived document root is not a directory")
    paths = [p for p in root.iterdir() if not p.name.startswith("._")]
    if len(paths) > limit:
        raise SourceShareError("too many published document entries")
    if any(p.is_symlink() for p in paths):
        raise SourceShareError("symlink in published document entries")
    return sorted(paths)


def _empty(reason, at):
    return {
        "status": "N/A", "reason_code": reason, "content_scope": "LICENSED_ARTICLE_TEXT",
        "as_of": at.isoformat(), "themes": [],
        "verified_real_transaction": False, "verified_real_benefit": False,
        "independent_fact_verified": False,
    }


def bound_motir_document_evidence(source, collection_root, analysis_root, theme_root,
                                  *, registry_reader, as_of=None, now=None):
    """Return only events proven through all four existing immutable pins.

    No fallback from a current public RSS URL to an older article or a guessed
    corporate beneficiary is allowed. The original archive remains private.
    """
    at = _when((as_of or now or datetime.now(timezone.utc)).isoformat(), "body evidence as-of")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "body evidence now")
    if at > present:
        raise SourceShareError("future official document evidence")
    if not isinstance(source, dict) or any(not isinstance(source.get(k), str)
            for k in ("provider_id", "event_id", "title_sha256", "source_url", "source_available_at")):
        raise SourceShareError("exact completed source is required")
    if source["provider_id"] != FEED_ID:
        return _empty("NOT_MOTIR_RSS", at)
    if _when(source["source_available_at"], "RSS available") > at:
        return _empty("SOURCE_NOT_AVAILABLE_AS_OF", at)
    if any(PIN.fullmatch(source[k]) is None for k in ("event_id", "title_sha256")):
        raise SourceShareError("invalid original article version")
    matching = []
    for folder in _folders(collection_root, limit=64):
        if not PIN.fullmatch(folder.name) or not folder.is_dir():
            continue
        for path in _folders(folder / "bindings", limit=128):
            match = BINDING.fullmatch(path.name)
            if match is None or not path.is_file():
                continue
            try:
                binding = consume_motir_article_binding(path, match.group(1), now=present)
            except (SourceShareError, OSError, ValueError, TypeError):
                # Other corrupt publications cannot hide a valid independent one.
                continue
            if (binding["rss_provider_id"], binding["source_event_sha256"],
                    binding["title_sha256"], binding["source_url"],
                    binding["rss_first_seen_at"]) != (
                    source["provider_id"], source["event_id"], source["title_sha256"],
                    source["source_url"], source["source_available_at"]):
                continue
            matching.append((folder, match.group(1), binding))
    if not matching:
        return _empty("NO_EXACT_OFFICIAL_DOCUMENT_BINDING", at)
    if len(matching) != 1:
        return _empty("AMBIGUOUS_OFFICIAL_DOCUMENT_BINDING", at)
    folder, binding_pin, binding = matching[0]
    if _when(binding["binding_at"], "document binding") > at:
        return _empty("DOCUMENT_NOT_AVAILABLE_AS_OF", at)

    # Licensing is checked NOW, not merely at initial publication. The archive
    # SHA and rights-protected source bytes are inspected but never exposed.
    try:
        registry = registry_reader(folder / "registry.json")
        provider = registry.active(binding["article_provider_id"], at=present)
        if (provider.method != "DOCUMENT" or provider.endpoint != binding["source_url"]
                or not permits_document_storage(provider)):
            return _empty("DOCUMENT_RIGHTS_UNAVAILABLE", at)
        body, archive = read_archived_evidence(folder / "archive",
                                               binding["archive_version"], now=at)
        if (sha256(body).hexdigest() != binding["document_sha256"]
                or archive.receipt_sha256 != binding["archive_receipt_sha256"]
                or archive.provider_id != binding["article_provider_id"]
                or archive.archived_at.isoformat() != binding["article_archived_at"]
                or archive.content_scope != "LICENSED_SOURCE_BYTES"):
            return _empty("DOCUMENT_ARCHIVE_MISMATCH", at)
    except (SourceShareError, OSError, ValueError, TypeError, KeyError):
        return _empty("DOCUMENT_RIGHTS_OR_ARCHIVE_UNAVAILABLE", at)

    reports_dir = Path(analysis_root) / binding_pin / "reports"
    claims = {}
    report_count = 0
    latest = None
    for path in _folders(reports_dir, limit=256):
        match = REPORT.fullmatch(path.name)
        if match is None or not path.is_file():
            continue
        try:
            report = consume_motir_document_analysis(path, match.group(1), now=at)
        except (SourceShareError, OSError, ValueError, TypeError, KeyError):
            continue
        if (report["source_event_sha256"] != binding["source_event_sha256"]
                or report["title_sha256"] != binding["title_sha256"]
                or report["binding_sha256"] != binding_pin
                or report["document_sha256"] != binding["document_sha256"]
                or report["archive_receipt_sha256"] != binding["archive_receipt_sha256"]
                or report["source_url"] != binding["source_url"]
                or report["source_available_at"] != binding["binding_at"]
                or report["analysis_event_sha256"] != sha256((
                    "licensed-motir-body-v1\0" + binding["source_event_sha256"]
                    + "\0" + binding["document_sha256"]).encode()).hexdigest()):
            continue
        report_count += 1
        if latest is None or report["analysis_available_at"] > latest:
            latest = report["analysis_available_at"]
        for change in report.get("economic_changes", []):
            observation = economic_observation(
                change, origin_reference=report["source_url"],
                source_url=report["source_url"], source_id=FEED_ID,
                source_available_at=report["source_available_at"],
                source_binding={"source_event_sha256": binding["archive_version"],
                                "document_sha256": binding["document_sha256"]},
            )
            key = (observation["event_id"], change["source_paragraph_sha256"])
            previous = claims.get(key)
            if previous is None or report["analysis_available_at"] < previous[0]:
                claims[key] = (report["analysis_available_at"], change)
    if not report_count:
        return _empty("NO_VERIFIED_BOUND_DOCUMENT_ANALYSIS", at)
    if not claims:
        return _empty("NO_REPORTED_DOCUMENT_ECONOMIC_CHANGE", at)

    themes = []
    for theme in ThemeStore(theme_root).search(as_of=at, now=present):
        # V1 supported industry: non-semiconductor items stay independent N/A.
        if "SEMICONDUCTOR" not in theme["industry_tags"]:
            continue
        events = {}
        for ref in theme["source_refs"]:
            version = ref.get("source_binding")
            if (not isinstance(version, dict)
                    or version.get("source_event_sha256") != binding["archive_version"]
                    or version.get("document_sha256") != binding["document_sha256"]
                    or ref.get("source_id") != FEED_ID
                    or ref.get("source_url") != binding["source_url"]
                    or ref.get("source_available_at") != binding["binding_at"]
                    or ref.get("content_scope") not in (None, "LICENSED_ARTICLE_TEXT")):
                continue
            match = claims.get((ref["event_id"], ref["evidence_sha256"]))
            if not match or _when(match[0], "analysis publication") > _when(
                    ref["recorded_at"], "event observation"):
                continue
            _, change = match
            if (ref["action"] != change["action"] or ref.get("topic", change["topic"]) != change["topic"]
                    or ref["phase"] != change["phase"]
                    or ref.get("economic_driver", change["economic_driver"]) != change["economic_driver"]
                    or ref["evidence_level"] != change["evidence_level"]):
                continue
            companies = [dict(entity_id=n) for n in ref["entity_ids"]]
            for company in companies:
                matches = [m for m in ref.get("company_mappings", [])
                           if m["source_name"] == company["entity_id"]]
                if len(matches) == 1:
                    company["official_entity_id"] = matches[0]["entity_id"]
            events[ref["event_id"]] = {
                "event_id": ref["event_id"], "topic": change["topic"],
                "action": ref["action"], "phase": ref["phase"],
                "economic_driver": change["economic_driver"],
                "evidence_level": ref["evidence_level"],
                "polarity": ref["polarity"], "content_scope": "LICENSED_ARTICLE_TEXT",
                "active_in_theme": (ref["event_id"] in theme["event_ids"]
                                    and ref["event_id"] not in theme["invalidated_event_ids"]
                                    and ref["polarity"] == "SUPPORT"),
                "source_url": ref["source_url"],
                "source_available_at": ref["source_available_at"],
                "analysis_available_at": match[0], "recorded_at": ref["recorded_at"],
                "companies": companies,
            }
        if events:
            themes.append({
                "theme_id": theme["theme_id"], "name": theme["provisional_name"],
                "status": theme["status"], "first_detected_at": theme["first_detected_at"],
                "decision_at": theme["decision_at"], "events": list(events.values()),
            })
    if not themes:
        return _empty("NO_EXACT_BOUND_DOCUMENT_THEME", at)
    return {
        "status": "READY", "reason_code": None, "content_scope": "LICENSED_ARTICLE_TEXT",
        "as_of": at.isoformat(), "binding_sha256": binding_pin,
        "document_sha256": binding["document_sha256"],
        "archive_receipt_sha256": binding["archive_receipt_sha256"],
        "binding_available_at": binding["binding_at"],
        "latest_analysis_available_at": latest,
        "source_url": binding["source_url"], "themes": themes,
        "verified_real_transaction": False, "verified_real_benefit": False,
        "independent_fact_verified": False,
    }
