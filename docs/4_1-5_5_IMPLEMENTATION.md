# NewsCatalystOS V1.0 — 4_1~5_5 구현 현황 (2026-10-13)

## AI 분석 — 4_1~4_6
- **4_1 ai_provider.py: 공통 계약 구현, 실호출 미검증.** OpenAI/Gemini/Anthropic 모델 버전·prompt 버전·temperature·token 제한·가정 단가를 한 스키마로 처리. 명시적 transport가 없으면 네트워크 호출을 거부. 중요 신규 사건, PIT, 허가된 짧은 메타데이터만 입력 가능하며 AI 가설은 사실로 인증하지 않음.
- 맥북 환경변수 OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY의 **설정 여부**만 확인했고 세 항목 모두 미설정. API 키 값 읽기/노출 및 유료 API 호출 0. 실 연결·실비용·공급자 교체 운영 검증 전 **4_1 미완료**.
- **4_2 fact_extraction.py:** 금액/날짜/기업/제품/공정/정책 시행일은 허가된 원문 조각에 정확히 있는 값만 채택. 할루시네이션 수치는 UNKNOWN으로 보류. 실제 골드셋 사실·수치 정확도 95% 미측정 → **4_2 미완료**.
- **4_3 claim_boundaries.py:** 공식 채널 관측/배포 보도자료/독립 보도/SNS/AI 가설 분리. 최초 공개시각/issuer 인증은 boolean으로 만들 수 없고 기존 AnchoredOfficialPublication 증거가 필요. 4_3 기본 기능 테스트 PASS.
- **4_4 economic_path.py:** 수요·공급·CAPEX·실적·경쟁 영향 가설마다 반례/미확인 사항 필수. 매출·주가·확정 수혜를 임의 추정하지 않는 기본 기능 테스트 PASS.
- **4_5 analysis_validation.py:** AI 응답·수치 인용·파급 경로의 출처 SHA 연결 검사. 미지원 주장/근거 누락 시 UNKNOWN_HOLD. 실제 원문 사실 검증 API와 오류 복구 검증은 추후 → 미완료.
- **4_6 ai_cost_ledger.py:** 사건·모델·prompt·메타 digest 캐시로 중복 예약 차단, 월 3만원 경고·5만원 상한, 최대 예상 토큰값 예약/실사용 정산. 단가는 운영자 **가정치**이므로 실청구/500건 라벨 평가 전 4_6 미완료.

## 반도체 한 산업 — 5_1~5_5
- **5_1 semiconductor_profile.py: SemiconductorProfile v1 완성.** DRAM·NAND·HBM·웨이퍼 제조·제조장비·소재·기판·고급 패키징·테스트 9개 범위와 메모리 가격/물량/장비CAPEX/소재/패키징/테스트/수율 가설 경로. 타 산업 불허. 이것은 실제 거래·수혜 증거가 아닌 산업 분류표.
- **5_2 supply_chain_graph.py:** supplier/customer 2개 별도 기업ID 검토 증거, 공시/뉴스 문서ID 및 PIT가 일치할 때만 관계 후보 생성. 실제 독립 검증된 거래는 없음 → 5_2 인수 미완료.
- **5_3 semiconductor_impact.py:** 가격·증설·패키징·테스트의 영향 경로를 제품/공정에 구분하며 인과와 매출액은 HYPOTHESIS_ONLY → 실사례 검증 대기.
- **5_4 beneficiary_classification.py:** 직접 거래 주장과 테마 관계를 분리하여 잠재 수혜/잠재 피해/관계 불명만 분류. 수혜 확정과 매출 비중 생성 금지 → 실사례 검증 대기.
- **5_5 beneficiary_graph_contract.py:** 버전 JSON에 근거 ID/SHA·회사 역할/공정/출처 최초 가용 시각·불확실성·payload SHA를 기록. 실제 EraLeader 소비와 실데이터 전달 검증 전 인수 미완료.

## 경계 및 인수
- 사용된 가격·기업·금액·모델 응답은 **합성 테스트 픽스처**이며 실제 반도체 수혜기업이나 최초 웹 공개 증거가 아니다. 실제 AI 유료 호출·실청구/4_2 95%/4_6 500개 평가/5_2 실사례/5_6 반도체 95%/5거래일 자동운영은 완료하지 않았다.
- 기존 1_1~3_5 기능 보존, 2_6 및 3_6 실증 게이트 미완료 유지. EraLeader 코드/DB/Git과 DART/SEC/KRX 수집기 수정 0. NewsCatalystOS Public Git에는 원문·운영 DB·비밀키·개인 자료 공개 금지.


