"""6_2 cache key includes version, prompt, model and metadata digest."""
from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from newscatalystos.analysis_cache import cache_analysis_once,get_cached_analysis
from newscatalystos.ai_provider import run_ai_analysis
from newscatalystos.source_share import SourceShareError
from test_ai_provider import config,request,stub
from test_new_source_adapter import NOW


def result():
    return run_ai_analysis(config(),request(),transport=stub,now=NOW)


def db(tmp_path):
    return tmp_path/"private"/"analysis_cache.sqlite3"


def get(path,**changed):
    params=dict(
        event_sha256="a"*64,source_version_sha256="b"*64,
        metadata_sha256="c"*64,provider="OPENAI",
        model="synthetic-model-not-live",prompt_version="prompt-v1",
        decision_at=NOW,now=NOW,
    )
    params.update(changed)
    return get_cached_analysis(path,**params)


def test_replay_same_event_same_model_cached_once(tmp_path):
    path=db(tmp_path)
    original=result()
    stored=cache_analysis_once(
        path,original,source_version_sha256="b"*64,
        metadata_sha256="c"*64,recorded_at=NOW,
    )
    retried=cache_analysis_once(
        path,original,source_version_sha256="b"*64,
        metadata_sha256="c"*64,recorded_at=NOW,
    )
    assert retried.cache_key==stored.cache_key
    assert retried.recorded_at==stored.recorded_at
    assert get(path).result==original
    assert path.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM analysis_cache").fetchone()[0]==1


def test_revision_or_prompt_change_requires_new_analysis(tmp_path):
    path=db(tmp_path)
    cache_analysis_once(path,result(),source_version_sha256="b"*64,
                        metadata_sha256="c"*64,recorded_at=NOW)
    assert get(path,source_version_sha256="d"*64) is None
    assert get(path,metadata_sha256="d"*64) is None
    assert get(path,prompt_version="prompt-v2") is None
    assert get(path,provider="GEMINI") is None


def test_future_cache_unavailable_for_pit_replay(tmp_path):
    path=db(tmp_path)
    later=NOW+timedelta(seconds=5)
    cache_analysis_once(path,result(),source_version_sha256="b"*64,
                        metadata_sha256="c"*64,recorded_at=later)
    assert get(path,now=later) is None
    assert get(path,decision_at=later,now=later) is not None


def test_changed_result_cannot_rewrite_cached_evidence(tmp_path):
    path=db(tmp_path)
    existing=result()
    cache_analysis_once(path,existing,source_version_sha256="b"*64,
                        metadata_sha256="c"*64,recorded_at=NOW)
    with pytest.raises(SourceShareError,match="conflict"):
        cache_analysis_once(path,replace(existing,summary="secret new speculative number"),
                            source_version_sha256="b"*64,
                            metadata_sha256="c"*64,recorded_at=NOW)


def test_corrupted_cached_blob_never_used(tmp_path):
    path=db(tmp_path)
    cache_analysis_once(path,result(),source_version_sha256="b"*64,
                        metadata_sha256="c"*64,recorded_at=NOW)
    with sqlite3.connect(path) as con:
        con.execute("UPDATE analysis_cache SET payload='\u007b\u007d'")
    with pytest.raises(SourceShareError,match="SHA mismatch"):
        get(path)


def test_uncertified_or_oversized_results_not_persisted(tmp_path):
    path=db(tmp_path)
    with pytest.raises(SourceShareError):
        cache_analysis_once(path,replace(result(),is_verified_market_fact=True),
                            source_version_sha256="b"*64,
                            metadata_sha256="c"*64,recorded_at=NOW)
