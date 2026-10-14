"""Bridge verified RSS search identities to existing blind human-review cases.

No gold/answer creation, predictions, overlap suggestions, or other reviewer's
answers are exposed. Query-selected cases are NOT an unbiased evaluation set.
Only the original PIN-backed gold and human-review entry points are reused.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable

from .evidence_archive import _read_once
from .federated_news_search import TitleSearchWorkspace, search_completed_workspaces
from .human_review_entry import SLOTS, _existing_private_dir, list_review_cases
from .live_gold_samples import BATCH, MAX_CASES, MAX_FILE, _load_pinned_predictions
from .provider_registry import ProviderRegistry
from .source_share import SourceShareError, _json, _must_sha, _when

SCHEMA = "newscatalyst.search_gold_review_links.v1"


@dataclass(frozen=True)
class GoldSearchWorkspace:
    source: TitleSearchWorkspace
    out_root: Path
    pin_root: Path
    workspace_root: Path


def _pinned_case_index(workspace: GoldSearchWorkspace, at: datetime) -> dict:
    """Verify published gold and independent pins; never create missing roots."""
    root = _existing_private_dir(workspace.out_root)
    pins = _existing_private_dir(workspace.pin_root)
    names = set()
    for folder in root.iterdir():
        if folder.name.startswith("gold_batch_"):
            if BATCH.fullmatch(folder.name) is None or folder.is_symlink() or not folder.is_dir():
                raise SourceShareError("unexpected published gold folder")
            names.add(folder.name)
    pin_names = set()
    for path in pins.iterdir():
        if path.name.startswith("gold_batch_"):
            name = path.name.removesuffix(".pin.json")
            if (not path.name.endswith(".pin.json") or BATCH.fullmatch(name) is None
                    or path.is_symlink() or not path.is_file()):
                raise SourceShareError("unexpected gold pin file")
            pin_names.add(name)
    if names != pin_names or len(names) > MAX_CASES:
        raise SourceShareError("gold publication and independent pin inventory differ")
    indexed = {}
    for name in sorted(names):
        folder = root / name
        digest = name.removeprefix("gold_batch_")
        pin_file = pins / (name + ".pin.json")
        predictions, pinned_at = _load_pinned_predictions(
            folder, root, digest, pin_file, pins, at,
        )
        # Recheck the exact bytes we parse against the existing independent pin.
        pin = _json(_read_once(pin_file, 4096), "gold review locator pin")
        blind_bytes = _read_once(folder / "blind_cases.json", MAX_FILE)
        if sha256(blind_bytes).hexdigest() != pin["blind_sha256"]:
            raise SourceShareError("blind review locator SHA mismatch")
        blind = _json(blind_bytes, "blind review locators")
        by_id = {row.case_sha256: row for row in predictions}
        if len(by_id) != len(predictions):
            raise SourceShareError("duplicate prediction case identity")
        for item in blind["cases"]:
            case = _must_sha(item["case_sha256"], "frozen review identity")
            if case in indexed or case not in by_id:
                raise SourceShareError("ambiguous gold case identity")
            prediction = by_id[case]
            source_at = _when(item["source_available_at"], "blind source availability")
            ack_at = _when(item["first_acknowledged_at"], "blind acknowledgment")
            if (item["source_sha256"] != prediction.source_sha256
                    or source_at != prediction.source_available_at
                    or not source_at <= ack_at <= prediction.predicted_at <= pinned_at <= at
                    or prediction.pin_first_observed_at > pinned_at):
                raise SourceShareError("gold review case source/time mismatch")
            indexed[case] = (digest, item, pinned_at)
            if len(indexed) > MAX_CASES:
                raise SourceShareError("too many frozen cases for review lookup")
    return indexed


def _entry_arguments(workspace: GoldSearchWorkspace, batch: str,
                     case: str, slot: str) -> list[str]:
    # Display-only argv, never a shell execution or automatically assigned identity.
    return [
        "env", "PYTHONPATH=src", "python3", "scripts/review_news_interactive.py",
        "--out-root", str(workspace.out_root),
        "--pin-root", str(workspace.pin_root),
        "--workspace-root", str(workspace.workspace_root),
        "--batch-sha256", batch, "--case-sha256", case, "--slot", slot,
    ]


def search_gold_review_links(
    workspaces: tuple[GoldSearchWorkspace, ...], phrase: str, *,
    registry_reader: Callable[[Path], ProviderRegistry], slot: str,
    source_id: str | None = None, semiconductor_only: bool = False,
    limit: int = 20, now: datetime | None = None,
) -> dict:
    """Read-only query -> exact source/event/title SHA -> existing chosen slot.

    Selected-but-unfrozen cases remain pending; corrupt scopes never return a
    review locator. A submitted case cannot silently select a different case.
    Neither the truth values nor the other reviewer's completion is disclosed.
    """
    if (slot not in SLOTS or not isinstance(workspaces, tuple)
            or not 1 <= len(workspaces) <= 8
            or any(not isinstance(w, GoldSearchWorkspace) for w in workspaces)):
        raise SourceShareError("existing gold workspaces and one explicit reviewer slot required")
    paths = set()
    for workspace in workspaces:
        if not isinstance(workspace.source, TitleSearchWorkspace):
            raise SourceShareError("typed source workspace required")
        for value in (workspace.out_root, workspace.pin_root, workspace.workspace_root):
            path = Path(value)
            if (not path.is_absolute() or ".." in path.parts
                    or any(part.casefold() == "eraleader" for part in path.parts)
                    or path.resolve(strict=False) != path or path in paths):
                raise SourceShareError("distinct non-symlink review paths required")
            paths.add(path)
    search = search_completed_workspaces(
        tuple(w.source for w in workspaces), phrase, registry_reader=registry_reader,
        source_id=source_id, semiconductor_only=semiconductor_only, limit=limit, now=now,
    )
    at = _when(search["search_verified_at"], "search verification")
    scoped = {w.source.scope: w for w in workspaces}
    indexes, errors = {}, {}
    for scope in {row["search_scope"] for row in search["results"]}:
        try:
            indexes[scope] = _pinned_case_index(scoped[scope], at)
        except (SourceShareError, OSError, ValueError, TypeError, KeyError) as exc:
            errors[scope] = type(exc).__name__
    results = []
    for row in search["results"]:
        scope = row["search_scope"]
        workspace = scoped[scope]
        identity = (row["provider_id"], _must_sha(row["event_id"], "search event"),
                    _must_sha(row["title_sha256"], "search title version"))
        case = sha256("\0".join(identity).encode()).hexdigest()
        # Allowlist neutral source metadata. Do NOT copy search classification,
        # overlap hints, priority, predicted labels, or the other reviewer's data.
        item = {k: row[k] for k in (
            "search_scope", "provider_id", "event_id", "title_sha256", "headline",
            "source_url", "source_kind", "source_available_at", "triage_evidence_sha256",
        )}
        item.update({
            "case_sha256": case, "reviewer_slot": slot,
            "link_status": "NOT_FROZEN_YET", "batch_sha256": None,
            "gold_pinned_at": None, "review_entry_argv": None,
            "reviewer_code_required": True,
        })
        if scope in errors:
            item.update(link_status="GOLD_DATA_UNAVAILABLE", error_type=errors[scope])
        elif case in indexes[scope]:
            digest, blind, pinned_at = indexes[scope][case]
            try:
                if (blind["provider_id"] != row["provider_id"]
                        or blind["source_sha256"] != row["event_id"]
                        or blind["headline"] != row["headline"]
                        or blind["source_url"] != row["source_url"]
                        or blind["source_role"] != row["source_kind"]):
                    raise SourceShareError("search identity does not match pinned blind source")
                page = list_review_cases(
                    workspace.out_root, workspace.pin_root, workspace.workspace_root,
                    digest, slot, case_sha256=case, limit=1, now=at,
                )
                if page["cases"] and page["cases"][0]["case_sha256"] != case:
                    raise SourceShareError("review entry selected another case")
                ready = bool(page["cases"])
                item.update(
                    link_status="READY_FOR_HUMAN_REVIEW" if ready
                                else "SELECTED_SLOT_ALREADY_SUBMITTED",
                    batch_sha256=digest, gold_pinned_at=pinned_at.isoformat(),
                    review_entry_argv=_entry_arguments(workspace, digest, case, slot) if ready else None,
                )
            except (SourceShareError, OSError, ValueError, TypeError, KeyError) as exc:
                item.update(link_status="REVIEW_ENTRY_UNAVAILABLE", error_type=type(exc).__name__)
        results.append(item)
    checked = _when((now or datetime.now(timezone.utc)).isoformat(), "review link verified")
    if checked < at:
        raise SourceShareError("review link clock moved backwards")
    for item in results:
        item["link_verified_at"] = checked.isoformat()
    results.sort(key=lambda row: row["case_sha256"])
    linked = sum(row["link_status"] in (
        "READY_FOR_HUMAN_REVIEW", "SELECTED_SLOT_ALREADY_SUBMITTED") for row in results)
    complete = search["coverage_complete"] and linked == len(results)
    return {
        "schema": SCHEMA,
        "status": "SEARCH_GOLD_REVIEW_LINKS_READY" if complete else "SEARCH_GOLD_REVIEW_LINKS_PARTIAL",
        "coverage_complete": search["coverage_complete"], "review_links_complete": complete,
        "searched_document_versions": search["searched_document_versions"],
        "matched_document_versions": search["matched_document_versions"],
        "has_more_matches": search["has_more_matches"], "returned_case_count": len(results),
        "linked_case_count": linked,
        "ready_for_selected_reviewer_count": sum(
            r["link_status"] == "READY_FOR_HUMAN_REVIEW" for r in results),
        "pending_unfrozen_count": sum(r["link_status"] == "NOT_FROZEN_YET" for r in results),
        "scopes": search["scopes"], "results": results,
        "selection_scope": "QUERY_SUBSET_NOT_UNBIASED_EVALUATION_SAMPLE",
        "required_human_argument": "--reviewer-code <YOUR_OWN_REVIEWER_CODE>",
        "model_predictions_exposed": False, "automatic_overlap_hints_exposed": False,
        "other_reviewer_answers_exposed": False,
        "human_labels_added": 0, "gold_batches_created": 0,
        "review_entry_executed": False, "source_databases_modified": False,
        "network_calls": 0, "ai_calls": 0, "release_gate_verified": False,
    }
