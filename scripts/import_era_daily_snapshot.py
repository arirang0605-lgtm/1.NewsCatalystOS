"""Import a completed EraLeader daily publication into NewsCatalystOS only."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from newscatalystos.era_daily_assessment import refresh_daily
from newscatalystos.source_share import SourceShareError


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--check-only',action='store_true')
    opts=p.parse_args(argv)
    try:
        result=refresh_daily(opts.config,opts.output_root,check_only=opts.check_only)
        code=0
    except (SourceShareError,ValueError,KeyError,TypeError,OSError) as exc:
        result={'status':'UNAVAILABLE','error_type':type(exc).__name__};code=4
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return code

if __name__=='__main__':raise SystemExit(main())
