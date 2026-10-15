"""Connect an existing completed supply graph to matching theme source events."""
import argparse
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(PROJECT/'src'))

from newscatalystos.theme_emergence import ThemeStore


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder',type=Path,required=True)
    p.add_argument('--out-root',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--graph-version',choices=('v1','v2'),default='v2')
    p.add_argument('--root',type=Path,default=Path.home()/'Library/Application Support/NewsCatalystOS/document_analysis/theme_history')
    args=p.parse_args(argv)
    rows=ThemeStore(args.root).ingest_supply_graph(args.folder,args.out_root,args.expected_sha256,
                                                 graph_version=args.graph_version)
    print(json.dumps({'status':'SUPPLY_GRAPH_REGISTERED','theme_versions_created':len(rows),
        'theme_ids':[r['theme_id'] for r in rows],'ai_calls':0,'network_calls':0}))
    return 0


if __name__=='__main__':raise SystemExit(main())
