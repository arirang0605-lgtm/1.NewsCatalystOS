"""Import an explicitly pinned, completed WATCH publication into private NC storage."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from newscatalystos.era_company_assessment import import_watch


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--era-root',type=Path,required=True)
    p.add_argument('--watch-manifest',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--output-root',type=Path,default=Path.home()/'Library/Application Support/NewsCatalystOS/document_analysis/era_assessments')
    args=p.parse_args(argv)
    print(json.dumps(import_watch(args.era_root,args.watch_manifest,args.expected_sha256,args.output_root),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
