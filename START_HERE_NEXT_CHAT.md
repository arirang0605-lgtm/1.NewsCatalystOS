# START HERE — NewsCatalystOS

## 재개 기준
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 최신 유효 부분을 확인한다. V1은 반도체 한 산업, 기존 1_1~6_6 총36개 기능의 코드 구현 기록을 유지하며 실제 운영/출시/통합 인수는 따로 판정한다.
기능/운영 기준: docs/PRODUCT_COMPLETION_CRITERIA_20261016.md, docs/V1_RELEASE_POLICY_2026-10-15.md.
개발: /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). 원본 운영: /Volumes/T5DATA/1.NewsCatalystOS (미배포, 불변).

## 최신 작동 기능 — 2026-10-17T09:00:05+09:00
작업 NEWS-20261017-EXACT-SAVED-ARTICLE-EVIDENCE / 기능 SHA 2a19b9da9923538344944c87e6b787caa51aeb87 (로컬).
기존 뉴스검색 항목의 (provider,event,titleSHA) 고정 판본 클릭 → /api/news-evidence → 승인 완료 RSS 원문 재확인 → 기존 ThemeStore의 정확 source_binding/document SHA/가용시각 매칭 → 저장된 사건·테마·기사 당사자와 출처 링크 표시. 기사와 사건을 유사 제목/추론으로 결합하지 않는다. 직접 연결 증거 없는 자료는 N/A, 변경/과거 판본·PIT 및 철회 상태 구별, 공식 ID 없는 회사는 식별 미확인.
테스트: 신규 tests/test_saved_article_evidence.py + 변경 UI tests/test_dashboard_federated_news_search.py 6 PASS, 인접 tests/test_federated_news_search.py + tests/test_research_dashboard.py 26 PASS(합계32, 실패0). 실제 저장 자료 독립 조회: '피지컬' 검색 2 중 1건 READY(기존 사업개시/기사 내 회사1), 1건 N/A; '반도체' 검색 3건은 엄격한 RSS 원문 판본 기준으로 모두 N/A. 뉴스/테마 SQLite 및 공급자 설정 5파일 SHA 불변; 새 외부 호출·유료AI·중복 수집 없음. 비반도체 제목 일치 사례는 반도체 산업 발굴 성과로 주장하지 않는다.
개발 로컬 코드/임시 HTTP만 검증, SSD 상시 8766 대시보드/운영 배포 및 GitHub push 미수행.

## 현재 다음 작업
NEXT_TASK.md: 저장된 산업부 RSS 기사와 이미 보존된 공인 본문 분석의 명시 RSS↔본문 바인딩이 있는 경우에만 반도체 정책 ThemeStore 사건/근거를 같은 선택 기사에서 열람하도록 연결한다. 기존 motir_article_binding·motir_document_analysis 활용, 문서 SHA를 RSS 제목 SHA로 혼동하거나 기사 공통 키워드만으로 연결하지 않는다. 근거 부족은 해당 결과 N/A.
보존: 사용자 dirty AGENTS.md/DECISIONS.md/CODEX_PRODUCT_VISION_AND_NEXT_WORK_20261015.md, PIT/출처/비밀/공통예산, EraLeader read-only, 실주문·임의 배포 금지. 기존 원격 push 거절 우회하지 않는다.
