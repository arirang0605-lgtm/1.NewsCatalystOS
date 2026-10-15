# 산업부 보도자료 원문과 RSS 영수증 연결 — 2026-10-15

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

## 기능

`motir_article_binding.py`는 이미 SHA 확인된 산업부 RSS 수집 결과와 별도 공공누리 제1유형 본문 아카이브를 오프라인으로 결합한다. RSS의 `event_id`·제목 SHA·기사 URL·체크포인트·triage SHA와 아카이브의 제공자·문서 ID·본문 SHA·영수증 SHA를 모두 맞춘다. URL이 같아 보여도 다른 사건·제목 버전이면 결합하지 않는다. 기사 본문은 RSS 관측시각으로 소급하지 않고, 결합 영수증에 실제 아카이브·결합시각을 기록한다.

## 실제 자료 검증

- 기사: [2026-10-15 산업부 충청권 메가프로젝트 투자 이행 점검](https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172295/view). 본문은 이전에 발표된 투자계획의 **이행 점검**을 다루며, 오늘 신규 투자 확정으로 재분류하지 않았다.
- RSS 관측시각: `2026-10-15T02:10:53.192736+00:00`, RSS ACK: `2026-10-15T02:10:53.468625+00:00`.
- 허가 본문 아카이브: `private/motir_press_172295/archive`; 문서 SHA `a2644b1c9f8bbfc873c2f6f84d445292d5e587afeb3e3557cb854971898d13ba`; 아카이브시각 `2026-10-15T05:20:16.849855+00:00`.
- 결합 영수증: `private/motir_press_172295/rss_bindings/motir_article_binding_23e58e58d579fb6d2116fc31d3ccb131e8e85ec1b309a53fb8c680fe2a22301f.json`. 별도 프로세스에서 SHA `23e58e58d579fb6d2116fc31d3ccb131e8e85ec1b309a53fb8c680fe2a22301f`로 읽기 성공. `new_economic_event_verified=false`, `verified_real_transaction=false`.
- RSS 기반 분석의 실제 기초 입력은 기사 제목뿐이었으므로 이 결합으로 과거 제목 분석 결과를 몰래 수정하지 않는다. 본문 사건 선별은 아래의 별도 단계로 수행한다.

## 본문 사건 선별

`motir_document_screen.py`는 위 결합 SHA와 본문 아카이브를 다시 확인한 뒤, 투자금액이 포함된 문단의 과거 발표·이행 점검 표현과 신규 결정 표현을 구별한다. 금액과 문단 SHA만 비공개 결과에 남기며 자동으로 계약·매출·수혜를 확정하지 않는다. 명시적인 신규 반도체 투자 후보 중 1,000억원 이상은 **후속 AI 분석 후보**로만 표시한다. 이 단계는 AI를 호출하지 않는다.

기사 172295의 실제 본문 선별 결과는 `392조원`이 **지난 7월 발표된 계획**에 대한 `PRIOR_INVESTMENT_PLAN_MONITORING` 1건이다. 비공개 결과 SHA `57db4dcef75e85f3ac9bc11317de2955ff63b9c3a7602f75df34c65c8c5cdd65`를 별도 프로세스에서 소비했다. `ai_routing_candidate=false`, 실제 AI 호출 0, 신규 경제 사건 인증 0이다. 작은 합성 사례에서 명시적 신규 투자·과거 계획과 신규 표현이 섞인 문장도 각각 후보·보류로 분류함을 확인했다.

## 호출

`scripts/screen_motir_document.py`와 `scripts/consume_motir_document_screen.py`는 그 결합 영수증을 이용해 본문 선별 결과를 비공개 게시·검사한다.


## 허가 본문 Gemini 분석 연결 — 2026-10-15

`motir_document_analysis.py`와 `scripts/run_motir_document_analysis.py`가 결합 영수증→현재 본문 사용권→원문 SHA→본문 선별→기존 Gemini 비용 예약/정산→비공개 캐시/결과 게시를 연결한다. `LICENSED_ARTICLE_TEXT`와 별도 `newscatalyst.ai_document_analysis.v1`으로 제목 분석과 구분한다. 기존 제목 입력·결과·캐시는 유지한다. `consume_motir_document_analysis.py --path ... --expected-sha256 ...`는 네트워크나 캐시 쓰기 없이 저장 결과를 조회한다.

- 자동 분석은 본문 규칙이 선정한 중요 신규 투자 후보에 적용한다. `--analyze-existing`은 지정된 기존 기사 1건 분석이며 신규 사건·실거래·수혜 확정 플래그는 false다.
- 추출한 기사 텍스트 전체를 사용한다. 12,000자와 모델의 보수적 입력 예산을 넘으면 `DOCUMENT_INPUT_LIMIT_EXCEEDED`를 표시하고 유료 호출 전에 종료한다. 문맥을 임의로 잘라 보내지 않는다. 첨부파일·외부 링크 내용까지 읽었다고 주장하지 않는다.
- 기사 본문 SHA, 원문 가용시각, 결합 SHA, 입력 SHA, 모델·프롬프트를 보존한다. 제목과 본문은 별도 분석 식별자이며 같은 입력은 캐시로 재사용한다. 불명확한 HTTP 실패의 비용 예약은 보존해 중복 청구를 막는다.
- MOTIR 예약 실행의 `--document-jobs /비공개/jobs.json --document-model-config /비공개/model.json`이 등록된 본문을 최대 20건 처리한다. jobs 스키마는 `newscatalyst.motir_document_jobs.v1`, 각 항목은 `binding_path`, `binding_sha256`, `archive_root`, `article_registry`다. 사람 검수·건별 승인 없이 처리하며 하나의 오류는 다른 항목의 처리를 막지 않는다. `--replay-only`는 본문도 유료 호출하지 않는다.
- 등록된 원문을 처리하는 기능이다. 새 RSS 기사의 허가 본문 자동 확보·아카이브·등록은 다음 구현 항목이다.

### 실제 실행 증거

기존 기사 172295의 추출 본문 1,411자(3,353바이트)를 같은 승인 Gemini 모델로 분석했다. 입력 1,335·출력 238토큰, 설정 단가 기준 예상 비용 **1.991원**. `EXISTING_ARTICLE`, 신규 경제 사건 false. 모델은 투자 이행 점검·인허가/기반시설 지원을 요약하고 실제 투자 집행은 미확인으로 표시했다. 동일 입력 재실행은 CACHE_HIT, 추가 생성 0건이다. 별도 프로세스에서 SHA 고정 결과 조회도 성공했다. 실제 비용 청구서 확인이나 산업 정확도 인증을 뜻하지 않는다.

합성 응답을 이용한 관련 기존/신규 검사 170개 통과. 과거계획 자동 호출 제외, 본문 변경 시 캐시 분리, 접근권한 철회, 원문 SHA, 긴 입력의 호출 전 차단, 비용 중복 예약 방지, 예약 실행 및 replay 유료 호출 차단을 확인했다.
