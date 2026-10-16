const state={view:"day",date:new Date().toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"})};
const $=id=>document.getElementById(id);
let currentData=null,shown=20;
const economicPhaseLabels={SOURCE_REPORTED:"출처 보도",ADOPTED_NOT_YET_EFFECTIVE:"의결 · 시행 전",PLANNED:"계획 단계"};
const economicActionLabels={SUPPLY_RESUMPTION:"생산·공급 재개",MARKET_ENTRY:"시장 진출",DELIVERY_START:"납품·공급 개시",POLICY_CHANGE:"정책 변화",BUSINESS_START:"사업·서비스 개시",PRODUCTION_START:"생산 개시",CAPACITY_ADDITION:"생산능력 확대",SUPPLY_REDUCTION:"공급 축소",CONTRACT:"계약",INVESTMENT:"투자 결정",INVESTMENT_EXECUTION:"투자 집행",CUSTOMER_ACQUISITION:"신규 고객 확보"};
const economicDriverLabels={DEMAND_RECOVERY:"수요·주문 회복",DEMAND_EXPANSION:"수요 확대",DEMAND_CONTRACTION:"수요·주문 축소",PRODUCT_PRICE_INCREASE:"제품 가격 상승",PRODUCT_PRICE_DECREASE:"제품 가격 하락",POLICY_ENABLEMENT:"정책 기반 확대",CAPACITY_EXPANSION:"생산능력 확대",SUPPLY_CONTRACTION:"공급 축소",UNKNOWN:"공통 원인 미확인"};
function node(tag,cls,value){const x=document.createElement(tag);if(cls)x.className=cls;if(value!==undefined)x.textContent=value;return x}
function status(message,error=false){$("status").textContent=message;$("status").className=error?"error":""}
function shift(amount){const [y,m,d]=state.date.split("-").map(Number),day=new Date(Date.UTC(y,m-1,d));if(state.view==="month")day.setUTCMonth(day.getUTCMonth()+amount);else day.setUTCDate(day.getUTCDate()+amount*(state.view==="week"?7:1));state.date=day.toISOString().slice(0,10);load()}
function niceDate(value){return new Intl.DateTimeFormat("ko-KR",{year:"numeric",month:"long",day:"numeric",timeZone:"UTC"}).format(new Date(value+"T00:00:00Z"))}
function amountText(value){const parts=String(value).split(".");parts[0]=parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,",");return parts.join(".")}
function showNotes(place,notes,empty){place.replaceChildren();if(!notes.length){place.append(node("p","empty-small",empty));return}for(const item of [...notes].reverse()){const box=node("div","note");box.append(node("span","note-date",item.period+" · "+item.view),node("p","",item.text));place.append(box)}}
function savedCategoryLabel(item){const labels={PRODUCT_LAUNCH:"제품 출시",BUSINESS_START:"사업·서비스 개시",NEW_CONTRACT:"신규 계약",NEW_INVESTMENT:"신규 투자",COMMERCIALIZATION:"상용화",REGULATORY_APPROVAL:"인허가",NEW_FACILITY:"신규 시설",CONTRACT_TERMINATION:"계약 종료",CONTRACT_REDUCTION:"계약 감액",CONTRACT_DELAY:"납기 지연"};const label=labels[item.category];return label?label+(item.reported_plan_only?" 계획 보도":" 보도"):(item.category==="LICENSED_ARTICLE_ANALYSIS"?"허가 본문 분석":item.category||"분류 없음")}
function actionLabel(change){return (economicActionLabels[change.action]||change.action)+" · "+(economicPhaseLabels[change.phase]||"단계 미확인")}
function categoryLabel(item){
  // A cancellation/change warning must remain visible even when the source also
  // contains an economic action. Never rewrite category or AI eligibility.
  if(["CONTRACT_TERMINATION","CONTRACT_REDUCTION","CONTRACT_DELAY"].includes(item.category))return savedCategoryLabel(item);
  const labels=[...new Set((item.economic_changes||[]).map(actionLabel))];
  return labels.length?labels.join(" / "):savedCategoryLabel(item);
}
const actionSearchTerms={SUPPLY_RESUMPTION:"생산 재개 공급 재개",MARKET_ENTRY:"시장 진출 신규 시장",DELIVERY_START:"납품 시작 납품 개시 공급 시작 공급 개시",POLICY_CHANGE:"정책 변화 규제 허가",BUSINESS_START:"사업 개시 서비스 개시 사업 시작 서비스 시작",PRODUCTION_START:"생산 개시 생산 시작 양산 가동",CAPACITY_ADDITION:"생산능력 확대 생산량 확대 공급량 확대 증설",SUPPLY_REDUCTION:"공급 축소 생산 축소 감산 공급 중단",CONTRACT:"계약 체결 공급계약 납품계약 수주",INVESTMENT:"투자 결정 투자 확정",INVESTMENT_EXECUTION:"투자 집행",CUSTOMER_ACQUISITION:"신규 고객 확보"};
function actionSearchText(changes){return (changes||[]).map(c=>[c.action,actionLabel(c),actionSearchTerms[c.action]||""].join(" ")).join(" ")}
function matchesFinding(item,term){return !term||[item.headline,item.provider,item.category||"",savedCategoryLabel(item),categoryLabel(item),actionSearchText(item.economic_changes),JSON.stringify(item.economic_changes||[]),JSON.stringify(item.company_identity||{})].join(" ").toLocaleLowerCase().includes(term)}
function themeTitle(theme,presentation){return presentation?.name||theme.provisional_name}
function matchesTheme(theme,term,candidates,changes,presentation){return !term||[themeTitle(theme,presentation),JSON.stringify(theme),JSON.stringify(changes||{}),JSON.stringify(candidates||[]),actionSearchText(theme.source_refs)].join(" ").toLocaleLowerCase().includes(term)}
function inclusionBasisLabel(candidate,basis,index,presentations){
  const entry=presentations?.[candidate.candidate_id],item=entry?.items?.[index];
  if(!entry||entry.status!=="READY"||entry.theme_id!==candidate.theme_id||entry.entity_id!==candidate.entity_id||entry.theme_snapshot_sha256!==candidate.theme_snapshot_sha256||entry.decision_at!==candidate.decision_at||item?.basis_index!==index||item?.event_id!==basis.event_id||item?.extraction_method!=="AI_SOURCE_SPAN_MATCHED")return "";
  return item.label||"";
}
function companySearchResults(context,query){
  const term=query.normalize("NFKC").toLowerCase().trim().replace(/\s+/gu," "),direct=new Set(),ambiguous=new Set();
  for(const [id,entry] of Object.entries(context||{})){
    const keys=term?entry.keys.filter(k=>k.value===term):[];
    if(keys.some(k=>!k.ambiguous))direct.add(id);else if(keys.length)ambiguous.add(id);
  }
  const themes=new Set([...direct,...ambiguous].map(id=>context[id].theme_id));
  return Object.fromEntries(Object.entries(context||{}).map(([id,e])=>[id,{...e,match_kind:!term?"UNFILTERED":direct.has(id)?"DIRECT_COMPANY":ambiguous.has(id)?"AMBIGUOUS_NAME":themes.has(e.theme_id)?"RELATED_THEME":"TEXT_CONTEXT"}]));
}
function companySearchLabel(kind){return {DIRECT_COMPANY:"검색 기업명·식별자와 정확히 일치 · 거래·수혜 확인 아님",AMBIGUOUS_NAME:"동일 이름 복수 기업 · 식별 미확정",RELATED_THEME:"같은 테마의 연관 기업 · 검색 기업과 직접 관계 미확인",TEXT_CONTEXT:"검색어가 포함된 테마 맥락 · 기업 직접 일치 아님"}[kind]||""}
function renderEventImpactPaths(parent,source){
  const paths=source.impact_paths||[];
  if(!paths.length){parent.append(node("p","","분석상 테마 연관 · 영향 경로 미확인"));return}
  const relationLabels={REPORTED_DIRECT_TRANSACTION:"출처에 보고된 거래 관계",ANNOUNCED_SUPPLY_PLAN:"발표된 공급 계획",THEMATIC_ASSOCIATION:"분석상 테마 연관"};
  const impactLabels={POTENTIAL_BENEFICIARY_UNVERIFIED:"잠재 수혜 · 추론",POTENTIAL_DAMAGE_UNVERIFIED:"잠재 피해 · 추론",ANNOUNCED_SUPPLY_PLAN_UNVERIFIED:"계획 단계 · 실현 미확인",EFFECT_DIRECTION_UNKNOWN:"영향 방향 미확인",UNKNOWN_RELATIONSHIP:"영향 경로 미확인",THEMATIC_ONLY:"단순 테마 연관"};
  const stages={MEMORY_DRAM:"DRAM 메모리",MEMORY_NAND:"NAND 메모리",MEMORY_HBM:"HBM 메모리",WAFER_FAB:"웨이퍼 제조",FAB_EQUIPMENT:"반도체 제조 장비",MATERIALS:"소재",COMPONENTS:"부품",SUBSTRATES:"기판",ADVANCED_PACKAGING:"첨단 패키징",TESTING:"테스트"};
  for(const path of paths){
    const box=node("div","finding-detail");
    box.append(node("p","",(relationLabels[path.relation_kind]||"관계 미확인")+" · "+(impactLabels[path.impact_category]||"영향 미확인")));
    box.append(node("p","",(stages[path.product_stage]||path.product_stage)+" · "+(path.role==="supplier"?"공급자":"고객")+" · 상대 기업 "+path.counterparty_id));
    box.append(node("p","","독립 확인된 실거래·매출 기여·수혜 아님"));
    if(path.conflicting)box.append(node("p","","상충 근거가 있는 영향 경로"));
    for(const url of path.source_urls){const a=node("a","source-link","이 사건 공급망 관계의 출처");a.href=url;a.target="_blank";a.rel="noopener noreferrer";box.append(a)}
    box.append(node("p","","관계 출처 가용: "+path.source_available_at+" · 연결 확보: "+path.linked_at));
    const proof=node("details","");proof.append(node("summary","","관계·원본 그래프 근거"),node("p","","관계 SHA: "+path.relation_sha256),node("p","","원본 그래프 SHA: "+path.graph_sha256));
    if(path.document_sha256)proof.append(node("p","","원본 문서 SHA: "+path.document_sha256),node("p","","문서 ID: "+(path.document_id||"미확인")));
    box.append(proof);
    parent.append(box);
  }
}
function renderReportedContractAmount(parent,cause){
  const amount=cause?.contract_amount;
  if(amount?.status==="SOURCE_REPORTED_TOTAL")parent.append(node("p","","보도된 계약 총액: "+amount.source_expression+" · 실제 이행·매출·수혜 확인 아님"));
}
function renderReportedDemandReduction(parent,source){
  if(source.action==="SUPPLY_REDUCTION"&&source.cause?.kind==="adjacent_demand_cause")parent.append(node("p","","보도된 수요 감소→감산 연결 · 실제 생산량·매출·손실을 독립 확인한 결과는 아닙니다."));
}
function renderReportedRecoveryContract(parent,source){
  if(source.economic_driver==="DEMAND_RECOVERY"&&source.action==="CONTRACT")parent.append(node("p","","회복 원인의 공급계약 체결 보도 · 공급 재개와 별도 행동 단계이며 실제 이행·납품·물량·매출·수혜 확인이 아닙니다."));
}
function renderReportedRecoveryDelivery(parent,source){
  if(source.economic_driver==="DEMAND_RECOVERY"&&source.action==="DELIVERY_START"&&source.phase==="SOURCE_REPORTED")parent.append(node("p","","회복 원인의 납품·공급 개시 보도 · 체결·재개와 출처별 행동 단계를 구별하며 완납·물량·매출·수혜 확인이 아닙니다."));
}
function renderReportedRecoveryProduction(parent,source){
  if(source.economic_driver==="DEMAND_RECOVERY"&&source.action==="PRODUCTION_START"&&source.phase==="SOURCE_REPORTED")parent.append(node("p","","회복 원인의 생산·양산 개시 보도 · 증설·재개·체결·납품과 출처별 단계를 구별하며 생산능력·물량·상업 납품·매출·수혜 확인이 아닙니다."));
}
function renderReportedRecoveryCapacity(parent,source){
  if(source.economic_driver==="DEMAND_RECOVERY"&&source.action==="CAPACITY_ADDITION"&&source.phase==="SOURCE_REPORTED")parent.append(node("p","","회복 원인의 생산능력 확대 보도 · 생산 개시·재개·체결·납품과 구별하며 실제 생산량·가동률·물량·매출·수혜 확인이 아닙니다."));
}
function renderReportedRecoveryInvestment(parent,source){
  if(source.economic_driver==="DEMAND_RECOVERY"&&source.action==="INVESTMENT_EXECUTION"&&source.phase==="SOURCE_REPORTED")parent.append(node("p","","회복 원인의 투자 집행 보도 · 결정/계획·능력 확대·생산·상업 행동과 구별하며 실제 자금 지급·설비 완공·가동·물량·매출·수혜 확인이 아닙니다."));
}
function renderReportedRecoveryCustomer(parent,source){
  if(source.economic_driver==="DEMAND_RECOVERY"&&source.action==="CUSTOMER_ACQUISITION"&&source.phase==="SOURCE_REPORTED")parent.append(node("p","","회복 원인의 신규 고객 확보 보도 · 미명시 고객 실명·확정 관계·계약 규모·납품·매출·수혜를 추정하지 않습니다."));
}
function renderReportedRecoveryMarket(parent,source){
  if(source.economic_driver!=="DEMAND_RECOVERY"||source.action!=="MARKET_ENTRY"||source.phase!=="SOURCE_REPORTED")return;
  parent.append(node("p","","회복 원인의 명시 시장 진출 보도 · 수요처·진출시장·고객회사를 구별하며 고객·계약·납품·매출·수혜를 확정하지 않습니다."));
  if(source.market_entry)parent.append(node("p","","진출시장(원문): "+source.market_entry.market_name+" · “"+source.market_entry.source_expression+"” · SHA: "+source.market_entry.expression_sha256));
  if(source.demand_scope)parent.append(node("p","","이 출처의 수요처: "+source.demand_scope.destination+" · 진출시장과 별도 표현"));
}
function renderReportedRecoveryService(parent,source){
  if(source.economic_driver!=="DEMAND_RECOVERY"||source.action!=="BUSINESS_START"||source.phase!=="SOURCE_REPORTED")return;
  parent.append(node("p","","회복 원인의 명시 서비스 개시 보도 · 수요처·서비스·고객회사를 구별하며 실제 고객·이용량·상업 납품·매출·수혜를 확정하지 않습니다."));
  if(source.service_name)parent.append(node("p","","서비스명(원문): "+source.service_name+(source.service_event_key?" · 저장된 서비스 키: "+source.service_event_key:"")));
}
function renderCommonCauseComparison(card,theme,candidates,comparisons,period){
  const comparison=comparisons?.[theme.theme_id],cs=candidates.filter(c=>c.theme_id===theme.theme_id);
  if(!comparison||comparison.theme_id!==theme.theme_id||comparison.decision_at!==theme.decision_at||!cs.length||cs.some(c=>c.theme_snapshot_sha256!==comparison.theme_snapshot_sha256||c.decision_at!==comparison.decision_at))return;
  const box=node("details","finding-detail");box.append(node("summary","","공통 원인 · 기업별 행동·출처 비교"));
  box.append(node("p","","독립 행동 묶음 "+comparison.distinct_action_groups+"개 · 같은 사건의 여러 보도는 별도 행동으로 세지 않습니다. 공통 원인은 테마 가설이며 거래·수혜 확인이 아닙니다."));
  for(const row of comparison.rows){
    const group=node("div","finding-detail");group.append(node("h5","",row.display_name),node("p","","연결 사건 "+row.distinct_event_count+"개 · 출처 근거 "+row.sources.length+"개"));
    if(period?.status==="READY"&&period.action_group_ids.includes(row.action_group_id))group.append(node("p","",row.sources.some(s=>s.company_participation==="SOURCE_EVENT_ACTOR")?"기간 내 새 독립 행동의 당사자 근거":"기간 내 새 행동의 관계 맥락 · 당사자 확산 집계 아님"));
    for(const source of row.sources){
      if(source.cause?.kind==="adjacent_demand_cause"){
        group.append(node("p","","인접 문장의 명시적 원인 연결 · 출처 보도이며 독립 사실 확인 아님"),node("p","","원인 문장: "+source.cause.cause_expression),node("p","","행동 문장: "+source.cause.action_expression));
        if(source.cause.demand_scope)group.append(node("p","","명시 수요처: "+(source.cause.demand_scope.status==="EXPLICIT"?source.cause.demand_scope.destination:"복수·불명확 · 공동 수요처 미확인")+" · 고객회사·계약·수혜 확인 아님"));
      }
      renderReportedContractAmount(group,source.cause);renderReportedDemandReduction(group,source);renderReportedRecoveryContract(group,source);renderReportedRecoveryDelivery(group,source);renderReportedRecoveryProduction(group,source);renderReportedRecoveryCapacity(group,source);renderReportedRecoveryInvestment(group,source);renderReportedRecoveryCustomer(group,source);renderReportedRecoveryMarket(group,source);renderReportedRecoveryService(group,source);renderReportedPolicyProduction(group,source);renderReportedPolicyCapacity(group,source);renderReportedPolicyContract(group,source);renderReportedPolicyDelivery(group,source);renderReportedPolicyCustomer(group,source);renderReportedPolicyMarket(group,source);renderReportedPolicyInvestment(group,source);renderReportedPolicyService(group,source);
      const contextOnly=source.company_participation==="SUPPLY_CHAIN_CONTEXT";
      group.append(node("p","",(contextOnly?"공급망으로 연결된 사건 · 이 기업의 직접 행동 확인 아님 · ":"")+actionLabel(source)+" · 사건 "+source.event_id));
      if(contextOnly)group.append(node("p","","사건 당사자: "+source.event_entity_ids.join(" · ")));
      group.append(node("p","",source.cause.status==="STORED_EXPRESSION"?"저장된 원인 표현: “"+source.cause.source_expression+"”":"원인 유형: "+(economicDriverLabels[comparison.economic_driver]||"공통 원인 미확인")+" · 원문 근거 미확인"));
      group.append(node("p","",source.extraction_method==="AI_SOURCE_SPAN_MATCHED"?"AI 해석의 원문 근거 · 독립 사실 확인 아님":({OFFICIAL_SOURCE:"공식 출처 보도 · 독립 사실 확인 아님",REPORTED:"출처 보도 · 독립 사실 확인 아님",INFERRED:"추론 · 독립 사실 확인 아님"}[source.evidence_level]||"미확인 근거")));
      if(source.conflicting)group.append(node("p","","상충 근거가 있는 사건"));
      const a=node("a","source-link","이 행동·원인 근거의 출처");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";group.append(a);
      group.append(node("p","",({RSS_TITLE_METADATA:"RSS 제목 근거",LICENSED_ARTICLE_TEXT:"허가 본문 근거"}[source.content_scope]||"저장 근거")));
      group.append(node("p","","출처 가용: "+source.source_available_at+" · 관측: "+source.recorded_at+" · 판본: "+comparison.decision_at));
      group.append(node("p","","근거 SHA: "+source.evidence_sha256));
      renderEventImpactPaths(group,source);
    }
    box.append(group);
  }
  card.append(box);
}
function renderThemeActionOrder(card,period){
  if(!period)return;
  if(period.status!=="READY"){card.append(node("p","finding-detail","기간별 행동 증가 미확인 · 비교 자료를 확인할 수 없습니다."));return}
  card.append(node("p","finding-detail","선택 기간 독립 행동 추가 "+period.independent_actions_added+"개 · 제외 "+period.independent_actions_removed+"개 · 새 행동의 신규 당사자 "+period.new_event_participant_count+"개"));
  card.append(node("p","finding-detail","추가 보도·같은 프로젝트 후속·식별·관계 갱신은 새 독립 행동으로 세지 않습니다. 아래 공통 원인·기업별 행동·출처 비교에서 근거를 확인하세요. 거래·수혜·대장주 확정이 아닙니다."));
}
function renderReportedPolicyProduction(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="PRODUCTION_START"||source.phase!=="SOURCE_REPORTED")return;
  parent.append(node("p","","정책 원인의 실제 생산 개시 보도 · 정책의 법적 효력·이전 장벽 해소·거래·매출·수혜를 독립 확인한 결과가 아닙니다."));
  const proof=source.policy_cause;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
}
function renderReportedPolicyCapacity(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="CAPACITY_ADDITION"||source.phase!=="SOURCE_REPORTED"||!source.policy_capacity_action)return;
  parent.append(node("p","","정책 원인의 실제 생산능력 확대 보도 · 생산 개시·설비 완공·가동률·실물량·매출·수혜의 독립 확인이 아닙니다. 정책 보도와 법적 효력·장벽 해소는 구별합니다."));
  const proof=source.policy_cause;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
  if(source.policy_capacity_action)parent.append(node("p","","확대 행동 원문: “"+source.policy_capacity_action.source_expression+"” · SHA: "+source.policy_capacity_action.expression_sha256));
}
function renderReportedPolicyContract(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="CONTRACT"||source.phase!=="SOURCE_REPORTED"||!source.policy_contract_action)return;
  parent.append(node("p","","정책 원인의 실제 공급계약 체결 보도 · 계약 이행·납품·매출·수혜의 독립 확인이 아닙니다. 미명시 상대방·계약 규모를 추정하지 않으며 정책 보도와 법적 효력·장벽 해소를 구별합니다."));
  const proof=source.policy_cause;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
  parent.append(node("p","","체결 행동 원문: “"+source.policy_contract_action.source_expression+"” · SHA: "+source.policy_contract_action.expression_sha256));
}
function renderReportedPolicyDelivery(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="DELIVERY_START"||source.phase!=="SOURCE_REPORTED")return;
  parent.append(node("p","","정책 원인의 실제 납품·공급 개시 보도 · 완납·실물량·매출·수혜의 독립 확인이 아닙니다. 미명시 고객회사·계약 상대방·확정 관계를 만들지 않으며 정책 보도와 법적 효력·장벽 해소를 구별합니다."));
  const proof=source.policy_cause;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
}
function renderReportedPolicyCustomer(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="CUSTOMER_ACQUISITION"||source.phase!=="SOURCE_REPORTED")return;
  parent.append(node("p","","정책 원인의 실제 신규 고객 확보 보도 · 계약·이행·납품·매출·수혜의 독립 확인이 아닙니다. 미명시 고객회사 실명·ID·확정 관계·계약 규모를 만들지 않으며 정책 보도와 법적 효력·장벽 해소를 구별합니다."));
  const proof=source.policy_cause;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
}
function renderReportedPolicyMarket(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="MARKET_ENTRY"||source.phase!=="SOURCE_REPORTED")return;
  parent.append(node("p","","정책 원인의 실제 명시 시장 진출 보도 · 정책 관할·대상국·진출시장·고객회사를 구별하며 고객·계약·납품·매출·시장 전체 수혜를 확정하지 않습니다. 정책 보도는 법적 효력·독립 장벽 해소의 확인이 아닙니다."));
  const proof=source.policy_cause,market=source.market_entry;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
  if(market)parent.append(node("p","","출처의 진출시장: "+market.market_name+" · “"+market.source_expression+"” · SHA: "+market.expression_sha256));
}
function renderReportedPolicyInvestment(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="INVESTMENT_EXECUTION"||source.phase!=="SOURCE_REPORTED"||!source.policy_investment_action)return;
  parent.append(node("p","","정책 원인의 실제 투자 집행 보도 · 실제 자금 지급·설비 완공·가동·물량·매출·수혜의 독립 확인이 아닙니다. 정책 보도와 법적 효력·독립 장벽 해소를 구별합니다."));
  const proof=source.policy_cause,action=source.policy_investment_action;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
  parent.append(node("p","","집행 원문: “"+action.source_expression+"” · SHA: "+action.expression_sha256));
  if(action.investment_project)parent.append(node("p","","원문 프로젝트: "+action.investment_project.project_name+" · SHA: "+action.investment_project.expression_sha256));
}
function renderReportedPolicyService(parent,source){
  if(source.cause?.kind!=="policy_cause"||source.action!=="BUSINESS_START"||source.phase!=="SOURCE_REPORTED"||!source.service_name)return;
  parent.append(node("p","","정책 원인의 명시 서비스 실제 개시 보도 · 서비스·고객회사를 구별하며 실제 고객·이용량·납품·매출·수혜를 확정하지 않습니다. 정책 보도는 법적 효력·독립 장벽 해소의 확인이 아닙니다."));
  if(source.service_name)parent.append(node("p","","원문 서비스명: "+source.service_name));
  const proof=source.policy_cause;
  if(proof)parent.append(node("p","","정책: "+proof.policy_name+" · 관할: "+proof.jurisdiction+" · "+proof.restriction+" · "+proof.change+" · 대상국: "+(proof.destination||"원문 미명시")),node("p","","정책 원문: “"+proof.source_expression+"” · SHA: "+proof.expression_sha256));
}
function renderCrossProductDemand(parent,comparison,term="",search={}){
  if(!comparison)return;
  if(comparison.status==="PARTIAL")parent.append(node("p","fineprint","일부 제품의 선택 판본·근거를 확인할 수 없어 해당 비교는 미확인으로 남겼습니다."));
  if(comparison.period_status==="UNAVAILABLE")parent.append(node("p","fineprint","기간 비교 자료를 읽지 못했습니다. 현재 후보군은 유지하고 변화는 미확인으로 표시합니다."));
  for(const group of comparison.groups||[]){
    const direct=group.products.some(p=>p.actions.some(a=>search[a.candidate_id]?.match_kind==="DIRECT_COMPANY"));
    if(term&&!direct&&!JSON.stringify(group).normalize("NFKC").toLowerCase().includes(term.normalize("NFKC").toLowerCase()))continue;
    const card=node("article","finding"),decreasing=group.economic_driver==="DEMAND_CONTRACTION",recovering=group.economic_driver==="DEMAND_RECOVERY",policy=group.economic_driver==="POLICY_ENABLEMENT";
    const recoveryProducts=[...group.products,...(group.removed_products||[]),...(group.removed_action_contexts||[])];
    const policyService=policy&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="BUSINESS_START")));
    const policyInvestment=policy&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="INVESTMENT_EXECUTION")));
    const policyMarket=policy&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="MARKET_ENTRY")));
    const policyCustomer=policy&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="CUSTOMER_ACQUISITION")));
    const policyDelivery=policy&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="DELIVERY_START")));
    const policyContract=policy&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="CONTRACT")));
    const policyCapacity=policy&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="CAPACITY_ADDITION")));
    const recoveryContract=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="CONTRACT")));
    const recoveryDelivery=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="DELIVERY_START")));
    const recoveryProduction=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="PRODUCTION_START")));
    const recoveryCapacity=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="CAPACITY_ADDITION")));
    const recoveryInvestment=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="INVESTMENT_EXECUTION")));
    const recoveryCustomer=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="CUSTOMER_ACQUISITION")));
    const recoveryMarket=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="MARKET_ENTRY")));
    const recoveryService=recovering&&recoveryProducts.some(p=>p.actions.some(a=>a.sources.some(s=>s.action==="BUSINESS_START")));
    card.append(node("h4","",(group.status==="PERIOD_CONTEXT_ONLY"?"복수 제품의 과거 비교 맥락 · ":policy?"복수 제품 동일 정책 반응 후보 · ":decreasing?"복수 제품 수요 감소 공통 원인 후보 · ":recovering?"복수 제품 수요·주문 회복 공통 원인 후보 · ":"복수 제품 공통 원인 후보 · ")+(policy?group.policy_cause_key.filter(Boolean).join(" / "):group.destination_expressions.join(" / "))));
    card.append(node("p","",policyService?"같은 명시 정책 범위에 따른 명시 서비스 개시와 기존 기업 행동을 비교한 가설 · 원문 서비스명과 계획 후속을 보존하며 고객·이용량·납품·매출·수혜를 확정하지 않습니다.":policyInvestment?"같은 명시 정책 범위에 따른 투자 집행과 기존 기업 행동을 비교한 가설 · 같은 명시 프로젝트의 결정→집행은 후속 맥락이며 자금 지급·완공·가동·물량·매출·수혜를 확정하지 않습니다.":policyMarket?"같은 명시 정책 범위에 따른 명시 시장 진출과 기존 기업 행동을 비교한 가설 · 각 진출시장은 출처별로 보존하고 정책 관할·대상국·고객회사와 구별합니다. 계약·납품·매출·시장 전체 수혜를 확정하지 않습니다.":policyCustomer?"같은 명시 정책 범위에 따른 신규 고객 확보와 기존 기업 행동을 비교한 가설 · 미명시 고객 실명·ID·확정 관계·규모를 추정하지 않으며 계약·납품·매출·수혜를 확정하지 않습니다.":policyDelivery?"같은 명시 정책 범위에 따른 납품·공급 개시와 생산·체결 행동을 비교한 가설 · 개시와 완납·실물량·매출·수혜를 구별하며 미명시 고객회사·확정 관계를 추정하지 않습니다.":policyContract?"같은 명시 정책 범위에 따른 공급계약 체결·생산 행동을 비교한 가설 · 체결과 실제 이행·납품·매출·수혜를 구별하며 미명시 계약 상대방·규모를 추정하지 않습니다.":policyCapacity?"같은 명시 정책 범위에 따른 생산능력 확대·생산 개시 보도를 비교한 가설 · 생산 단계와 능력을 구별하며 완공·가동률·실물량·매출·수혜를 확정하지 않습니다.":policy?"같은 명시 정책 범위에 따른 생산 개시 보도를 비교한 가설 · 정책 관할·대상국은 수요처가 아닙니다. 법적 효력·장벽 해소·거래·매출·수혜를 확정하지 않습니다.":decreasing?"같은 명시 수요처의 수요 감소 보도를 비교한 가설 · 실제 생산량·매출·손실의 독립 확인이 아닙니다. 경제적 감소 방향과 근거 철회에 따른 후보 상태는 구별합니다. 거래·수혜·대장주 확정이 아닙니다.":recoveryService?"같은 명시 수요처의 수요·주문 회복에 따른 명시 서비스 개시와 기존 행동을 비교한 가설 · 각 서비스명과 계획 후속을 구별하며 고객·이용량·납품·매출·수혜를 확정하지 않습니다.":recoveryMarket?"같은 명시 수요처의 수요·주문 회복에 따른 시장 진출과 기존 행동을 비교한 가설 · 각 진출시장은 출처별로 보존하며 수요처·고객회사·실제 매출·시장 전체 수혜로 바꾸지 않습니다.":recoveryCustomer?"같은 명시 수요처의 수요·주문 회복에 따른 고객 확보·투자·생산·상업 행동을 단계별로 비교한 가설 · 수요처를 고객회사로 만들지 않으며 미명시 고객·계약·납품·매출·수혜를 확정하지 않습니다.":recoveryInvestment?"같은 명시 수요처의 수요·주문 회복에 따른 투자 집행·능력 확대·생산·체결·재개·납품 근거를 단계별로 비교한 가설 · 집행 보도는 실제 자금 지급·설비 완공·가동·물량·매출·수혜의 독립 확인이 아닙니다.":recoveryCapacity?"같은 명시 수요처의 수요·주문 회복에 따른 생산능력 확대·생산 개시·체결·재개·납품 근거를 단계별로 비교한 가설 · 능력 확대 보도는 실제 생산량·가동률·물량·매출·수혜·시장 전체 회복의 독립 확인이 아닙니다.":recoveryProduction?"같은 명시 수요처의 수요·주문 회복에 따른 생산 개시·체결·재개·납품 근거를 단계별로 비교한 가설 · 생산 개시 보도는 증설·물량·상업 납품·매출·수혜·시장 전체 회복의 독립 확인이 아닙니다.":recoveryDelivery?"같은 명시 수요처의 수요·주문 회복에 따른 체결·재개·납품/공급 개시 근거를 단계별로 비교한 가설 · 개시 보도는 완납·물량·매출·수혜·시장 전체 회복의 독립 확인이 아닙니다.":recoveryContract?"같은 명시 수요처의 수요·주문 회복에 따른 계약 체결·공급 재개 근거를 단계별로 비교한 가설 · 실제 이행·납품·물량·매출·수혜·시장 전체 회복의 독립 확인이 아닙니다.":recovering?"같은 명시 수요처의 수요·주문 회복과 공급·생산 재개 보도를 비교한 가설 · 수요/주문 근거를 구별하며 실제 물량·매출·수혜·시장 전체 회복의 독립 확인이 아닙니다. 경제 회복과 근거의 재활성화 상태는 구별합니다.":"같은 명시 수요처의 수요 증가 보도를 비교한 가설 · 기존 제품별 테마는 유지합니다. 거래·수혜·대장주 확정이 아닙니다."));
    card.append(node("p","","독립 행동 "+group.distinct_action_groups+"개 · 식별된 기업 "+group.identified_company_count+"개 · 미식별 기업 맥락 "+group.unresolved_company_contexts+"개 (테마 간 동일 기업으로 합치지 않음)"));
    if(policy)card.append(node("p","","출처의 서로 다른 당사자 이름 "+group.source_actor_name_count+"개 · 동일 이름의 기업 동일성은 별도 확인이 필요합니다."));
    const change=group.period_change;
    if(change?.status==="READY"){
      card.append(node("p","",(change.formed_in_period?"기간 내 복수 제품 형성 · 기준점 대비 (전체 이력 최초 확정 아님) · ":"")+"새 제품: "+(change.new_products.join(" · ")||"없음")+" · 새 독립 행동 "+change.new_action_group_ids.length+"개 · 제외 행동 "+change.removed_action_group_ids.length+"개"));
      card.append(node("p","","비교 기준: "+change.baseline+" · 기간 시작 "+change.since+" · 기간 말 "+change.as_of+" · 자료 부재만으로 약화·무효를 추정하지 않습니다."));
      const baseline=node("details","finding-detail");baseline.append(node("summary","","기간 직전 제품·판본 기준"));
      for(const pin of change.before.theme_snapshots)baseline.append(node("p","",pin.theme_id+" · "+pin.decision_at+" · SHA: "+pin.sha256));
      for(const context of change.investment_stage_contexts||[]){
        const link=context.stored_stage_link,stage=node("details","finding-detail");
        stage.append(node("summary","","기존 명시 투자 프로젝트의 결정→집행 후속 · 새 독립 행동으로 세지 않음"),node("p","",link.project_name+" · 결정 "+link.decision_event_id+" · 집행 "+link.execution_event_id));
        stage.append(node("p","","기준 판본: "+context.before_snapshot.decision_at+" · SHA: "+context.before_snapshot.sha256),node("p","","현재 판본: "+context.after_snapshot.decision_at+" · SHA: "+context.after_snapshot.sha256));
        for(const source of link.sources){const a=node("a","source-link","저장된 투자 단계 출처");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";stage.append(a,node("p","","근거 SHA: "+source.evidence_sha256))}
        card.append(stage);
      }
      for(const context of change.service_stage_contexts||[]){
        const stage=node("details","finding-detail"),link=context.stored_followup;
        stage.append(node("summary","",link?"기존 명시 서비스의 계획→개시 후속 · 새 독립 행동으로 세지 않음":"기존 서비스 사건의 판본/단계 갱신 · 계획 실현 확정 아님"));
        if(link)stage.append(node("p","",link.service_name+" · 계획 "+link.planned_event_id+" · 개시 "+link.realization_event_id));
        stage.append(node("p","","기준 판본: "+context.before_snapshot.decision_at+" · SHA: "+context.before_snapshot.sha256),node("p","","현재 판본: "+context.after_snapshot.decision_at+" · SHA: "+context.after_snapshot.sha256));
        for(const source of context.sources){const a=node("a","source-link","저장된 서비스 단계 출처");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";stage.append(node("p","",(source.service_name||"서비스명 미확인")+" · "+actionLabel(source)),a,node("p","","가용: "+source.source_available_at+" · 관측: "+source.recorded_at+" · 근거 SHA: "+source.evidence_sha256))}
        card.append(stage);
      }
      for(const context of change.existing_policy_action_contexts||[]){
        const stage=node("details","finding-detail");stage.append(node("summary","","기존 정책 사건의 판본/단계 갱신 · 새 독립 행동으로 세지 않음"));
        stage.append(node("p","","기준 판본: "+context.before_snapshot.decision_at+" · SHA: "+context.before_snapshot.sha256),node("p","","현재 판본: "+context.after_snapshot.decision_at+" · SHA: "+context.after_snapshot.sha256));
        for(const source of context.sources){const a=node("a","source-link","정책 사건의 저장 출처");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";stage.append(node("p","",actionLabel(source)+" · "+source.policy_cause.source_expression),a,node("p","","가용: "+source.source_available_at+" · 관측: "+source.recorded_at+" · 근거 SHA: "+source.evidence_sha256))}
        card.append(stage);
      }
      card.append(baseline);
    }else if(change)card.append(node("p","","기간 변화 미확인 · 기준 판본/근거를 확인할 수 없습니다. 현재 근거와 구분합니다."));
    for(const product of [...group.products,...(group.removed_products||[]),...(group.removed_action_contexts||[])]){
      const box=node("details","finding-detail");box.append(node("summary","",product.product+" · "+product.theme_status));
      const contextLabel={EXISTING_PRODUCT_CONTEXT:"기존 비교 맥락 · 활동 필터의 새 테마로 세지 않음",HISTORICAL_REMOVED_PRODUCT:"현재 제품 후보에서 제외된 과거 근거",HISTORICAL_REMOVED_ACTION:"현재 행동에서 제외된 과거 근거"}[product.context_kind];
      if(contextLabel)box.append(node("p","",contextLabel));
      if(product.current_snapshot)box.append(node("p","","현재 상태: "+product.current_theme_status+" · 현재 판본: "+product.current_snapshot.decision_at+" · SHA: "+product.current_snapshot.sha256));
      box.append(node("p","","제품별 테마: "+product.theme_id+" · 판본: "+product.decision_at+" · SHA: "+product.theme_snapshot_sha256));
      if(product.invalidated_event_ids.length)box.append(node("p","","현재 제외된 사건 "+product.invalidated_event_ids.length+"개 · 기존 제품별 철회 근거도 확인하세요."));
      for(const action of product.actions){
        if(change?.status==="READY"&&action.period_action_group_ids?.some(id=>change.new_action_group_ids.includes(id)))box.append(node("p","","기간 내 새 독립 행동 · 단순 추가 보도/식별 갱신과 구분"));
        box.append(node("h5","",action.display_name),node("p","",action.identity_status==="IDENTIFIED"?"식별된 사건 당사자":"출처 이름 맥락 · 기업 동일성 미확인"));
        for(const source of action.sources){
          box.append(node("p","",actionLabel(source)+" · "+(source.in_period?"기간 내 관측 근거":"기간 이전 맥락")),node("p","","원문 원인: "+source.cause.source_expression));
          renderReportedContractAmount(box,source.cause);renderReportedDemandReduction(box,source);renderReportedRecoveryContract(box,source);renderReportedRecoveryDelivery(box,source);renderReportedRecoveryProduction(box,source);renderReportedRecoveryCapacity(box,source);renderReportedRecoveryInvestment(box,source);renderReportedRecoveryCustomer(box,source);renderReportedRecoveryMarket(box,source);renderReportedRecoveryService(box,source);renderReportedPolicyProduction(box,source);renderReportedPolicyCapacity(box,source);renderReportedPolicyContract(box,source);renderReportedPolicyDelivery(box,source);renderReportedPolicyCustomer(box,source);renderReportedPolicyMarket(box,source);renderReportedPolicyInvestment(box,source);renderReportedPolicyService(box,source);
          if(source.demand_recovery_cause)box.append(node("p","","회복 원문 근거: "+(source.demand_recovery_cause.basis==="ORDER"?"주문":"수요")+" · “"+source.demand_recovery_cause.source_expression+"” · SHA: "+source.demand_recovery_cause.expression_sha256));
          if(source.conflicting)box.append(node("p","","상충 보도가 있는 사건 · 해소 또는 수혜 확정 아님"));
          box.append(node("p","","출처 근거 수준: "+source.evidence_level+" · 독립 사실 확인 아님"));
          const a=node("a","source-link","이 제품·기업 행동의 출처");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";box.append(a);
          box.append(node("p","","출처 가용: "+source.source_available_at+" · 관측: "+source.recorded_at+" · 근거 SHA: "+source.evidence_sha256));
        }
      }
      for(const report of product.counterevidence||[]){
        box.append(node("p","","제품 테마에 저장된 "+(report.polarity==="RETRACT"?"철회·정정":"상충 보도")+" · 대상 사건: "+(report.supersedes_event_id||"명시 대상 미확인")));
        const a=node("a","source-link","제품 테마의 반대 근거 출처");a.href=report.source_url;a.target="_blank";a.rel="noopener noreferrer";box.append(a);
        box.append(node("p","","출처 가용: "+report.source_available_at+" · 관측: "+report.recorded_at+" · 실거래 취소 확정 아님"));
      }
      card.append(box);
    }
    parent.append(card);
  }
}
function renderCompanyTimelines(parent,timeline,term,search){
  if(!term||!timeline)return;
  const direct=new Set(Object.entries(search||{}).filter(([,v])=>v.match_kind==="DIRECT_COMPANY").map(([id])=>id));
  const companies=(timeline.companies||[]).filter(c=>c.candidate_ids.some(id=>direct.has(id)));
  const labels={ECONOMIC_ACTION_FIRST_OBSERVED:"경제 행동 최초 관측",SOURCE_REPORTED_FOLLOWUP:"같은 행동의 후속 단계 보도",EVENT_STAGE_UPDATE:"같은 사건의 단계 갱신",ADDITIONAL_SOURCE:"같은 사건의 추가 근거",RELATION_CONTEXT_ADDED:"공급망 관계 맥락 추가"};
  for(const company of companies){
    const card=node("article","finding");card.append(node("h4","","기업별 경제 변화 타임라인 · "+company.display_names.join(" / ")));
    card.append(node("p","","현재 활성 당사자 경제 행동 "+company.distinct_economic_actions+"개 · 기간 내 첫 관측 행동 "+company.new_actions_in_period+"개 · 공급망 관계 맥락 "+company.related_action_contexts+"개"+(company.historical_target_actions?" · 제외된 과거 행동 "+company.historical_target_actions+"개":"")+(company.historical_relation_contexts?" · 활성 제외 사건의 관계 맥락 "+company.historical_relation_contexts+"개":"")));
    if(company.identity_status!=="IDENTIFIED")card.append(node("p","","미식별 출처 이름 · 다른 테마와 기업 동일성 미확인"));
    card.append(node("p","","추가 보도·이름 연결은 새 경제 행동이 아닙니다. 자료가 없는 날짜는 약화·무효를 뜻하지 않습니다."));
    if(company.period_evidence_status==="NO_NEW_EVIDENCE")card.append(node("p","","선택 기간 새 근거 없음 · 약화·무효를 뜻하지 않습니다."));
    for(const entry of company.entries){
      const box=node("details","finding-detail");
      box.append(node("summary","",entry.observed_at+" · "+(entry.in_period?labels[entry.change_kind]:"기간 이전 근거")+" · "+actionLabel(entry)+(entry.counterevidence?.length?" · 반대 근거 "+entry.counterevidence.length+"건":"")+(entry.relation_counterevidence?.length?" · 관계 사건 맥락 "+entry.relation_counterevidence.length+"건":"")));
      if(!entry.in_period&&entry.period_evidence_kinds?.length)box.append(node("p","","기간 이전 대상 사건 · 아래 새 근거를 이해하기 위한 맥락"));
      box.append(node("p","",entry.theme_name+" · "+(entry.company_participation==="SUPPLY_CHAIN_CONTEXT"?"공급망 관계 기업 · 직접 행동 주체 아님":"출처의 사건 당사자")));
      box.append(node("p","",entry.cause.source_expression?"저장된 원인 표현: “"+entry.cause.source_expression+"”":"원인 유형: "+(economicDriverLabels[entry.economic_driver]||"미확인")+" · 원문 근거 미확인"));
      renderReportedContractAmount(box,entry.cause);renderReportedDemandReduction(box,entry);renderReportedRecoveryContract(box,entry);renderReportedRecoveryDelivery(box,entry);renderReportedRecoveryProduction(box,entry);renderReportedRecoveryCapacity(box,entry);renderReportedRecoveryInvestment(box,entry);renderReportedRecoveryCustomer(box,entry);renderReportedRecoveryMarket(box,entry);renderReportedRecoveryService(box,entry);renderReportedPolicyProduction(box,entry);renderReportedPolicyCapacity(box,entry);renderReportedPolicyContract(box,entry);renderReportedPolicyDelivery(box,entry);renderReportedPolicyCustomer(box,entry);renderReportedPolicyMarket(box,entry);renderReportedPolicyInvestment(box,entry);renderReportedPolicyService(box,entry);
      if(entry.extraction_method==="AI_SOURCE_SPAN_MATCHED")box.append(node("p","","AI 해석의 원문 근거 · 독립 사실 확인 아님"));
      if(entry.identity_available_at)box.append(node("p","","기업 식별 연결 확보: "+entry.identity_available_at+" · 사건의 최초 관측과 별도"));
      box.append(node("p","","출처 가용: "+entry.source_available_at+" · 최초 기록: "+entry.recorded_at+" · 선택 판본: "+entry.decision_at));
      const a=node("a","source-link","이 사건·역할의 출처");a.href=entry.source_url;a.target="_blank";a.rel="noopener noreferrer";box.append(a);
      if(entry.current_activity==="EXCLUDED_BY_STORED_RETRACTION")box.append(node("p","","저장된 철회·정정에 따라 현재 활성 사건에서 제외 · 당시 관측 사실은 보존"));
      for(const proof of entry.counterevidence||[]){
        box.append(node("p","",(proof.in_period?"기간 내 새 직접 반대 근거 · ":"기간 이전 직접 반대 근거 · ")+(proof.polarity==="RETRACT"?"대상 사건의 철회·정정 근거 · 실거래 취소 확정 아님":"대상 사건의 상충 보도 · 실거래 취소 확정 아님")));
        const a=node("a","source-link","이 사건을 명시한 반대 근거 출처");a.href=proof.source_url;a.target="_blank";a.rel="noopener noreferrer";box.append(a);
        box.append(node("p","","대상 사건: "+proof.target_event_id+" · 근거 수준: "+({OFFICIAL_SOURCE:"공식 출처 보도",REPORTED:"출처 보도",INFERRED:"추론"}[proof.evidence_level]||"미확인")));
        box.append(node("p","","출처 가용: "+proof.source_available_at+" · 관측: "+proof.recorded_at));
        if(proof.reason)box.append(node("p","","원문 문서 ID 미확인 · 저장 출처 해시로 연결"));
      }
      for(const proof of entry.relation_counterevidence||[]){
        box.append(node("p","",(proof.context_in_period?"기간 내 새 관계 사건 맥락 · ":"기간 이전 관계 사건 맥락 · ")+"이 기업의 직접 행동 철회·실거래 취소·수혜 소멸 확정 아님"));
        box.append(node("p","",(proof.polarity==="RETRACT"?"연결 사건의 철회·정정 근거":"연결 사건의 상충 보도")+" · 원래 당사자 "+proof.target_actor_ids.join(" · ")));
        if(entry.current_activity==="RELATION_EVENT_CONTEXT_EXCLUDED")box.append(node("p","","연결 사건은 현재 활성에서 제외 · 과거 관계 관측은 보존"));
        for(const url of proof.relationship.source_urls){const a=node("a","source-link","원래 공급망 관계 출처");a.href=url;a.target="_blank";a.rel="noopener noreferrer";box.append(a)}
        box.append(node("p","","관계 출처 가용: "+proof.relationship.source_available_at+" · 관계 확보: "+proof.relationship.linked_at));
        const a=node("a","source-link","연결 사건의 반대 근거 출처");a.href=proof.source_url;a.target="_blank";a.rel="noopener noreferrer";box.append(a);
        box.append(node("p","","관계 사건 맥락 확보: "+proof.context_observed_at+" · 반대 근거 가용: "+proof.source_available_at+" · 관측: "+proof.recorded_at+" · 근거 수준: "+({OFFICIAL_SOURCE:"공식 출처 보도",REPORTED:"출처 보도",INFERRED:"추론"}[proof.evidence_level]||"미확인")));
        if(proof.reason)box.append(node("p","","문서 ID 미확인 · 저장 바인딩/해시로 관계 맥락 연결"));
      }
      if(entry.company_participation==="SUPPLY_CHAIN_CONTEXT"&&!entry.relation_counterevidence?.length&&entry.relation_counterevidence_status!=="LINKED_CONTEXT")box.append(node("p","","관계 사건 반대 근거: 검증된 연결 없음"));
      renderEventImpactPaths(box,entry);card.append(box);
    }
    parent.append(card);
  }
  const ids=new Set(Object.values(search||{}).filter(v=>v.match_kind==="DIRECT_COMPANY").map(v=>v.entity_id));
  const unresolved=(timeline.counterevidence_unresolved||[]).filter(e=>e.entity_ids.some(id=>ids.has(id)||id.normalize("NFKC").toLowerCase()===term.normalize("NFKC").toLowerCase()));
  if(unresolved.length){
    const box=node("article","finding");box.append(node("h4","","대상 사건 연결 미확인"));
    const reasons={TARGET_NOT_SPECIFIED:"대상 사건 ID 미명시",TARGET_NOT_FOUND:"해당 사건 근거 없음",TARGET_NOT_AVAILABLE_BEFORE_REPORT:"반대 근거 이전의 대상 판본 미확인",COMPANY_BINDING_MISMATCH:"당시 기업 바인딩 불일치",COMPANY_ID_UNRESOLVED:"기업 식별 또는 동일 원문 바인딩 미확인",TARGET_SOURCE_VERSION_MISMATCH:"당시 원문 판본 바인딩 불일치",HISTORICAL_VERSION_UNAVAILABLE:"과거 근거 판본을 읽지 못해 대상 연결 미확인"};
    for(const e of unresolved){box.append(node("p","",reasons[e.reason]||"정확한 대상 미확인"),node("p","","대상 사건: "+(e.target_event_id||"미명시")+" · 근거 수준: "+({OFFICIAL_SOURCE:"공식 출처 보도",REPORTED:"출처 보도",INFERRED:"추론"}[e.evidence_level]||"미확인")));const a=node("a","source-link","대상 연결이 미확인인 출처");a.href=e.source_url;a.target="_blank";a.rel="noopener noreferrer";box.append(a,node("p","","출처 가용: "+e.source_available_at+" · 관측: "+e.recorded_at));}
    parent.append(box);
  }
}
function comparisonExportURL(pin,term){
  const params=new URLSearchParams({as_of:pin.as_of,activity:pin.activity,q:term.trim()});
  if(pin.since)params.set("since",pin.since);
  return "/api/comparison-export?"+params.toString();
}
async function downloadComparison(){
  const pin=currentData?.comparison_export?.query;if(!pin)return;
  const button=$("comparison-export"),message=$("comparison-export-status");button.disabled=true;
  message.textContent="고정 조회 결과를 준비하는 중…";
  try{
    const response=await fetch(comparisonExportURL(pin,$("item-filter").value),{cache:"no-store"});
    if(!response.ok)throw new Error("비교 결과를 내보내지 못했습니다.");
    const bytes=await response.arrayBuffer(),digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
    if(digest!==response.headers.get("X-Content-SHA256"))throw new Error("비교 결과 SHA가 일치하지 않습니다.");
    const result=JSON.parse(new TextDecoder().decode(bytes)),preview=$("comparison-export-preview");
    preview.replaceChildren(node("h4","","내보낸 비교 결과"),node("p","fineprint","선택 판본의 제품별 기업·출처 비교 "+Object.keys(result.product_comparisons).length+"개를 포함합니다. 아래는 검색에 맞는 복수 제품·기간 비교입니다."));
    renderCrossProductDemand(preview,result.comparison);
    const url=URL.createObjectURL(new Blob([bytes],{type:"application/json"})),link=document.createElement("a");
    link.href=url;link.download="comparison_export_"+digest+".json";document.body.append(link);link.click();link.remove();URL.revokeObjectURL(url);
    message.textContent="로컬 파일 내려받기 · SHA-256 "+digest+" · 외부 소비·연동 완료를 의미하지 않습니다.";
  }catch(error){message.textContent=error.message||"내보내기 실패"}finally{button.disabled=!currentData?.comparison_export}
}
function renderItems(){
  if(!currentData)return;
  const term=$("item-filter").value.trim().toLocaleLowerCase();
  const matches=currentData.items.filter(x=>matchesFinding(x,term));
  const visible=matches.slice(0,shown);
  $("item-total").textContent=visible.length+" / "+matches.length+"건";
  $("items").replaceChildren();
  if(!matches.length)$("items").append(node("p","empty",term?"검색 결과가 없습니다.":"이 기간에 저장된 분석 기록이 없습니다. 다른 날짜를 선택하거나 메모를 남길 수 있습니다."));
  for(const item of visible){
    const card=node("article","finding"),meta=node("div","finding-meta");
    meta.append(node("span","",item.day+" · "+item.provider),node("span","pill",["HIGH_REVIEW","HIGH_PRIORITY_CANDIDATE"].includes(item.priority)?"분석 우선":item.priority==="PARTIAL_EVIDENCE_ONLY"?"근거 보류":"분석 후보"));
    const ai={"NOT_ELIGIBLE":"AI 미사용","AWAITING_EXPLICIT_AI_AUTHORIZATION":"AI 설정 미활성","AI_DISABLED_BY_CONFIGURATION":"AI 설정 미활성","ANALYZED_UNVERIFIED":"AI 해석·미검증","CACHE_HIT":"기존 AI 해석"}[item.ai_status]||"AI 결과 없음";
    card.append(meta,node("h4","",item.headline),node("p","finding-detail",[categoryLabel(item),ai,"미확인 "+item.uncertainty_count+"개"].join(" · ")));
    if(item.source_products?.length)card.append(node("p","finding-detail","제목에 명시된 제품·서비스·기술: "+item.source_products.join(", ")));
    if(item.ai_summary){
      card.append(node("p","finding-detail",(item.analysis_purpose==="EXISTING_ARTICLE"?"기존 기사 AI 분석":"AI 분석")+" · "+(item.content_scope==="LICENSED_ARTICLE_TEXT"?"허가된 기사 본문 기준":"제목 기준")));
      card.append(node("p","",item.ai_summary));
      for(const claim of item.ai_claims||[])card.append(node("p","finding-detail","해석: "+claim));
      for(const unknown of item.ai_uncertainties||[])card.append(node("p","finding-detail","미확인: "+unknown));
    }
    for(const match of item.company_identity?.matches||[])card.append(node("p","finding-detail","기업 식별: "+match.source_name+" · "+match.entity_id+" (공시 명부 이름 일치 · 거래·수혜 확정 아님)"));
    if(item.semantic_analysis?.analysis){
      const evidenceScope=item.content_scope==="LICENSED_ARTICLE_TEXT"?"본문":"제목";
      card.append(node("p","finding-detail","AI 사건 해석 · "+evidenceScope+" 근거 대조 · 독립 사실 확인 아님"));
      if(item.ai_summary!==item.semantic_analysis.analysis.summary)card.append(node("p","",item.semantic_analysis.analysis.summary));
      if(item.bound_title)card.append(node("p","finding-detail","연결된 기사 제목: "+item.bound_title));
      card.append(node("p","finding-detail","의미 분석 시각: "+item.semantic_analysis.analysis.available_at));
      for(const event of item.semantic_analysis.events||[]){
        card.append(node("p","finding-detail","주체: "+(event.actors.join(", ")||"미확인")+" · "+(economicActionLabels[event.action]||event.action)+" · "+(economicPhaseLabels[event.phase]||event.phase)));
        card.append(node("p","finding-detail",evidenceScope+" 근거: "+event.quote));
        card.append(node("p","finding-detail",event.cause_quote?"원인 근거: "+event.cause_quote:"명시된 공통 원인 없음 · 개별 관찰"));
      }
    }
    for(const change of item.economic_changes||[])card.append(node("p","finding-detail","경제 변화: "+change.topic+" · "+(economicActionLabels[change.action]||change.action)+" · "+(economicPhaseLabels[change.phase]||change.phase)));
    if(item.content_scope==="LICENSED_ARTICLE_TEXT")card.append(node("p","finding-detail","본문 확인: "+item.source_available_at+" · 첨부자료 제외"));
    const link=node("a","source-link","출처 열기 ↗");link.href=item.source_url;link.target="_blank";link.rel="noopener noreferrer";card.append(link);$("items").append(card)
  }
  $("more-items").hidden=visible.length>=matches.length;
  renderThemes(term);
  renderCompanyIdentities(term);
}
function render(data){
  currentData=data;shown=20;
  $("comparison-export").disabled=!data.comparison_export;$("comparison-export-status").textContent="";$("comparison-export-preview").replaceChildren();
  $("period-kind").textContent={day:"DAILY VIEW",week:"WEEKLY REVIEW",month:"MONTHLY REVIEW"}[data.view];
  $("period-title").textContent=data.view==="day"?niceDate(data.start):data.view==="week"?"주간 조사 돌아보기":"월간 조사 돌아보기";
  $("period-range").textContent=data.start===data.end?data.start:data.start+" ~ "+data.end;
  $("count-items").textContent=data.counts.items;$("count-review").textContent=data.counts.review;$("count-held").textContent=data.counts.held;$("count-ai").textContent=data.counts.ai_analyzed;
  $("feedback-title").textContent=data.view==="day"?"일간 자동 정리":data.view==="week"?"일간 기록 주간 피드백":"주간 결과 월간 피드백";
  $("feedback").replaceChildren(...data.feedback.map(line=>node("li","",line)));
  $("breakdown-panel").hidden=data.view==="day";
  $("breakdown-title").textContent=data.view==="week"?"일간 기록":"주간 결과";
  $("breakdown").replaceChildren();
  const max=Math.max(1,...data.children.map(x=>x.items));
  for(const child of data.children){const row=node("div","breakdown-row"),track=node("div","bar-track"),bar=node("span","bar");bar.style.width=(child.items?Math.max(5,child.items/max*100):0)+"%";track.append(bar);row.append(node("span","",child.label),track,node("strong","",child.items+"건"));$("breakdown").append(row)}
  renderItems();
  showNotes($("own-notes"),data.notes,"아직 이 기간의 메모가 없습니다.");
  $("inherited-panel").hidden=data.view==="day";$("inherited-title").textContent=data.view==="week"?"일간 메모":"주간 메모";
  showNotes($("inherited-notes"),data.inherited_notes,"하위 기간의 메모가 아직 없습니다.");
  $("source-count").textContent="저장 보고서 "+(data.source.saved_reports_seen||0)+"개 중 읽기 제외 "+(data.source.saved_reports_skipped||0)+"개";
}
async function load(){status("저장된 조사 기록을 불러오는 중…");for(const button of document.querySelectorAll("[data-view]"))button.classList.toggle("active",button.dataset.view===state.view);$("date").value=state.date;try{const response=await fetch("/api/period?view="+encodeURIComponent(state.view)+"&date="+encodeURIComponent(state.date)+"&theme_activity="+encodeURIComponent($("theme-activity").value)+"&theme_sort="+encodeURIComponent($("theme-sort")?.value||"latest")+"&timeline_activity="+encodeURIComponent($("timeline-activity")?.value||"all"),{cache:"no-store"});if(!response.ok)throw new Error("조사 기록을 읽지 못했습니다.");render(await response.json());status("")}catch(error){status(error.message||"불러오기에 실패했습니다.",true)}}
for(const button of document.querySelectorAll("[data-view]"))button.addEventListener("click",()=>{state.view=button.dataset.view;load()});
$("theme-activity").addEventListener("change",()=>load());
$("theme-sort").addEventListener("change",()=>load());
$("timeline-activity").addEventListener("change",()=>load());
$("date").addEventListener("change",event=>{if(event.target.value){state.date=event.target.value;load()}});
$("previous").addEventListener("click",()=>shift(-1));$("next").addEventListener("click",()=>shift(1));$("today").addEventListener("click",()=>{state.date=new Date().toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"});load()});
$("comparison-export").addEventListener("click",downloadComparison);
$("item-filter").addEventListener("input",()=>{shown=20;renderItems()});$("more-items").addEventListener("click",()=>{shown+=20;renderItems()});
$("note-text").addEventListener("input",event=>{$("note-count").textContent=event.target.value.length+" / 2000"});
$("note-form").addEventListener("submit",async event=>{event.preventDefault();const text=$("note-text").value.trim();if(!text)return;status("메모를 저장하는 중…");try{const response=await fetch("/api/notes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({view:state.view,date:state.date,text})});if(!response.ok)throw new Error("메모를 저장하지 못했습니다.");$("note-text").value="";$("note-count").textContent="0 / 2000";await load()}catch(error){status(error.message,true)}});
load();

function renderThemes(term){
  const candidates=currentData.company_candidates||[];
  const search=companySearchResults(currentData.company_search?.candidates,term);
  const themes=(currentData.themes||[]).filter(x=>matchesTheme(x,term,candidates.filter(c=>c.theme_id===x.theme_id),currentData.theme_changes?.[x.theme_id],currentData.theme_presentations?.[x.theme_id])||candidates.some(c=>c.theme_id===x.theme_id&&["DIRECT_COMPANY","AMBIGUOUS_NAME"].includes(search[c.candidate_id]?.match_kind)));
  $("theme-total").textContent=themes.length+"개";$("themes").replaceChildren();
  renderCrossProductDemand($("themes"),currentData.cross_product_demand,term,search);
  renderCompanyTimelines($("themes"),currentData.company_timelines,term,companySearchResults(currentData.timeline_search_context||currentData.company_search?.candidates,term));
  if(!themes.length)$("themes").append(node("p","empty-small",currentData.theme_status==="UNAVAILABLE"?"테마 기록을 읽지 못했습니다. 뉴스 분석 기록은 계속 표시합니다.":"이 시점·검색 조건에 해당하는 테마 후보가 없습니다."));
  const labels={CANDIDATE:"관찰 후보",EMERGING:"형성 중",EXPANDING:"확산",WEAKENING:"약화",INVALIDATED:"무효",REACTIVATED:"재활성화"};
  if(currentData.theme_order?.mode==="actions")$("themes").append(node("p","fineprint","정렬: 기간 비교가 있는 후보 → 독립 행동 추가 수 → 신규 당사자 수 → 최근 갱신 → 테마 ID 내림차순. 증가가 없는 후보도 표시합니다."));
  for(const theme of themes){
    const card=node("article","finding"),meta=node("div","finding-meta");
    meta.append(node("span","pill",labels[theme.status]||theme.status),node("span","","사건 후보 "+theme.scores.distinct_economic_events+" · 기업 "+theme.scores.company_breadth));
    const activity=currentData.theme_activity?.[theme.theme_id];
    if(activity==="new"||activity==="updated")meta.append(node("span","pill",activity==="new"?"기간 내 신규":"기간 내 갱신"));
    const title=themeTitle(theme,currentData.theme_presentations?.[theme.theme_id]);
    card.append(meta,node("h4","",title),node("p","finding-detail","최초 발견: "+theme.first_detected_at),node("p","finding-detail","최근 근거: "+theme.last_evidence_at));
    if(title!==theme.provisional_name){const saved=node("details","finding-detail");saved.append(node("summary","","저장 당시 테마명"),node("p","",theme.provisional_name));card.append(saved)}
    renderThemeActionOrder(card,currentData.theme_order?.entries?.[theme.theme_id]);
    renderThemeChanges(card,currentData.theme_changes?.[theme.theme_id],labels);
    if(["DEMAND_EXPANSION","DEMAND_RECOVERY","DEMAND_CONTRACTION","PRODUCT_PRICE_INCREASE","PRODUCT_PRICE_DECREASE"].includes(theme.economic_driver)){
      const refs=theme.source_refs.filter(r=>r.polarity==="SUPPORT"&&!theme.invalidated_event_ids.includes(r.event_id));
      const scopes=[...new Set(refs.map(r=>r.demand_scope?(r.demand_scope.status==="EXPLICIT"?r.demand_scope.destination+"용":"복수·불명확 (공통 수요처 미확인)"):"N/A (수요처 미명시)"))];
      card.append(node("p","finding-detail","보도된 수요처 범위: "+scopes.join(" · ")+" · 고객회사·계약·수혜 확인을 뜻하지 않습니다."));
    }
    if(theme.topic_aliases?.length>1)card.append(node("p","finding-detail","같은 주제 표기: "+theme.topic_aliases.join(" · ")));
    for(const ref of theme.source_refs.filter(r=>r.topic_alias_evidence)){
      const proof=ref.topic_alias_evidence,detail=node("details","finding-detail");
      detail.append(node("summary","","출처에 명시된 기술명·약어: "+proof.source_expression));
      detail.append(node("p","","이 출처의 병기에만 적용 · 약어만 같은 다른 기사는 자동 연결하지 않습니다."));
      const a=node("a","source-link","병기 근거 출처");a.href=ref.source_url;a.target="_blank";a.rel="noopener noreferrer";detail.append(a);
      detail.append(node("p","","출처 가용: "+ref.source_available_at+" · 연결 확보: "+ref.recorded_at));
      detail.append(node("p","","병기 구간 SHA: "+proof.expression_sha256));card.append(detail);
    }

    card.append(node("p","finding-detail",theme.economic_driver==="UNKNOWN"?"명시된 공통 원인이 없어 개별 사건으로 관찰합니다.":"같은 주제에서 "+(economicDriverLabels[theme.economic_driver]||theme.economic_driver)+"에 연결된 독립 행동 "+theme.scores.distinct_economic_events+"개를 묶었습니다. 원인 연결은 테마 가설입니다."));
    renderCommonCauseComparison(card,theme,candidates,currentData.common_cause_comparisons,currentData.theme_order?.entries?.[theme.theme_id]);
    const relationLabels={REPORTED_DIRECT_TRANSACTION:"출처에 보고된 직접 계약",ANNOUNCED_SUPPLY_PLAN:"공급 계획"};
    const impactLabels={POTENTIAL_BENEFICIARY_UNVERIFIED:"잠재 수혜 (추론)",POTENTIAL_DAMAGE_UNVERIFIED:"잠재 피해 (추론)",ANNOUNCED_SUPPLY_PLAN_UNVERIFIED:"계획 단계 · 실현 미확인",UNKNOWN_RELATIONSHIP:"영향 경로 미확인",EFFECT_DIRECTION_UNKNOWN:"영향 방향 미확인",THEMATIC_ONLY:"단순 테마 연관"};
    for(const company of theme.company_links){
      const names=[...new Set(theme.source_refs.filter(r=>theme.event_ids.includes(r.event_id)).flatMap(r=>r.company_mappings||[]).filter(m=>m.entity_id===company.entity_id).map(m=>m.source_name))];
      const display=names.length?names.join(" / ")+" ("+company.entity_id+")":company.entity_id;
      card.append(node("p","",display+" · "+(company.supply_chain_links?.length?"공급망 근거 연결":"테마 연관")+" · 수혜 미확정"));
      const candidate=candidates.find(c=>c.theme_id===theme.theme_id&&c.entity_id===company.entity_id);
      if(candidate){
        const directoryName=candidate.official_name_context;
        if(directoryName?.status==="MATCHED"&&directoryName.proof.entity_id===candidate.entity_id){
          card.append(node("p","finding-detail","공식 명부 이름: "+directoryName.proof.issuer_name+" · 기사 명시 이름 아님"));
          card.append(node("p","finding-detail","명부 가용: "+directoryName.proof.available_at+" · 이름 연결 확보: "+directoryName.decision_at));
          if(directoryName.name_ambiguous)card.append(node("p","finding-detail","같은 명부 이름의 다른 기업 ID 존재 · 이름만으로 식별 미확정"));
        }
        const match=search[candidate.candidate_id];
        if(match&&match.status==="READY"&&match.theme_snapshot_sha256===candidate.theme_snapshot_sha256&&match.decision_at===candidate.decision_at&&match.entity_id===candidate.entity_id&&match.theme_id===candidate.theme_id){
          const label=companySearchLabel(match.match_kind);
          if(label){
            card.append(node("p","finding-detail",label));
            if(match.match_kind==="DIRECT_COMPANY"&&match.identity_status==="SOURCE_NAME_ONLY")card.append(node("p","finding-detail","출처 이름 일치 · 공식 기업 식별은 미확인"));
            const sources=node("details","finding-detail");sources.append(node("summary","","이 기업의 사건·출처 근거"));
            if(!match.sources.length)sources.append(node("p","","이 판본의 활성 사건 근거 없음"));
            for(const source of match.sources){
              const relationOnly=source.company_participation==="SUPPLY_CHAIN_CONTEXT";
              sources.append(node("p","",(relationOnly?"공급망 관계 기업 · 직접 행동 주체 아님 · 연결 사건: ":"출처의 사건 당사자 · ")+actionLabel(source)+" · 사건 "+source.event_id));
              if(relationOnly)sources.append(node("p","","사건 당사자: "+source.event_entity_ids.join(" · ")));
              sources.append(node("p","",source.extraction_method==="AI_SOURCE_SPAN_MATCHED"?"AI 해석의 원문 근거 · 독립 사실 확인 아님":({OFFICIAL_SOURCE:"공식 출처 보도",REPORTED:"출처 보도",INFERRED:"추론"}[source.evidence_level]||"근거 수준 미확인")));
              sources.append(node("p","","출처 가용: "+source.source_available_at+" · 관측: "+source.recorded_at));
              if(source.impact_paths?.length)renderEventImpactPaths(sources,source);
              const a=node("a","source-link","이 기업 사건의 출처");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";sources.append(a);
            }
            card.append(sources);
          }
        }
        const reasons=node("details","finding-detail");reasons.append(node("summary","","기업 포함 이유·수혜 경로·불확실성"));
        const kinds={SOURCE_REPORTED_INVESTMENT_STAGES:"같은 투자 프로젝트의 단계 보도",SOURCE_REPORTED_PARTICIPANT:"출처에 등장한 당사자",SOURCE_REPORTED_SUPPLY_RELATION:"출처에 보고된 공급 관계",INFERRED_ASSOCIATION:"추론한 연관"};
        for(const [basisIndex,basis] of candidate.inclusion_basis.entries()){
          reasons.append(node("p","",(kinds[basis.kind]||basis.kind)+" · "+basis.reason+(basis.phase?" · "+(economicPhaseLabels[basis.phase]||basis.phase):"")));
          const basisLabel=inclusionBasisLabel(candidate,basis,basisIndex,currentData.company_inclusion_presentations);
          if(basisLabel)reasons.append(node("p","",basisLabel));
          for(const url of basis.source_urls||(basis.source_url?[basis.source_url]:[])){const a=node("a","source-link","포함 근거 원문");a.href=url;a.target="_blank";a.rel="noopener noreferrer";reasons.append(a)}
        }
        const evidence=node("details","finding-detail");evidence.append(node("summary","","저장된 원인·행동 근거 문장"));
        const evidenceBody=node("div","");evidence.append(evidenceBody);let evidenceLoaded=false;
        evidence.addEventListener("toggle",async()=>{
          if(!evidence.open||evidenceLoaded)return;evidenceLoaded=true;
          evidenceBody.replaceChildren(node("p","","저장 근거를 읽고 있습니다."));
          try{
            const end=new Date(currentData.end+"T23:59:59.999+09:00");
            const at=currentData.as_of||new Date(Math.min(end.getTime(),Date.now())).toISOString();
            const params=new URLSearchParams({theme_id:theme.theme_id,entity_id:company.entity_id,as_of:at});
            const response=await fetch("/api/company-evidence?"+params);
            if(!response.ok)throw new Error("unavailable");
            const result=await response.json();evidenceBody.replaceChildren();
            if(!result.items.length)evidenceBody.append(node("p","","N/A · "+result.reason));
            for(const item of result.items){
              const box=node("div","finding-detail");
              box.append(node("p","",(item.content_scope==="RSS_TITLE_METADATA"?"RSS 제목 범위":item.content_scope==="LICENSED_ARTICLE_TEXT"?"허가 본문 범위":"저장 근거")+" · "+(economicActionLabels[item.action]||item.action)+" · "+(economicPhaseLabels[item.phase]||item.phase)));
              box.append(node("p","",item.status==="READY"?item.excerpt:"N/A · "+item.reason));
              if(item.status==="READY"&&item.extraction_method==="AI_SOURCE_SPAN_MATCHED")box.append(node("p","","AI 해석의 원문 근거 · 독립 사실 확인 아님"));
              const a=node("a","source-link","해당 판본의 출처");a.href=item.source_url;a.target="_blank";a.rel="noopener noreferrer";box.append(a);
              box.append(node("p","","출처 가용: "+item.source_available_at+(item.analysis_available_at?" · 분석 가용: "+item.analysis_available_at:"")));
              const history=item.contract_amount_history;
              if(history){
                const amounts=node("details","");amounts.append(node("summary","","보도 계약금액 변경 전후"));
                amounts.append(node("p","","출처가 보도한 계약금액이며 실현 매출·이익·수혜를 뜻하지 않습니다."));
                if(!history.changes.length)amounts.append(node("p","","N/A · "+history.reason));
                for(const revision of history.changes){
                  amounts.append(node("p","","이전 "+(revision.before_amount||"N/A")+" → 변경 후 "+(revision.after_amount||"N/A")));
                  amounts.append(node("p","",revision.status==="READY"?"차액 "+amountText(revision.difference)+" 원 · 증감률 "+revision.percent_change+"%":"N/A · "+revision.reason));
                  for(const [label,source] of [["이전",revision.before_source],["변경 후",revision.after_source]]){
                    amounts.append(node("p","",label+" 보도: "+source.headline));
                    const link=node("a","source-link",label+" 판본 출처");link.href=source.source_url;link.target="_blank";link.rel="noopener noreferrer";amounts.append(link);
                    amounts.append(node("p","","출처 가용: "+source.source_available_at+" · 분석 가용: "+source.analysis_available_at));
                    const proof=node("details","");proof.append(node("summary","",label+" 원본·분석 SHA"));
                    for(const key of ["source_event_sha256","source_title_sha256","analysis_event_sha256","report_sha256"])proof.append(node("p","",key+": "+source[key]));
                    amounts.append(proof);
                  }
                }
                box.append(amounts);
              }
              const hashes=node("details","");hashes.append(node("summary","","사건·원본 판본 SHA"));
              for(const [label,value] of [["사건 ID",item.event_id],["원본 제목/문단 SHA",item.evidence_sha256],["표시 구간 SHA",item.excerpt_sha256],["분석 보고서 SHA",item.report_sha256]])if(value)hashes.append(node("p","",label+": "+value));
              box.append(hashes);evidenceBody.append(box);
            }
          }catch{evidenceBody.replaceChildren(node("p","","N/A · 저장 근거를 읽지 못했습니다. 다른 조사 결과는 계속 사용할 수 있습니다."));evidenceLoaded=false;}
        });reasons.append(evidence);
        reasons.append(node("p","","보도된 제품·사업 주제: "+(candidate.business_context.source_topics.join(" · ")||"미확인")+" · 기업의 실제 사업 구성은 미확인"));
        if(!candidate.benefit_paths.length)reasons.append(node("p","","기업까지 이어지는 수혜 경로: 미확인"));
        for(const path of candidate.benefit_paths)reasons.append(node("p","","수혜 경로: "+path.product_stage+" · "+(impactLabels[path.category]||path.category)+" · 상대 기업 "+path.counterparty_id));
        const financial=candidate.financial_assessment,assessment=financial?.value;
        const identity=candidate.identity_context;
        const identityLabels={MATCHED:"공식 명부의 정확한 이름으로 연결",NOT_IN_SNAPSHOT:"현재 공식 명부에 없는 기업",AMBIGUOUS:"공식 명부에 같은 이름의 기업이 여러 개 있음",NOT_RESOLVED_AS_OF:"조회 시점에 기업 식별 근거 없음",ALREADY_IDENTIFIED:"사건에 공식 기업 코드가 연결됨"};
        if(identity){
          reasons.append(node("p","","기업 식별: "+(identityLabels[identity.status]||"미확인")+(candidate.resolved_entity_id?" · "+candidate.resolved_entity_id:"")));
          if(identity.decision_at)reasons.append(node("p","","식별 근거 확보: "+identity.decision_at));
          for(const match of identity.matches||[])reasons.append(node("p","","명부 근거: "+match.issuer_name+" · "+match.source_id+" · "+match.filing_document_id));
        }
        const missingLabels={IDENTITY_UNRESOLVED:"기업 코드 미확인",NOT_AVAILABLE_AS_OF:"조회 시점에 사용할 평가 없음",COMPANY_NOT_IN_SNAPSHOT:"평가 목록에 없는 기업",AMBIGUOUS_IDENTITY:"기업 코드 연결이 모호함",NOT_CONNECTED:"평가 미연결"};
        if(assessment){
          reasons.append(node("p","","EraLeader 재무 근거 · "+(assessment.annual_fiscal_year?assessment.annual_fiscal_year+"년":"재무기간 미확인")+" · 평가일 "+assessment.assessment_day+" · 시장자료 "+assessment.source_market_session));
          reasons.append(node("p","","재무 위험 항목 "+assessment.financial_risk.assessed_items+" / "+assessment.financial_risk.possible_items+"개 확보 · "+(!assessment.financial_risk.assessed_items?"평가 자료 부족":assessment.financial_risk.signals.length?"위험 신호 있음":"확인 항목에서 위험 신호 미관측 · 안전 확정 아님")));
          for(const [label,items] of [["긍정 관측",assessment.competitiveness.supporting],["약화 관측",assessment.competitiveness.weakening],["위험 신호",assessment.financial_risk.signals]])for(const item of items)reasons.append(node("p","",label+": "+item.reason));
          for(const line of [...assessment.missing,...assessment.limitations])reasons.append(node("p","",line));
          for(const source of Object.values(assessment.sources))if(source.fiscal_year){
            reasons.append(node("p","","재무 출처: "+source.fiscal_year+"년 · "+source.currency+" · 연결재무 · 가용시각 "+source.available_at_utc));
            if(/^[0-9]{14}$/.test(source.report_accession||"")){const a=node("a","source-link","DART 공시 근거");a.href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+source.report_accession;a.target="_blank";a.rel="noopener noreferrer";reasons.append(a)}
          }
          reasons.append(node("p","","평가 게시: "+financial.published_at+" · 이 프로그램에서 확보: "+financial.imported_at));
        }else reasons.append(node("p","","재무 근거: "+(missingLabels[financial?.status]||"미확인")));
        reasons.append(node("p","","현재 가격·투자 매력: 미평가"));
        for(const uncertainty of candidate.uncertainties)reasons.append(node("p","",uncertainty));
        card.append(reasons);
      }
      for(const rel of company.supply_chain_links||[]){
        const detail=node("div","finding-detail");
        detail.append(node("p","",(relationLabels[rel.relation_kind]||rel.relation_kind)+" · "+rel.product_stage+" · "+(rel.role==="supplier"?"공급자 → 고객 ":"고객 ← 공급자 ")+rel.counterparty_id));
        detail.append(node("p","",(impactLabels[rel.impact_category]||rel.impact_category)+" · 동일 문서·기업 근거 · 사건의 인과관계는 미확정"));
        detail.append(node("p","","근거 가용: "+rel.source_available_at+" · 연결: "+rel.linked_at+(rel.conflicting_event_ids.length?" · 상충 보도 있음":"")));
        for(const url of rel.source_urls){const link=node("a","source-link","관계 근거 원문");link.href=url;link.target="_blank";link.rel="noopener noreferrer";detail.append(link)}
        card.append(detail);
      }
    }
    const details=node("details",""),summary=node("summary","","근거와 상태 이력");details.append(summary);
    const actions=economicActionLabels;
    const phases=economicPhaseLabels;
    renderInvestmentStages(details,theme.investment_stage_links);
    for(const followup of theme.event_followups||[])details.append(node("p","finding-detail",followup.service_name+" · 계획 → 개시 보도 연결 · 독립 사건 1개 · 실제 실현·매출·수혜는 미확인"));
    for(const ref of theme.source_refs){const link=node("a","source-link",(ref.entity_ids?.join(", ")||"기업 미식별")+" · "+(ref.topic||theme.provisional_name)+" · "+(actions[ref.action]||ref.action)+" · "+(phases[ref.phase]||ref.phase)+" · "+(ref.content_scope==="RSS_TITLE_METADATA"?"제목 근거 · ":"")+ref.evidence_level+(ref.extraction_method?" · AI 해석/제목 대조":""));link.href=ref.source_url;link.target="_blank";link.rel="noopener noreferrer";details.append(link)}
    for(const item of theme.history)details.append(node("p","finding-detail",item.decision_at+" · "+(labels[item.status]||item.status)));
    card.append(details);$("themes").append(card);
  }
}

function renderInvestmentStages(parent,links){
  for(const link of links||[]){
    parent.append(node("p","finding-detail",link.project_name+" · 투자 결정 → 집행 보도 연결 · 실제 지출·거래·수혜는 독립 확인되지 않음"));
    for(const [i,source] of link.sources.entries()){
      const a=node("a","source-link",(i===0?"투자 결정 근거":"투자 집행 근거")+" · "+source.project_evidence.source_expression);
      a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";parent.append(a);
    }
  }
}

function renderThemeChanges(card,change,labels){
  if(!change){if(currentData.theme_changes_status==="UNAVAILABLE")card.append(node("p","finding-detail","기간 변화 근거를 읽지 못했습니다. 저장 테마는 계속 표시합니다."));return}
  const box=node("details","finding-detail");box.append(node("summary","","이 기간 달라진 근거"));
  box.append(node("p","",change.before?"기간 직전: "+(labels[change.before.status]||change.before.status)+" → 기간 말: "+(labels[change.after.status]||change.after.status):"기간 시작 전 판본 없음 · 이 기간에 처음 관측"));
  box.append(node("p","","기간 양끝 비교: 활성 독립 행동 "+(change.before?.scores.distinct_economic_events||0)+" → "+change.after.scores.distinct_economic_events+" · 추가 "+change.events.independent_actions_added+" · 제외 "+change.events.independent_actions_removed+" · 새 행동에 등장한 기업 "+change.companies.new_event_participant_count));
  for(const reason of change.reasons)if(!change.status_transitions.some(step=>step.reasons.some(r=>r.code===reason.code)))box.append(node("p","",reason.text));
  for(const [direction,events] of [["추가",change.events.added],["제외",change.events.removed]])for(const event of events){
    const ref=event.supporting_source;
    const text=direction+"된 사건: "+(ref?(ref.entity_ids.join(", ")||"기업 미식별")+" · "+ref.topic+" · "+(economicActionLabels[ref.action]||ref.action):"근거 설명 미확인")+(event.kind==="FOLLOWUP_OBSERVATION"?" · 기존 행동의 후속 보도":"");
    if(ref){const link=node("a","source-link",text);link.href=ref.source_url;link.target="_blank";link.rel="noopener noreferrer";box.append(link)}else box.append(node("p","",text));
  }
  renderInvestmentStages(box,change.investment_stage_links_added);
  for(const item of change.companies.added)box.append(node("p","","기업 포함: "+item.entity_id+" · "+({NEW_EVENT_PARTICIPANT:"새 경제 행동의 당사자",SUPPLY_CONTEXT:"공급 관계 근거 추가",EXISTING_EVENT_COMPANY_CONTEXT:"기존 사건의 기업 식별 보완"}[item.kind]||item.kind)));
  for(const item of change.companies.removed)box.append(node("p","","활성 근거에서 제외된 기업: "+item.entity_id));
  for(const item of change.companies.identity_updates)box.append(node("p","","기업 식별 갱신: "+item.from_entity_id+" → "+item.to_entity_id+" · 기업 확산에 포함하지 않음"));
  for(const step of change.status_transitions){
    box.append(node("p","",step.decision_at+" · "+(labels[step.from_status]||"최초 관측")+" → "+(labels[step.to_status]||step.to_status)));
    for(const reason of step.reasons)box.append(node("p","finding-detail",reason.text));
  }
  const polarities={SUPPORT:"추가 근거",CONTRADICT:"상충 근거",RETRACT:"철회·정정 근거"};
  for(const ref of change.sources.added){
    const link=node("a","source-link",(polarities[ref.polarity]||ref.polarity)+" · "+(ref.entity_ids.join(", ")||"기업 미식별")+" · "+(economicActionLabels[ref.action]||ref.action));
    link.href=ref.source_url;link.target="_blank";link.rel="noopener noreferrer";box.append(link);
    box.append(node("p","finding-detail","출처 가용: "+ref.source_available_at+" · 이 테마에 기록: "+ref.recorded_at+(ref.supersedes_event_id?" · 기존 사건을 대상으로 한 후속 근거":"")));
  }
  for(const ref of change.sources.removed){const link=node("a","source-link","비교 판본에서 제외된 출처");link.href=ref.source_url;link.target="_blank";link.rel="noopener noreferrer";box.append(link)}
  card.append(box);
}

function renderCompanyIdentities(term){
  const place=$("company-identities");place.replaceChildren();
  const rows=(currentData.company_identities||[]).filter(r=>!term||JSON.stringify(r).toLocaleLowerCase().includes(term));
  if(!rows.length)place.append(node("p","empty-small",currentData.company_identity_status==="UNAVAILABLE"?"기업 식별 기록을 읽지 못했습니다. 뉴스는 계속 표시합니다.":"해당 시점·검색 조건의 기업 식별 기록이 없습니다."));
  for(const row of rows){
    const card=node("article","finding");
    card.append(node("h4","","기사 속 기업 · "+row.matches.length+"개 식별"));
    for(const item of row.matches){
      card.append(node("p","",item.source_name+" · "+item.entity_id));
      card.append(node("p","finding-detail","근거: "+item.source_id+" / "+item.filing_document_id+" · 명부 확인: "+item.available_at));
    }
    for(const item of row.unresolved)card.append(node("p","finding-detail",item.source_name+" · "+(item.status==="AMBIGUOUS"?"동명 기업으로 식별 미확정":"현재 명부에서 식별하지 못함")));
    const link=node("a","source-link","기사 원문");link.href=row.source_url;link.target="_blank";link.rel="noopener noreferrer";
    card.append(link,node("p","finding-detail","식별 기록: "+row.decision_at));place.append(card);
  }
}
