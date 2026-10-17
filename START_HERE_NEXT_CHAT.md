# START HERE — NewsCatalystOS

## 현재 재개 기준
먼저 AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 유효 내용과 Git 상태를 확인한다. 사용자의 최신 지시: **기능 구현을 우선하고 실제 운영에 꼭 필요한 최소 변경 영향 검증만 한다.** 기존 정상 코드 CONTINUE, 검증·관리도구 확대나 동일 실패 반복 점검 금지.
현재 개발: /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. SSD 운영 /Volumes/T5DATA/1.NewsCatalystOS 및 EraLeader 원본/DB/Git 쓰기 금지. 범위 V1 반도체 한 산업, 키/개인정보·유료본문·PIT/예산·실주문 금지.
완료 판정 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md, docs/V1_RELEASE_POLICY_2026-10-15.md. 기존 1_1~6_6 코드 구현 36/36은 제품/실자료/운영·통합 완료가 아니다.

## 최신 신규 작동 기능 — 2026-10-17T10:50:35+09:00
NEWS-20261017-SAVED-TITLE-ECONOMIC-DETAIL / 기능 로컬 SHA `3a5bf844c341c452a93a6709efd7663cd87dc131`.
뉴스검색 결과의 정확 (provider_id,event_id,title_sha256)와 저장 RSS 경제변화 분석 판본을 기존 SHA/PIT 읽기 전용 scan_saved_analysis로 연결해 /api/news-evidence 및 클릭 상세에서 기사별 경제 행동/보도 당사자/계획 단계/근거 수준/저장보고 SHA를 표시. 저장 분석이 없으면 N/A, 분석은 있지만 사건 없음은 명시. 본문 정책 사건/테마와 분리, 추측한 수혜·실거래·회사코드 없음.
신규 집중2 + 변경영향13 = **15 PASS, 실패0**, JS 구문·Git stage 검사. 실제 승인 분석: NICE평가정보 서비스 출시 제목 BUSINESS_START 1건(반도체 V1 성과 아님); 반도체 제목 3건 직접 분석 존재·명시 제목경제행동 0건, 그중 산업부 공식 허용 본문에서 POLICY_CHANGE 1건은 기존 판정 유지. 임시 로컬 HTTP 전체 200, 원본 설정/상태/테마 DB5개 SHA 불변. 네트워크 수집/유료 AI/자동주문0.
새 코드는 개발 작업트리 로컬 커밋만. SSD 상시 8766 서버/launchd와 GitHub push 미반영. 사용자 dirty AGENTS.md/DECISIONS.md/비전 3파일 SHA 불변.

## 다음
NEXT_TASK.md: 기사 상세에서 해당 기사에 실제 보고된 기업의 기존 테마별 포함 이유·공식명부 근거·공급망 관계 및 수혜 미확인을 바로 볼 수 있도록, 이미 있는 회사 검색/테마 기업 API를 **정확 기사·테마 ID·시점**에 한해 연결하는 사용자 기능. 근거·기업이 없는 반도체 정책 뉴스는 N/A. 정규 운영 백업·복원 OP-05는 필수 운영 인수 때 기존 증거를 재사용; 새 개발 작업을 가로막지 않는다.
