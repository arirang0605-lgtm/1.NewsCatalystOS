# START HERE — NewsCatalystOS

AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md와 실제 Git 상태를 확인한다. 최신 사용자 지시가 우선한다. 사람 검수 조건을 복구하지 않는다.

운영: `/Volumes/T5DATA/1.NewsCatalystOS`
작업 체크아웃: `/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project`

**2026-10-16 개발 방향 전환 승인:** 개별 표현 규칙 추가보다 뉴스 의미 추출→기사 연결→공통 원인/테마 설명의 전체 사용자 경로를 우선한다. 기존 작동 코드와 원본·사용자 변경은 보존한다.

현재 첫 단계: Gemini 의미 추출을 기존 사건/테마/조회/JSON에 연결했다. 명부 없는 회사명도 출처 표현으로 활용한다. 관련 245 PASS, 실제 기사 2건 분석/원장 추정 1.7528원. NICE평가정보를 기존 후보에 연결하고 사건 수 유지. 클루닉스는 추가 사건 미추출. 운영 후보 4개, 실자료 다기업 테마 성과 아직 없음.

두 시간별 예약 서비스는 의미 추출 활성, 매체별 실행당 새 호출 1회/기존 월 원장 유지. replay는 캐시만 사용하며 정상 확인했다. 다음은 NEXT_TASK의 기존 허가 본문 의미 추출 및 제목 사건과의 근거 연결이다. 무인 운영·SHA/PIT·비밀·EraLeader 읽기 전용·실주문 금지를 유지한다.
