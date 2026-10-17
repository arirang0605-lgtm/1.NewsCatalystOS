"""Read companies of one exactly linked article/theme event.

This reuses immutable ThemeStore and CompanyCandidates. A theme neighbor is
not an article party, and a reported supplier is not a realized beneficiary.
"""
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from .source_share import SourceShareError, _when
from .standard_delivery import build_theme_bundle
from .theme_emergence import ThemeStore

_OFFICIAL_ID = re.compile(r"(?:DART_CORP:[0-9]{8}|KRX_STOCK:[0-9]{6}|SEC_CIK:[0-9]{1,10})\Z")
_RELATIONS = {"SOURCE_REPORTED_SUPPLY_RELATION", "INFERRED_ASSOCIATION"}


def article_company_context(detail: dict, theme_root: Path, *, as_of=None, now=None) -> dict:
    """Read existing companies after the caller authenticated article details."""
    at = _when((as_of or now or datetime.now(timezone.utc)).isoformat(), "company context at")
    present = _when((now or datetime.now(timezone.utc)).isoformat(), "company context now")
    if at > present:
        raise SourceShareError("future article company context")
    source = detail.get("source") if isinstance(detail, dict) else None
    if (not isinstance(source, dict)
            or any(not isinstance(source.get(k), str) for k in (
                "provider_id", "event_id", "title_sha256", "source_url", "source_available_at"))):
        raise SourceShareError("exact completed title detail required")
    result = {
        "schema": "newscatalyst.saved_article_company_context.v1",
        "status": "N/A", "reason_code": "NO_EXACT_ARTICLE_THEME",
        "as_of": at.isoformat(), "themes": [],
        "verified_real_transaction": False, "verified_real_benefit": False,
        "investment_merit": "NOT_ASSESSED",
    }
    if _when(source["source_available_at"], "article source at") > at:
        result["reason_code"] = "SOURCE_NOT_AVAILABLE_AS_OF"
        return result

    links = []
    if detail.get("status") == "READY":
        for row in detail.get("themes", []):
            for event in row["events"]:
                if event.get("content_scope") == "RSS_TITLE_METADATA":
                    links.append((row, event, "RSS_TITLE_METADATA", None))
    official = detail.get("official_document_evidence", {})
    if isinstance(official, dict) and official.get("status") == "READY":
        for row in official["themes"]:
            for event in row["events"]:
                if event.get("content_scope") == "LICENSED_ARTICLE_TEXT":
                    links.append((row, event, "LICENSED_ARTICLE_TEXT",
                                  official.get("document_sha256")))
    if not links:
        return result

    ids = {row["theme_id"] for row, _, _, _ in links}
    snapshots = {t["theme_id"]: t for t in ThemeStore(theme_root).search(as_of=at, now=present)
                 if t["theme_id"] in ids}
    if not snapshots:
        return result
    payload = json.loads(build_theme_bundle(
        list(snapshots.values()), decision_at=at, now=present,
        include_company_candidates=True))
    candidate_map = {(c["theme_id"], c["entity_id"]): c
                     for c in payload["CompanyCandidates"]}
    groups = {}
    for row, event, scope, body_sha in links:
        theme = snapshots.get(row["theme_id"])
        if theme is None or (theme["decision_at"] != row["decision_at"]
                             or theme["status"] != row["status"]):
            continue
        if (event.get("source_url") != source["source_url"]
                or _when(event["source_available_at"], "event source at") > at
                or _when(event["recorded_at"], "event evidence at") > at):
            continue
        anchors = []
        for ref in theme["source_refs"]:
            binding = ref.get("source_binding")
            if (not isinstance(binding, dict)
                    or any(ref.get(k) != event.get(k) for k in (
                        "event_id", "source_url", "source_available_at", "recorded_at",
                        "action", "phase", "polarity", "evidence_level"))):
                continue
            if scope == "RSS_TITLE_METADATA":
                if (ref.get("content_scope") != scope
                        or ref.get("source_id") != source["provider_id"]
                        or binding.get("source_event_sha256") != source["event_id"]
                        or binding.get("document_sha256") != source["title_sha256"]
                        or ref.get("evidence_sha256") != source["title_sha256"]):
                    continue
            elif (ref.get("content_scope") not in (None, scope)
                  or ref.get("source_id") != source["provider_id"]
                  or binding.get("document_sha256") != body_sha):
                continue
            anchors.append(ref)
        if len(anchors) != 1:
            continue
        ref = anchors[0]
        group = groups.setdefault(row["theme_id"], {
            "theme_id": theme["theme_id"], "name": theme["provisional_name"],
            "theme_status": theme["status"], "decision_at": theme["decision_at"],
            "direct_parties": [], "related_supply_context": [],
            "industry_supported_in_v1": "SEMICONDUCTOR" in theme["industry_tags"],
        })
        seen = {(c["event_id"], c["entity_id"], c["source_url"])
                for c in group["direct_parties"]}
        for entity in ref["entity_ids"]:
            if (event["event_id"], entity, ref["source_url"]) in seen:
                continue
            mappings = [m for m in ref.get("company_mappings", [])
                        if m["entity_id"] == entity and _OFFICIAL_ID.fullmatch(entity)]
            pinned = mappings[0] if len(mappings) == 1 else None
            company = candidate_map.get((theme["theme_id"], entity))
            matched_basis = []
            if event.get("active_in_theme") and company:
                matched_basis = [b for b in company["inclusion_basis"]
                                 if b.get("event_id") == ref["event_id"]
                                 and b.get("source_url") == ref["source_url"]
                                 and b.get("source_available_at") == ref["source_available_at"]
                                 and b.get("recorded_at") == ref["recorded_at"]
                                 and b.get("evidence_sha256") == ref["evidence_sha256"]
                                 and b.get("source_binding") == ref["source_binding"]
                                 and b.get("kind") in (
                                     "SOURCE_REPORTED_PARTICIPANT", "INFERRED_ASSOCIATION")]
            party = {
                "entity_id": entity,
                "source_name": pinned["source_name"] if pinned else entity,
                "official_entity_id": entity if pinned else None,
                "identity_status": "PINNED_OFFICIAL_ID" if pinned else "SOURCE_NAME_ONLY",
                "identity_evidence_sha256": pinned["evidence_sha256"] if pinned else None,
                "event_id": ref["event_id"], "action": ref["action"],
                "phase": ref["phase"], "evidence_level": ref["evidence_level"],
                "polarity": ref["polarity"], "active_in_theme": bool(event["active_in_theme"]),
                "inclusion_status": "READY" if matched_basis else "N/A",
                "inclusion_reasons": [b["reason"] for b in matched_basis],
                "source_url": ref["source_url"],
                "source_available_at": ref["source_available_at"],
                "recorded_at": ref["recorded_at"],
                "content_scope": scope,
                "benefit_status": "UNVERIFIED",
                "financial_assessment": "NOT_EVALUATED_HERE",
                "price_assessment": "NOT_EVALUATED_HERE",
            }
            group["direct_parties"].append(party)

        # Other participants are shown only when a separate supply relation
        # is explicitly attached to this same active event; no theme-wide
        # supplier or profit guesses.
        if not event.get("active_in_theme") or not ref["entity_ids"]:
            continue
        other = {(r["entity_id"], r["relation_sha256"])
                 for r in group["related_supply_context"]}
        for candidate in payload["CompanyCandidates"]:
            if candidate["theme_id"] != theme["theme_id"]:
                continue
            for basis in candidate["inclusion_basis"]:
                if (basis["kind"] not in _RELATIONS
                        or "relation_sha256" not in basis
                        or ref["event_id"] not in basis.get("event_ids", [])):
                    continue
                identity = (candidate["entity_id"], basis["relation_sha256"])
                if identity in other:
                    continue
                other.add(identity)
                group["related_supply_context"].append({
                    "entity_id": candidate["entity_id"],
                    "role": basis.get("role"),
                    "relation_kind": basis.get("relation_kind"),
                    "counterparty_id": basis.get("counterparty_id"),
                    "product_stage": basis.get("product_stage"),
                    "impact_category": basis.get("impact_category"),
                    "evidence_level": basis.get("impact_evidence_level"),
                    "linked_event_id": ref["event_id"],
                    "linked_at": basis.get("linked_at"),
                    "relation_sha256": basis["relation_sha256"],
                    "source_urls": basis.get("source_urls", []),
                    "reported_in_selected_article": any(
                        party["entity_id"] == candidate["entity_id"]
                        and party["event_id"] == ref["event_id"]
                        for party in group["direct_parties"]),
                    "realized_benefit": False,
                })
    result["themes"] = [group for group in groups.values()
                        if group["direct_parties"] or group["related_supply_context"]]
    if result["themes"]:
        result.update(status="READY", reason_code=None)
    else:
        result["reason_code"] = "NO_COMPANY_IN_EXACT_ARTICLE_EVENTS"
    return result
