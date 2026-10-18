"""Import explicitly reviewed public company titles; never pretend to poll HTTP.

Input JSON: {"items":[{"id":<canonical URL>,"title":<literal title>,"url":<same URL>}]}
Only titles/links. Existing PIT ledger, durable checkpoint, triage ACK and common
discovery remain the sole downstream path. No body ingestion or scheduler.
"""
import argparse
from datetime import datetime, timezone
import json,os,tempfile
from hashlib import sha256
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from newscatalystos.provider_registry import SCHEMA, parse_provider_registry
from newscatalystos.official_relation_intake import _private_input
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_triage import _registry, parser as triage_parser, evaluate
from scripts.run_economic_discovery import execute as discover
from newscatalystos.news_search import read_completed_title_snapshots
from newscatalystos.text_normalization import canonicalize_url


def prepare(workspace, provider_id, official_list_url, at):
    root=Path(workspace)
    if (not root.is_absolute() or root.resolve()!=root or root.is_symlink()
            or any(p.casefold()=='eraleader' for p in root.parts)):
        raise SourceShareError('isolated absolute News workspace required')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.stat().st_mode & 0o077:raise SourceShareError('owner-only workspace required')
    folder=root/'providers';folder.mkdir(mode=0o700,exist_ok=True)
    path=folder/'authorized_sources.json'
    # An explicitly supplied manual source may share a scope with other
    # sources. Preserve their grants/endpoints/rate budgets byte-for-value.
    if folder.resolve()!=folder or folder.stat().st_mode & 0o077:
        raise SourceShareError('owner-only providers folder required')
    lock=folder/'.manual-registration.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        os.close(fd)
        config=json.loads(_private_input(path,32768)) if path.exists() else {'schema':SCHEMA,'providers':[]}
        if config['providers']:parse_provider_registry(json.dumps(config).encode(),now=at)
        if not any(p['provider_id']==provider_id for p in config['providers']):
            config['providers'].append({
                'provider_id':provider_id,'kind':'COMPANY_IR','method':'MANUAL_METADATA',
                'endpoint':official_list_url,'grant':'OFFICIAL_TERMS_REVIEWED',
                'rights_reference':official_list_url,'reviewed_at':at.isoformat(),
                'expires_at':None,'approved':True,'allow_full_text_storage':False,'hourly_limit':1})
            raw=json.dumps(config,ensure_ascii=False,sort_keys=True).encode()
            parse_provider_registry(raw,now=at)
            handle,temp=tempfile.mkstemp(prefix='.registry-',dir=folder)
            try:
                with os.fdopen(handle,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                os.replace(temp,path)
            finally:
                if os.path.exists(temp):os.unlink(temp)
    finally:lock.unlink()
    p=_registry(path).active(provider_id,at=at)
    if p.method!='MANUAL_METADATA' or p.endpoint!=official_list_url or p.allow_full_text_storage:
        raise SourceShareError('existing manual metadata configuration differs')
    return root,path


def execute(workspace, discovery_root, *, provider_id, official_list_url, metadata_file, scope):
    # Private bounded JSON only. Bodies/extra fields and foreign domains rejected
    # by the adapter before the source ledger may change.
    payload=_private_input(Path(metadata_file),1024*1024)
    root,registry=prepare(workspace,provider_id,official_list_url,datetime.now(timezone.utc))
    opts=triage_parser().parse_args([
        '--registry',str(registry),'--provider-id',provider_id,
        '--state',str(root/'state/incremental_feeds.sqlite3'),
        '--dedup-state',str(root/'state/triage_exact_index.sqlite3'),
        '--inbox-root',str(root/'inbox/feed_triage'),'--output-root',str(root/'triage')])
    code,receipt=evaluate(opts,manual_metadata=payload)
    if code:return code,{'status':'INPUT_UNAVAILABLE','ingest':receipt,'network_called':False}
    result=analyze_submitted(discovery_root,root,registry,payload,scope,provider_id)
    return (0 if result['status']=='READY' else 4),{
        'status':result['status'],'ingest':receipt,'discovery':result,
        'acquisition_method':'MANUAL_METADATA','network_called':False,
        'stored_article_bodies':0,'paid_ai_calls':0,'industry_selected_before_analysis':False}


def analyze_submitted(discovery_root,root,registry,payload,scope,provider_id):
    state=root/'state/incremental_feeds.sqlite3';inbox=root/'inbox/feed_triage'
    # Analyze only the explicitly submitted saved versions. Reprocessing every
    # old title would publish new report bindings and invalidate earlier notes
    # despite unchanged news. Exact checkpoint/SHA checks still apply.
    desired={(canonicalize_url(i['url']),sha256(i['title'].strip().encode()).hexdigest())
             for i in json.loads(payload)['items']}
    selected=set()
    for ack,document,digest in read_completed_title_snapshots(
            inbox,state,_registry(registry),now=datetime.now(timezone.utc)):
        for item in document['items']:
            if item['provider_id']==provider_id and (item['canonical_url'],item['title_sha256']) in desired:
                selected.add((item['event_id'],item['title_sha256']))
    if len(selected)!=len(desired):raise SourceShareError('submitted metadata not fully checkpointed')
    result=discover(discovery_root,[(scope,registry,state,inbox)],
                    selected_versions={provider_id:sorted(selected)})
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','discovery-root','metadata-file'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('provider-id','official-list-url','scope'):p.add_argument('--'+name,required=True)
    p.add_argument('--once',action='store_true',required=True)
    args=vars(p.parse_args(argv));args.pop('once')
    try:code,result=execute(**args)
    except (SourceShareError,OSError,ValueError,KeyError,TypeError) as exc:
        code,result=4,{'status':'UNAVAILABLE','error_type':type(exc).__name__,'network_called':False}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return code
if __name__=='__main__':raise SystemExit(main())
