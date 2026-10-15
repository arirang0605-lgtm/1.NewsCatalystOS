"""Synthetic exact-name identity proofs; no official API or paid inference."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta, datetime, timezone
from hashlib import sha256
import json
import threading
from urllib.request import urlopen

import pytest

from newscatalystos.theme_company_identity import ensure_identities, resolve_candidates, resolve_stored_candidates
from newscatalystos.era_company_assessment import import_watch, enrich_candidates
from newscatalystos.article_company_identity import encoded
from newscatalystos.theme_emergence import ThemeStore
from test_article_company_identity import context
from test_era_company_assessment import candidates, source
from test_theme_emergence import T, event
from test_feed_company_identity import directory


def test_exact_name_to_financial_with_first_availability_and_no_theme_write(tmp_path):
    cs=candidates(tmp_path,'가상기업');original=deepcopy(cs)
    db=tmp_path/'themes/themes.sqlite3';before=db.read_bytes()
    at=T+timedelta(hours=1);identity=tmp_path/'identities'
    rows={'a':context(at,'가상기업','12345678')}
    assert ensure_identities(cs,rows,identity,at=at)=={'created':1,'cache_hits':0}
    receipt=next(identity.glob('*.json'));raw=receipt.read_bytes()
    rows['a']=replace(rows['a'],local_context_verified_at=at+timedelta(hours=1))
    assert ensure_identities(cs,rows,identity,at=at+timedelta(hours=1))=={'created':0,'cache_hits':1}
    assert receipt.read_bytes()==raw
    root,path,pin=source(tmp_path);cache=tmp_path/'assessments';import_watch(root,path,pin,cache,now=T)
    old=enrich_candidates(cs,cache,as_of=T,now=at,identity_root=identity)['CompanyCandidates'][0]
    assert old['identity_context']['status']=='NOT_RESOLVED_AS_OF'
    assert old['financial_assessment']['status']=='IDENTITY_UNRESOLVED'
    new=enrich_candidates(cs,cache,as_of=at,now=at,identity_root=identity)['CompanyCandidates'][0]
    assert new['entity_id']=='가상기업' and new['resolved_entity_id']=='DART_CORP:12345678'
    assert new['financial_assessment']['status']=='AVAILABLE'
    assert new['identity_context']['matches'][0]['source_receipt_sha256']=='a'*64
    assert new['candidate_id']==cs[0]['candidate_id'] and new['investment_merit']=='NOT_ASSESSED'
    assert cs==original and db.read_bytes()==before


def test_directory_change_creates_later_resolution_not_retroactive(tmp_path):
    cs=candidates(tmp_path,'가상기업');identity=tmp_path/'identities'
    at=T+timedelta(hours=1)
    ensure_identities(cs,{'a':context(T,'다른기업')},identity,at=T)
    ensure_identities(cs,{'a':context(at,'가상기업','12345678')},identity,at=at)
    assert len(list(identity.glob('*.json')))==2
    assert resolve_candidates(cs,identity,as_of=T,now=at)[0][0]['identity_context']['status']=='NOT_IN_SNAPSHOT'
    assert resolve_candidates(cs,identity,as_of=at,now=at)[0][0]['resolved_entity_id']=='DART_CORP:12345678'
    later=deepcopy(cs);later[0]['theme_snapshot_sha256']='f'*64
    assert resolve_candidates(later,identity,as_of=at,now=at)[0][0]['identity_context']['status']=='NOT_RESOLVED_AS_OF'


@pytest.mark.parametrize('name,rows,status',[
    ('가상기업서비스',{'a':context(T,'가상기업')},'NOT_IN_SNAPSHOT'),
    ('가상기업',{'a':context(T,'가상기업'),'b':context(T,'가상기업','00000002')},'AMBIGUOUS'),
])
def test_no_substring_or_ambiguous_guess(tmp_path,name,rows,status):
    cs=candidates(tmp_path,name);root=tmp_path/'identities'
    ensure_identities(cs,rows,root,at=T)
    c=resolve_candidates(cs,root,as_of=T,now=T)[0][0]
    assert c['identity_context']['status']==status and 'resolved_entity_id' not in c


@pytest.mark.parametrize('fault',['json','proof'])
def test_invalid_optional_receipt_keeps_candidate_without_false_id(tmp_path,fault):
    cs=candidates(tmp_path,'가상기업');root=tmp_path/'identities'
    ensure_identities(cs,{'a':context(T,'가상기업')},root,at=T)
    path=next(root.glob('*.json'))
    if fault=='json':path.write_text('{}')
    else:
        data=json.loads(path.read_bytes());data['report']['matches'][0]['original_sha256']='c'*64
        data['sha256']=sha256(encoded(data['report'])).hexdigest();path.write_bytes(encoded(data))
    cs[0]['resolved_entity_id']='DART_CORP:00000001'
    result=enrich_candidates(cs,tmp_path/'missing',as_of=T,now=T,identity_root=root)
    assert result['identity_receipts_skipped']==1
    assert result['CompanyCandidates'][0]['financial_assessment']['status']=='IDENTITY_UNRESOLVED'
    assert 'resolved_entity_id' not in result['CompanyCandidates'][0]


def test_existing_id_needs_no_directory_or_receipt(tmp_path,monkeypatch):
    cs=candidates(tmp_path)
    monkeypatch.setattr('newscatalystos.feed_company_identity.load_directory',lambda *a,**k:pytest.fail('unnecessary load'))
    assert resolve_stored_candidates(tmp_path/'themes',tmp_path/'absent',tmp_path/'identities',now=T)=={'created':0,'cache_hits':0}
    assert resolve_candidates(cs,tmp_path/'identities',as_of=T,now=T)[0][0]['identity_context']['status']=='ALREADY_IDENTIFIED'


def test_cli_http_search_by_new_official_id_and_legacy_history(tmp_path,monkeypatch,capsys):
    from scripts.resolve_theme_companies import main as resolve_main
    from scripts.search_themes import main as search_main
    from scripts.open_research_dashboard import DashboardServer
    docs=tmp_path/'docs';store=ThemeStore(docs/'theme_history');store.ingest([event(company='가상기업')])
    at=datetime.now(timezone.utc)
    config=directory(tmp_path,monkeypatch,{'a':context(at,'가상기업','12345678')})
    identity=docs/'theme_company_identity';db=store.root/'themes.sqlite3';before=db.read_bytes()
    assert resolve_main(['--theme-root',str(store.root),'--identity-config',str(config),'--output-root',str(identity)])==0
    assert json.loads(capsys.readouterr().out)['created']==1
    root,path,pin=source(tmp_path);cache=docs/'era_assessments';import_watch(root,path,pin,cache)
    assert search_main(['--root',str(store.root),'--with-financials','--assessment-root',str(cache),'--query','DART_CORP:12345678'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['CompanyCandidates'][0]['financial_assessment']['status']=='AVAILABLE'
    server=DashboardServer(0,tmp_path/'reports',tmp_path/'notes',docs)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}'
        with urlopen(base+'/api/company-research?q=DART_CORP:12345678') as response:r=json.load(response)
        assert r['CompanyCandidates'][0]['resolved_entity_id']=='DART_CORP:12345678'
        with urlopen(base+'/api/company-research?q=unrelated') as response:assert json.load(response)['CompanyCandidates']==[]
        with urlopen(base+'/api/themes?company_candidates=1') as response:legacy=json.load(response)
        assert 'identity_context' not in legacy['CompanyCandidates'][0]
        with urlopen(base+'/api/period') as response:period=json.load(response)
        assert period['company_candidates'][0]['identity_context']['status']=='MATCHED'
    finally:server.shutdown();server.server_close();worker.join(2)
    assert db.read_bytes()==before


def test_scheduled_analysis_resolves_existing_candidates_without_new_news(tmp_path,monkeypatch):
    from scripts import run_feed_analysis
    from test_feed_analysis import setup
    from test_scheduled_feed_analysis import opts, no_call
    news,*_=setup(tmp_path,'새빛공업, HBM 공급계약 체결')
    work=tmp_path/'analysis/core';work.mkdir(parents=True,mode=0o700)
    params=opts(news,work,operation='--replay-only')
    at=datetime.now(timezone.utc)+timedelta(minutes=1)
    config=directory(tmp_path,monkeypatch,{'a':context(at,'가상기업','12345678')})
    params.company_identity_config=config
    ThemeStore(work/'theme_history').ingest([event(company='가상기업')],now=at)
    # This calls the normal feed runner argument adapter, including identity config.
    from scripts import run_scheduled_triage
    code,result=run_scheduled_triage.execute(params,
        feed_runner=lambda _: (0,{'status':'NO_PENDING_REPLAY'}),
        analysis_runner=lambda a:run_feed_analysis.evaluate(a,opener=no_call,now=at))
    detail=result['providers'][0]['analysis']
    assert code==0, result
    assert detail['theme_identity_resolution']['created']==1, detail
    assert len(list((work/'theme_company_identity').glob('*.json')))==1
