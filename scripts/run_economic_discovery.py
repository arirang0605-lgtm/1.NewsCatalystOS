"""One pass over existing approved news, without selecting an industry or fetching.

Called by the current research runner or directly. Outputs are News-owned,
separate from semiconductor/power profiles. A missing source stays local.
"""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from scripts.run_feed_triage import _registry
from scripts.run_feed_analysis import parser as analysis_parser,evaluate
from newscatalystos.source_share import SourceShareError


def execute(root,sources,*,now=None,dry_run=False):
    root=Path(root);at=now or datetime.now(timezone.utc)
    if not root.is_absolute() or root.resolve()!=root or any('eraleader' in p.casefold() for p in root.parts):
        raise SourceShareError('separate News discovery root required')
    outcomes=[]
    for scope,registry_path,state_path,inbox_path in sources:
        try:
            registry=_registry(registry_path)
            providers=registry.approved_ids(at=at)
        except (SourceShareError,OSError,ValueError,KeyError,TypeError) as e:
            outcomes.append({'scope':scope,'status':'SOURCE_UNAVAILABLE','error_type':type(e).__name__});continue
        for provider in providers:
            if dry_run:
                outcomes.append({'scope':scope,'provider_id':provider,'status':'DRY_RUN'});continue
            folder='d_'+sha256((scope+':'+provider).encode()).hexdigest()[:16]
            # Keep the existing 100-title report bound, but finish the same
            # approved source snapshot. Older stored news used to remain forever
            # behind the newest 100 even when it contained an unmapped industry.
            offset=0;expected=None
            outcome={'scope':scope,'provider_id':provider,'titles':0,'events':0,
                'theme_versions_created':0,'unclassified_events':0,'analysis_batches':0,
                'has_more_older_titles':False,'source_fetch_calls':0,'paid_ai_calls':0}
            while True:
                opts=analysis_parser().parse_args(['--registry',str(registry_path),'--state',str(state_path),
                    '--inbox-root',str(inbox_path),'--provider-id',provider,'--discover-economy','--limit','100',
                    '--discovery-offset',str(offset),'--analysis-root',str(root/'feed_analysis'/folder/'core'),
                    '--theme-root',str(root/'theme_history')])
                code,data=evaluate(opts,now=at)
                rows=data.get('results',[]);total=data.get('matched_versions',0)
                more=data.get('has_more_results',False)
                outcome.update(status=data.get('status'),exit_code=code,has_more_older_titles=more)
                if code!=0:
                    outcome['has_more_older_titles']=True
                    break
                if (expected is not None and total!=expected) or (more and not rows):
                    outcome.update(status='SOURCE_SNAPSHOT_CHANGED',exit_code=4,has_more_older_titles=True)
                    break
                expected=total
                outcome['analysis_batches']+=1
                outcome['titles']+=len(rows)
                outcome['events']+=data.get('economic_changes_count',0)
                outcome['theme_versions_created']+=data.get('theme_versions_created',0)
                outcome['unclassified_events']+=sum(not c['industry_tags'] for r in rows for c in r.get('economic_changes',[]))
                outcome['source_fetch_calls']+=data.get('source_fetch_calls',0)
                if not more:break
                offset+=len(rows)
            outcomes.append(outcome)
    bad=sum(r.get('exit_code',0)!=0 or r['status']=='SOURCE_UNAVAILABLE' for r in outcomes)
    return {'status':'PARTIAL' if bad else 'READY','sources_failed':bad,'sources':outcomes,
            'analyzed_titles':sum(r.get('titles',0) for r in outcomes),'economic_events':sum(r.get('events',0) for r in outcomes),
            'unclassified_events':sum(r.get('unclassified_events',0) for r in outcomes),
            'source_fetch_calls':0,'paid_ai_calls':0,'industry_selected':None}


def source_roots(base,workspaces):
    base,workspaces=Path(base),Path(workspaces)
    rows=[('core',base/'providers/authorized_sources.json',base/'state/incremental_feeds.sqlite3',base/'inbox/feed_triage'),
          ('motir',base/'providers/motir_authorized_sources.json',base/'state/motir_incremental_feeds.sqlite3',base/'inbox/motir_feed_triage')]
    for scope in ('msit','company','nist'):
        p=workspaces/(scope+'_live_dev')
        rows.append((scope,p/'providers/authorized_sources.json',p/'state/incremental_feeds.sqlite3',p/'inbox/feed_triage'))
    return rows


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--source-base',type=Path,required=True)
    p.add_argument('--workspaces-root',type=Path,required=True)
    p.add_argument('--dry-run',action='store_true')
    args=p.parse_args(argv)
    try:
        result=execute(args.root,source_roots(args.source_base,args.workspaces_root),dry_run=args.dry_run)
    except (SourceShareError,OSError,ValueError,TypeError) as e:
        result={'status':'UNAVAILABLE','error_type':type(e).__name__}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if result['status']=='READY' else 4
if __name__=='__main__':raise SystemExit(main())
