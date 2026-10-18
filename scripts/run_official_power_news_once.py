"""One official public title listing -> existing event-first discovery.

Uses existing rate ledger/checkpoint/ACK/analysis. Stores titles and links only.
No article-body download, paid AI, scheduler install or EraLeader access.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from newscatalystos.provider_registry import SCHEMA, parse_provider_registry
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_triage import parser as triage_parser, evaluate as triage
from scripts.run_economic_discovery import execute as discover

SOURCE='hd-electric-official-news-metadata'
ENDPOINT='https://www.hd-hyundaielectric.com/elect/ko/PR/newsList.jsp?paging.pageNo=2'


def prepare(workspace, at):
    root=Path(workspace)
    if (not root.is_absolute() or root.resolve()!=root or root.is_symlink()
            or any(p.casefold()=='eraleader' for p in root.parts)):
        raise SourceShareError('isolated absolute News workspace required')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.stat().st_mode & 0o077:raise SourceShareError('owner-only News workspace required')
    provider_dir=root/'providers';provider_dir.mkdir(mode=0o700,exist_ok=True)
    registry=provider_dir/'authorized_sources.json'
    if not registry.exists():
        # This source is a public official title/URL list selected under the
        # user's real-news connection instruction. No full-text license claim.
        data={'schema':SCHEMA,'providers':[{
            'provider_id':SOURCE,'kind':'COMPANY_IR','method':'HTML_METADATA',
            'endpoint':ENDPOINT,'grant':'OFFICIAL_TERMS_REVIEWED',
            'rights_reference':'https://www.hd-hyundaielectric.com/elect/ko/PR/newsList.jsp',
            'reviewed_at':at.isoformat(),'expires_at':None,'approved':True,
            'allow_full_text_storage':False,'hourly_limit':1}]}
        raw=json.dumps(data,ensure_ascii=False,sort_keys=True).encode()
        parse_provider_registry(raw,now=at)
        with registry.open('xb') as f:f.write(raw)
        registry.chmod(0o600)
    from scripts.run_feed_triage import _registry
    selected=_registry(registry).active(SOURCE,at=at)
    if selected.endpoint!=ENDPOINT or selected.method!='HTML_METADATA' or selected.allow_full_text_storage:
        raise SourceShareError('existing official metadata configuration differs')
    return root,registry


def execute(workspace, discovery_root):
    at=datetime.now(timezone.utc)
    root,registry=prepare(workspace,at)
    opts=triage_parser().parse_args([
        '--registry',str(registry),'--provider-id',SOURCE,
        '--state',str(root/'state/incremental_feeds.sqlite3'),
        '--dedup-state',str(root/'state/triage_exact_index.sqlite3'),
        '--inbox-root',str(root/'inbox/feed_triage'),
        '--output-root',str(root/'triage')])
    code,receipt=triage(opts)
    if code!=0:return code,{'status':'SOURCE_UNAVAILABLE','ingest':receipt}
    result=discover(discovery_root,[('power',registry,opts.state,opts.inbox_root)])
    return (0 if result['status']=='READY' else 4),{
        'status':result['status'],'ingest':receipt,'discovery':result,
        'stored_article_bodies':0,'paid_ai_calls':0,'industry_selected_before_analysis':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--discovery-root',type=Path,required=True)
    p.add_argument('--once',action='store_true',required=True)
    args=p.parse_args(argv)
    try:code,result=execute(args.workspace,args.discovery_root)
    except (SourceShareError,OSError,ValueError,KeyError,TypeError) as exc:
        code,result=4,{'status':'UNAVAILABLE','error_type':type(exc).__name__}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return code
if __name__=='__main__':raise SystemExit(main())
