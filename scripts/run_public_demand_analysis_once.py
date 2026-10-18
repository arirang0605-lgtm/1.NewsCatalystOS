"""Connect short public-news reading analyses to exact saved events; no source text."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from newscatalystos.discovery_watch import read_discovery
from newscatalystos.public_demand_analysis import publish_notes,sources_from_outlook
from newscatalystos.official_relation_intake import _private_input
from newscatalystos.source_share import _json,SourceShareError


def execute(root,notes_file):
    data=_json(_private_input(Path(notes_file),32768),'public reading analysis input')
    now=datetime.now(timezone.utc)
    view=read_discovery(root,as_of=now,now=now,include_common_causes=True)
    sources=sources_from_outlook(view['theme_outlook'])
    return publish_notes(root,data,sources,now=now)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--discovery-root',required=True,type=Path)
    p.add_argument('--notes-file',required=True,type=Path)
    p.add_argument('--once',required=True,action='store_true')
    args=p.parse_args(argv)
    try:result=execute(args.discovery_root,args.notes_file);code=0
    except (SourceShareError,OSError,ValueError,KeyError,TypeError) as exc:
        code=4;result={'status':'ANALYSIS_INPUT_UNAVAILABLE','error_type':type(exc).__name__}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return code
if __name__=='__main__':raise SystemExit(main())
