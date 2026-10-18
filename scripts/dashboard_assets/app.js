const state={view:"day",date:new Date().toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"})};
const $=id=>document.getElementById(id);
let currentData=null,shown=20;
const economicPhaseLabels={SOURCE_REPORTED:"출처 보도",ADOPTED_NOT_YET_EFFECTIVE:"의결 · 시행 전",PLANNED:"계획 단계"};
const economicActionLabels={PRODUCT_LAUNCH:"제품·솔루션 출시 발표",SUPPLY_RESUMPTION:"생산·공급 재개",MARKET_ENTRY:"시장 진출",DELIVERY_START:"납품·공급 개시",POLICY_CHANGE:"정책 변화",BUSINESS_START:"사업·서비스 개시",PRODUCTION_START:"생산 개시",CAPACITY_ADDITION:"생산능력 확대",SUPPLY_REDUCTION:"공급 축소",CONTRACT:"계약",INVESTMENT:"투자 결정",INVESTMENT_EXECUTION:"투자 집행",CUSTOMER_ACQUISITION:"신규 고객 확보"};
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
const actionSearchTerms={PRODUCT_LAUNCH:"제품 솔루션 출시 발표 launch launches",SUPPLY_RESUMPTION:"생산 재개 공급 재개",MARKET_ENTRY:"시장 진출 신규 시장",DELIVERY_START:"납품 시작 납품 개시 공급 시작 공급 개시",POLICY_CHANGE:"정책 변화 규제 허가",BUSINESS_START:"사업 개시 서비스 개시 사업 시작 서비스 시작",PRODUCTION_START:"생산 개시 생산 시작 양산 가동",CAPACITY_ADDITION:"생산능력 확대 생산량 확대 공급량 확대 증설",SUPPLY_REDUCTION:"공급 축소 생산 축소 감산 공급 중단",CONTRACT:"계약 체결 공급계약 납품계약 수주",INVESTMENT:"투자 결정 투자 확정",INVESTMENT_EXECUTION:"투자 집행",CUSTOMER_ACQUISITION:"신규 고객 확보"};
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
      renderReportedContractAmount(group,source.cause);renderReportedDemandReduction(group,source);renderReportedRecoveryContract(group,source);renderReportedRecoveryDelivery(group,source);renderReportedRecoveryProduction(group,source);renderReportedRecoveryCapacity(group,source);renderReportedRecoveryInvestment(group,source);renderReportedRecoveryCustomer(group,source);renderReportedRecoveryMarket(group,source);renderReportedRecoveryService(group,source);renderReportedPolicyProduction(group,source);renderReportedPolicyCapacity(group,source);renderReportedPolicyContract(group,source);renderReportedPolicyDelivery(group,source);renderReportedPolicyCustomer(group,source);renderReportedPolicyMarket(group,source);renderReportedPolicyInvestment(group,source);renderReportedPolicyService(group,source);renderSharedPolicyAction(group,source);
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
function renderSharedPolicyAction(parent,source){
  const p=source.policy_parallel_action||source.recovery_parallel_action||source.growth_parallel_action||source.order_service_action||source.price_service_action||source.price_parallel_action||source.function_service_action;if(!p)return;
  parent.append(node("p","",source.function_service_action?(source.phase==="PLANNED"?"기능으로 설명된 서비스 계획 · 실제 개시로 확정하지 않습니다.":"기능으로 설명된 서비스 개시 보도 · 이용량·매출·수혜를 확정하지 않습니다."):source.price_service_action?(source.phase==="PLANNED"?"제품 가격 상승에 따른 서비스 계획 · 실제 개시로 확정하지 않습니다.":"제품 가격 상승에 따른 서비스 개시 보도 · 주문·판매량·매출·수혜를 확정하지 않습니다."):source.order_service_action?(source.phase==="PLANNED"?"주문 확대에 따른 서비스 계획 · 실제 개시로 확정하지 않습니다.":"주문 확대에 따른 서비스 개시 보도 · 이용량·매출·수혜를 확정하지 않습니다."):"같은 원인·당사자의 병렬 행동 · 같은 회사를 새 기업으로 세지 않습니다."),node("p","","원문: “"+p.source_expression+"” · SHA: "+p.expression_sha256),node("p","","이 행동 원문: “"+p.action_expression+"” · 범위 "+p.action_span.join("–")+((source.price_service_action||source.price_parallel_action)?" · 제품 가격 원인 범위 ":(source.recovery_parallel_action||(source.function_service_action&&source.economic_driver==="DEMAND_RECOVERY"))?" · 회복 원인 범위 ":(source.growth_parallel_action||source.order_service_action)?" · 성장 원인 범위 ":" · 정책 범위 ")+p.cause_span.join("–")));
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
          renderReportedContractAmount(box,source.cause);renderReportedDemandReduction(box,source);renderReportedRecoveryContract(box,source);renderReportedRecoveryDelivery(box,source);renderReportedRecoveryProduction(box,source);renderReportedRecoveryCapacity(box,source);renderReportedRecoveryInvestment(box,source);renderReportedRecoveryCustomer(box,source);renderReportedRecoveryMarket(box,source);renderReportedRecoveryService(box,source);renderReportedPolicyProduction(box,source);renderReportedPolicyCapacity(box,source);renderReportedPolicyContract(box,source);renderReportedPolicyDelivery(box,source);renderReportedPolicyCustomer(box,source);renderReportedPolicyMarket(box,source);renderReportedPolicyInvestment(box,source);renderReportedPolicyService(box,source);renderSharedPolicyAction(box,source);
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
      renderReportedContractAmount(box,entry.cause);renderReportedDemandReduction(box,entry);renderReportedRecoveryContract(box,entry);renderReportedRecoveryDelivery(box,entry);renderReportedRecoveryProduction(box,entry);renderReportedRecoveryCapacity(box,entry);renderReportedRecoveryInvestment(box,entry);renderReportedRecoveryCustomer(box,entry);renderReportedRecoveryMarket(box,entry);renderReportedRecoveryService(box,entry);renderReportedPolicyProduction(box,entry);renderReportedPolicyCapacity(box,entry);renderReportedPolicyContract(box,entry);renderReportedPolicyDelivery(box,entry);renderReportedPolicyCustomer(box,entry);renderReportedPolicyMarket(box,entry);renderReportedPolicyInvestment(box,entry);renderReportedPolicyService(box,entry);renderSharedPolicyAction(box,entry);
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
  if($("economic-discovery"))renderEconomicDiscovery(data.economic_discovery);
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

function renderCatalystMaterial(parent,value,entity){
  if(!value?.materials?.length)return;
  const box=node("div","finding-detail catalyst-material");
  box.append(node("p","eyebrow","재료 판단 · NewsCatalystOS → EraLeader"));
  const paths={CAPEX:"투자지출",SUPPLY:"공급능력",DEMAND:"수요",EARNINGS:"손익",COMPETITION:"사업·경쟁 여건"};
  const directions={INCREASE:"증가 가능",DECREASE:"감소 가능",MIXED:"복합",UNKNOWN:"방향 미확인"};
  const hints={CONTEXT_ONLY_MARKET_NOVELTY_UNKNOWN:"기존 자료/첫 관측 맥락으로 제공 · 시장 신규 재료로 단정하지 않음",
    REASSESS_UNRESOLVED_SOURCE_REVISION:"원문 변경에 따른 영향 재검토 · 실질 변화 미확정",
    REASSESS_REPORTED_PROGRESS:"단계 진전 근거를 후보 평가에 함께 반영",
    REASSESS_WITHDRAWAL:"철회된 재료를 후보 평가에서 재검토",
    REASSESS_CONFLICT:"상충하는 근거를 후보 평가에 함께 반영",
    EXCLUDE_INVALIDATED_CATALYST:"무효화된 재료를 새로운 강화 근거로 사용하지 않음",
    NO_NEW_CATALYST:"반복·유지: 새 재료 가산 근거 없음"};
  for(const event of value.materials){
    const companies=event.company_impacts.filter(c=>!entity||c.entity_id===entity||c.source_entity_id===entity);
    if(entity&&!companies.length&&!event.event_ids?.length)continue;
    box.append(node("p","",event.reason),
      node("p","finding-detail",(economicActionLabels[event.source_action]||event.source_action||"행동 미확보")+" · "+
        (economicPhaseLabels[event.source_phase]||event.source_phase||"단계 미확보")+" · "+(event.topic||"주제 미확보")),
      node("p","finding-detail","EraLeader 입력: "+(hints[event.news_input_for_era]||event.news_input_for_era)));
    const impacts=node("details","finding-detail");
    impacts.append(node("summary","","어느 기업에 왜 영향을 줄 수 있는가"));
    if(!companies.length)impacts.append(node("p","empty-small","유효한 기업별 영향 경로 없음 · 철회·상충/기업 근거를 확인"));
    for(const company of companies){
      impacts.append(node("p","",company.source_entity_id+" · "+(company.role==="DIRECT_SOURCE_ACTION_PARTY"?"이 사건의 직접 당사자":"같은 사건의 별도 공급관계 근거")));
      for(const h of company.hypotheses||[]){
        impacts.append(node("p","finding-detail",(paths[h.path]||h.path)+" — "+(directions[h.direction]||h.direction)+" (가설): "+h.premise),
          node("p","finding-detail","반증·조건: "+h.counter_argument));
      }
      if(company.hypothesis)impacts.append(node("p","finding-detail",company.hypothesis));
    }
    box.append(impacts,node("p","fineprint","원자료 확보 "+event.first_source_observed_at+" · 사건으로 기록 "+event.first_event_recorded_at));
  }
  box.append(node("p","fineprint","시장 최초 발생·주가 선반영 여부 미확인. 회사 선정·가격/거래대금·수급·경쟁력 종합 판단은 EraLeader, 매수·매도·손절은 개별 전략 담당."));
  parent.append(box);
}

function renderEraDailyAssessment(parent,assessment){
  if(!assessment)return;
  const panel=node("details","finding-detail era-daily-assessment");
  panel.append(node("summary","","EraLeader 기업 평가 연결"));
  if(assessment.status!=="AVAILABLE"){
    const labels={NOT_AVAILABLE_AS_OF:"조회 시점에 수신된 기업평가 없음",
      COMPANY_NOT_IN_SNAPSHOT:"선택한 EraLeader 평가 목록에 없는 기업",
      AMBIGUOUS_IDENTITY:"동일 이름/발행사에 복수 종목이 있어 자동 연결 보류",
      OFFICIAL_IDENTITY_UNAVAILABLE:"이 판본의 공식 기업코드/재무 근거 미확보",
      US_ASSESSMENT_NOT_CONNECTED:"미국 SEC 기업평가 연결은 아직 미완료"};
    panel.append(node("p","empty-small","N/A · "+(labels[assessment.status]||"기업평가 근거 미확보")));
    parent.append(panel);return;
  }
  const row=assessment.value,annual=row.dart_annual_cfs||{},quote=row.krx_completed_close||{},brief=row.evidence_brief||{};
  const number=value=>typeof value==="number"?new Intl.NumberFormat("ko-KR",{maximumFractionDigits:4}).format(value):"N/A";
  panel.append(node("p","",assessment.source_name+" · "+assessment.security_id+" · "+assessment.entity_id),
    node("p","finding-detail","EraLeader 완료 판본의 공식 기업코드와 정확히 연결 · "+
      (assessment.assessment_scope==="INDIVIDUAL_COMPANY_RESEARCH"?
        "뉴스에 연결된 개별 기업 평가 · WATCH 선정과 별개":
        "후보 상태 "+row.formal_selection_state+" (투자순위·매수신호 아님)")));
  if(annual.status==="DART_VERIFIED_ANNUAL_CFS"){
    panel.append(node("p","","연결재무 FY"+annual.fiscal_year+" · 매출 "+number(annual.revenue_krw)+
      "원 · 영업이익 "+number(annual.operating_income_krw)+"원"),
      node("p","finding-detail","영업이익률 "+number(annual.operating_margin_pct)+"% · 영업현금흐름 "+
      number(annual.operating_cashflow_krw)+"원"));
  }else panel.append(node("p","empty-small","연결재무: N/A"));
  if(quote.status==="OBSERVED_COMPLETED_KRX_CLOSE"){
    panel.append(node("p","","KRX "+quote.source_market_session+" 보관 종가 "+number(quote.close_krw)+
      "원 · 실시간 현재가격 아님"));
  }else panel.append(node("p","empty-small","가격: N/A · 해당 판본 종가 미확보"));
  const existing=annual.existing_financial_assessment||{};
  const supporting=brief.supporting_evidence||existing.competitiveness?.supporting||[];
  const weakening=brief.weakening_evidence||[...(existing.competitiveness?.weakening||[]),...(existing.financial_risk?.signals||[])];
  for(const [label,rows] of [["긍정 근거",supporting],["약화·위험 근거",weakening]]){
    for(const item of rows.slice(0,3))panel.append(node("p","finding-detail",label+": "+item.reason));
  }
  if(!weakening.length)
    panel.append(node("p","finding-detail","이 판본에서 제시된 약화 근거 없음 · 위험이 없다는 인증은 아님"));
  for(const reason of (brief.unavailable_or_limited||[...(existing.missing||[]),...(existing.limitations||[])]).slice(0,3))
    panel.append(node("p","finding-detail","한계: "+reason));
  panel.append(node("p","finding-detail","현재 저평가·정식 PER/PBR·뉴스의 실제 수혜는 미확인"),
    node("p","fineprint","EraLeader 평가 "+assessment.producer_evaluated_at+" · 뉴스 시스템 최초 수신 "+assessment.imported_at),
    node("p","fineprint","평가판본 SHA "+assessment.source_sha256));
  for(const source of row.official_annual_sources||[]){
    const link=node("a","source-link","FY"+source.fiscal_year+" 공식 연간공시 원문 ↗");
    link.href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+source.report_accession;
    link.target="_blank";link.rel="noopener noreferrer";panel.append(link);
  }
  parent.append(panel);
}

function renderThemes(term){
  const candidates=currentData.company_candidates||[];
  const search=companySearchResults(currentData.company_search?.candidates,term);
  const themes=(currentData.themes||[]).filter(x=>matchesTheme(x,term,candidates.filter(c=>c.theme_id===x.theme_id),currentData.theme_changes?.[x.theme_id],currentData.theme_presentations?.[x.theme_id])||candidates.some(c=>c.theme_id===x.theme_id&&["DIRECT_COMPANY","AMBIGUOUS_NAME"].includes(search[c.candidate_id]?.match_kind)));
  // Additional approved sources retain independent, PIT-safe theme histories:
  // same topic IDs in two stores are NOT merged into one invented event.
  const scoped=(currentData.additional_source_themes||[]).flatMap(group=>
    (group.themes||[]).filter(t=>matchesTheme(t,term,(group.company_candidates||[]).filter(c=>c.theme_id===t.theme_id)))
      .map(theme=>({scope:group.scope,theme,companies:(group.company_candidates||[]).filter(c=>c.theme_id===theme.theme_id)})));
  $("theme-total").textContent=(themes.length+scoped.length)+"개";$("themes").replaceChildren();
  renderCrossProductDemand($("themes"),currentData.cross_product_demand,term,search);
  renderCompanyTimelines($("themes"),currentData.company_timelines,term,companySearchResults(currentData.timeline_search_context||currentData.company_search?.candidates,term));
  if(!themes.length&&!scoped.length)$("themes").append(node("p","empty-small",currentData.theme_status==="UNAVAILABLE"?"테마 기록을 읽지 못했습니다. 뉴스 분석 기록은 계속 표시합니다.":"이 시점·검색 조건에 해당하는 테마 후보가 없습니다."));
  const labels={CANDIDATE:"관찰 후보",EMERGING:"형성 중",EXPANDING:"확산",WEAKENING:"약화",INVALIDATED:"무효",REACTIVATED:"재활성화"};
  if(currentData.theme_order?.mode==="actions")$("themes").append(node("p","fineprint","정렬: 기간 비교가 있는 후보 → 독립 행동 추가 수 → 신규 당사자 수 → 최근 갱신 → 테마 ID 내림차순. 증가가 없는 후보도 표시합니다."));
  for(const theme of themes){
    const card=node("article","finding"),meta=node("div","finding-meta");
    meta.append(node("span","pill",labels[theme.status]||theme.status),node("span","","사건 후보 "+theme.scores.distinct_economic_events+" · 기업 "+theme.scores.company_breadth));
    const activity=currentData.theme_activity?.[theme.theme_id];
    if(activity==="new"||activity==="updated")meta.append(node("span","pill",activity==="new"?"기간 내 첫 기록":"기간 내 갱신"));
    const title=themeTitle(theme,currentData.theme_presentations?.[theme.theme_id]);
    card.append(meta,node("h4","",title),node("p","finding-detail","최초 발견: "+theme.first_detected_at),node("p","finding-detail","최근 근거: "+theme.last_evidence_at));
    if(title!==theme.provisional_name){const saved=node("details","finding-detail");saved.append(node("summary","","저장 당시 테마명"),node("p","",theme.provisional_name));card.append(saved)}
    if(currentData.catalyst_material?.[theme.theme_id])
      renderCatalystMaterial(card,currentData.catalyst_material[theme.theme_id]);
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
        if(candidate.era_daily_assessment)renderEraDailyAssessment(reasons,candidate.era_daily_assessment);
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
  for(const {scope,theme,companies} of scoped){
    const card=node("article","finding");
    card.append(node("p","eyebrow",({msit:"과기정통부",company:"반도체 기업 공식 뉴스룸"}[scope]||"추가 승인 출처")+" · 독립 저장 이력"),
      node("h4","",theme.provisional_name),
      node("p","finding-detail","상태: "+theme.status+" · 독립 경제 행동 후보 "+
        theme.scores.distinct_economic_events+"개 · 출처에 명시된 기업 "+companies.length+"개"),
      node("p","finding-detail","확보 시점: "+theme.first_detected_at+
        " · 마지막 판정: "+theme.decision_at+" · 다른 저장소의 같은 이름과 자동 병합하지 않음"));
    const material=(currentData.additional_source_themes||[]).find(g=>g.scope===scope)?.catalyst_material?.[theme.theme_id];
    if(material)renderCatalystMaterial(card,material);
    for(const candidate of companies){
      card.append(node("p","","출처 기업: "+candidate.display_name+
        " · 기사/공급망 근거에 나타난 대상 · 실거래·매출·수혜 미확정"));
      for(const basis of candidate.inclusion_basis||[])
        if(basis.kind==="SOURCE_REPORTED_PARTICIPANT"){
          card.append(node("p","finding-detail","기업 포함 이유: "+basis.reason));
        }
      if(candidate.era_daily_assessment)renderEraDailyAssessment(card,candidate.era_daily_assessment);
    }
    const evidence=node("details","finding-detail");
    evidence.append(node("summary","","해당 승인 출처의 경제 행동·기록 근거"));
    for(const ref of theme.source_refs){
      const link=node("a","source-link",
        (ref.entity_ids?.join(", ")||"명시 기업 없음")+" · "+
        (economicActionLabels[ref.action]||ref.action)+" · "+
        (economicPhaseLabels[ref.phase]||ref.phase)+" · "+ref.evidence_level);
      link.href=ref.source_url;link.target="_blank";link.rel="noopener noreferrer";
      evidence.append(link,node("p","fineprint","출처 관측: "+ref.source_available_at+
        " · 시스템 저장: "+ref.recorded_at+" · 확정 거래/수혜 아님"));
    }
    card.append(evidence);$("themes").append(card);
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
    const text=direction+"된 사건: "+(ref?(ref.entity_ids.join(", ")||"기업 미식별")+" · "+(ref.topic||change.provisional_name||"주제 미확인")+" · "+(economicActionLabels[ref.action]||ref.action):"근거 설명 미확인")+(event.kind==="FOLLOWUP_OBSERVATION"?" · 기존 행동의 후속 보도":"");
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

function renderSavedArticleThemeEvents(place,themes,caption,articleContext){
  place.append(node("p","finding-detail",caption+" · 테마 "+themes.length+"개 · 독립 사실·거래·수혜 인증 아님"));
  for(const theme of themes){
    const card=node("div","news-evidence-theme");
    card.append(node("p","",theme.name+" · "+theme.status),
      node("p","finding-detail","테마 기록 시각: "+theme.decision_at+" · ID: "+theme.theme_id));
    for(const event of theme.events){
      const label=(economicActionLabels[event.action]||event.action)+" · "+(economicPhaseLabels[event.phase]||event.phase);
      card.append(node("p","finding-detail",label+" · "+(event.active_in_theme?"활성 사건 근거":"과거/상충·철회 등 상태 확인 필요")),
        node("p","finding-detail","보도상 사건 · "+event.topic+" · "+event.evidence_level+" · "+event.polarity));
      card.append(node("p","finding-detail",event.companies.length?
        "기사 근거 당사자: "+event.companies.map(c=>c.entity_id+(c.official_entity_id?" / "+c.official_entity_id:" (공식 ID 미확인)")).join(", "):
        "N/A · 이 기사 근거에서 기업 당사자 미식별"));
      card.append(node("p","finding-detail","출처 가용: "+event.source_available_at+
        (event.analysis_available_at?" · 본문 분석 가용: "+event.analysis_available_at:"")+" · 분석 기록: "+event.recorded_at));
      const link=node("a","source-link","동일 기사 사건의 출처 ↗");
      link.href=event.source_url;link.rel="noopener noreferrer";link.target="_blank";
      card.append(link);
    }
    if(articleContext){
      const form=node("div","news-change-toolbar");
      const startLabel=node("label","","변화 시작일"),endLabel=node("label","","종료일");
      const start=node("input","",""),end=node("input","","");
      start.type="date";end.type="date";
      const asKst=value=>new Date(value).toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"});
      start.value=asKst(theme.first_detected_at);
      end.value=asKst(new Date().toISOString());
      startLabel.append(start);endLabel.append(end);
      const button=node("button","news-evidence-button","선택 기간 변화 보기"),results=node("div","news-evidence-results");
      button.type="button";
      button.addEventListener("click",()=>loadSavedThemeChange(articleContext,theme,start.value,end.value,results));
      form.append(startLabel,endLabel,button);
      card.append(form,results);
    }
    place.append(card);
  }
}
async function loadSavedThemeChange(context,theme,start,end,place){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(start)||!/^\d{4}-\d{2}-\d{2}$/.test(end)||start>end){
    place.replaceChildren(node("p","empty-small","N/A · 날짜 순서와 시작·종료일을 확인하세요."));return;
  }
  const beginning=new Date(start+"T00:00:00+09:00"),finish=new Date(end+"T23:59:59.999+09:00");
  const upper=new Date(Math.min(finish.getTime(),Date.now()));
  if(!Number.isFinite(beginning.getTime())||!Number.isFinite(upper.getTime())||beginning>upper){
    place.replaceChildren(node("p","empty-small","N/A · 기간이 미래이거나 범위를 벗어납니다."));return;
  }
  place.replaceChildren(node("p","finding-detail","저장된 기간별 사건·후속 근거를 조회합니다."));
  try{
    const item=context.item,params=new URLSearchParams({q:context.phrase,provider_id:item.provider_id,
      event_id:item.event_id,title_sha256:item.title_sha256,theme_id:theme.theme_id,
      since:beginning.toISOString(),as_of:upper.toISOString()});
    if(context.item.analysis_scope==="ECONOMIC_DISCOVERY")params.set("discovery","1");
    const response=await fetch("/api/news-evidence?"+params);
    if(!response.ok)throw new Error("N/A · 해당 시점에서 연결된 테마·기사 근거를 확인할 수 없습니다.");
    const result=await response.json(),change=result.theme_change;
    place.replaceChildren();
    if(!change){place.append(node("p","empty-small","N/A · 선택 기간에 조회 가능한 저장 판본이 없습니다."));return;}
    place.append(node("p","finding-detail","기간 "+start+" ~ "+end+" · 신규 독립 행동 "+
      change.events.independent_actions_added+" · 제외 "+change.events.independent_actions_removed+
      " · 추가 근거 "+change.sources.added.length+" · 상충·철회는 별도 표시"));
    if(result.theme_change_status==="NO_CHANGE")place.append(node("p","empty-small","변화 없음 · 후속 보도 부재는 테마 무효화 근거가 아닙니다."));
    const labels={CANDIDATE:"관찰 후보",EMERGING:"형성 중",EXPANDING:"확산",
      WEAKENING:"약화",INVALIDATED:"무효",REACTIVATED:"재활성화"};
    renderThemeChanges(place,change,labels);
  }catch(error){place.replaceChildren(node("p","empty-small",error.message||"N/A · 저장 변화 조회 실패"));}
}
function renderSavedTitleAnalysis(place,result){
  if(!result)return;
  const section=node("div","news-evidence-theme");
  section.append(node("p","","저장 뉴스 분석 · 원문 제목의 경제 변화 근거"));
  if(result.status!=="READY"){
    const messages={SOURCE_NOT_AVAILABLE_AS_OF:"해당 시점에는 기사가 아직 가용하지 않음",
      NO_EXACT_SAVED_TITLE_ANALYSIS:"이 기사 판본의 저장 분석 보고서 없음",
      PARTIAL_SAVED_ANALYSIS_COVERAGE:"저장 보고서 일부를 읽지 못해 판본 확인 불가"};
    section.append(node("p","empty-small","N/A · "+(messages[result.reason_code]||"저장 분석 조회 불가")));
    place.append(section);return;
  }
  section.append(node("p","finding-detail","분석 가용: "+result.analysis_available_at+
    " · "+(result.reported_plan_only?"계획 표현 포함":"계획 여부는 개별 행동 기준")+
    " · AI 상태: "+result.ai_status+" · 보도/제목은 독립 사실 인증 아님"));
  if(result.economic_change_status==="NO_EXPLICIT_TITLE_CHANGE"){
    section.append(node("p","empty-small","제목에서 명시된 경제 변화 없음 · 공식 본문/테마 판정은 아래에서 별도 확인"));
  }
  for(const change of result.economic_changes){
    const card=node("div","finding-detail");
    const action=economicActionLabels[change.action]||change.action;
    card.append(node("p","",action+" · "+change.topic+" · "+(economicPhaseLabels[change.phase]||change.phase)),
      node("p","",change.entity_ids.length?"기사 명시 당사자: "+change.entity_ids.join(", "):
        "N/A · 명시된 기업 당사자 없음"),
      node("p","","변화 원인: "+change.economic_driver+" · "+change.evidence_level+
        (change.extraction_method==="AI_SOURCE_SPAN_MATCHED"?" · AI 원문구간 대조(미검증)":" · 규칙/출처 보도")));
    const industries={SEMICONDUCTOR:"반도체",POWER_EQUIPMENT:"전력기기",CRITICAL_MINERALS:"핵심광물",
      QUANTUM_TECHNOLOGY:"양자기술",ROBOTICS:"로봇",SOFTWARE_SERVICES:"소프트웨어·디지털 서비스"};
    card.append(node("p","finding-detail",change.industry_tags.length?
      "관련 산업: "+change.industry_tags.map(x=>industries[x]||x).join(" · ")+" · 원문 표현 기반 연결":
      "산업 미분류 · 경제 행동과 명시 기업은 보존"));
    section.append(card);
  }
  const proof=node("details","finding-detail");
  proof.append(node("summary","","분석 근거 SHA 확인"),
    node("p","","저장 보고서 SHA: "+result.report_sha256));
  section.append(proof);place.append(section);
}
async function loadSavedArticleCompanyExcerpt(articleContext,theme,company,place){
  place.replaceChildren(node("p","finding-detail","확인된 저장 원문에서 이 기업의 근거 표현을 조회합니다."));
  try{
    const article=articleContext.item;
    const params=new URLSearchParams({
      q:articleContext.phrase,provider_id:article.provider_id,
      event_id:article.event_id,title_sha256:article.title_sha256,
      excerpt_theme_id:theme.theme_id,
      excerpt_entity_id:company.entity_id,
      excerpt_claim_event_id:company.event_id,
      excerpt_evidence_sha256:company.evidence_sha256
    });
    if(article.analysis_scope==="ECONOMIC_DISCOVERY")params.set("discovery","1");
    const response=await fetch("/api/news-evidence?"+params);
    if(!response.ok)throw new Error("N/A · 해당 기사 판본의 기업 근거 요청 불가");
    const data=await response.json();
    const result=data.article_company_excerpt;
    place.replaceChildren();
    if(!result||result.status!=="READY"){
      const reasons={NO_EXACT_ACTIVE_ARTICLE_PARTY:"다른 기사·기업이거나 현재 활성인 근거가 아님",
        EXACT_ARTICLE_CLAUSE_UNAVAILABLE:"정확한 기사 사건 근거 판본을 확인하지 못함",
        NOT_AVAILABLE_AS_OF:"조회 시점에 이 근거가 아직 없었음",
        SOURCE_MISMATCH:"저장 원문/경제 행동 SHA가 일치하지 않음",
        RIGHTS_UNAVAILABLE:"공식 원문 사용권을 확인할 수 없음",
        CLAUSE_UNRESOLVED:"이 기업의 경제 행동 구간을 유일하게 식별할 수 없음"};
      place.append(node("p","empty-small","N/A · "+(reasons[result?.reason_code]||"검증된 표현 근거 없음")));
      return;
    }
    place.append(node("p","","원문 근거: "+result.excerpt+(result.excerpt_truncated?"…":"")),
      node("p","finding-detail",(result.content_scope==="RSS_TITLE_METADATA"?
        "뉴스 제목 표현":"허용 공식 본문 구간")+
        " · 직접 경제 행동 근거(실거래·수혜 인증 아님)"),
      node("p","finding-detail","원문 가용: "+result.source_available_at+
        " · 저장 분석 가용: "+result.analysis_available_at));
    const link=node("a","source-link","해당 경제 변화 원문 ↗");
    link.href=result.source_url;link.target="_blank";link.rel="noopener noreferrer";
    place.append(link);
  }catch(error){
    place.replaceChildren(node("p","empty-small",error.message||"N/A · 원문 구간 조회 오류"));
  }
}
function renderSavedArticleCompanyContext(place,context,articleContext){
  if(!context)return;
  const box=node("div","news-evidence-company-context");
  box.append(node("p","finding-detail","이 기사에 연결된 테마·기업 · 기사 당사자와 별도 공급망 근거를 구분 · 실제 수혜·투자 매력 미확정"));
  if(context.status!=="READY"){
    const reasons={
      NO_EXACT_ARTICLE_THEME:"N/A · 정확히 연결된 경제 사건·테마 없음",
      NO_COMPANY_IN_EXACT_ARTICLE_EVENTS:"N/A · 이 기사 근거에 기업 당사자 또는 같은 사건의 공급망 관계 없음",
      SOURCE_NOT_AVAILABLE_AS_OF:"N/A · 선택 시점에 기업 근거 사용 불가"
    };
    box.append(node("p","empty-small",reasons[context.reason_code]||"N/A · 기사별 기업 포함 근거 없음"));
    place.append(box);return;
  }
  for(const theme of context.themes){
    const card=node("div","news-evidence-theme");
    card.append(node("p","",theme.name+" · "+theme.theme_status));
    if(!theme.direct_parties.length)
      card.append(node("p","empty-small","N/A · 기사에서 직접 확인된 기업 당사자 없음"));
    for(const company of theme.direct_parties){
      const party=node("div","news-evidence-company");
      party.append(node("p","",company.source_name+" · "+(economicActionLabels[company.action]||company.action)+" · "+
        (economicPhaseLabels[company.phase]||company.phase)));
      party.append(node("p","finding-detail",company.identity_status==="PINNED_OFFICIAL_ID"?
        "같은 출처의 고정 기업식별 근거: "+company.official_entity_id:
        "기사 자체는 회사명만 명시 · 별도 EraLeader 코드 연결은 아래 표시"));
      party.append(node("p","finding-detail",company.active_in_theme?
        "저장된 현재 사건 당사자 · 실제 수혜/매출 미확인":
        "과거/정정·철회 가능 사건 당사자 · 활성 기업 확정 아님"));
      if(company.inclusion_status==="READY"){
        for(const reason of company.inclusion_reasons)
          party.append(node("p","finding-detail","테마 포함 이유: "+reason));
      }else party.append(node("p","empty-small","N/A · 이 기사 판본의 활성 기업 포함 근거 없음"));
      party.append(node("p","finding-detail","출처 가용: "+company.source_available_at+" · 근거 기록: "+company.recorded_at));
      if(company.catalyst_materials?.length)
        renderCatalystMaterial(party,{materials:company.catalyst_materials},company.entity_id);
      if(company.era_daily_assessment)renderEraDailyAssessment(party,company.era_daily_assessment);
      const link=node("a","source-link","해당 기사 기업 행동의 원문 ↗");
      link.href=company.source_url;link.target="_blank";link.rel="noopener noreferrer";party.append(link);
      if(articleContext&&company.active_in_theme&&company.inclusion_status==="READY"){
        const expandable=node("details","finding-detail");
        const summary=node("summary","","이 기사 속 경제 변화 근거 문장 보기");
        const excerptPlace=node("div","finding-detail");
        expandable.append(summary,excerptPlace);
        let loaded=false;
        expandable.addEventListener("toggle",async()=>{
          if(!expandable.open||loaded)return;
          loaded=true;
          await loadSavedArticleCompanyExcerpt(articleContext,theme,company,excerptPlace);
        });
        party.append(expandable);
      }
      card.append(party);
    }
    if(theme.related_supply_context.length){
      card.append(node("p","finding-detail","별도 출처의 같은 경제 사건 공급망 맥락 · 이 기사에 직접 등장한 기업/실제 수혜로 계산하지 않음"));
      for(const rel of theme.related_supply_context){
        const detail=node("div","news-evidence-company");
        detail.append(node("p","",rel.entity_id+" · "+
          (rel.role==="supplier"?"공급자":rel.role==="customer"?"고객":"역할 미확인")+
          " · 상대: "+rel.counterparty_id+" · "+rel.product_stage));
        detail.append(node("p","finding-detail","관계: "+rel.relation_kind+" · 영향 후보: "+
          rel.impact_category+" · 수혜 미확인 · "+(rel.reported_in_selected_article?
          "기업은 기사에 등장하지만 공급 관계 자체는 별도 출처 근거":
          "이 기사에서 직접 확인된 기업은 아님")));
        detail.append(node("p","finding-detail","별도 연결 기록: "+rel.linked_at));
        for(const url of rel.source_urls){
          const link=node("a","source-link","별도 공급 관계 근거 ↗");
          link.href=url;link.target="_blank";link.rel="noopener noreferrer";detail.append(link);
        }
        card.append(detail);
      }
    }
    box.append(card);
  }
  place.append(box);
}
async function saveFollowupComparison(data,query={}){
  const bytes=new TextEncoder().encode(JSON.stringify({
    schema:"newscatalyst.company_followup_comparison.v1",query,comparison:data,
    source_text_stored:false,orders_enabled:false},null,2)+"\n");
  const hash=await crypto.subtle.digest("SHA-256",bytes);
  const digest=Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,"0")).join("");
  const url=URL.createObjectURL(new Blob([bytes],{type:"application/json"}));
  const link=document.createElement("a");link.href=url;
  link.download="news_company_comparison_"+digest+".json";
  document.body.append(link);link.click();link.remove();URL.revokeObjectURL(url);
}
function renderRecentThemeComparison(place,data,withButton=false,query={}){
  if(!data?.notes?.length)return;
  const box=node("details","finding-detail");
  box.append(node("summary","","최근 실제 뉴스와 기존 수요 근거 비교 · "+(data.status_label||"기업별 근거")),
    node("p","fineprint","전력 인프라 수요라는 넓은 가설의 분석 비교입니다. 기사 수를 강화 점수로 쓰지 않습니다. 신재생 관련 언급이 없다는 이유로 수요 약화를 추정하지 않습니다."));
  if(data.status_label)box.append(node("p","",data.status_label+" · 조건·제품 범위는 기업별로 확인"));
  for(const f of data.shared_recent_factors||[])
    box.append(node("p","finding-detail","최근 공통 배경(분석 분류): "+f.label+" → "+f.source_companies.join(" · ")));
  const period=data.period_comparison;
  if(period){
    box.append(node("h4","","기간 시작과 비교한 근거 변화"),
      node("p","fineprint","비교 시작 "+period.since+" · 새로 읽은 과거 자료를 최근 수요 증가로 계산하지 않습니다."));
    for(const company of period.company_results)
      box.append(node("p","finding-detail",company.source_company+" → "+company.status_label+
        " · "+({SOURCE_REPORTED_PROGRESS:"같은 계약의 이행 진전",SOURCE_REPORTED_SETBACK:"같은 계약의 이행 차질",
          MIXED_EXECUTION_EVIDENCE:"진전·차질 혼재",NO_NEW_EXECUTION_PROOF:"같은 계약의 새 이행 근거 미확보"}[company.execution_status])));
  }
  const assessments=data.company_assessment_comparison;
  if(assessments){
    box.append(node("h4","","기업 평가 근거의 변화"),
      node("p","fineprint","뉴스의 사업 근거와 기존 재무·위험 평가를 각각 비교합니다."));
    for(const company of assessments.company_results){
      const panel=node("details","finding-detail");
      panel.append(node("summary","",company.source_company+" → "+company.status_label));
      const changes=company.observation_changes;
      if(changes){
        const fields={fiscal_year:"재무연도",revenue_krw:"매출(원)",operating_income_krw:"영업이익(원)",net_income_krw:"순이익(원)",
          operating_margin_pct:"영업이익률(%)",operating_cashflow_krw:"영업현금흐름(원)",cash_after_ppe_intangibles_krw:"유형·무형자산 투자 후 현금(원)"};
        const value=v=>v===null?"미확보":typeof v==="number"?new Intl.NumberFormat("ko-KR",{maximumFractionDigits:4}).format(v):String(v);
        for(const change of changes.metrics)
          panel.append(node("p","finding-detail",(fields[change.field]||change.field)+": "+value(change.previous)+" → "+value(change.current)));
        for(const [key,label] of [["support_added","새로 제시된 긍정 근거"],["support_removed","이전 긍정 근거에서 제외"],
          ["risk_added","새로 제시된 약화·위험 근거"],["risk_removed","이전 약화·위험 근거에서 제외"],
          ["limitations_added","추가된 평가 한계"],["limitations_removed","이전 평가 한계에서 제외"]])
          for(const reason of changes[key]||[])panel.append(node("p","finding-detail",label+": "+reason));
        panel.append(node("p","fineprint","기존 평가 항목의 변화입니다. 투자등급 상향·하향이나 위험 해소를 확정하지 않습니다."));
      }
      renderEraDailyAssessment(panel,company.current);box.append(panel);
    }
  }
  if(withButton&&data.period_comparison){
    const save=node("button","news-evidence-button","이 비교 자료 저장");
    save.addEventListener("click",async()=>{
      save.disabled=true;
      try{await saveFollowupComparison(data,query);save.textContent="비교 자료 저장 완료";}
      catch{save.textContent="비교 자료 저장 실패 · 다시 시도";}
      finally{save.disabled=false;}
    });box.append(save);
  }
  const execution=data.execution_comparison;
  if(execution){
    box.append(node("h4","","개별 발주·납품·수주 실적의 실행 비교"),
      node("p","",execution.status_label),
      node("p","fineprint","관련 사업의 실적 개선과 특정 계약의 이행을 구분합니다. 발표가 뒤여도 실적 대상 기간이 앞서면 해당 계약의 실행 증거로 쓰지 않습니다."));
    for(const company of execution.company_results)
      box.append(node("p","finding-detail",company.source_company+" → "+company.status_label+
        (company.risk_reference_note_ids.length?" · 별도 반론·위험 참고자료 있음":"")));
    box.append(node("p","fineprint","우려·전망은 실제 취소·수요 감소와 구분합니다. 미확보는 약화 판정이 아닙니다."));
  }
  const kinds={REPORTED_CONTRACT:"신규 계약 보도",REPORTED_CAPACITY_OPERATION:"생산 능력 가동 보도",
    CONDITIONAL_FRAMEWORK:"후속 발주가 필요한 기본 공급계약",PLAN_ONLY:"계획·완료 미확인",
    DEMAND_REDUCTION:"수요 감소 보도",CANCELLATION:"취소 보도",CONTEXT_ONLY:"배경·누적 실적 설명",REPORTED_ORDER_PERFORMANCE:"수주·매출 실적 보도",
    REPORTED_DELIVERY:"납품 완료 보도",REPORTED_DELAY:"납품 지연 보도",RISK_ONLY:"위험·반론 설명"};
  for(const row of data.notes){
    const n=row.note,r=n.recent_source,card=node("article","finding");
    card.append(node("h4","",row.source_company+" · "+(kinds[n.evidence_kind]||n.evidence_kind)),
      node("p","",r.headline),node("p","fineprint","원문 표시일 "+(n.reported_date||"미확인")+" · 제목 확보 "+row.recent_available_at+" · 비교 분석 확보 "+row.available_at),
      node("p","finding-detail","기존 근거: "+row.baseline_headline),
      node("p","finding-detail",row.baseline_analysis),
      node("p","",n.analysis_text),node("p","finding-detail","제품·사업 범위: "+n.product_scope),
      node("p","fineprint","조건·차이·미확인: "+n.limitation),
      node("p","fineprint","원문 위치: "+n.source_location+" · 공개 원문을 읽은 별도 분석 · 독립 거래·수혜 인증 아님"));
    const x=n.execution,context=row.execution_context;
    if(x&&context){
      const timing={EARLIER_PUBLICATION:"기준 기사보다 앞선 발표",LATER_PUBLICATION_PRIOR_PERIOD:"발표는 뒤지만 실적 대상 기간은 앞섬",
        ON_OR_AFTER_ANCHOR:"기준 기사 이후 또는 같은 날의 자료",
        PUBLICATION_DATE_UNAVAILABLE:"원문 날짜 미확인 · 후속 이행 시점 판단 제외"};
      card.append(node("p","finding-detail","비교 기준 기사: "+context.anchor_headline+" · "+context.anchor_reported_date),
        node("p","fineprint","시간 관계: "+timing[context.chronology]+(x.period_end?" · 실적 기간 말 "+x.period_end:"")),
        node("p","fineprint","프로젝트 관계: "+(x.project_relation==="SAME_PROJECT_EXPLICIT"?"원문상 같은 프로젝트로 분류(분석)":"관련 사업·별도 프로젝트")+" · "+x.matching_basis),
        node("p","finding-detail",context.reported_execution_progress?"원문상 개별 발주·납품 진전 근거":
          context.reported_execution_setback?"원문상 이행 차질 근거":"이 자료만으로 기준 계약의 개별 발주·납품 진전을 확인할 수 없습니다."));
      const anchorLink=node("a","source-link","비교 기준 기사 원문 ↗");anchorLink.href=context.anchor_source_url;
      anchorLink.target="_blank";anchorLink.rel="noopener noreferrer";card.append(anchorLink);
      if(x.counter_reference){
        const ref=x.counter_reference,refBox=node("details","finding-detail");
        refBox.append(node("summary","","반증 후보·위험 참고 기사"),node("p","",ref.title+" · "+ref.reported_date),
          node("p","",ref.analysis_text),
          node("p","fineprint",(ref.access_basis==="PUBLIC_PAGE_READING"?"공개 기사 본문을":"공개 검색 결과를")+" 읽은 별도 분석 · 수집 원장 미등록 외부 참고 링크 · 실제 취소·수요 감소를 확인한 자료 아님"));
        const refLink=node("a","source-link","반론 기사 원문 ↗");refLink.href=ref.source_url;
        refLink.target="_blank";refLink.rel="noopener noreferrer";refBox.append(refLink);card.append(refBox);
      }
    }
    if(row.era_daily_assessment){
      card.append(node("p","fineprint","기업 연결은 이 기사와 기준 근거에 결속된 읽기 분석을 사용합니다. 평가는 가용한 EraLeader 완료 판본의 정확한 기업 식별로 연결합니다."));
      renderEraDailyAssessment(card,row.era_daily_assessment);
    }
    const link=node("a","source-link","최근 뉴스 공식 원문 ↗");link.href=r.source_url;link.target="_blank";link.rel="noopener noreferrer";
    const baseline=node("a","source-link","기존 근거 공식 원문 ↗");baseline.href=row.baseline_source_url;baseline.target="_blank";baseline.rel="noopener noreferrer";
    card.append(link,baseline);
    if(withButton){
      const detail=node("div","news-evidence-results"),button=node("button","news-evidence-button","최근 뉴스의 기업·비교 근거 보기");
      button.type="button";button.addEventListener("click",()=>loadSavedNewsEvidence({
        provider_id:r.provider_id,event_id:r.event_id,title_sha256:r.title_sha256,analysis_scope:"ECONOMIC_DISCOVERY"
      },r.headline.slice(0,80),detail));card.append(button,detail);
    }
    box.append(card);
  }
  if(data.companies_without_followups?.length)box.append(node("p","fineprint","후속 근거 미확보: "+data.companies_without_followups.join(" · ")+" · 약화 판정 아님"));
  place.append(box);
}
function renderPublicDemandNotes(place,notes,withCompany=false){
  if(!notes?.length)return;
  const detail=node("details","finding-detail");
  detail.append(node("summary","","공개 원문을 읽은 기업별 수요 분석"));
  const markets={US:"미국",KR:"한국",GLOBAL:"글로벌"};
  const relation={MARKET_BACKGROUND:"시장 배경",PROJECT_PURPOSE:"사업 목적",ACTION_REASON:"행동 이유"};
  const factors={GRID_REPLACEMENT:"노후 전력망 교체",RENEWABLE_INTEGRATION:"신재생 발전의 전력망 연계",
    AI_LOAD:"AI·데이터센터 관련 전력 수요",TRANSMISSION_CONSTRAINTS:"송전 제약 해소",LOAD_GROWTH:"전력 수요 증가"};
  detail.append(node("p","fineprint","공개 원문 내용을 읽어 정리한 분석입니다. 원문 문장 인용·본문 보관·독립 사실 인증이 아닙니다."));
  for(const row of notes){
    const n=row.note,card=node("article","finding");
    card.append(node("h4","",n.source_company+" · "+n.market_codes.map(x=>markets[x]||x).join(" · ")),
      node("p","",n.analysis_text),
      node("p","finding-detail",n.factors.map(f=>(factors[f.code]||f.code)+" ("+(relation[f.relation]||f.relation)+")").join(" · ")),
      node("p","fineprint","원문 위치: "+n.source_location+" · 분석 확보 "+row.available_at+" · 새 뉴스 발생 시각 아님"));
    const link=node("a","source-link","수요 설명의 공식 원문 ↗");
    link.href=n.source_url;link.target="_blank";link.rel="noopener noreferrer";card.append(link);
    if(withCompany){
      const box=node("div","news-evidence-results"),button=node("button","news-evidence-button","이 수요 분석의 기업·기사 근거 보기");
      button.type="button";button.addEventListener("click",()=>loadSavedNewsEvidence({
        provider_id:n.provider_id,event_id:n.source_event_sha256,title_sha256:n.source_title_sha256,
        analysis_scope:"ECONOMIC_DISCOVERY"
      },row.source_headline.slice(0,80),box));
      card.append(button,box);
    }
    detail.append(card);
  }
  place.append(detail);
}
function showSavedNewsEvidence(place,data,article,phrase){
  place.replaceChildren();
  const articleContext=article&&phrase?{item:article,phrase}:null;
  if(data.acquisition_method==="MANUAL_METADATA")
    place.append(node("p","fineprint","공개 원문 확인 후 제목·링크 수동 입력 · 자동 수집 자료 아님"));
  renderPublicDemandNotes(place,data.public_page_demand_analysis);
  if(data.recent_theme_followup_analysis)renderRecentThemeComparison(place,{notes:data.recent_theme_followup_analysis});
  renderSavedTitleAnalysis(place,data.saved_title_analysis);
  renderSavedArticleCompanyContext(place,data.article_company_context,articleContext);
  const reasons={NO_SAVED_EXACT_THEME_EVIDENCE:"이 기사 RSS 판본에 연결된 저장 경제 사건·테마 근거 없음",
                 SOURCE_NOT_AVAILABLE_AS_OF:"선택 시점에는 해당 기사 판본이 아직 가용하지 않음"};
  if(data.status==="READY"){
    renderSavedArticleThemeEvents(place,data.themes,"저장된 동일 기사 판본의 테마",articleContext);
  }else if(data.recent_theme_followup_analysis?.length&&data.reason_code==="NO_SAVED_EXACT_THEME_EVIDENCE"){
    place.append(node("p","fineprint","이 기사는 위의 공개 원문 읽기 분석으로 기존 기업별 수요 근거와 연결했습니다. 제목 규칙으로 확정한 별도 경제 사건은 없습니다."));
  }else{
    place.append(node("p","empty-small","N/A · "+(reasons[data.reason_code]||"검증된 뉴스 제목 근거 없음")));
  }
  const official=data.official_document_evidence;
  if(!official)return;
  if(official.status!=="READY"){
    const unavailable={
      NO_EXACT_OFFICIAL_DOCUMENT_BINDING:"RSS 판본에 직접 결속된 공식 본문 없음",
      DOCUMENT_NOT_AVAILABLE_AS_OF:"선택 시점에는 공식 본문 바인딩 이전",
      NO_REPORTED_DOCUMENT_ECONOMIC_CHANGE:"본문 분석은 있지만 명시된 경제 변화 근거 없음",
      NO_VERIFIED_BOUND_DOCUMENT_ANALYSIS:"같은 공식 본문의 완료 분석 근거 없음",
      NO_EXACT_BOUND_DOCUMENT_THEME:"공식 본문 분석에 연결된 정확한 반도체 테마 없음",
      DOCUMENT_RIGHTS_OR_ARCHIVE_UNAVAILABLE:"공식 본문 사용권·보존판본 확인 불가"
    };
    place.append(node("p","empty-small","공식 본문 N/A · "+(unavailable[official.reason_code]||"본문 근거 연결 미확인")));
    return;
  }
  place.append(node("p","finding-detail","산업부 허용 공식 본문 근거 · RSS 제목과 별도 본문 SHA로 검증 · 계약·실제 수혜 확인 아님"));
  const proof=node("details","finding-detail");
  proof.append(node("summary","","공식 본문 바인딩·SHA 확인"),
    node("p","","본문 SHA: "+official.document_sha256),
    node("p","","RSS↔본문 바인딩 SHA: "+official.binding_sha256),
    node("p","","공식 본문 가용: "+official.binding_available_at));
  place.append(proof);
  renderSavedArticleThemeEvents(place,official.themes,"검증된 공식 본문에서 저장한 반도체 정책 사건",articleContext);
}
async function loadSavedNewsEvidence(item,phrase,place){
  place.replaceChildren(node("p","finding-detail","같은 기사 판본의 기존 저장 근거를 조회합니다."));
  try{
    const query=new URLSearchParams({q:phrase,provider_id:item.provider_id,event_id:item.event_id,title_sha256:item.title_sha256});
    if(item.analysis_scope==="ECONOMIC_DISCOVERY")query.set("discovery","1");
    const response=await fetch("/api/news-evidence?"+query);
    if(!response.ok)throw new Error("N/A · 이 기사 판본을 검증할 수 없습니다.");
    showSavedNewsEvidence(place,await response.json(),item,phrase);
  }catch(error){place.replaceChildren(node("p","empty-small",error.message||"N/A · 근거 조회 실패"));}
}

async function searchStoredNews(event){
  event.preventDefault();
  const message=$("news-search-status"),place=$("news-search-results");
  const phrase=$("news-search-query").value.trim();
  if(phrase.length<2||phrase.length>80){message.textContent="2~80자 검색어를 입력하세요.";return}
  place.replaceChildren();message.textContent="기존 저장 뉴스 제목을 검색하고 있습니다.";
  try{
    const params=new URLSearchParams({q:phrase,semiconductor_only:$("news-semiconductor-only").checked?"1":"0",limit:"20"});
    const response=await fetch("/api/news-search?"+params);
    if(!response.ok)throw new Error("저장 뉴스 검색을 수행할 수 없습니다.");
    const result=await response.json();
    message.textContent="일치 "+result.matched_document_versions+"개 자료 판본 중 "+result.keyword_hits+"개 표시 · "+(result.coverage_complete?"허용 출처 확인 완료":"일부 출처 조회 불가 · 부분 결과")+" · 중복 제목은 별도 자료 판본이며 같은 경제 사건임이 확인된 것은 아닙니다.";
    if(!result.results.length){place.append(node("p","empty-small","일치하는 저장 뉴스 제목이 없습니다."));return}
    for(const item of result.results){
      const card=node("article","finding");
      card.append(node("h4","",item.headline),
        node("p","finding-detail",item.provider_id+" · 출처 가용: "+item.source_available_at+" · "+(item.semiconductor_keyword_candidate?"반도체 단어 후보":"일반 제목 맥락")),
        node("p","finding-detail","뉴스 제목 메타데이터 · 기사 본문 미포함 · 사실/거래/수혜 확인 아님"));
      if(item.acquisition_method==="MANUAL_METADATA")
        card.append(node("p","fineprint","공개 원문 확인 후 제목·링크 수동 입력 · 자동 수집 자료 아님"));
      const link=node("a","source-link","저장 뉴스의 원래 출처 ↗");
      link.href=item.source_url;link.target="_blank";link.rel="noopener noreferrer";
      const action=node("button","news-evidence-button","경제 사건·테마·기업 근거 보기");
      action.type="button";
      const evidence=node("div","news-evidence-results");
      action.addEventListener("click",()=>loadSavedNewsEvidence(item,phrase,evidence));
      const common=node("button","news-evidence-button","공통 뉴스 분석·기업 보기");common.type="button";
      common.addEventListener("click",()=>loadSavedNewsEvidence({...item,analysis_scope:"ECONOMIC_DISCOVERY"},phrase,evidence));
      card.append(link,action,common,evidence);place.append(card);
    }
    if(result.has_more_matches)place.append(node("p","fineprint","검색 결과는 최신 20개까지 표시합니다."));
  }catch(error){message.textContent=error.message||"저장 뉴스 검색 실패";}
}
$("news-search-form").addEventListener("submit",searchStoredNews);


function renderEconomicDiscovery(data){
  const place=$("economic-discovery"),panel=$("discovery-panel"),summary=$("discovery-summary");
  place.replaceChildren();panel.hidden=!data;
  if(!data)return;
  if(data.status!=="READY"){
    summary.textContent=data.status==="NOT_STARTED"?"경제 변화 공통 관찰을 아직 시작하지 않았습니다.":"관찰 자료 일부를 읽지 못했습니다. 기존 뉴스 분석은 유지됩니다.";
    return;
  }
  summary.textContent="관찰 주제 "+data.counts.topics+"개 · 원문에 연결된 행동 "+data.counts.events+
    "개 · 미분류 주제 "+data.counts.unclassified_topics+"개 · 먼저 탐지한 뒤 분류 · 심층 산업 검증 아님";
  renderDiscoveryCauses(place,data.common_cause_connections);
  renderThemeOutlook(place,data.theme_outlook,{as_of:data.as_of,since:data.comparison_since});
  renderLaunchComparisons(place,data.launch_comparisons);
  for(const row of data.candidates){
    const card=node("article","finding");
    const labels=[...new Set(row.industry_links.map(x=>x.label))];
    card.append(node("h4","",row.watch_topic),
      node("p","",labels.length?"관찰 분야 단서: "+labels.join(" · "):"산업 미분류 · 경제 행동은 계속 관찰"),
      node("p","finding-detail","직접 명시 기업: "+(row.source_companies.join(" · ")||"미확보 · 회사 추정하지 않음")),
      node("p","finding-detail",row.economic_actions.map(x=>economicActionLabels[x]||x).join(" · ")),
      node("p","fineprint","최초 기록 "+row.first_observed_at+" · 공급망·수혜·시장 신규성 미확인"));
    if(row.economic_actions.includes("PRODUCT_LAUNCH"))
      card.append(node("p","fineprint","제품·솔루션 출시를 보도한 제목의 관측입니다. 출시 주체를 제조사로 단정하거나 판매·매출·수혜를 확정하지 않습니다. 번역·재배포 제목은 독립 시장사건으로 인증하지 않습니다."));
    for(const context of row.source_context_connections||[]){
      for(const company of context.company_links){
        card.append(node("p","finding-detail","원문 수신 대상: "+company.source_name+
          " · 원문에 명시된 모회사: "+company.source_parent_name),
          node("p","fineprint","관계 표현: "+company.relation_evidence.text+
          " · 모회사를 직접 지원 대상이나 수혜주로 승격하지 않음 · 법적 소유관계 별도 확인"));
      }
      if(context.purpose_evidence){
        card.append(node("p","finding-detail","지원 목적 원문: "+context.purpose_evidence.text));
      }
      card.append(node("p","fineprint","연결 근거 해석시각 "+context.available_at+
        " · 기존 사건의 연결 보완이며 새 발표 아님"));
    }
    const evidence=node("details","finding-detail");evidence.append(node("summary","","원래 뉴스와 조건부 영향 확인"));
    for(const source of row.source_evidence){
      evidence.append(node("p","",source.headline),node("p","fineprint","원자료 확보 "+source.source_available_at+" · "+source.provider_id));
      const a=node("a","source-link","뉴스의 원래 출처 ↗");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";evidence.append(a);
      const action=node("button","news-evidence-button","기업·분석 근거 보기");action.type="button";
      const detail=node("div","news-evidence-results");
      const item={provider_id:source.provider_id,event_id:source.source_event_sha256,
        title_sha256:source.title_sha256,analysis_scope:"ECONOMIC_DISCOVERY"};
      action.addEventListener("click",()=>loadSavedNewsEvidence(item,source.headline.slice(0,80),detail));
      evidence.append(action,detail);
    }
    if(row.material)renderCatalystMaterial(evidence,row.material);
    card.append(evidence);place.append(card);
  }
  if(!data.candidates.length)place.append(node("p","empty-small","현재 자료에서 명시적 경제 행동을 찾지 못했습니다. 산업 이름이 없다는 이유로 제외한 것은 아닙니다."));
}


function renderThemeOutlook(place,data,query={}){
  if(!data?.candidates?.length)return;
  const section=node("section","theme-outlook");
  section.append(node("h3","","주목할 테마 후보·관련 산업"),
    node("p","fineprint","뉴스 원문의 공통 사업 대상과 기업 행동으로 연결한 조사 후보입니다. 산업분류표 없이 관련 사업 분야와 역할을 정리하며 유망성은 근거·반증과 함께 판단합니다."));
  if(data.public_page_demand_analysis_status==="UNAVAILABLE")
    section.append(node("p","fineprint","추가 수요 분석 판본을 확인할 수 없습니다. 기존 원문 제목의 테마는 계속 표시합니다."));
  if(data.recent_news_comparison_status==="UNAVAILABLE")
    section.append(node("p","fineprint","최근 비교 자료를 확인할 수 없습니다. 기존 테마 근거는 표시합니다."));
  const early=node("details","finding-detail");
  const earlyCount=data.candidates.filter(row=>row.attention_tier==="EARLY_WATCH").length;
  early.append(node("summary","","초기 관찰 후보 "+earlyCount+"개 · 후속 근거 확인"));
  const changes={FIRST_LOCAL_OBSERVATION:"비교기간에 처음 관측 · 시장 신규성 미확인",
    NO_SUBSTANTIVE_OBSERVATION_CHANGE:"비교기간의 실질 관측 변화 없음",
    SUPPORT_BROADENED:"관측 범위 확대 · 회사명 또는 행동 추가",
    SUPPORT_NARROWED:"현재 유효 근거의 회사명 범위 축소",EVIDENCE_CHANGED:"관측 근거 변경"};
  for(const row of data.candidates){
    const card=node("article","finding");
    card.append(node("h4","",row.title),node("p","",row.attention_label),
      node("p","finding-detail","원문 회사명: "+(row.source_company_names.join(" · ")||"미확보")));
    for(const reason of row.attention_reasons)card.append(node("p","finding-detail",reason));
    const comparison=row.public_page_demand_analysis;
    if(comparison){
      const shared=comparison.shared_background_factors.filter(f=>f.all_group_companies_covered);
      card.append(node("p","finding-detail","공개 원문 기반 비교 · "+comparison.companies_with_notes.join(" · ")),
        node("p","finding-detail","공통 배경(분석 분류): "+(shared.map(f=>f.label).join(" · ")||"전체 기업에 공통된 배경 미확보")),
        node("p","fineprint",comparison.market_scope_comparison==="DIFFERENT_STATED_SCOPES"?
          "기사의 지역 범위는 서로 다릅니다. 공통 배경 분류가 같은 수요 충격·발주를 뜻하지 않습니다.":
          "기사의 지역 범위가 같아도 같은 수요 충격·발주인지는 별도 확인이 필요합니다."));
      for(const factor of comparison.shared_background_factors.filter(f=>!f.all_group_companies_covered))
        card.append(node("p","finding-detail","일부 기업의 공통 배경(분석 분류): "+factor.label+" → "+factor.source_companies.join(" · ")));
      if(comparison.companies_without_notes.length)
        card.append(node("p","fineprint","추가 원문 분석 미확보: "+comparison.companies_without_notes.join(" · ")));
      renderPublicDemandNotes(card,comparison.notes,true);
    }
    if(row.recent_news_comparison)renderRecentThemeComparison(card,row.recent_news_comparison,true,{...query,outlook_id:row.outlook_id});
    const demand=row.source_demand_context;
    if(demand){
      card.append(node("p","finding-detail",demand.cross_company_source_cause_match?
        "기업 간 동일한 수요 원인 표현 확인 · 공통 시장 충격은 미검증":
        demand.claims.length?"공통 수요 변화 근거: 일부 기업 원문만 명시 · 제목 기준":"공통 수요 변화 근거: 원문 명시 원인 미확보"));
      for(const claim of demand.claims)
        card.append(node("p","finding-detail",claim.source_companies.join(" · ")+" → "+claim.cause_evidence.text+
          " → "+(economicActionLabels[claim.action]||claim.action)+" · "+(claim.phase==="PLANNED"?"계획·완료 미확인":"출처 보도")));
      if(demand.companies_without_explicit_cause.length)
        card.append(node("p","fineprint","같은 수요 원인인지 미확인: "+demand.companies_without_explicit_cause.join(" · ")+" · 제목 기준"));
      card.append(node("p","fineprint","수요 근거는 해당 기사에만 적용합니다. 다른 기업으로 원인을 전이하지 않습니다."));
    }
    if(row.period_change)card.append(node("p","finding-detail",changes[row.period_change.status]||"관측 변화 확인"));
    const areas=node("details","finding-detail");
    areas.append(node("summary","","관련 산업·사업 분야와 기업 역할"));
    for(const area of row.related_business_areas){
      areas.append(node("p","",area.source_described_area+" → "+area.role_label+
        " · "+(area.source_companies.join(" · ")||"회사 미확보")));
    }
    areas.append(node("p","fineprint","원문에 적힌 사업 대상·행동을 정리했습니다. 분야 사이의 공급망 거래는 별도 근거가 필요합니다."));
    card.append(areas);
    const detail=node("details","finding-detail");detail.append(node("summary","","기회·반증·원문 근거"));
    for(const path of row.conditional_paths){
      detail.append(node("p","",path.opportunity),node("p","fineprint","반증·미확인: "+path.countercondition));
    }
    for(const source of row.source_evidence){
      detail.append(node("p","",source.headline),
        node("p","finding-detail","연결 단서: "+source.shared_object_evidence.text+
          " · "+(economicActionLabels[source.action]||source.action)+
          " · "+(source.phase==="PLANNED"?"계획":"출처 보도")),
        node("p","fineprint","근거 확보 "+source.basis_available_at));
      const evidence=node("div","news-evidence-results");
      const company=node("button","news-evidence-button","이 테마의 기업·분석 근거 보기");company.type="button";
      company.addEventListener("click",()=>loadSavedNewsEvidence({
        provider_id:source.provider_id,event_id:source.source_event_sha256,
        title_sha256:source.source_title_sha256,headline:source.headline,
        source_url:source.source_url,analysis_scope:"ECONOMIC_DISCOVERY"
      },source.headline.slice(0,80),evidence));
      detail.append(company,evidence);
      const link=node("a","source-link","테마 후보의 원문 ↗");
      link.href=source.source_url;link.target="_blank";link.rel="noopener noreferrer";detail.append(link);
    }
    card.append(detail,node("p","fineprint","원문 회사명의 개수는 독립 법인·독립 사건 수가 아닙니다. 수요 증가·매출·수혜·주가 상승은 미확인입니다."));
    if(row.attention_tier==="EARLY_WATCH")early.append(card);else section.append(card);
  }
  if(earlyCount)section.append(early);
  if(data.previous_groups_not_currently_matched?.length)
    section.append(node("p","fineprint","이전 비교 묶음 "+data.previous_groups_not_currently_matched.length+
      "개는 현재 근거·묶음과 달라졌습니다. 철회·취소로 단정하지 않습니다."));
  place.append(section);
}


function renderLaunchComparisons(place,groups){
  if(!groups?.length)return;
  const section=node("section","finding");
  section.append(node("h3","","같은 회사·제품의 출시 보도 비교"),
    node("p","fineprint","회사·제품이 같아도 같은 발표라고 합치지 않습니다. 원문별 기록을 보존하고 반복·판본 변경·단계 차이를 나란히 봅니다."));
  for(const group of groups){
    const block=node("details","finding-detail launch-comparison");
    block.append(node("summary","",group.source_company_name+" · "+group.source_product_name+" · 제목 "+group.source_observation_count+"개 비교"));
    for(const pair of group.pairs){
      block.append(node("p","",pair.reason));
      if(pair.scripts_differ)block.append(node("p","finding-detail","표기 언어 차이 있음 · 번역·재배포 여부는 미확인"));
      if(pair.source_phase_differs)block.append(node("p","finding-detail","계획·발표 단계가 다름 · 실제 이행으로 확정하지 않음"));
    }
    for(const source of group.observations){
      block.append(node("p","",source.headline),
        node("p","finding-detail","출처 회사: "+source.company_evidence.text+" · 제품: "+source.product_evidence.text),
        node("p","fineprint","출처 확보 "+source.source_available_at+" · 발표 단계 "+(economicPhaseLabels[source.phase]||source.phase)),
        node("p","fineprint","원문 판본 SHA "+source.source_title_sha256));
      const a=node("a","source-link","비교한 원래 뉴스 ↗");a.href=source.source_url;a.target="_blank";a.rel="noopener noreferrer";block.append(a);
    }
    block.append(node("p","fineprint","독립 신규 재료 수 미확인 · 자료 확보 시각은 실제 출시일이 아닙니다. 원래 사건 수·후보 점수를 변경하지 않았습니다."));
    section.append(block);
  }
  place.append(section);
}


function renderDiscoveryCauses(place,data){
  if(!data?.groups?.length)return;
  const section=node("section","theme-outlook");
  section.append(node("h3","","명시 수요·정책 원인으로 연결한 사업 행동"));
  if(!data.groups?.length){
    section.append(node("p","empty-small","현재 저장 자료에서 서로 다른 반도체 제품의 행동을 연결하는 명시 수요처·정책 근거는 확보되지 않았습니다."));
  }
  for(const row of data.groups||[]){
    const card=node("article","finding");
    const labels={DEMAND_RECOVERY:"수요·주문 회복",DEMAND_EXPANSION:"수요·주문 확대",POLICY_ENABLEMENT:"정책 변화"};
    card.append(node("h4","",row.subject+" · "+(labels[row.economic_driver]||row.economic_driver)),
      node("p","",row.products.join(" · ")+"의 행동 연결 · 출처가 명시한 원인에 따른 조사 가설"));
    for(const source of row.source_evidence){
      card.append(node("p","",source.cause_evidence.text+" → "+source.product+" · "+
        (economicActionLabels[source.action]||source.action)+" · "+source.source_companies.join(" · ")+
        " · "+(source.phase==="PLANNED"?"계획":"출처 보도")),
        node("p","finding-detail",source.headline),node("p","fineprint","근거 확보 "+source.basis_available_at));
      const link=node("a","source-link","공통 원인의 원문 ↗");
      link.href=source.source_url;link.target="_blank";link.rel="noopener noreferrer";card.append(link);
    }
    for(const path of row.conditional_paths)
      card.append(node("p","finding-detail",path.opportunity),node("p","fineprint","반증·미확인: "+path.countercondition));
    card.append(node("p","fineprint","같은 시장 충격·기업 간 거래·실제 지출·매출·수혜는 미확인입니다. 조회 시 원문 해석이며 기존 사건·점수는 유지됩니다."));
    section.append(card);
  }
  place.append(section);
}
