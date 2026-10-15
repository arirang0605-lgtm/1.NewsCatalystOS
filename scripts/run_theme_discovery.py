"""Consume pinned normalized economic events into the existing private theme store.

Upstream adapters supply explicit original claim identity and source evidence.
This does not infer origin independence from syndicated article URLs.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

PROJECT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(PROJECT/'src'))
from newscatalystos.evidence_archive import _read_once
from newscatalystos.source_share import SourceShareError, _json, _must_sha
from newscatalystos.theme_emergence import ThemeStore


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events-file',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--root',type=Path,default=Path.home()/'Library/Application Support/NewsCatalystOS/document_analysis/theme_history')
    args=p.parse_args(argv)
    raw=_read_once(args.events_file,2_000_000)
    if sha256(raw).hexdigest()!=_must_sha(args.expected_sha256,'economic events pin'):
        raise SourceShareError('economic events SHA mismatch')
    packet=_json(raw,'economic events')
    if set(packet)!={'schema','observations'} or packet['schema']!='newscatalyst.economic_observations.v1':
        raise SourceShareError('normalized economic observation packet required')
    themes=ThemeStore(args.root).ingest(packet['observations'])
    print(json.dumps({'status':'THEME_DISCOVERY_READY','theme_versions_created':len(themes),
                      'theme_ids':[row['theme_id'] for row in themes],'ai_calls':0},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
