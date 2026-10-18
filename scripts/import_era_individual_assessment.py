"""Import one completed result of Era's existing individual company evaluator."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from newscatalystos.era_individual_assessment import import_individual
from newscatalystos.source_share import SourceShareError

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--era-root',required=True,type=Path)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--sha256',required=True)
    p.add_argument('--output-root',required=True,type=Path)
    p.add_argument('--once',required=True,action='store_true')
    a=p.parse_args(argv)
    try:
        result=import_individual(a.era_root,a.manifest,a.sha256,a.output_root);code=0
    except (SourceShareError,ValueError,KeyError,TypeError,OSError) as exc:
        result={'status':'INDIVIDUAL_ASSESSMENT_UNAVAILABLE','error_type':type(exc).__name__};code=4
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return code
if __name__=='__main__':raise SystemExit(main())
