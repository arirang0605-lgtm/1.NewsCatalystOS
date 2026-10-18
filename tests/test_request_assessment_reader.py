"""Reuse immutable producer assessments within a request, then revalidate."""
from copy import deepcopy
from datetime import timedelta
import pytest
from newscatalystos import era_daily_assessment as era
from newscatalystos.source_share import SourceShareError
from test_era_daily_assessment import source,T
from test_federated_news_search import fingerprint

def test_request_reuse_missing_snapshot_and_next_request_revalidation(tmp_path,monkeypatch):
    root,path,pin,_=source(tmp_path/'first');out=tmp_path/'news'
    at=T+timedelta(hours=1);era.import_daily(root,path,pin,out,now=at)
    real=era.read_latest;calls=[]
    def read(*args,**kwargs):
        calls.append(kwargs['as_of']);return real(*args,**kwargs)
    monkeypatch.setattr(era,'read_latest',read)
    reader=era.request_assessment_reader(out,now=at)
    assert reader(T)==(None,0) and reader(T)==(None,0)
    original=reader(at)
    rows=[{'entity_id':'KRX_STOCK:000660','decision_at':T.isoformat()}]
    joined=era.enrich_daily(rows,out,as_of=at,now=at,snapshot_reader=reader)
    assert joined[0]['era_daily_assessment']['status']=='AVAILABLE'
    joined[0]['era_daily_assessment']['value']['name']='caller mutation'
    assert era.assessment_for('KRX_STOCK:000660',reader(at)[0])['value']['name']=='가상전자'
    assert calls==[T,at]
    receipt=next(out.glob('era_daily_*.json'));receipt.write_bytes(receipt.read_bytes()+b' ')
    assert reader(at)==original # already validated request, not a persistent cache
    fresh=era.request_assessment_reader(out,now=at)
    assert fresh(at)==(None,1) and calls==[T,at,at]

def test_empty_candidates_do_not_load_receipts(tmp_path):
    def unexpected(at):raise AssertionError('empty candidates loaded financial cache')
    assert era.enrich_daily([],tmp_path,as_of=T,now=T,snapshot_reader=unexpected)==[]

def test_streaming_selection_preserves_order_pit_and_corruption_isolation(tmp_path):
    out=tmp_path/'news';at=T+timedelta(hours=4)
    older,path,pin,_=source(tmp_path/'old',at=T)
    era.import_daily(older,path,pin,out,now=T+timedelta(hours=1))
    newer,path2,pin2,_=source(tmp_path/'new',at=T+timedelta(hours=2))
    era.import_daily(newer,path2,pin2,out,now=T+timedelta(hours=3))
    pins=fingerprint(tmp_path)
    assert era.read_latest(out,as_of=T,now=at)==(None,0)
    assert era.read_latest(out,as_of=T+timedelta(hours=2),now=at)[0][0]['source_sha256']==pin
    assert era.read_latest(out,as_of=at,now=at)[0][0]['source_sha256']==pin2
    assert fingerprint(tmp_path)==pins
    newest=next(out.glob('era_daily_'+pin2+'_*.json'));newest.write_bytes(newest.read_bytes()+b' ')
    selected,errors=era.read_latest(out,as_of=at,now=at)
    assert errors==1 and selected[0]['source_sha256']==pin
    with pytest.raises(SourceShareError):era.request_assessment_reader(out,now=at)(at+timedelta(seconds=1))

def test_period_http_reuses_one_current_and_one_previous_snapshot(tmp_path,monkeypatch):
    import json,threading
    from urllib.request import urlopen
    from test_reading_company_assessment import setup
    server,_,before=setup(tmp_path,monkeypatch,'available')
    selected=(before+timedelta(hours=9)).date().isoformat()
    reader=era.read_latest;calls=[]
    def counted(*args,**kwargs):
        calls.append(kwargs['as_of']);return reader(*args,**kwargs)
    monkeypatch.setattr(era,'read_latest',counted)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/period?view=day&date={selected}') as r:data=json.load(r)
        group=next(g['recent_news_comparison'] for g in data['economic_discovery']['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
        assert group['company_assessment_comparison']['company_results']
        assert len(calls)==len(set(calls))==2
    finally:server.shutdown();server.server_close();worker.join(2)
