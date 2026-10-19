"""Source-bound business context must not invent a demand cause or delivery."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import pytest
from newscatalystos.source_share import SourceShareError
from newscatalystos.recent_theme_followups import (
    SCHEMA, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5,
    publish_followups, read_followups, metadata_resolver, assess,
)
from newscatalystos.discovery_watch import read_discovery, export_discovery
from test_recent_theme_followups import scenario
from test_federated_news_search import fingerprint


def context(document):
    note = deepcopy(document['notes'][0])
    note.update(evidence_kind='CONTEXT_ONLY', factor_codes=[], market_codes=['KR'],
                product_scope='합성: HVDC 제어기의 가상 시험환경',
                analysis_text='합성: 시험환경 구축을 보도했다. 실제 전력망 납품이 아니다.',
                limitation='합성: 수요 증가 원인·개별 발주·납품·매출은 미확인이다.')
    return {'schema': SCHEMA_V5, 'notes': [note]}


def test_context_roundtrip_keeps_old_results_pit_duplicates_and_exact_source(tmp_path, monkeypatch):
    root, _, _, ws, baselines, doc, opener = scenario(tmp_path, monkeypatch)
    # Existing V1 evidence remains byte-for-byte and available before V5.
    old = {'schema': SCHEMA, 'notes': [doc['notes'][1]]}
    publish_followups(root, old, baselines, metadata_resolver((ws,), now=datetime.now(timezone.utc)))
    before = datetime.now(timezone.utc)
    fixed = export_discovery(root, as_of=before, now=before,
                             include_common_causes=True, recent_workspaces=(ws,))
    old_view = read_discovery(root, as_of=before, now=before, include_common_causes=True, recent_workspaces=(ws,))
    old_comparison = next(g['recent_news_comparison'] for g in old_view['theme_outlook']['candidates'] if g.get('recent_news_comparison'))
    old_files = {p.name: p.read_bytes() for p in (root/'analysis_notes/recent_followups').glob('*.json')}
    data = context(doc)
    resolve = metadata_resolver((ws,), now=datetime.now(timezone.utc))
    result = publish_followups(root, data, baselines, resolve)
    assert result['created'] == 1 and not result['source_text_stored']
    assert publish_followups(root, data, baselines, resolve)['created'] == 0
    now = datetime.now(timezone.utc)
    rows = read_followups(root, baselines, resolve, as_of=now, now=now)
    added, = [r for r in rows if r['schema'] == SCHEMA_V5]
    assert added['note']['recent_source'] == data['notes'][0]['recent_source']
    assert added['note']['factor_codes'] == [] and 'execution_context' not in added
    assert assess([added] * 5, ['가상전기', '자료없는기업'])['status'] == 'NO_SUBSTANTIVE_CHANGE'
    assert assess([added], ['가상전기'])['shared_recent_factors'] == []
    view = read_discovery(root, as_of=now, now=now, include_common_causes=True, recent_workspaces=(ws,))
    comparison, = [g['recent_news_comparison'] for g in view['theme_outlook']['candidates']
                   if g.get('recent_news_comparison')]
    assert len(comparison['notes']) == 2 and comparison['status'] == old_comparison['status']
    assert comparison['shared_recent_factors'] == []
    assert not comparison['article_count_used_as_strength']
    assert export_discovery(root, as_of=before, now=now,
                            include_common_causes=True, recent_workspaces=(ws,)) == fixed
    assert all((root/'analysis_notes/recent_followups'/n).read_bytes() == b for n,b in old_files.items())
    assert opener.calls == 1
    # Actual renderer makes the missing demand/execution proof explicit.
    script = r'''const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const src=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(t,c,text){return {textContent:text||'',children:[],append(...x){this.children.push(...x)},addEventListener(){}}}
const ctx={node}, box=node('div');
vm.runInNewContext(src.slice(src.indexOf('function renderRecentThemeComparison('),src.indexOf('function renderPublicDemandNotes(')),ctx);
ctx.renderRecentThemeComparison(box,JSON.parse(fs.readFileSync(0,'utf8')),true);
function all(n){return [n,...n.children.flatMap(all)]}
assert(all(box).map(n=>n.textContent).join(' ').includes('사업·기술 배경 · 수요·이행 미확인'));'''
    subprocess.run(['node', '-e', script], input=json.dumps(comparison), text=True,
                   capture_output=True, check=True, cwd=Path(__file__).resolve().parents[1])


@pytest.mark.parametrize('schema', [SCHEMA, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4])
def test_old_versions_do_not_silently_adopt_new_context_semantics(tmp_path, monkeypatch, schema):
    root, _, _, ws, baselines, doc, _ = scenario(tmp_path, monkeypatch)
    data = context(doc); data['schema'] = schema
    before = fingerprint(tmp_path)
    with pytest.raises(SourceShareError):
        publish_followups(root, data, baselines, metadata_resolver((ws,), now=datetime.now(timezone.utc)))
    assert fingerprint(tmp_path) == before


@pytest.mark.parametrize('change', [
    {'evidence_kind': 'REPORTED_CONTRACT'}, {'evidence_kind': 'REPORTED_DELIVERY'},
    {'evidence_kind': 'CANCELLATION'}, {'reported_date': None},
    {'reported_date': '2999-01-01'}, {'market_codes': []},
    {'factor_codes': ['INVENTED_CAUSE']}, {'execution': {}}, {'body': 'source body'},
])
def test_context_version_cannot_bypass_identity_date_scope_or_execution(tmp_path, monkeypatch, change):
    root, _, _, ws, baselines, doc, _ = scenario(tmp_path, monkeypatch)
    data = context(doc); data['notes'][0].update(change)
    before = fingerprint(tmp_path)
    with pytest.raises((SourceShareError, ValueError)):
        publish_followups(root, data, baselines, metadata_resolver((ws,), now=datetime.now(timezone.utc)))
    assert fingerprint(tmp_path) == before
