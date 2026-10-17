# PROJECT_STATE — NewsCatalystOS 현재 재개 상태

2026-10-17T09:33:08+09:00; 브랜치 codex/real-data-path / 기능 SHA `2dab08843cd05481e58e29dca00d058e9ebfc435`. 기존 36개 세부 코드의 36/36 기록은 유지하되 실제 제품 운영·출시·공동 연동 완료로 계산하지 않는다. V1 반도체 1산업, EraLeader는 검증된 스냅샷 읽기전용. 적용 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md.

## 새로 작동하는 기능
- NEWS-20261017-ARTICLE-THEME-PERIOD-HISTORY: 승인 완료 동일 RSS (provider/event/titleSHA) 및 기존 허용 공식 본문 binding으로 확인한 동일 theme_id에 한해서 GET /api/news-evidence의 `theme_id/since/as_of` 기간 조회를 허용. 기존 compare_themes에서 최초 발견·독립 사건·신규 근거·상충/철회·기업/상태 변화와 원문 링크를 선택하고 기존 JS renderThemeChanges로 화면 표시. 과거 시점에 링크 근거가 없다면 404/N/A. 날짜 초과/순서 오류 명시, 원본/DB 쓰기·새 수집·유료AI 없음.
- 변경 집중 테스트: `tests/test_news_article_period_change.py` 신규 3(기사 연결/NO_CHANGE/시점거부, 동일사건 재보도, 공식 철회), 수정 브라우저3, 기존 기사/허용 본문/테마·대시보드 회귀 포함 **31 PASS / 실패0**, Python·JS 구문/Git diff 검사 완료.
- 실제 승인 자료: 산업부 '반도체 메가프로젝트 전담국 출범' 본문 정책 테마 1. 10/15 최초 관측부터 1독립 행동·3출처 근거, 10/15 19:02 KST 이후 0독립·1추가 근거, 10/16 이후 0독립·0근거/NO_CHANGE. 특정 기업0·실제 거래/수혜 미확인. 운영 registry/상태 SQLite/ThemeStore 5파일 SHA 불변.
- 작업트리는 로컬 커밋만. 운영 SSD/상시 8766 서비스 배포·GitHub push 미수행, 이전 명시 push 거절 우회 없음. 사용자 기존 dirty3 변경없음. 실자료 확인과 독립 운영·연동 인수는 별도.

## 다음
NEXT_TASK.md — 개발 대시보드가 기본 빈 reports-root 대신 실제 보존된 운영 보고를 읽기전용 옵션으로 열어 뉴스검색/일간/테마/기간이 한 사용자 화면에서 실제 작동하도록 실행 장애 해소. 기존 기능을 다시 만들거나 원본/운영 DB·타 프로젝트를 변경하지 않는다.
