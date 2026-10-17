"""Search stored themes as-of and optionally export pinned read-only JSON."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sys

PROJECT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(PROJECT/'src'))
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.standard_delivery import build_theme_bundle
from newscatalystos.evidence_archive import _private_root, _write_new, _read_once
from newscatalystos.source_share import _when


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path.home()/'Library/Application Support/NewsCatalystOS/document_analysis/theme_history')
    p.add_argument('--query',default='')
    p.add_argument('--as-of')
    p.add_argument('--since',help='inclusive availability start, ISO timestamp with zone')
    p.add_argument('--activity',choices=['all','changed','new','updated'],default='all')
    p.add_argument('--export-root',type=Path)
    p.add_argument('--company-candidates',action='store_true',help='include source-grounded company reasons in v3 delivery')
    p.add_argument('--with-financials',action='store_true',help='return optional EraLeader financial context as company_research.v1')
    p.add_argument('--assessment-root',type=Path,default=Path.home()/'Library/Application Support/NewsCatalystOS/document_analysis/era_assessments')
    p.add_argument('--identity-root',type=Path,help='candidate identity receipts; defaults next to assessment cache')
    p.add_argument('--comparison',action='store_true',help='pinned read-only cross-product/period query, separate from standard v3')
    p.add_argument('--changes',action='store_true',help='compare theme evidence before --since and at --as-of')
    p.add_argument('--materials',action='store_true',help='include news material novelty and conditional company impact for the independent selector')
    args=p.parse_args(argv)
    if args.materials and (args.changes or args.comparison or args.with_financials):
        p.error('--materials is an optional standard news delivery extension, not a financial report')
    if args.comparison and (args.changes or args.with_financials or args.company_candidates):
        p.error('--comparison cannot be combined with standard, financial or changes modes')
    if args.changes and (not args.since or args.with_financials or args.company_candidates):
        p.error('--changes requires --since and cannot be combined with company output modes')
    now=datetime.now(timezone.utc)
    at=_when(args.as_of,'as of') if args.as_of else now
    if args.comparison:
        from newscatalystos.comparison_export import query_comparison_export,publish_comparison_export
        payload=query_comparison_export(ThemeStore(args.root),as_of=at,
            since=_when(args.since,'since') if args.since else None,activity=args.activity,query=args.query,now=now,
            identity_root=args.identity_root or args.assessment_root.parent/'theme_company_identity')
        if args.export_root:
            print(json.dumps(publish_comparison_export(payload,args.export_root,now=now),ensure_ascii=False))
        else:print(payload.decode(),end='')
        return 0
    if args.changes:
        from newscatalystos.theme_changes import compare_themes
        from newscatalystos.theme_emergence import _bytes
        comparison=compare_themes(ThemeStore(args.root),since=_when(args.since,'period start'),
            as_of=at,query=args.query,activity=args.activity,now=now)
        themes=comparison['ThemeChanges'];payload=_bytes(comparison)
    else:
        themes=ThemeStore(args.root).search(as_of=at,query='' if args.with_financials else args.query,now=now,
            since=_when(args.since,'period start') if args.since else None,activity=args.activity)
        if args.materials:
            from newscatalystos.catalyst_material import materials_for_store,attach_material,default_since
            materials=materials_for_store(ThemeStore(args.root),as_of=at,now=now,
                since=_when(args.since,'material since') if args.since else default_since(at))
            themes=attach_material(themes,materials)
        payload=build_theme_bundle(themes,decision_at=at,now=now,
                                   include_company_candidates=args.company_candidates or args.with_financials)
    if args.with_financials:
        from newscatalystos.era_company_assessment import enrich_candidates, canonical
        from newscatalystos.theme_company_identity import filter_research
        research=enrich_candidates(json.loads(payload)['CompanyCandidates'],args.assessment_root,as_of=at,now=now,
                                   identity_root=args.identity_root or args.assessment_root.parent/'theme_company_identity')
        filter_research(research,themes,args.query)
        payload=canonical(research)+b'\n'
    digest=sha256(payload).hexdigest()
    if args.export_root:
        prefix='theme_changes_' if args.changes else 'company_research_' if args.with_financials else 'theme_delivery_'
        path=_private_root(args.export_root)/(prefix+digest+'.json')
        try:_write_new(path,payload)
        except FileExistsError:
            if _read_once(path,2_000_000)!=payload:raise ValueError('theme publication conflict')
        print(json.dumps({'themes':len(themes),'sha256':digest,'path':str(path)},ensure_ascii=False))
    else:print(payload.decode(),end='')
    return 0


if __name__=='__main__':raise SystemExit(main())
