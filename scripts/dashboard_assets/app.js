const state={view:"day",date:new Date().toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"})};
const $=id=>document.getElementById(id);
let currentData=null,shown=20;
function node(tag,cls,value){const x=document.createElement(tag);if(cls)x.className=cls;if(value!==undefined)x.textContent=value;return x}
function status(message,error=false){$("status").textContent=message;$("status").className=error?"error":""}
function shift(amount){const [y,m,d]=state.date.split("-").map(Number),day=new Date(Date.UTC(y,m-1,d));if(state.view==="month")day.setUTCMonth(day.getUTCMonth()+amount);else day.setUTCDate(day.getUTCDate()+amount*(state.view==="week"?7:1));state.date=day.toISOString().slice(0,10);load()}
function niceDate(value){return new Intl.DateTimeFormat("ko-KR",{year:"numeric",month:"long",day:"numeric",timeZone:"UTC"}).format(new Date(value+"T00:00:00Z"))}
function showNotes(place,notes,empty){place.replaceChildren();if(!notes.length){place.append(node("p","empty-small",empty));return}for(const item of [...notes].reverse()){const box=node("div","note");box.append(node("span","note-date",item.period+" · "+item.view),node("p","",item.text));place.append(box)}}
function renderItems(){
  if(!currentData)return;
  const term=$("item-filter").value.trim().toLocaleLowerCase();
  const matches=currentData.items.filter(x=>!term||(x.headline+" "+x.provider+" "+(x.category||"")).toLocaleLowerCase().includes(term));
  const visible=matches.slice(0,shown);
  $("item-total").textContent=visible.length+" / "+matches.length+"건";
  $("items").replaceChildren();
  if(!matches.length)$("items").append(node("p","empty",term?"검색 결과가 없습니다.":"이 기간에 저장된 분석 기록이 없습니다. 다른 날짜를 선택하거나 메모를 남길 수 있습니다."));
  for(const item of visible){
    const card=node("article","finding"),meta=node("div","finding-meta");
    meta.append(node("span","",item.day+" · "+item.provider),node("span","pill",item.priority==="HIGH_REVIEW"?"우선 검토":item.priority==="PARTIAL_EVIDENCE_ONLY"?"근거 보류":"분석 후보"));
    const ai={"NOT_ELIGIBLE":"AI 미사용","AWAITING_EXPLICIT_AI_AUTHORIZATION":"AI 승인 대기","ANALYZED_UNVERIFIED":"AI 해석·미검증","CACHE_HIT":"기존 AI 해석"}[item.ai_status]||"AI 결과 없음";
    card.append(meta,node("h4","",item.headline),node("p","finding-detail",[item.category||"분류 없음",ai,"미확인 "+item.uncertainty_count+"개"].join(" · ")));
    if(item.ai_summary){
      card.append(node("p","finding-detail",item.analysis_purpose==="EXISTING_ARTICLE"?"기존 기사 AI 분석 · 제목 기준":"AI 분석 · 제목 기준"));
      card.append(node("p","",item.ai_summary));
      for(const claim of item.ai_claims||[])card.append(node("p","finding-detail","해석: "+claim));
      for(const unknown of item.ai_uncertainties||[])card.append(node("p","finding-detail","미확인: "+unknown));
    }
    const link=node("a","source-link","출처 열기 ↗");link.href=item.source_url;link.target="_blank";link.rel="noopener noreferrer";card.append(link);$("items").append(card)
  }
  $("more-items").hidden=visible.length>=matches.length;
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
async function load(){status("저장된 조사 기록을 불러오는 중…");for(const button of document.querySelectorAll("[data-view]"))button.classList.toggle("active",button.dataset.view===state.view);$("date").value=state.date;try{const response=await fetch("/api/period?view="+encodeURIComponent(state.view)+"&date="+encodeURIComponent(state.date),{cache:"no-store"});if(!response.ok)throw new Error("조사 기록을 읽지 못했습니다.");render(await response.json());status("")}catch(error){status(error.message||"불러오기에 실패했습니다.",true)}}
for(const button of document.querySelectorAll("[data-view]"))button.addEventListener("click",()=>{state.view=button.dataset.view;load()});
$("date").addEventListener("change",event=>{if(event.target.value){state.date=event.target.value;load()}});
$("previous").addEventListener("click",()=>shift(-1));$("next").addEventListener("click",()=>shift(1));$("today").addEventListener("click",()=>{state.date=new Date().toLocaleDateString("sv-SE",{timeZone:"Asia/Seoul"});load()});
$("item-filter").addEventListener("input",()=>{shown=20;renderItems()});$("more-items").addEventListener("click",()=>{shown+=20;renderItems()});
$("note-text").addEventListener("input",event=>{$("note-count").textContent=event.target.value.length+" / 2000"});
$("note-form").addEventListener("submit",async event=>{event.preventDefault();const text=$("note-text").value.trim();if(!text)return;status("메모를 저장하는 중…");try{const response=await fetch("/api/notes",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({view:state.view,date:state.date,text})});if(!response.ok)throw new Error("메모를 저장하지 못했습니다.");$("note-text").value="";$("note-count").textContent="0 / 2000";await load()}catch(error){status(error.message,true)}});
load();
