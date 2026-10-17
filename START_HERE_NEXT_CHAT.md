# START HERE — NewsCatalystOS

## 현행 재개 기준
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 현재 부분을 확인한다. 기존 기능 CONTINUE, V1 반도체 1개 산업, AI 유료/원본·비밀/PIT/안전 정책 보존. 제품 판정: docs/PRODUCT_COMPLETION_CRITERIA_20261016.md · docs/V1_RELEASE_POLICY_2026-10-15.md.
개발 워크트리 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (branch codex/real-data-path). SSD 운영 원본 /Volumes/T5DATA/1.NewsCatalystOS·EraLeader 코드는 불변. 기존 1_1~6_6 36/36은 코드 구현 기록이며 실제 운영·공동 연동 완료로 계산하지 않는다.

## 최근 사용자 화면 실제 연결 — 2026-10-17T10:06:51+09:00
기능 코드 SHA 4f6d6b16b496387b1754b0ed65563079080fb481; 이번 턴은 코드 변경 없음.
기존 scripts/open_research_dashboard.py 실행 옵션만으로 개발 신버전의 격리 HTTP(127.0.0.1 임시포트, 별도 임시 Notes)를 실행하고 SSD 기존 승인 저장 보고를 읽기 전용으로 연결. 2026-10-16 일간 분석 43건, 테마 8개, 기업 후보 5개; 승인된 전체 RSS 판본 173개에서 '반도체' 제목 검색 3건. 정확 산업부 본문 바인딩→POLICY_CHANGE 1테마, 기간별 근거 1추가/신규 독립사건0. 모든 GET HTTP 200, 화면 HTML·JS 연결 정상. 인증 설정/수집 상태/테마 DB 5개 SHA 보존. 로컬 테스트 서버 종료 완료. 기존 8766 서비스·운영 코드/DB·예약·유료AI·GitHub push 무변경.
기존 기능 SHA 2dab08843cd05481e58e29dca00d058e9ebfc435의 기간별 UI도 실제 저장 판본에서 검증. 새 스크립트/관리도구/불필요한 기능 추가 없음.

## 새로 확인한 국소 운영 장애
기존 launchd com.newscatalystos.triage 최근 마지막 종료0; com.newscatalystos.motir 마지막 종료4. MOTIR 로그의 마지막 분석 exit_code4, semantic_ai_attempts1, 문서 분석/수집 상태 READY. 원인은 아직 확정 못했고 예약 운용 완료로 보고하지 않는다. NEXT_TASK.md에서 신규 API·유료 호출·전체 재검증 없이 이 국소 장애를 조사·해소한다.
사용자 기존 dirty AGENTS.md/DECISIONS.md/비전 파일 3개 보존. 배포와 원격 push는 별도 승인/검증 사항이다.
