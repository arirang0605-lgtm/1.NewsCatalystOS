# NewsCatalystOS V1.0 — 4_1~5_5 구현 현황 (2026-10-13)

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

## 2026-10-15 실제 Gemini 연결 완료 (`5465403`)

- 기존 기사 1건의 명시 선택(`--provider-id`, `--event-id`, `--title-sha256`, `--limit 1`, `--analyze-existing`)으로 실제 생성과 저장·읽기 전용 조회를 확인했다. 기사 신규성·중요도 판정을 바꾸지 않는다. 제목만 전송하며 결과는 한국어 요약·해석·미확인으로 제공한다.
- Gemini `responseFormat.text.mimeType`은 [공식 API 문서](https://ai.google.dev/api/generate-content#TextResponseFormat)의 enum `APPLICATION_JSON`을 사용한다. 종전 `application/json` 문자열을 수정했다. HTTP 오류는 본문·키 없이 상태 코드만 전달한다.
- [Gemini 공식 단가](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite)는 일반 호출 입력 $0.30/백만 토큰, 출력 $2.50/백만 토큰이다. 로컬 예산은 환율 여유를 둔 기존 가정치 입력 600원/백만·출력 5,000원/백만을 사용한다. 실제 청구 환율이나 계정 요금제 확인을 뜻하지 않는다.
- 성공 입력 259·출력 135토큰, 예상 0.8304원. 최초 실패의 예약 7.5776원은 미정산으로 남겨 합계 8.408원을 예산에서 계산한다. 동일 입력 재실행 캐시 적중, 추가 생성 0회. 실제 결과·원장은 공개 Git 제외.
- `--ai-ledger` / 예약 실행의 `--analysis-ai-ledger`로 core/MOTIR의 월 5만원을 공통 원장에 예약한다. 두 설치된 서비스에 같은 모델 설정·원장을 적용하고 첫 실행 정상 확인.
- 대시보드는 이전 규칙 분석이 있어도 나중에 도착한 AI 결과를 표시한다. 최초 관측일은 유지하고 실제 결과 시각은 별도 보존한다. 실제 결과 1건을 주간 화면에서 확인했다.
- 비용 원장·AI 캐시 2개 DB의 새 폴더 백업/복원 성공. 전체 회귀 1,158 PASS/0 FAIL. 아래 실호출 미완료 표기는 과거 구현 이력이다.

## 반도체 한 산업 — 5_1~5_5
- **5_1 semiconductor_profile.py: SemiconductorProfile v1 완성.** DRAM·NAND·HBM·웨이퍼 제조·제조장비·소재·기판·고급 패키징·테스트 9개 범위와 메모리 가격/물량/장비CAPEX/소재/패키징/테스트/수율 가설 경로. 타 산업 불허. 이것은 실제 거래·수혜 증거가 아닌 산업 분류표.
- **5_2 supply_chain_graph.py:** supplier/customer 2개 별도 기업ID 검토 증거, 공시/뉴스 문서ID 및 PIT가 일치할 때만 관계 후보 생성. 실제 독립 검증된 거래는 없음 → 5_2 인수 미완료.
- **5_3 semiconductor_impact.py:** 가격·증설·패키징·테스트의 영향 경로를 제품/공정에 구분하며 인과와 매출액은 HYPOTHESIS_ONLY → 실사례 검증 대기.
- **5_4 beneficiary_classification.py:** 직접 거래 주장과 테마 관계를 분리하여 잠재 수혜/잠재 피해/관계 불명만 분류. 수혜 확정과 매출 비중 생성 금지 → 실사례 검증 대기.
- **5_5 beneficiary_graph_contract.py:** 버전 JSON에 근거 ID/SHA·회사 역할/공정/출처 최초 가용 시각·불확실성·payload SHA를 기록. 실제 EraLeader 소비와 실데이터 전달 검증 전 인수 미완료.

## 경계 및 인수
- 사용된 가격·기업·금액·모델 응답은 **합성 테스트 픽스처**이며 실제 반도체 수혜기업이나 최초 웹 공개 증거가 아니다. 실제 AI 유료 호출·실청구/4_2 95%/4_6 500개 평가/5_2 실사례/5_6 반도체 95%/5거래일 자동운영은 완료하지 않았다.
- 기존 1_1~3_5 기능 보존, 2_6 및 3_6 실증 게이트 미완료 유지. EraLeader 코드/DB/Git과 DART/SEC/KRX 수집기 수정 0. NewsCatalystOS Public Git에는 원문·운영 DB·비밀키·개인 자료 공개 금지.

## 2026-10-15 | Gemini API 경로 연결 (인증 모델 GET 성공, 유료 생성 미실행)
- 사용자 선택에 따라 src/newscatalystos/ai_gemini_transport.py가 Gemini REST 요청을 처리한다. 키는 호출 직전 GEMINI_API_KEY 환경변수 또는 Mac 내부 ~/Library/Application Support/NewsCatalystOS/api-credentials/gemini_api.env에서 읽는다. scripts/open_gemini_setup.py는 127.0.0.1 전용 일회용 입력 화면으로 비밀 파일을 저장한다. 소유자 폴더 0700·파일 0600 및 symlink 거부를 적용하고 키를 명령 인자·모델 설정·로그·Git에 남기지 않는다. 키 부재·불안전한 권한은 예산 예약·HTTP 전 차단한다. 공식 API 형식: https://ai.google.dev/api/generate-content .
- 기존 중요 신규 사건/PIT/짧은 승인 메타데이터 선별, 4_6 월간 최대비용 예약·중복호출 방지, 모델별 캐시와 비공개 보고서·읽기전용 소비를 재사용한다. `allow_paid=True` 없이 HTTP를 열지 않고, 도구/검색 grounding·리다이렉트·자동 재시도를 사용하지 않는다. Gemini `usageMetadata.totalTokenCount - promptTokenCount`를 출력·사고 토큰의 보수적 사용량으로 잡아 정산한다.
- 2026-10-15 기존 키체인 접근 장애를 우회하기 위해 EraLeader의 로컬 전용 입력 화면·Mac 내부 0600 비공개 파일 패턴을 별도 구현했다. 사용자가 이 화면에서 Gemini 키를 직접 저장했고, 비밀값을 출력하지 않은 인증 모델 GET이 HTTP 200을 반환했다. models/gemini-3.5-flash-lite가 generateContent를 지원한다. 비공개 AIModel 설정은 최대 4,096/1,024 토큰·예산 가정 상한 약 7.58원/호출이며 실제 환율·청구액이 아니다. 관련 6개 테스트파일 96 PASS/0 FAIL. 유료 Gemini 생성 POST 0회, 저장된 RSS 후보 중 AI 적격 0개다. 코드 연결과 모델 조회를 유료 뉴스 분석 또는 운영 인수로 표시하지 않는다.
