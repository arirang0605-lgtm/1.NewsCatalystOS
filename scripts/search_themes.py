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
    args=p.parse_args(argv)
    now=datetime.now(timezone.utc)
    at=_when(args.as_of,'as of') if args.as_of else now
    themes=ThemeStore(args.root).search(as_of=at,query=args.query,now=now,
        since=_when(args.since,'period start') if args.since else None,activity=args.activity)
    payload=build_theme_bundle(themes,decision_at=at,now=now,
                               include_company_candidates=args.company_candidates)
    digest=sha256(payload).hexdigest()
    if args.export_root:
        path=_private_root(args.export_root)/('theme_delivery_'+digest+'.json')
        try:_write_new(path,payload)
        except FileExistsError:
            if _read_once(path,2_000_000)!=payload:raise ValueError('theme publication conflict')
        print(json.dumps({'themes':len(themes),'sha256':digest,'path':str(path)},ensure_ascii=False))
    else:print(payload.decode(),end='')
    return 0


if __name__=='__main__':raise SystemExit(main())
