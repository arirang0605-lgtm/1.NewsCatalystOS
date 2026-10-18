"""Exact evidence reads its own source receipts and retains all identity guards."""
from dataclasses import replace
import pytest
from newscatalystos.source_share import SourceShareError
from newscatalystos.provider_registry import ProviderRegistry
from newscatalystos.federated_news_search import search_completed_workspaces
from scripts.run_feed_triage import _registry
from test_federated_news_search import sample,search,write_registry,fingerprint


def exact(scopes,row,**kw):
    return search_completed_workspaces(tuple(scopes),row['headline'][:80],registry_reader=_registry,
        exact_identity=tuple(row[k] for k in ('provider_id','event_id','title_sha256')),
        exact_source_only=True,limit=1,**kw)


def test_exact_source_skips_unrelated_receipts_but_keeps_same_verified_article(sample,monkeypatch,tmp_path):
    import newscatalystos.federated_news_search as module
    scopes,_,_,_=sample
    row=next(r for r in search(scopes)['results'] if r['search_scope']=='motir')
    original=module.read_completed_title_snapshots;calls=[]
    def read(root,*a,**kw):
        calls.append(root);return original(root,*a,**kw)
    monkeypatch.setattr(module,'read_completed_title_snapshots',read)
    before=fingerprint(tmp_path);data=exact(scopes,row)
    assert calls==[scopes[1].inbox_root]
    assert data['coverage_scope']=='EXACT_PROVIDER_WORKSPACE' and data['coverage_complete']
    assert [{k:v for k,v in r.items() if k!='search_verified_at'} for r in data['results']]==[
        {k:v for k,v in row.items() if k!='search_verified_at'}]
    assert fingerprint(tmp_path)==before
    # A new request revalidates, so corruption cannot be hidden by prior success.
    target=next(scopes[1].inbox_root.parent.glob('results/*/triage.json'))
    target.write_bytes(target.read_bytes()+b' ')
    assert exact(scopes,row)['results']==[]


def test_exact_source_still_rejects_duplicate_provider_ownership(sample,monkeypatch):
    scopes,regs,_,_=sample;row=search(scopes)['results'][0]
    write_registry(scopes[1].registry_path,regs[0])
    def forbidden(*a,**kw):raise AssertionError('data read before ownership check')
    monkeypatch.setattr('newscatalystos.federated_news_search.read_completed_title_snapshots',forbidden)
    with pytest.raises(SourceShareError,match='multiple'):exact(scopes,row)


def test_exact_source_rechecks_revocation_and_pit(sample):
    from test_new_source_adapter import NOW
    scopes,regs,_,_=sample;row=next(r for r in search(scopes)['results'] if r['search_scope']=='motir')
    assert exact(scopes,row,now=NOW)['results']==[]
    write_registry(scopes[1].registry_path,ProviderRegistry(tuple(replace(p,approved=False) for p in regs[1].providers)))
    with pytest.raises(SourceShareError,match='unapproved'):exact(scopes,row)


@pytest.mark.parametrize('flag,identity',[(True,None),('yes',None)])
def test_exact_source_mode_needs_valid_exact_identity(sample,flag,identity):
    with pytest.raises(SourceShareError):
        search_completed_workspaces(tuple(sample[0]),'반도체',registry_reader=_registry,
            exact_identity=identity,exact_source_only=flag)
