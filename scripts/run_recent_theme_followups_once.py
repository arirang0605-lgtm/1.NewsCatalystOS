"""Connect recent completed title metadata to earlier public-source reading notes."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from newscatalystos.discovery_watch import read_discovery
from newscatalystos.public_demand_analysis import read_notes,sources_from_outlook
from newscatalystos.recent_theme_followups import publish_followups,metadata_resolver
from newscatalystos.federated_news_search import TitleSearchWorkspace
from newscatalystos.official_relation_intake import _private_input
from newscatalystos.source_share import _json,SourceShareError

def workspace(text):
    scope,path=text.split('=',1);root=Path(path)
    return TitleSearchWorkspace(scope,root/'providers/authorized_sources.json',
        root/'state/incremental_feeds.sqlite3',root/'inbox/feed_triage')

def execute(root,notes_file,workspaces):
    data=_json(_private_input(Path(notes_file),32768),'recent reading input')
    now=datetime.now(timezone.utc)
    view=read_discovery(root,as_of=now,now=now,include_common_causes=True)
    notes=read_notes(root,sources_from_outlook(view['theme_outlook']),as_of=now,now=now)
    return publish_followups(root,data,{n['note_id']:n for n in notes},
        metadata_resolver(tuple(workspaces),now=now),now=now)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--discovery-root',required=True,type=Path)
    p.add_argument('--notes-file',required=True,type=Path)
    p.add_argument('--source-workspace',required=True,action='append',type=workspace)
    p.add_argument('--once',required=True,action='store_true')
    a=p.parse_args(argv)
    try:result=execute(a.discovery_root,a.notes_file,a.source_workspace);code=0
    except (SourceShareError,OSError,ValueError,KeyError,TypeError) as exc:
        result={'status':'FOLLOWUP_INPUT_UNAVAILABLE','error_type':type(exc).__name__};code=4
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return code
if __name__=='__main__':raise SystemExit(main())
