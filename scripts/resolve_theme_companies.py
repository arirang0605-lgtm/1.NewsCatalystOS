"""Resolve stored theme names against the existing pinned official directory."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from newscatalystos.theme_company_identity import resolve_stored_candidates


def main(argv=None):
    base=Path.home()/'Library/Application Support/NewsCatalystOS'
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--theme-root',type=Path,default=base/'document_analysis/theme_history')
    p.add_argument('--identity-config',type=Path,default=base/'company_identity.json')
    p.add_argument('--output-root',type=Path,default=base/'document_analysis/theme_company_identity')
    args=p.parse_args(argv)
    print(json.dumps(resolve_stored_candidates(args.theme_root,args.identity_config,args.output_root),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
