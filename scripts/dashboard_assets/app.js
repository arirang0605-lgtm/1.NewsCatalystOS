const state={view:"day",date:new Date().toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"})};
const $=id=>document.getElementById(id);
let currentData=null,shown=20;
const economicPhaseLabels={SOURCE_REPORTED:"출처 보도",ADOPTED_NOT_YET_EFFECTIVE:"의결 · 시행 전",PLANNED:"계획 단계"};
const economicActionLabels={POLICY_CHANGE:"정책 변화",BUSINESS_START:"사업·서비스 개시",PRODUCTION_START:"생산 개시",CAPACITY_ADDITION:"생산능력 확대",SUPPLY_REDUCTION:"공급 축소",CONTRACT:"계약",INVESTMENT:"투자 결정"};
function node(tag,cls,value){const x=document.createElement(tag);if(cls)x.className=cls;if(value!==undefined)x.textContent=value;return x}
function status(message,error=false){$("status").textContent=message;$("status").className=error?"error":""}
function shift(amount){const [y,m,d]=state.date.split("-").map(Number),day=new Date(Date.UTC(y,m-1,d));if(state.view==="month")day.setUTCMonth(day.getUTCMonth()+amount);else day.setUTCDate(day.getUTCDate()+amount*(state.view==="week"?7:1));state.date=day.toISOString().slice(0,10);load()}
function niceDate(value){return new Intl.DateTimeFormat("ko-KR",{year:"numeric",month:"long",day:"numeric",timeZone:"UTC"}).format(new Date(value+"T00:00:00Z"))}
function showNotes(place,notes,empty){place.replaceChildren();if(!notes.length){place.append(node("p","empty-small",empty));return}for(const item of [...notes].reverse()){const box=node("div","note");box.append(node("span","note-date",item.period+" · "+item.view),node("p","",item.text));place.append(box)}}
function categoryLabel(item){const labels={PRODUCT_LAUNCH:"제품 출시",BUSINESS_START:"사업·서비스 개시",NEW_CONTRACT:"신규 계약",NEW_INVESTMENT:"신규 투자",COMMERCIALIZATION:"상용화",REGULATORY_APPROVAL:"인허가",NEW_FACILITY:"신규 시설",CONTRACT_TERMINATION:"계약 종료",CONTRACT_REDUCTION:"계약 감액",CONTRACT_DELAY:"납기 지연"};const label=labels[item.category];return label?label+(item.reported_plan_only?" 계획 보도":" 보도"):(item.category||"분류 없음")}
function renderItems(){
  if(!currentData)return;
  const term=$("item-filter").value.trim().toLocaleLowerCase();
  const matches=currentData.items.filter(x=>!term||(x.headline+" "+x.provider+" "+(x.category||"")+" "+categoryLabel(x)+" "+JSON.stringify(x.economic_changes||[])+" "+JSON.stringify(x.company_identity||{})).toLocaleLowerCase().includes(term));
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
async function load(){status("저장된 조사 기록을 불러오는 중…");for(const button of document.querySelectorAll("[data-view]"))button.classList.toggle("active",button.dataset.view===state.view);$("date").value=state.date;try{const response=await fetch("/api/period?view="+encodeURIComponent(state.view)+"&date="+encodeURIComponent(state.date)+"&theme_activity="+encodeURIComponent($("theme-activity").value),{cache:"no-store"});if(!response.ok)throw new Error("조사 기록을 읽지 못했습니다.");render(await response.json());status("")}catch(error){status(error.message||"불러오기에 실패했습니다.",true)}}
for(const button of document.querySelectorAll("[data-view]"))button.addEventListener("click",()=>{state.view=button.dataset.view;load()});
$("theme-activity").addEventListener("change",()=>load());
$("date").addEventListener("change",event=>{if(event.target.value){state.date=event.target.value;load()}});
$("previous").addEventListener("click",()=>shift(-1));$("next").addEventListener("click",()=>shift(1));$("today").addEventListener("click",()=>{state.date=new Date().toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"});load()});
$("item-filter").addEventListener("input",()=>{shown=20;renderItems()});$("more-items").addEventListener("click",()=>{shown+=20;renderItems()});
$("note-text").addEventListener("input",event=>{$("note-count").textContent=event.target.value.length+" / 2000"});
$("note-form").addEventListener("submit",async event=>{event.preventDefault();const text=$("note-text").value.trim();if(!text)return;status("메모를 저장하는 중…");try{const response=await fetch("/api/notes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({view:state.view,date:state.date,text})});if(!response.ok)throw new Error("메모를 저장하지 못했습니다.");$("note-text").value="";$("note-count").textContent="0 / 2000";await load()}catch(error){status(error.message,true)}});
load();

function renderThemes(term){
  const themes=(currentData.themes||[]).filter(x=>!term||(JSON.stringify(x)+" "+(x.source_refs||[]).map(r=>economicActionLabels[r.action]||r.action).join(" ")).toLocaleLowerCase().includes(term));
  $("theme-total").textContent=themes.length+"개";$("themes").replaceChildren();
  if(!themes.length)$("themes").append(node("p","empty-small",currentData.theme_status==="UNAVAILABLE"?"테마 기록을 읽지 못했습니다. 뉴스 분석 기록은 계속 표시합니다.":"이 시점·검색 조건에 해당하는 테마 후보가 없습니다."));
  const labels={CANDIDATE:"관찰 후보",EMERGING:"형성 중",EXPANDING:"확산",WEAKENING:"약화",INVALIDATED:"무효",REACTIVATED:"재활성화"};
  for(const theme of themes){
    const card=node("article","finding"),meta=node("div","finding-meta");
    meta.append(node("span","pill",labels[theme.status]||theme.status),node("span","","사건 후보 "+theme.scores.distinct_economic_events+" · 기업 "+theme.scores.company_breadth));
    const activity=currentData.theme_activity?.[theme.theme_id];
    if(activity==="new"||activity==="updated")meta.append(node("span","pill",activity==="new"?"기간 내 신규":"기간 내 갱신"));
    card.append(meta,node("h4","",theme.provisional_name),node("p","finding-detail","최초 발견: "+theme.first_detected_at),node("p","finding-detail","최근 근거: "+theme.last_evidence_at));
    if(theme.topic_aliases?.length>1)card.append(node("p","finding-detail","같은 주제 표기: "+theme.topic_aliases.join(" · ")));
    const drivers={DEMAND_EXPANSION:"수요 확대",POLICY_ENABLEMENT:"정책 기반 확대",CAPACITY_EXPANSION:"생산능력 확대",SUPPLY_CONTRACTION:"공급 축소",UNKNOWN:"공통 원인 미확인"};
    card.append(node("p","finding-detail","연결 기준: 같은 주제의 "+(drivers[theme.economic_driver]||theme.economic_driver)+" 사건 · 테마 후보 추론"));
    const relationLabels={REPORTED_DIRECT_TRANSACTION:"출처에 보고된 직접 계약",ANNOUNCED_SUPPLY_PLAN:"공급 계획"};
    const impactLabels={POTENTIAL_BENEFICIARY_UNVERIFIED:"잠재 수혜 (추론)",POTENTIAL_DAMAGE_UNVERIFIED:"잠재 피해 (추론)",ANNOUNCED_SUPPLY_PLAN_UNVERIFIED:"계획 단계 · 실현 미확인",UNKNOWN_RELATIONSHIP:"영향 경로 미확인",EFFECT_DIRECTION_UNKNOWN:"영향 방향 미확인",THEMATIC_ONLY:"단순 테마 연관"};
    for(const company of theme.company_links){
      const names=[...new Set(theme.source_refs.filter(r=>theme.event_ids.includes(r.event_id)).flatMap(r=>r.company_mappings||[]).filter(m=>m.entity_id===company.entity_id).map(m=>m.source_name))];
      const display=names.length?names.join(" / ")+" ("+company.entity_id+")":company.entity_id;
      card.append(node("p","",display+" · "+(company.supply_chain_links?.length?"공급망 근거 연결":"테마 연관")+" · 수혜 미확정"));
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
    for(const ref of theme.source_refs){const link=node("a","source-link",(ref.entity_ids?.join(", ")||"기업 미식별")+" · "+(ref.topic||theme.provisional_name)+" · "+(actions[ref.action]||ref.action)+" · "+(phases[ref.phase]||ref.phase)+" · "+(ref.content_scope==="RSS_TITLE_METADATA"?"제목 근거 · ":"")+ref.evidence_level);link.href=ref.source_url;link.target="_blank";link.rel="noopener noreferrer";details.append(link)}
    for(const item of theme.history)details.append(node("p","finding-detail",item.decision_at+" · "+(labels[item.status]||item.status)));
    card.append(details);$("themes").append(card);
  }
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
