# START HERE — NewsCatalystOS

## 현재 유효 기준
기존 코드 CONTINUE, V1 반도체 1산업. 먼저 AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 부분과 Git 상태를 확인한다. 운영기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md · docs/V1_RELEASE_POLICY_2026-10-15.md.
현재 코드 위치 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). SSD 운영 원본 /Volumes/T5DATA/1.NewsCatalystOS 변경 금지. 과거 세부기능 36/36은 제품·실자료/독립 운영/통합 출시 인수 완료가 아니다.

## 최근 새로 작동하는 사용자 기능 — 2026-10-17T09:33:08+09:00
NEWS-20261017-ARTICLE-THEME-PERIOD-HISTORY / SHA `2dab08843cd05481e58e29dca00d058e9ebfc435` (로컬).
기존 뉴스 검색→SHA 인증 기사→명시 RSS/허용 본문→테마에서 사용자가 시작/종료일을 선택해 기존 ThemeChanges 저장판본의 신규 사건/추가 근거/후속/상충/정정/철회/상태 전환·원문 링크를 열람한다. 기존 /api/news-evidence+compare_themes+renderThemeChanges 재사용. 동일 기사·테마 ID와 질의 종료시점에 실제 확인된 링크만 제공, 과거에 없는 링크·동명 기업 추론 금지. 변화 없으면 NO_CHANGE, 추가 출처는 독립 사건으로 중복 계산하지 않는다.
변경영향 `tests/test_news_article_period_change.py` 등 6개 파일 집중 실행 **31 PASS**, 실패 0. 합성 정상/철회·무변화·중복출처/이전시점 거부와 JS 버튼 구동 확인.
실자료: 산업부 '반도체 메가프로젝트 전담국 출범' 정책 테마. 10/15 최초구간 독립 행동+1/출처+3, 10/15 19:02 KST 이후 독립+0/추가 출처+1, 10/16 이후 독립+0/출처+0·NO_CHANGE. 원본 설정·상태·테마DB 5파일 SHA 불변. 기존 본문 정책 근거가 있는 기사만 연결되며 거래·수익·실수혜 검증 아님.
개발 코드 로컬 커밋만 수행, 운영 SSD·상시 8766 서버 및 GitHub 미반영. 사용자 dirty AGENTS/DECISIONS/비전 3파일 SHA 보존.

## 다음
NEXT_TASK.md: 기존 개발 UI 일간 보고의 기본 저장 경로에는 실제 운영 보고 기록이 없어 특정 날짜가 0건으로 보이는 **읽기 전용 사용자 화면 실행 장애**를 기존 --reports-root 등의 옵션으로 우선 해결한다. 운영DB/원본/상시서버 변경 없이 다른 포트·격리 메모·읽기전용 기사/테마/기간 UI가 실제 자료를 함께 보여주는지 확인. 기존 옵션이 충분하면 도구를 새로 만들지 않는다.
