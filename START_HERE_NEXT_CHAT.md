# START HERE — NewsCatalystOS

## 현재 개발 기준
승인된 V1 반도체 산업 범위와 기존 1_1~6_6 기능 기록을 보존한다. 최신 AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 순으로 필요한 정보만 확인한다.
완료 판정은 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md / docs/V1_RELEASE_POLICY_2026-10-15.md를 따르며 과거 코드 36/36을 제품·실운영 완료로 계산하지 않는다.
개발 작업트리 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. SSD 운영 원본/DB, EraLeader 코드는 읽기 전용 또는 불변.

## 최신 신규 작동 기능 — 2026-10-17T08:45:29+09:00
NEWS-20261017-DASHBOARD-FEDERATED-NEWS-SEARCH / 73d6afb412d07f5bc4d6d286b793aa4778a85c1b (로컬 코드)
기존 두 공급자 워크스페이스의 SHA 확인 완료 RSS 제목 검색을 로컬 대시보드 '전체 저장 뉴스 검색'에 연결했다. 입력 검색어/반도체 후보 필터→기존 재사용 검색→HTTP /api/news-search→출처·시각·제목·N/A 표시. 새로운 수집기/검색 인덱스/유료 AI/실주문 없음. 출처가 빠지면 부분 결과로 분리하고 중복 제목은 독립 사건으로 승격하지 않는다.
신규 집중시험 3 PASS, 인접 대시보드/기업검색 15 PASS. 실제 허용 저장 173개 판본(core156/motir17)에서 반도체 제목 3건, HTTP200/coverage=true, 네트워크·AI 호출0. 공개 전 민감정보 체크/코드 검증·사용자 dirty3 보존. 원본 공급자 설정+상태 DB4건 SHA 불변. 이전 실제 운영 보고서 2026-10-16 저장 기사43·테마8·후보5는 읽기 전용 조회로 확인. 실증은 저장 제목 검색이며 경제적 사실·실거래·반도체 수혜 확정은 아님.
기능은 **개발 작업트리 로컬 커밋만**, 운영 SSD/기존 8766 서버로 배포/반영하지 않았고 GitHub push 시도 없음.

## 기존 기능 · 다음
직전 시장진출+납품/신규고객 소스병렬 기능 SHA 15b3848; 신규315/기존237 PASS(과거 기록 재사용). 합성 양성/실기사 특정조합 미확인, 운영 미배포.
다음은 NEXT_TASK.md: 저장 검색 결과 원문 판본에서 기존 경제변화·테마·기업 근거를 같은 ID/SHA/시점으로 연결하여 기사→사건→기업 확인 경로를 완성. 저장 근거가 없으면 N/A, 새 허위 회사·수혜 주장 금지.
사용자 기존 dirty AGENTS.md·DECISIONS.md·CODEX_PRODUCT_VISION_AND_NEXT_WORK_20261015.md 보존. 원본/비밀/사용권/PIT·월5만원 한도·Era 읽기전용·실주문/무단 push/유료 API 금지.
