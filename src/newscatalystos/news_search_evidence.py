"""Link a SHA-pinned completed RSS title to already-stored theme source evidence.

No title similarity, inferred firm ID, network request, new parser, or DB writes.
This is an optional read-only detail for the existing federated title search.
"""
from datetime import datetime, timezone
from pathlib import Path

from .source_share import SourceShareError, _when
from .theme_emergence import ThemeStore


def saved_article_evidence(source: dict, theme_root: Path, *, as_of=None, now=None) -> dict:
    at = _when((as_of or now or datetime.now(timezone.utc)).isoformat(), "evidence as-of")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "evidence now")
    if at > present:
        raise SourceShareError("future evidence selection")
    keys = ("provider_id", "event_id", "title_sha256", "source_url", "source_available_at")
    if not isinstance(source, dict) or any(not isinstance(source.get(k), str) for k in keys):
        raise SourceShareError("exact completed source required")
    # Caller authenticated this version through the approved completed
    # RSS archive, never by accepting user supplied titles or URLs.
    public_source = {k: source[k] for k in keys}
    public_source["headline"] = source["headline"]
    result = {
        "schema": "newscatalyst.saved_article_theme_evidence.v1",
        "source": public_source,
        "as_of": at.isoformat(),
        "status": "N/A",
        "reason_code": "NO_SAVED_EXACT_THEME_EVIDENCE",
        "themes": [],
        "verified_real_transaction": False,
        "verified_real_benefit": False,
        "independent_fact_verified": False,
    }
    if _when(source["source_available_at"], "source availability") > at:
        result["reason_code"] = "SOURCE_NOT_AVAILABLE_AS_OF"
        return result
    themes = ThemeStore(theme_root).search(as_of=at, now=present)
    for theme in themes:
        related = []
        for ref in theme["source_refs"]:
            binding = ref.get("source_binding")
            if (not isinstance(binding, dict) or ref.get("content_scope") != "RSS_TITLE_METADATA"
                    or ref.get("source_id") != source["provider_id"]
                    or binding.get("source_event_sha256") != source["event_id"]
                    or binding.get("document_sha256") != source["title_sha256"]
                    or ref.get("evidence_sha256") != source["title_sha256"]
                    or ref.get("source_url") != source["source_url"]
                    or ref.get("source_available_at") != source["source_available_at"]):
                continue
            if (_when(ref["recorded_at"], "saved event decision") > at
                    or _when(ref["source_available_at"], "source available") > at):
                continue
            companies = [dict(entity_id=c) for c in ref["entity_ids"]]
            # Official identifiers are attached ONLY if the same pinned
            # original source was linked through an explicit directory match.
            for company in companies:
                pins = [m for m in ref.get("company_mappings", [])
                        if m["source_name"] == company["entity_id"]]
                if len(pins) == 1:
                    company["official_entity_id"] = pins[0]["entity_id"]
                    company["identity_evidence_sha256"] = pins[0]["evidence_sha256"]
            related.append({
                "event_id": ref["event_id"],
                "topic": ref["topic"],
                "action": ref["action"],
                "phase": ref["phase"],
                "economic_driver": ref["economic_driver"],
                "evidence_level": ref["evidence_level"],
                "polarity": ref["polarity"],
                "active_in_theme": (ref["event_id"] in theme["event_ids"]
                                    and ref["event_id"] not in theme["invalidated_event_ids"]
                                    and ref["polarity"] == "SUPPORT"),
                "source_available_at": ref["source_available_at"],
                "recorded_at": ref["recorded_at"],
                "content_scope": ref["content_scope"],
                "source_url": ref["source_url"],
                "companies": companies,
            })
        if related:
            result["themes"].append({
                "theme_id": theme["theme_id"],
                "name": theme["provisional_name"],
                "status": theme["status"],
                "first_detected_at": theme["first_detected_at"],
                "decision_at": theme["decision_at"],
                "events": related,
            })
    if result["themes"]:
        result["status"] = "READY"
        result["reason_code"] = None
    return result
