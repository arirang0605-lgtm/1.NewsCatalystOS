"""Read already-published RSS analysis; never reanalyze, poll, label, or trade.

The expected SHA comes from the producer's prior output, not this file's name.
Integrity of a stored report is not factual accuracy or source freshness.
No database, registry, AI credential or source document is opened by this reader.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from .analysis_cache import _decode
from .feed_analysis import SCHEMA as ANALYSIS_SCHEMA
from .official_relation_intake import _private_input
from .provider_registry import _safe_https_endpoint
from .reviewed_beneficiary_delivery import _handoff_root
from .source_share import SourceShareError, _json, _must_sha, _when
from .theme_emergence import validate_change

SCHEMA = "newscatalyst.feed_analysis_delivery.v1"
MAX_REPORT_BYTES = 2_000_000  # Existing producer's bound, not a new acceptance gate.
AI_SUCCESS = frozenset({"ANALYZED_UNVERIFIED", "CACHE_HIT"})


def _time(now: datetime | None) -> datetime:
    return _when((now or datetime.now(timezone.utc)).isoformat(), "consumer time")


def _text(value: object, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise SourceShareError("invalid stored " + name)
    return value


def _source_changes(headline,change):
    """Match current claims or pre-market-entry clauses without rewriting data."""
    from .economic_changes import extract_economic_changes
    if change.get('industry_tags')==['POWER_EQUIPMENT']:
        from .power_equipment import extract_power_equipment_changes
        return extract_power_equipment_changes(headline,company_names=change['entity_ids'])
    options=dict(include_function_service_actions='function_service_action' in change,include_price_parallel='price_parallel_action' in change,include_price_services='price_service_action' in change,include_order_services='order_service_action' in change,include_growth_parallel='growth_parallel_action' in change,include_recovery_parallel='recovery_parallel_action' in change,include_policy_parallel='policy_parallel_action' in change,include_policy_services=(change['action']=='BUSINESS_START' and 'policy_cause' in change),include_policy_investment_actions=('policy_investment_action' in change or ('policy_cause' in change and 'investment_event_key' in change)),company_names=change['entity_ids'],include_adjacent_demand='adjacent_demand_cause' in change,include_adjacent_reductions=change.get('adjacent_demand_cause',{}).get('action')=='SUPPLY_REDUCTION',include_adjacent_contracts=change['action']=='CONTRACT',include_adjacent_amounts='contract_amount' in change.get('adjacent_demand_cause',{}),include_adjacent_scopes='demand_scope' in change,include_demand_recovery='demand_recovery_cause' in change,include_product_prices='product_price_cause' in change,include_resumption=(change['action']=='SUPPLY_RESUMPTION' or 'demand_recovery_cause' in change or 'growth_parallel_action' in change))
    rows=extract_economic_changes(headline,**options)
    if change['action']!='MARKET_ENTRY' and '진출' in headline:
        rows+=extract_economic_changes(headline,**options,include_market_entry=False)
    return rows


def _validate_report(data: dict, now: datetime) -> datetime | None:
    """Check the stored format without rerunning economic rules or AI."""
    if (data.get("schema") != ANALYSIS_SCHEMA
            or data.get("status") not in {"FEED_ECONOMIC_ANALYSIS_READY", "NO_COMPLETED_FEED_INPUT"}
            or not isinstance(data.get("results"), list) or len(data["results"]) > 100
            or data.get("source_fetch_calls") != 0 or data.get("human_labels_added", 0) != 0):
        raise SourceShareError("unsupported saved feed analysis")
    rows = data["results"]
    if data["status"] == "NO_COMPLETED_FEED_INPUT":
        if rows or data.get("new_ai_results") != 0 or data.get("cache_hits") != 0:
            raise SourceShareError("empty feed report contains results")
        return None  # Older empty reports have no producer timestamp; do not invent one.
    checked = _when(data.get("checked_at"), "producer checked time")
    if checked > now:
        raise SourceShareError("future analysis report")
    if (data.get("source_inputs_modified") is not False
            or data.get("article_body_included") is not False
            or data.get("verified_economic_facts") != 0
            or data.get("market_action") is not None
            or data.get("release_gate_verified") is not False):
        raise SourceShareError("stored analysis is not an unverified metadata result")
    for field in ("source_versions_checked", "matched_versions", "ai_eligible_candidates",
                  "new_ai_results", "cache_hits"):
        if type(data.get(field)) is not int or data[field] < 0:
            raise SourceShareError("invalid producer result count")
    offset=data.get('discovery_offset',0)
    if (type(offset) is not int or offset<0
            or ('discovery_offset' in data and data.get('analysis_industry')!='ECONOMIC_DISCOVERY')
            or not data["source_versions_checked"] >= data["matched_versions"] >= offset+len(rows)
            or data.get("has_more_results") is not (data["matched_versions"] > offset+len(rows))):
        raise SourceShareError("producer coverage counts disagree")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SourceShareError("invalid stored analysis row")
        provider = _text(row.get("provider_id"), "provider", 128)
        _text(row.get("document_id"), "document", 512)
        _text(row.get("headline"), "headline", 2048)
        _text(row.get("source_kind"), "source kind", 64)
        _safe_https_endpoint(row.get("source_url"))
        event = _must_sha(row.get("source_event_sha256"), "source event")
        title = _must_sha(row.get("source_title_sha256"), "title version")
        analysis = _must_sha(row.get("analysis_event_sha256"), "analysis event")
        _must_sha(row.get("source_triage_sha256"), "source triage")
        expected = sha256((provider + "\0" + event + "\0" + title).encode()).hexdigest()
        if analysis != expected or analysis in seen:
            raise SourceShareError("duplicate or mismatched source version")
        seen.add(analysis)
        source_at = _when(row.get("source_available_at"), "source available")
        analyzed_at = _when(row.get("analysis_available_at"), "analysis available")
        if not source_at <= analyzed_at <= checked:
            raise SourceShareError("source/analysis availability mismatch")
        if (any(row.get(k) is not False for k in (
                "verified_economic_fact", "verified_supply_transaction", "verified_beneficiary"))
                or row.get("revenue_estimate_krw") is not None
                or type(row.get("ai_eligible")) is not bool
                or type(row.get("reported_plan_only")) is not bool):
            raise SourceShareError("stored claim cannot become a confirmed fact or benefit")
        if (not isinstance(row.get("uncertainties"), list)
                or not isinstance(row.get("dimensions"), dict)
                or not isinstance(row.get("source_matched_fields"), list)
                or not isinstance(row.get("known_dimensions"), list)
                or not isinstance(row.get("unknown_dimensions"), list)):
            raise SourceShareError("stored evidence and uncertainty fields required")
        for item in row["source_matched_fields"]:
            if not isinstance(item, dict):
                raise SourceShareError("invalid source-matched field")
            _text(item.get("field"), "field name", 64)
            _text(item.get("value"), "source-matched value", 120)
            _must_sha(item.get("evidence_quote_sha256"), "source quote digest")
            if item.get("status") != "EXACT_SOURCE_MATCH_ISSUER_NOT_ATTESTED":
                raise SourceShareError("source phrase matching is not independent truth")
        if "company_identity" in row:
            from .feed_company_identity import validate_feed_identity
            validate_feed_identity(row["company_identity"], row, at=analyzed_at)
        if "semantic_analysis" in row:
            from .news_semantics import validate_saved
            validate_saved(row, analyzed_at)
        changes = row.get("economic_changes", [])
        if not isinstance(changes, list) or len(changes) > 30:
            raise SourceShareError("bounded title economic changes required")
        discovery_mode=row.get('analysis_industry')=='ECONOMIC_DISCOVERY'
        if discovery_mode:
            from .economic_discovery import discover_economic_events,SUPPORTED_RULE_VERSIONS
            from .feed_analysis import BLOCKED
            discovery_rule=data.get('rule_version')
            if discovery_rule not in SUPPORTED_RULE_VERSIONS:raise SourceShareError('unsupported discovery extraction edition')
            original=(discover_economic_events(row['headline'],rule_version=discovery_rule)
                      if row['source_claim_classification'] not in BLOCKED else [])
            # The existing receipt pins the RAW title. Evidence spans use its
            # already-normalized display text, with a separate text SHA.
            for item in original:item['change']['source_paragraph_sha256']=title
            if (data.get('analysis_industry')!='ECONOMIC_DISCOVERY' or data.get('rule_version')!=discovery_rule
                    or row.get('economic_discovery')!=original or changes!=[v['change'] for v in original]
                    or row.get('ai_eligible') is not False):
                raise SourceShareError('discovered event/industry link must match original evidence in that order')
            if 'discovery_source_connections' in row:
                from .economic_discovery import connect_discovered_source_context
                if row['discovery_source_connections']!=connect_discovered_source_context(row['headline'],original):
                    raise SourceShareError('additional discovery context must match the same source action')
        for change in changes:
            validate_change(change)
            if discovery_mode:continue  # exact generic extraction fully validated above
            if row.get('analysis_industry')=='POWER_EQUIPMENT':
                from .power_equipment import RULE_VERSION as power_rule
                if (data.get('analysis_industry')!='POWER_EQUIPMENT' or data.get('rule_version')!=power_rule
                        or change['industry_tags']!=['POWER_EQUIPMENT']
                        or change['source_paragraph_sha256']!=title
                        or not any(all(c.get(k)==change.get(k) for k in ('topic','action','phase','economic_driver','entity_ids','industry_tags'))
                                   for c in _source_changes(row['headline'],change))):
                    raise SourceShareError('power action does not match exact saved source')
            if change['action'] in {'CUSTOMER_ACQUISITION','DELIVERY_START','MARKET_ENTRY','SUPPLY_RESUMPTION'}:
                from .economic_changes import extract_economic_changes
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','policy_cause','market_entry'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('commercial action is not in the saved source title')
            if change['action']=='BUSINESS_START' and change['economic_driver']=='DEMAND_EXPANSION' and 'order_service_action' not in change:
                from .economic_changes import order_service_actions
                if order_service_actions(row['headline'],company_names=change['entity_ids']):
                    raise SourceShareError('standalone order service requires its source action')
            if 'function_service_action' in change:
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','function_service_action','policy_cause','demand_recovery_cause','demand_scope','service_name','service_event_key'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('function service is not in the saved source title')
            if 'price_service_action' in change:
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','price_service_action','product_price_cause','demand_scope','service_name','service_event_key'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('price service is not in the saved source title')
            if 'order_service_action' in change:
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','order_service_action','demand_scope','service_name','service_event_key'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('order service is not in the saved source title')
            if 'price_parallel_action' in change:
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','price_parallel_action','product_price_cause','demand_scope','service_name','service_event_key','market_entry','investment_project','investment_event_key'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('shared price action is not in the saved source title')
            if 'growth_parallel_action' in change:
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','growth_parallel_action','demand_scope','service_name','service_event_key','market_entry','investment_project','investment_event_key'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('shared growth action is not in the saved source title')
            if 'demand_recovery_cause' in change:
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','demand_recovery_cause','recovery_parallel_action','demand_scope','service_name','service_event_key','investment_event_key'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('recovery cause is not in the saved source title')
            if 'product_price_cause' in change:
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','product_price_cause','demand_scope'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('product price cause is not in the saved source title')
            if 'demand_scope' in change:
                from .economic_changes import extract_economic_changes
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','entity_ids','demand_scope'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('demand scope is not in the saved source title')
            if 'adjacent_demand_cause' in change:
                if not any(all(c.get(k)==change.get(k) for k in ('topic','economic_driver','action','phase','entity_ids','source_paragraph_sha256','adjacent_demand_cause','demand_scope')) for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('adjacent demand is not in the saved source')
            if 'investment_project' in change:
                from .economic_changes import extract_economic_changes
                if not any(all(c.get(k)==change.get(k) for k in
                        ('topic','action','phase','economic_driver','investment_project','entity_ids','investment_event_key'))
                        for c in _source_changes(row['headline'],change)):
                    raise SourceShareError('investment project is not in the saved source title')
            if 'policy_cause' in change:
                from .economic_changes import extract_economic_changes
                options=dict(include_function_service_actions='function_service_action' in change,include_price_parallel='price_parallel_action' in change,include_price_services='price_service_action' in change,include_order_services='order_service_action' in change,include_growth_parallel='growth_parallel_action' in change,include_recovery_parallel='recovery_parallel_action' in change,include_policy_parallel='policy_parallel_action' in change,include_policy_services=(change['action']=='BUSINESS_START' and 'policy_cause' in change),include_policy_investment_actions=('policy_investment_action' in change or ('policy_cause' in change and 'investment_event_key' in change)),include_policy_contract_actions='policy_contract_action' in change,include_policy_capacity_actions='policy_capacity_action' in change,company_names=change['entity_ids'],include_adjacent_demand='adjacent_demand_cause' in change,include_adjacent_reductions=change.get('adjacent_demand_cause',{}).get('action')=='SUPPLY_REDUCTION',include_adjacent_contracts=change['action']=='CONTRACT',include_adjacent_amounts='contract_amount' in change.get('adjacent_demand_cause',{}),include_adjacent_scopes='demand_scope' in change,include_investment_projects=('investment_project' in change or 'policy_parallel_action' in change),
                             include_demand_recovery='demand_recovery_cause' in change,include_product_prices='product_price_cause' in change,include_resumption=(change['action']=='SUPPLY_RESUMPTION' or 'demand_recovery_cause' in change or 'growth_parallel_action' in change))
                extracted=extract_economic_changes(row['headline'],**options)
                if change['action']=='INVESTMENT':
                    extracted+=extract_economic_changes(row['headline'],**options,
                                                        include_investment_execution=False)
                if 'destination' not in change['policy_cause']:
                    extracted+=extract_economic_changes(row['headline'],**options,
                                                        include_policy_destinations=False)
                    if change['action']=='INVESTMENT':
                        extracted+=extract_economic_changes(row['headline'],**options,
                            include_policy_destinations=False,include_investment_execution=False)
                if change['action']!='MARKET_ENTRY':
                    extracted+=extract_economic_changes(row['headline'],**options,include_market_entry=False)
                if change['action']!='DELIVERY_START':
                    extracted+=extract_economic_changes(row['headline'],**options,include_delivery_start=False)
                if change['action']!='CUSTOMER_ACQUISITION':
                    extracted+=extract_economic_changes(row['headline'],**options,include_new_customers=False)
                if not any(all(c.get(k)==change.get(k) for k in (
                        'topic','action','phase','economic_driver','policy_cause','policy_capacity_action','policy_contract_action','policy_investment_action','policy_parallel_action','service_name','service_event_key')) for c in extracted):
                    raise SourceShareError('policy response is not in the saved source title')
                if change['action']=='BUSINESS_START' and not any(c.get('entity_ids')==change['entity_ids'] and c.get('service_name')==change.get('service_name') and c.get('phase')==change['phase'] for c in extracted):
                    raise SourceShareError('policy service actor is not in the saved source title')
            if 'topic_alias_evidence' in change:
                import re
                from .economic_changes import explicit_topic_aliases, company_clauses
                actors=list({n for c in changes for n in c['entity_ids']})
                proofs=[p for sentence in re.split(r'(?<=[.!?。])\s+',row['headline'])
                        for clause in company_clauses(sentence,actors)
                        for p in explicit_topic_aliases(clause,actors)]
                if change['topic_alias_evidence'] not in proofs:
                    raise SourceShareError('topic alias is not in the saved source title')
            if (change["source_paragraph_sha256"] != title
                    or change["evidence_level"] != "REPORTED"):
                raise SourceShareError("economic change must retain title evidence scope")
        # A report carrying a new bounded action group cannot downgrade
        # one sibling to a pre-feature keyword claim by removing its span proof.
        # Reports wholly predating this feature still use their legacy path.
        from .economic_changes import price_parallel_actions,growth_parallel_actions,recovery_parallel_actions,policy_parallel_actions,business_start_names
        for proof_key,parser in (('price_parallel_action',price_parallel_actions),
                                 ('growth_parallel_action',growth_parallel_actions),
                                 ('recovery_parallel_action',recovery_parallel_actions),
                                 ('policy_parallel_action',policy_parallel_actions)):
            for sibling in changes:
                proof=sibling.get(proof_key)
                if not proof:continue
                parsed=parser(proof['source_expression'],company_names=proof['actors'])
                # Function-service and delivery/customer pairs need sibling binding;
                # preserve the older named two-action report contract.
                if len(parsed)!=3 and 'BUSINESS_START' in parsed and business_start_names(parsed['BUSINESS_START']['action_expression']):continue
                for change in changes:
                    if (proof_key not in change and change['action'] in parsed
                            and all(change.get(k)==sibling.get(k) for k in
                                    ('topic','economic_driver','entity_ids','phase','demand_scope','policy_cause'))):
                        # An earlier standalone clause may legitimately have kept
                        # this action's first identity during source deduplication.
                        native=_source_changes(row['headline'],dict(change,**{proof_key:proof}))
                        if not any(proof_key not in c and all(c.get(k)==v
                                for k,v in change.items() if k not in {'evidence_level','source_paragraph_sha256'})
                                for c in native):
                            raise SourceShareError('shared sibling requires its source span')
        _text(row.get("ai_status"), "AI status", 128)
        ai = row.get("ai_analysis")
        if ai is not None:
            raw = json.dumps(ai, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()
            result = _decode(raw)  # Existing AI schema + unverified classification checks.
            if (row["ai_status"] not in AI_SUCCESS or result.event_sha256 != analysis
                    or result.available_at > analyzed_at):
                raise SourceShareError("AI result does not match stored source/time")
            content = {"summary": result.summary, "claims": list(result.claims),
                       "uncertainties": list(result.uncertainties)}
            digest = sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
            if digest != result.content_sha256:
                raise SourceShareError("AI content digest mismatch")
        elif row["ai_status"] in AI_SUCCESS:
            raise SourceShareError("successful AI result missing from saved report")
    if (data["ai_eligible_candidates"] != sum(r["ai_eligible"] for r in rows)
            or data["cache_hits"] != sum(r["ai_status"] == "CACHE_HIT" for r in rows)
            or data["new_ai_results"] != sum(r["ai_status"] == "ANALYZED_UNVERIFIED" for r in rows)):
        raise SourceShareError("saved AI counters disagree with results")
    return checked


def consume_feed_analysis(
    report_file: Path, reports_root: Path, expected_sha256: str, *,
    provider_id: str | None = None, event_id: str | None = None,
    title_sha256: str | None = None, offset: int = 0, limit: int = 20,
    now: datetime | None = None,
) -> dict:
    """Read one SHA-selected report and page its original results, with no writes.

    Original source/analysis timestamps are preserved. Consumer availability is
    stamped after this read, never backdated to the article or analysis time.
    The reader does not certify current collection rights, source freshness,
    a historic backtest decision, human truth, or realized commercial benefits.
    """
    started = _time(now)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise SourceShareError("invalid result page")
    if provider_id is not None:
        _text(provider_id, "selected provider", 128)
    if event_id is not None:
        _must_sha(event_id, "selected source event")
    if title_sha256 is not None:
        _must_sha(title_sha256, "selected title version")
        if event_id is None:
            raise SourceShareError("title version selection requires a source event")
    expected = _must_sha(expected_sha256, "expected analysis report SHA")
    root = _handoff_root(reports_root, create=False)
    path = Path(report_file)
    if (path.parent != root or path.name != "feed_analysis_" + expected + ".json"
            or path.is_symlink()):
        raise SourceShareError("analysis report outside selected private root or SHA")
    raw = _private_input(path, MAX_REPORT_BYTES)
    if sha256(raw).hexdigest() != expected:
        raise SourceShareError("analysis report differs from expected SHA")
    data = _json(raw, "published feed analysis")
    produced = _validate_report(data, started)
    matches = [row for row in data["results"]
        if (provider_id is None or row["provider_id"] == provider_id)
        and (event_id is None or row["source_event_sha256"] == event_id)
        and (title_sha256 is None or row["source_title_sha256"] == title_sha256)]
    page = matches[offset:offset + limit]
    completed = _time(now)
    if completed < started:
        raise SourceShareError("consumer clock moved backwards")
    return {
        "schema": SCHEMA,
        "status": ("NO_COMPLETED_FEED_INPUT" if data["status"] == "NO_COMPLETED_FEED_INPUT"
                   else "FEED_ANALYSIS_READONLY_READY"),
        "analysis_schema": data["schema"], "producer_status": data["status"],
        "source_report_sha256": expected,
        "producer_checked_at": produced.isoformat() if produced is not None else None,
        "consumer_available_at": completed.isoformat(),
        "report_result_count": len(data["results"]), "matched_result_count": len(matches),
        "returned_result_count": len(page), "offset": offset,
        "has_more_matches": offset + len(page) < len(matches),
        "producer_summary": {k: data[k] for k in (
            "source_versions_checked", "matched_versions", "has_more_results",
            "ai_eligible_candidates", "new_ai_results", "cache_hits",
            "paid_execution_requested", "requested_ai_complete") if k in data},
        "rule_version": data.get("rule_version"),
        "routing_assumptions_not_acceptance_criteria": data.get("routing_assumptions_not_acceptance_criteria"),
        "results": page, "scope": "SAVED_ANALYSIS_REPORT_ONLY",
        "source_freshness_certified": False, "historical_decision_certified": False,
        "report_modified": False, "source_fetch_calls": 0, "ai_calls": 0,
        "database_writes": 0,
        "verified_economic_facts": 0, "market_action": None,
    }


def attach_saved_analysis_to_search(
    search_report: dict, report_file: Path, reports_root: Path,
    expected_sha256: str, *, now: datetime | None = None,
) -> dict:
    """Join one prior SHA-pinned report to verified title-search identities.

    No matching analysis means *not present in this report*, not no event.
    Both paths remain separate and no earlier search time is retroactively
    awarded the later analysis availability timestamp.
    """
    saved = consume_feed_analysis(
        report_file, reports_root, expected_sha256, limit=100, now=now,
    )
    indexed = {(r["provider_id"], r["source_event_sha256"],
                r["source_title_sha256"]): r for r in saved["results"]}
    joined = []
    count = 0
    for original in search_report["results"]:
        key = (original["provider_id"], original["event_id"], original["title_sha256"])
        analysis = indexed.get(key)
        if analysis is not None:
            # A matching ID with different verified source evidence is not a join.
            if any((original[search_key] != analysis[analysis_key]) for search_key, analysis_key in (
                ("headline", "headline"), ("source_url", "source_url"),
                ("source_kind", "source_kind"),
                ("source_available_at", "source_available_at"),
                ("triage_evidence_sha256", "source_triage_sha256"),
            )):
                raise SourceShareError("search result differs from saved analysis source")
            count += 1
        joined.append(dict(original, saved_analysis=analysis))
    return dict(search_report, results=joined,
                saved_analysis_report_sha256=saved["source_report_sha256"],
                saved_analysis_producer_checked_at=saved["producer_checked_at"],
                saved_analysis_consumer_available_at=saved["consumer_available_at"],
                saved_analysis_matches=count,
                saved_analysis_unmatched=len(joined) - count,
                saved_analysis_scope="EXACT_SOURCE_VERSION_IN_ONE_SAVED_REPORT",
                analysis_source_freshness_certified=False,
                historical_analysis_join_certified=False)
