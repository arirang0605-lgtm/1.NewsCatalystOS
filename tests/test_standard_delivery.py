"""6_4 read-only CatalystEvent/BeneficiaryGraph/EventHistory JSON and Parquet."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import json

import pytest

from newscatalystos.standard_delivery import (
    build_standard_bundle,read_standard_bundle,to_parquet_bytes,SCHEMA,
)
from newscatalystos.event_lifecycle import append_lifecycle,lifecycle_as_of
from newscatalystos.catalyst_audit import append_catalyst_audit,audit_as_of
from newscatalystos.source_share import SourceShareError
from test_beneficiary_graph_contract import graph
from test_economic_path import build as impact_analysis
from test_catalyst_audit import new as audit_event
from test_new_source_adapter import NOW


def create(tmp_path):
    beneficiary,profile,impact,edge,candidate=graph()
    economic=impact_analysis()
    assert beneficiary.source_event_sha256==economic.event_sha256
    target=tmp_path/"private"/"lifecycle.sqlite3"
    append_lifecycle(target,"a"*64,"DETECTED","b"*64,NOW,at=NOW)
    history=lifecycle_as_of(target,"a"*64,NOW,now=NOW)
    auditdb=tmp_path/"private"/"audit.sqlite3"
    append_catalyst_audit(auditdb,audit_event(),now=NOW)
    audit=audit_as_of(auditdb,"a"*64,NOW,now=NOW)
    package=build_standard_bundle(
        economic,beneficiary,history,decision_at=NOW,audited=audit,now=NOW
    )
    return package,economic,beneficiary,history,audit


def test_json_contract_contains_three_named_documents(tmp_path):
    package,*_=create(tmp_path)
    data=read_standard_bundle(package.payload,package.payload_sha256,
                              decision_at=NOW,now=NOW)
    assert data["schema"]==SCHEMA
    assert data["verified_beneficiary_count"]==0
    assert data["original_content_included"] is False
    assert {k for k in ("CatalystEvent","BeneficiaryGraph","EventHistory")}<=set(data)
    assert data["CatalystEvent"]["economic_effect_verified"] is False
    assert data["CatalystEvent"]["market_action"] is None
    assert data["EventHistory"]["versions"][0]["state"]=="DETECTED"
    assert len(data["EventHistory"]["audit_shas"])==1
    assert package.payload_sha256==sha256(package.payload).hexdigest()


def test_parquet_round_trip_three_read_only_documents(tmp_path):
    import pyarrow.parquet as pq
    package,*_=create(tmp_path)
    parquet=to_parquet_bytes(package)
    result=pq.read_table(BytesIO(parquet)).to_pydict()
    assert len(result["kind"])==3
    assert set(result["kind"])=={"CatalystEvent","BeneficiaryGraph","EventHistory"}
    assert all(k==SCHEMA for k in result["schema"])
    assert all(x=="a"*64 for x in result["event_sha256"])
    assert all(json.loads(x)["event_sha256"]=="a"*64 for x in result["document_json"])


def test_consumer_cannot_read_earlier_or_with_wrong_pin(tmp_path):
    package,*_=create(tmp_path)
    with pytest.raises(SourceShareError,match="not PIT available"):
        read_standard_bundle(package.payload,package.payload_sha256,
                             decision_at=NOW-timedelta(seconds=1),now=NOW)
    with pytest.raises(SourceShareError,match="SHA differs"):
        read_standard_bundle(package.payload,"f"*64,decision_at=NOW,now=NOW)


def test_future_edge_cannot_enter_past_graph_bundle(tmp_path):
    package,economic,graph_value,history,audit=create(tmp_path)
    later=NOW+timedelta(seconds=1)
    with pytest.raises(SourceShareError,match="future delivery"):
        build_standard_bundle(economic,graph_value,
                              replace(history,decision_at=later),
                              decision_at=NOW,now=NOW)
    with pytest.raises(SourceShareError,match="future or cross-event"):
        build_standard_bundle(economic,graph_value,history,
                              decision_at=NOW,audited=(replace(audit[0],recorded_at=later),),
                              now=later)


def test_event_identity_cannot_change_from_graph(tmp_path):
    package,economic,graph_value,history,audit=create(tmp_path)
    with pytest.raises(SourceShareError,match="linkage differs"):
        build_standard_bundle(economic,replace(graph_value,source_event_sha256="f"*64),
                              history,decision_at=NOW,now=NOW)


def test_modified_payload_or_copyright_body_cannot_be_consumed(tmp_path):
    package,*_=create(tmp_path)
    corrupted=package.payload.replace(b'"verified_beneficiary_count":0',
                                      b'"verified_beneficiary_count":999')
    with pytest.raises(SourceShareError,match="SHA differs"):
        read_standard_bundle(corrupted,package.payload_sha256,decision_at=NOW,now=NOW)
    modified=json.loads(package.payload)
    modified["paid_article_body"]="copyright restricted content"
    raw=(json.dumps(modified,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode()
    with pytest.raises(SourceShareError,match="schema"):
        read_standard_bundle(raw,sha256(raw).hexdigest(),decision_at=NOW,now=NOW)
