# START HERE — NewsCatalystOS

## 유효 기준
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md를 필요한 범위만 읽는다.
V1은 반도체 1산업, 기존 1_1~6_6 36개 기능 범위. 제품 판정은 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md를 따른다. 과거 36/36 기능 기록을 독립 운영·전체 출시 완료로 대체하지 않는다.

## 최신 완료 기능 · 2026-10-17
NEWS-20261017-MARKET-COMMERCIAL-PARALLEL-01 / 15b3848c606353d493f4e215e4ef2fe88ce9edc2 (로컬).
동일 원문의 시장 진출 + 납품 개시 또는 신규 고객 확보를 다섯 가지 기확정 원인과 각 완전 원문 구간에 묶어 경제변화→ThemeStore→검색/기간비교/HTTP→세 화면·고정 JSON에 전달. 시장명은 MARKET_ENTRY 원문에서만 추출, 고객은 새 actor가 아니다. 잘못된 추가 행동·의향·타 제품/주체·시점·부분근거는 차단하고 구판 옵션과 최초시각/PIT 유지.
변경 테스트 tests/test_market_commercial_parallel.py 315 PASS 및 영향 기존 tests/test_delivery_customer_parallel.py 237 PASS(실행 2026-10-17). 합성 양성·로컬 코드/저장/HTTP UI 확인이며 실제 양성/운영 배포/원격 push는 미확인·미수행.

## 보존과 다음
기존 개발경로 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. 운영 원본 /Volumes/T5DATA/1.NewsCatalystOS 및 EraLeader 자산은 변경하지 않는다.
사용자 기존 dirty AGENTS.md·DECISIONS.md·CODEX_PRODUCT_VISION_AND_NEXT_WORK_20261015.md 보존. 무단 API·유료 AI·원본/DB/백업·공개 push·실거래 금지.
다음은 NEXT_TASK.md의 기존 허용 실자료→경제변화/테마→사용자 화면 경로에 남은 실제 연결 장애 해소. 외부 사건 부재 자체를 실패 또는 추가 개발 완료 조건으로 만들지 않는다.