## 2026-10-14 | 4_1 단일 제공자 OpenAI Responses 실제 HTTP 준비 (유료 호출 미승인/미실행)
- 기존 `ai_provider.py` 공통 `AIModel/AIRequest/run_ai_analysis`, `ai_cost_ledger.py`의 사건+모델+프롬프트 월간 비용 SHA 예약·정산을 **그대로 재사용**한다. 신규 `src/newscatalystos/ai_openai_transport.py`는 공식 `https://api.openai.com/v1/responses` 한 목적지에 **명시 `allow_paid=True`**인 경우만 HTTPS POST를 열고, 리다이렉트·자동 재시도를 거부한다. 실제 키는 `OPENAI_API_KEY` 환경변수에서 호출 직전에만 읽으며, 응답 오류·본문·키는 로그로 출력하지 않는다.
- HTTP 요청은 이벤트 SHA/시각 및 최대 512자 승인 공식·라이선스 **메타데이터만** 전송하고, `store=false`, 최대 출력 토큰 제한, 엄격 JSON Schema(`summary, claims, uncertainties`)와 `usage.input_tokens/output_tokens`를 검증한다. 내부 사고/추론은 투자 사실로 인증하지 않는다. 실제 사용 토큰이 등록 상한을 초과하거나 제공자 모델/완료 상태·응답 JSON이 불일치하면 정상 결과로 저장하지 않는다. 서비스 보안상 공급자 JSON 원문/유료 뉴스 기사 본문 저장 금지.
- 통합 `run_budgeted_openai_analysis`는 4_6 승인원장에 예상 **최대 비용을 먼저 예약**한 뒤에만 네트워크 호출을 허용한다. 동일 사건·모델·프롬프트·메타 입력이 `CACHED/IN_FLIGHT_OR_UNSETTLED`이면 추가 유료 호출 0; 장애 시 자동 재시도 없이 기존 예약 비용을 보류한다. 단가 KRW/백만 토큰은 운영자 가정치이므로 실청구 요율/월 비용에 대한 독립 검증이 필요하다. 실제 OpenAI 계정의 API 사용권한·모델/JSON Schema 지원·청구 검증 없이는 **4_1/4_6 완료 판정 불가**.
- 공식 API 참조: https://developers.openai.com/api/reference/resources/responses/methods/create . 모델별 지원 파라미터는 다를 수 있어 요청은 공통 JSON Schema·기본 샘플링 경로를 사용하고 `temperature`와 같은 비필수 옵션을 무조건 전송하지 않는다. 운영자 인증이 별도로 확인되지 않으면 `allow_paid=False` 기본값, credential 누락, 미승인 중요도/PIT/월간 예산 초과 모두 네트워크 전 실패한다.
- 현재 실제 유료 AI HTTP **0회**, 키는 공개·Git 기록 금지. 동작 시험은 테스트 전용 가짜 환경변수와 내부 가짜 HTTP 연결만 사용한다. 테스트 PASS가 실공급자 모델 호출 성공/정답 500건/5거래일 완료를 뜻하지 않는다.


## 2026-10-15 | Gemini API 경로 연결 (실호출 미실행)
- 사용자 선택에 따라 `src/newscatalystos/ai_gemini_transport.py`가 Google Gemini `models/{model}:generateContent` REST 요청을 처리한다. Gemini 키는 호출 직전 `GEMINI_API_KEY` 환경변수 또는 macOS 로그인 키체인의 항목 이름 `newscatalystos`/계정 `NewsCatalystOS.Gemini.API`에서 읽는다. 키 값은 코드·설정파일·공개 Git·로그에 남기지 않는다. 키체인 접근 실패와 키 부재는 예약/HTTP 전 차단한다. 모델명은 비공개 `AIModel` 설정에서 고르고 URL 경로 문자를 제한한다. 공식 API 형식: https://ai.google.dev/api/generate-content 및 https://ai.google.dev/gemini-api/docs/generate-content/structured-output .
- 기존 중요 신규 사건/PIT/짧은 승인 메타데이터 선별, 4_6 월간 최대비용 예약·중복호출 방지, 모델별 캐시와 비공개 보고서·읽기전용 소비를 재사용한다. `allow_paid=True` 없이 HTTP를 열지 않고, 도구/검색 grounding·리다이렉트·자동 재시도를 사용하지 않는다. Gemini `usageMetadata.totalTokenCount - promptTokenCount`를 출력·사고 토큰의 보수적 사용량으로 잡아 정산한다.
- 2026-10-15 사용자가 Gemini 키를 macOS 키체인에 직접 입력했다. 항목 이름·계정의 존재만 키체인 UI와 `security` 종료코드 0으로 확인했으며 키 값은 읽거나 출력하지 않았다. 합성 응답 연결 테스트는 통과했지만 실제 Gemini API 요청은 **0회**다. 키 유효성, 모델별 사용권·현재 원화 환산 단가와 청구 형태는 확인되지 않았으며 운영자가 비공개 `AIModel`에 입력해야 한다. 코드 연결 성공을 실호출 성공이나 운영 인수로 표시하지 않는다.
