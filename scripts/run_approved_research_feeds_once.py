"""Run existing approved research RSS pipelines together in one unattended tick.

This is a caller of run_scheduled_triage, NOT another collector. Each source
retains its own approved registry, rate ledger, durable ACK, theme history and
article provenance. A broken source never prevents healthy sources executing.

One explicit --once performs bounded authorized source requests. --dry-run and
--replay-only do not fetch external RSS. Never installs or changes launchd.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import os
import stat
import sys

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from scripts import run_scheduled_triage
from newscatalystos.source_share import SourceShareError

# Source identifiers are deliberately fixed to existing reviewed rights.
# Company and NIST category feeds use the SAME source owner and budget.
FEEDS = (
    ("msit", "msit-official-press", None),
    ("msit", "msit-official-rnd-policy", None),
    ("company", "samsung-newsroom-korea", None),
    ("company", "skhynix-newsroom-korea",
     "skhynix_press_variant_authorized_sources.json"),
    ("nist", "nist-official-electronics",
     "nist_manufacturing_variant_authorized_sources.json"),
)
WORKSPACES = {
    "msit": "msit_live_dev",
    "company": "company_live_dev",
    "nist": "nist_live_dev",
}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspaces-root", required=True, type=Path,
                   help="absolute parent of 3 isolated, owner-only approved RSS workspaces")
    p.add_argument("--era-daily-config",type=Path,
                   help="optional read-only producer daily snapshot connection")
    p.add_argument("--era-daily-root",type=Path,
                   help="NewsCatalystOS private received assessment folder")
    p.add_argument("--material-outbox",type=Path,
                   help="News-owned immutable forward material delivery after the existing tick")
    p.add_argument("--material-base-root",type=Path,
                   help="existing base ThemeStore; required with --material-outbox")
    p.add_argument("--economic-discovery-root",type=Path,
                   help="optional event-first watch using current approved stored news, no industry prerequisite")
    p.add_argument("--discovery-source-base",type=Path,
                   help="existing core/MOTIR source base, required with discovery")
    p.add_argument("--material-news-workspace",action="append",default=[],metavar="SCOPE=ABSOLUTE_ROOT",
                   help="additional current approved title workspace for company-economic publication; no fetch")
    operation = p.add_mutually_exclusive_group(required=True)
    operation.add_argument("--once", action="store_true")
    operation.add_argument("--dry-run", action="store_true")
    operation.add_argument("--replay-only", action="store_true")
    return p


def _workspace_root(parent: Path, name: str) -> Path:
    root = parent / WORKSPACES[name]
    if (not parent.is_absolute() or ".." in parent.parts
            or parent.is_symlink() or not root.is_dir() or root.is_symlink()
            or root.resolve() != root
            or any(x.casefold() == "eraleader" for x in root.parts)):
        raise SourceShareError("isolated approved RSS workspace required")
    info = root.lstat()
    if (info.st_uid != os.geteuid()
            or not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise SourceShareError("owner-only approved workspace required")
    return root


def execute(opts: argparse.Namespace, *, run_tick=run_scheduled_triage.execute) -> tuple[int, dict]:
    """One bounded pass of existing collectors; failures isolated by provider."""
    if sum(bool(getattr(opts, name, False)) for name in ("once", "dry_run", "replay_only")) != 1:
        raise SourceShareError("one explicit collection mode required")
    operation = ("--once" if opts.once else "--dry-run" if opts.dry_run
                 else "--replay-only")
    rows = []
    failures = 0
    for scope, provider, alternate in FEEDS:
        try:
            root = _workspace_root(Path(opts.workspaces_root), scope)
            args = [
                "--registry", str(root / "providers/authorized_sources.json"),
                "--provider-id", provider,
                "--state", str(root / "state/incremental_feeds.sqlite3"),
                "--dedup-state", str(root / "state/triage_exact_index.sqlite3"),
                "--inbox-root", str(root / "inbox/feed_triage"),
                "--output-root", str(root / "triage"),
                "--analysis-root", str(root / "feed_analysis/core"),
                "--analysis-theme-root", str(root / "document_analysis/theme_history"),
                "--analysis-limit", "100", operation,
            ]
            if alternate is not None:
                args.extend(["--alternate-registry", str(root / "providers" / alternate)])
            code, result = run_tick(run_scheduled_triage.parser().parse_args(args))
            result_rows = result.get("providers", [])
            entry = result_rows[0] if len(result_rows) == 1 else {}
            analysis = entry.get("analysis", {})
            status = entry.get("status", result.get("status", "DATA_UNAVAILABLE"))
            bad = code != 0 or not entry
            rows.append({
                "scope": scope, "provider_id": provider, "status": status,
                "feed_variant": entry.get("feed_variant"),
                "new_articles": entry.get("new_provider_ids", 0),
                "keyword_candidates": entry.get("semiconductor_keyword_candidates", 0),
                "analysis_status": analysis.get("status",
                          "NOT_RUN" if operation == "--dry-run" else "UNAVAILABLE"),
                "analyzed_rows": analysis.get("analyzed_rows", 0),
                "economic_changes": analysis.get("economic_changes_count", 0),
                "new_theme_versions": analysis.get("theme_versions_created", 0),
                "failed": bad,
            })
            failures += int(bad)
        except (SourceShareError, OSError, ValueError, TypeError, KeyError) as exc:
            failures += 1
            rows.append({"scope": scope, "provider_id": provider,
                         "status": "DATA_UNAVAILABLE",
                         "error_type": type(exc).__name__, "failed": True})
    # Producer failure is local to optional corporate context: a working
    # news source never waits for the independent EraLeader workflow.
    integration=None
    if getattr(opts,"era_daily_config",None) is not None:
        try:
            if getattr(opts,"era_daily_root",None) is None:
                raise SourceShareError("explicit consumer-owned daily cache required")
            from newscatalystos.era_daily_assessment import refresh_daily
            integration=refresh_daily(opts.era_daily_config,opts.era_daily_root,
                                      check_only=bool(opts.dry_run))
        except (SourceShareError,OSError,ValueError,TypeError,KeyError) as exc:
            integration={"status":"UNAVAILABLE","error_type":type(exc).__name__}
    discovery=None
    if getattr(opts,"economic_discovery_root",None) is not None:
        try:
            if getattr(opts,"discovery_source_base",None) is None:
                raise SourceShareError("explicit current source base required for discovery")
            from scripts.run_economic_discovery import execute as discover,source_roots
            discovery=discover(opts.economic_discovery_root,
                source_roots(opts.discovery_source_base,opts.workspaces_root),dry_run=bool(opts.dry_run))
        except (SourceShareError,OSError,ValueError,TypeError,KeyError) as exc:
            discovery={"status":"UNAVAILABLE","error_type":type(exc).__name__}
    delivery=None
    if getattr(opts,"material_outbox",None) is not None:
        try:
            if getattr(opts,"material_base_root",None) is None:
                raise SourceShareError("explicit base source required for material publication")
            from newscatalystos.material_publication import publish_material
            sources={"base":opts.material_base_root}
            sources.update({scope:Path(opts.workspaces_root)/name/"document_analysis/theme_history"
                            for scope,name in WORKSPACES.items()})
            recent=()
            if getattr(opts,'economic_discovery_root',None) is not None:
                from scripts.run_economic_discovery import source_roots
                from newscatalystos.federated_news_search import TitleSearchWorkspace
                import re
                if getattr(opts,'discovery_source_base',None) is None:
                    raise SourceShareError('current source base required for company changes')
                recent=tuple(TitleSearchWorkspace(scope,registry,state,inbox) for scope,registry,state,inbox
                             in source_roots(opts.discovery_source_base,opts.workspaces_root))
                for item in getattr(opts,'material_news_workspace',[]):
                    scope,separator,location=item.partition('=');path=Path(location)
                    if (not separator or not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}',scope)
                            or any(w.scope==scope for w in recent) or not path.is_absolute()
                            or path.resolve()!=path or path.is_symlink()
                            or any('eraleader' in p.casefold() for p in path.parts)):
                        raise SourceShareError('distinct current approved News workspace required')
                    recent+=(TitleSearchWorkspace(scope,path/'providers/authorized_sources.json',
                        path/'state/incremental_feeds.sqlite3',path/'inbox/feed_triage'),)
            delivery=publish_material(opts.material_outbox,sources,
                identity_root=getattr(opts,"era_daily_root",None),dry_run=bool(opts.dry_run),
                economic_discovery_root=getattr(opts,'economic_discovery_root',None),recent_workspaces=recent)
        except (SourceShareError,OSError,ValueError,TypeError,KeyError) as exc:
            delivery={"status":"UNAVAILABLE","error_type":type(exc).__name__}
    # A delivery problem must be visible without rolling back source collection
    # or invoking another fetch. The previous completed delivery stays readable.
    delivery_failed=delivery is not None and (delivery['status']=='UNAVAILABLE'
                       or bool(delivery.get('unavailable_scopes')))
    return (4 if failures or delivery_failed else 0), {
        **({"economic_discovery":discovery} if discovery is not None else {}),
        **({"era_daily_connection":integration} if integration is not None else {}),
        **({"material_delivery":delivery} if delivery is not None else {}),
        "status": "APPROVED_RESEARCH_FEED_TICK_PARTIAL" if failures or delivery_failed
                  else "APPROVED_RESEARCH_FEED_TICK_COMPLETE",
        "mode": operation[2:].upper().replace("-", "_"),
        "sources_checked": len(FEEDS), "sources_failed": failures,
        "providers": rows,
        "new_articles": sum(r.get("new_articles", 0) for r in rows),
        "economic_changes": sum(r.get("economic_changes", 0) for r in rows),
        "ai_calls": 0, "stored_article_bodies": 0,
        "era_api_calls": 0,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        code, result = execute(parser().parse_args(argv))
    except (SourceShareError, OSError, ValueError, TypeError) as exc:
        code, result = 4, {"status": "APPROVED_RESEARCH_FEEDS_INPUT_UNAVAILABLE",
                           "error_type": type(exc).__name__,
                           "ai_calls": 0, "stored_article_bodies": 0}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
