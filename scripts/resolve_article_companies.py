"""Read pinned existing filing identities and resolve names in a licensed article."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
PROJECT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PROJECT/'src'),str(PROJECT)]
from scripts.run_feed_triage import _registry
from newscatalystos.official_filing_context import read_pinned_filing_context
from newscatalystos.article_company_identity import prepare_article_identity,publish_article_identity


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('era-root','era-report','independent-anchor','archive-root','registry'):
        p.add_argument('--'+key,type=Path,required=True)
    for key in ('archive-version','receipt-sha256','document-sha256'):p.add_argument('--'+key,required=True)
    p.add_argument('--output-root',type=Path,default=Path.home()/'Library/Application Support/NewsCatalystOS/document_analysis/company_identity')
    args=p.parse_args(argv)
    context=read_pinned_filing_context(args.era_root,args.era_report,args.independent_anchor)
    report=prepare_article_identity(args.archive_root,args.archive_version,args.receipt_sha256,
        args.document_sha256,_registry(args.registry),context)
    path,digest=publish_article_identity(report,args.output_root)
    print(json.dumps({'status':'ARTICLE_COMPANY_IDENTITY_READY','matched':len(report['matches']),
        'unresolved':len(report['unresolved']),'path':str(path),'sha256':digest,
        'ai_calls':0,'network_calls':0},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
