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
