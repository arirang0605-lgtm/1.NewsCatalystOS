# START HERE — NewsCatalystOS

## 재개 기준
현재 NewsCatalystOS 개발 브랜치: /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, codex/real-data-path. AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 최신 내용만 확인한다.
기존 1_1~6_6 36개 코드 구현 기록은 유지하되 제품/실자료/독립 운영/공동 연동 인수와 구분한다. 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md, docs/V1_RELEASE_POLICY_2026-10-15.md. V1 반도체 1산업, EraLeader 스냅샷만 읽기 전용, 원본/PIT·기밀·비용·주문 금지. SSD 운영 원본 /Volumes/T5DATA/1.NewsCatalystOS 미배포·불변.

## 최신 실제 기능 수정 — 2026-10-17T10:35:59+09:00
NEWS-20261017-MOTIR-OPTIONAL-SEMANTIC-RESERVATION / 기능 SHA `b23a9acdb1e348b22e0b295bba2ddb70f6d72b73` (개발 로컬만).
MOTIR 예약 exit4의 직접 원인은 RSS 분석17건 중 구형 반도체 기사1건의 optional semantic AI 미정산 예약. 지난 예약 기록이 있으면 SQLite 비용원장을 읽기 전용으로 확인하여 재유료 호출 없이 `AI_PREVIOUS_CALL_UNSETTLED`/별도 N/A로 남긴다. 예약된 기존 문서는 정규 소스 RSS 분석 정상 판정을 방해하지 않되 미완료 숫자·requested_ai_complete=false는 로그에 남긴다. AI가 실제 중요한 신규 제목에만 사용되도록 예약 시 24시간 내 승인 V1 검색 후보 + 기존 triage 후보에만 유료 의미 분석 가능; 수동 명시 기사 분석과 기존 AI 캐시는 보존. 새로운 강제 검증/인적 검수 없음.
수정 인접 시험 160 PASS / 실패0. 현재 실제 미정산 기사 read-only 테스트: AI 외부 호출0·비공개 비용 DB/AI 캐시/보고서 SHA3 불변. 승인 저장 MOTIR RSS 17건으로 격리 개발 scheduler replay-only(유료 AI/외부 수집0): 종료코드0, 분석17, 보류1, 6개 원본 파일 SHA 불변, 보고서 SHA 검증. 이 실증은 **예약 유료 운영 tick 검증이 아님**. 기존 launchctl com.newscatalystos.motir은 여전히 SSD 구버전을 실행하므로 이전 종료4 판정 유지; 운영 배포/push 시도 없음.

## 다음
NEXT_TASK.md — 운영 갱신 승인이 없는 OP-02 실서비스 증거는 대기로만 기록한다. 독립 운영 필수 OP-05: 기존 backup_sqlite/restore_to_new_dir를 그대로 사용해 사본을 별도 비공개 폴더로 복원하고 읽는 정상 경로를 한 번 확인. 재수집/유료AI/원본 DB 쓰기 금지. 기존 실제 복원 유효 증거가 충분하면 재실행하지 않는다.
사용자 dirty AGENTS/DECISIONS/비전3파일 불변 보존.
