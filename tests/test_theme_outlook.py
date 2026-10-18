"""Taxonomy-free theme synthesis through real ingestion contracts, synthetic news."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import json
import subprocess
import threading
from urllib.request import urlopen

import pytest

from newscatalystos.discovery_watch import read_discovery, export_discovery
from newscatalystos.theme_emergence import ThemeStore
from newscatalystos.theme_outlook import build_theme_outlook, compare_outlooks
from newscatalystos.research_dashboard import scan_saved_analysis
from newscatalystos.source_share import SourceShareError
from scripts.run_feed_analysis import evaluate
from test_discovery_launch_comparison import analyzed, source
from test_economic_discovery import flags
from test_federated_news_search import fingerprint

TITLES = ('가상소재는 초격자센서 생산을 시작했다',
          '미래전기는 초격자센서 공급계약을 체결했다',
          '신성테크는 초격자센서 생산능력을 확대했다')


def test_unknown_business_object_groups_economic_actions_without_industry_taxonomy(tmp_path, monkeypatch):
    monkeypatch.setattr('newscatalystos.economic_discovery.HINTS', ())
    root, w, opts, at, report = analyzed(tmp_path, TITLES)
    pins = fingerprint(tmp_path)
    view = read_discovery(root, as_of=at, now=at)
    outlook = view['theme_outlook']
    candidate, = outlook['candidates']
    assert not outlook['industry_taxonomy_required']
    assert candidate['subject'] == '초격자센서'
    assert candidate['attention_tier'] == 'MULTI_ACTIVITY'
    assert len(candidate['related_business_areas']) == 3
    assert candidate['source_company_name_count'] == 3
    assert set(candidate['economic_actions']) == {'PRODUCTION_START', 'CAPACITY_ADDITION', 'CONTRACT'}
    assert all(c['industry_tags'] == [] for c in view['candidates'])
    assert not candidate['common_demand_cause_verified']
    assert candidate['independent_market_event_count'] is None
    assert candidate['investment_score'] is None and not candidate['orders_enabled']
    assert candidate['conditional_paths']
    assert candidate['period_change']['status'] == 'FIRST_LOCAL_OBSERVATION'
    for item in candidate['source_evidence']:
        for key in ('object_evidence', 'action_evidence', 'shared_object_evidence'):
            e = item[key]
            assert item['headline'][e['start']:e['end']] == e['text']
    exported = json.loads(export_discovery(root, as_of=at, now=at))
    originals = {t['theme_id']: t for t in ThemeStore(root/'theme_history').search(now=at)}
    for theme in exported['ThemeCandidates']:
        extension = theme['discovery_theme_outlook']
        assert extension['candidates'] == [candidate]
        assert extension['original_events_unchanged']
        for field in ('event_ids', 'entity_ids', 'industry_tags', 'scores', 'source_refs'):
            assert theme[field] == originals[theme['theme_id']][field]
    assert fingerprint(tmp_path) == pins
    assert report['semantic_ai_attempts'] == report['source_fetch_calls'] == 0


def test_actual_style_shared_purpose_handles_hyphen_without_guessing_a_sector(tmp_path):
    titles = (
        'Department of Commerce Announces Definitive Agreement with Alpha for a CHIPS R&D Award to Develop Novel Silicon-Carbide Semiconductors',
        'Department of Commerce Announces Direct Funding Agreement with Beta for a CHIPS Program Award to Support Domestic Production of Silicon Carbide Semiconductors',
        'Department of Commerce Announces Finalization of CHIPS R&D Award with QuantumCo',
        'Department of Commerce Announces Finalization of CHIPS R&D Award with AnotherCo',
    )
    root, w, opts, at, _ = analyzed(tmp_path, titles)
    candidate, = read_discovery(root, as_of=at, now=at)['theme_outlook']['candidates']
    assert candidate['subject'].casefold() == 'silicon carbide semiconductors'
    assert candidate['attention_tier'] == 'MULTI_COMPANY'
    assert set(candidate['source_company_names']) == {'Alpha', 'Beta'}
    assert len(candidate['source_evidence']) == 2
    assert candidate['period_change']['market_newness_confirmed'] is False


@pytest.mark.parametrize('titles', [
    ('ACME Launches NovaProbe 11', 'OTHER Launches NovaProbe 12'),
    ('ACME Launches Alpha AI', 'OTHER Launches Beta AI'),
    ('가상기업은 초격자센서 생산을 시작했다', '가상기업은 초격자센서 생산능력을 확대했다'),
    ('가상기업은 초격자센서 생산을 시작했다', '가상기업은 초격자센서 생산을 시작했다'),
])
def test_product_versions_generic_ai_and_repeated_company_do_not_promote_a_theme(tmp_path, titles):
    root, w, opts, at, _ = analyzed(tmp_path, titles)
    outlook = read_discovery(root, as_of=at, now=at)['theme_outlook']
    assert all(c['attention_tier'] == 'EARLY_WATCH' for c in outlook['candidates'])
    assert outlook['counts']['priority_research_candidates'] == 0


def test_plan_only_multiple_company_support_is_still_early(tmp_path):
    root, w, opts, at, _ = analyzed(tmp_path, (
        '가상소재는 초격자센서 생산을 시작할 계획이다',
        '미래소재는 초격자센서 생산능력을 확대할 계획이다'))
    c, = read_discovery(root, as_of=at, now=at)['theme_outlook']['candidates']
    assert c['attention_tier'] == 'EARLY_WATCH'
    assert any('계획 단계' in reason for reason in c['attention_reasons'])


def test_period_comparison_and_PIT_do_not_borrow_later_company_or_export(tmp_path):
    w, reg, provider, at = source(tmp_path, TITLES)
    root = tmp_path/'discovery'; opts = flags(w, provider, root)
    from newscatalystos.feed_analysis import _sources
    rows = _sources(w.inbox_root, w.poll_state, reg, at)
    first = next(r for r in rows if r['headline'] == TITLES[0])
    opts.event_id = first['event_id']; opts.title_sha256 = first['title_sha256']
    assert evaluate(opts, now=at)[0] == 0
    baseline = read_discovery(root, as_of=at, now=at)
    original_export = json.loads(export_discovery(root, as_of=at, now=at))
    later = at + timedelta(minutes=2)
    opts.event_id = None; opts.title_sha256 = None
    assert evaluate(opts, now=later)[0] == 0
    view = read_discovery(root, as_of=later, since=at, now=later)
    c, = view['theme_outlook']['candidates']
    assert c['attention_tier'] == 'MULTI_ACTIVITY'
    assert c['period_change']['status'] == 'SUPPORT_BROADENED'
    assert c['period_change']['previous_company_name_count'] == 1
    assert read_discovery(root, as_of=at, now=later)['theme_outlook'] == baseline['theme_outlook']
    assert json.loads(export_discovery(root, as_of=at, now=later)) == original_export
    repeated = read_discovery(root, as_of=later+timedelta(days=1), since=later+timedelta(seconds=1), now=later+timedelta(days=1))
    assert repeated['theme_outlook']['candidates'][0]['period_change']['status'] == 'NO_SUBSTANTIVE_OBSERVATION_CHANGE'


def test_conflicting_retracted_and_missing_sources_are_excluded_from_positive_support(tmp_path):
    root, w, opts, at, _ = analyzed(tmp_path, TITLES)
    view = read_discovery(root, as_of=at, now=at)
    themes = ThemeStore(root/'theme_history').search(now=at)
    parents = tuple((p.name,p) for p in (root/'feed_analysis').glob('d_*'))
    reports, _ = scan_saved_analysis(root/'none', as_of=at, now=at, additional_roots=parents)
    titles = {(r['provider'],r['source_event_sha256'],r['source_title_sha256']): r for r in reports}
    for field in ('conflicting_event_ids', 'invalidated_event_ids'):
        changed = deepcopy(themes)
        for theme in changed:
            theme[field] = list(theme['event_ids'])
        current = build_theme_outlook(changed, titles, view['candidates'], as_of=at, since=at, now=at)
        assert current['candidates'] == []
        compare_outlooks(current, view['theme_outlook'])
        assert len(current['previous_groups_not_currently_matched']) == 1
    assert build_theme_outlook(themes, {}, view['candidates'], as_of=at, since=at, now=at)['candidates'] == []
    with pytest.raises(SourceShareError):
        build_theme_outlook(themes, titles, [], as_of=at+timedelta(seconds=1), since=at, now=at)


def test_supply_contraction_is_caution_and_duplicate_query_is_stable(tmp_path):
    root, w, opts, at, _ = analyzed(tmp_path, (
        '가상소재는 초격자센서 공급을 축소했다', TITLES[1]))
    first = read_discovery(root, as_of=at, now=at)
    candidate, = first['theme_outlook']['candidates']
    assert candidate['attention_tier'] == 'CAUTION'
    assert any(p['direction'] == 'DECREASE' for p in candidate['conditional_paths'])
    assert first['theme_outlook']['counts']['caution_candidates'] == 1
    assert read_discovery(root, as_of=at, now=at)['theme_outlook'] == first['theme_outlook']


def test_same_provider_document_revision_keeps_only_current_object_and_old_PIT(tmp_path):
    w, reg, provider, at = source(tmp_path, (
        '가상소재는 초격자센서 생산을 시작했다',
        '미래소재는 미세격자소재 생산을 시작했다'), same_doc=True)
    root = tmp_path/'discovery'
    assert evaluate(flags(w,provider,root), now=at)[0] == 0
    outlook = read_discovery(root, as_of=at, now=at)['theme_outlook']
    c, = outlook['candidates']
    assert c['subject'] == '미세격자소재'
    assert c['source_company_names'] == ['미래소재']
    assert c['attention_tier'] == 'EARLY_WATCH'


def test_current_http_view_and_standard_export_include_same_theme_hypothesis(tmp_path, monkeypatch):
    from datetime import datetime
    from scripts.open_research_dashboard import DashboardServer
    w, reg, provider, at = source(tmp_path, TITLES)
    documents = tmp_path/'documents'; root = documents/'economic_discovery'
    assert evaluate(flags(w,provider,root), now=at)[0] == 0
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return at
    monkeypatch.setattr('scripts.open_research_dashboard.datetime',Clock)
    server = DashboardServer(0,tmp_path/'reports',tmp_path/'notes',documents,news_search_workspaces=(w,))
    thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    pins = fingerprint(tmp_path)
    try:
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/economic-discovery') as response:
            data = json.load(response)
        candidate, = data['theme_outlook']['candidates']
        with urlopen(f'http://127.0.0.1:{server.server_port}/api/economic-discovery?export=1') as response:
            exported = json.load(response)
        assert all(t['discovery_theme_outlook']['candidates'] == [candidate] for t in exported['ThemeCandidates'])
    finally:
        server.shutdown();server.server_close();thread.join(3)
    assert fingerprint(tmp_path) == pins


def test_theme_UI_shows_reason_business_roles_counterconditions_and_safe_source_text():
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('scripts/dashboard_assets/app.js','utf8');
function node(t,c,txt){return {textContent:txt||'',children:[],append(...x){this.children.push(...x)},replaceChildren(...x){this.children=x}}}
const p=node('div');const ctx={node,economicActionLabels:{CONTRACT:'공급계약'}};
vm.runInNewContext(s.slice(s.indexOf('function renderThemeOutlook(')),ctx);
ctx.renderThemeOutlook(p,{candidates:[{title:'새소재<script> 관련 경제 변화',attention_label:'우선 조사 후보',
source_company_names:['가상기업'],attention_reasons:['다른 기업 행동 연결'],period_change:{status:'SUPPORT_BROADENED'},
related_business_areas:[{source_described_area:'새소재',role_label:'공급·구매 계약',source_companies:['가상기업']}],
conditional_paths:[{opportunity:'계약 이행 시 사업 기회',countercondition:'해지·납품 확인'}],
source_evidence:[{headline:'가상 기사',shared_object_evidence:{text:'새소재'},action:'CONTRACT',phase:'PLANNED',basis_available_at:'2026-10-18',source_url:'https://example.org'}]}]});
function text(n){return [n.textContent,...n.children.flatMap(text)].join(' ')}
for(const v of ['새소재<script>','주목할 테마 후보','우선 조사 후보','계약 이행','해지·납품','공급·구매 계약','계획','관측 범위 확대'])assert(text(p).includes(v));
assert(!s.slice(s.indexOf('function renderThemeOutlook(')).includes('innerHTML'));
'''
    subprocess.run(['node','-e',script],cwd=Path(__file__).resolve().parent.parent,
                   capture_output=True,text=True,check=True)
