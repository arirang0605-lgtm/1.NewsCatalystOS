# NEXT_TASK — 실자료가 표시되는 읽기 전용 사용자 대시보드 실행 경로

최신 완료 NEWS-20261017-ARTICLE-THEME-PERIOD-HISTORY `2dab08843cd05481e58e29dca00d058e9ebfc435`. 기존 기사 선택→테마의 기간 변화 조회 기능을 로컬 개발 브랜치에 연결, 집중 31 PASS. 실자료 정책 사건과 중복출처/NO_CHANGE 구별도 확인. SSD 운영 반영/공개 push는 미실행.

## 현재 사용자 사용 흐름의 구체적 장애 — NC-06/OP-01
개발 대시보드의 기본 reports-root는 개발 작업트리 output/feed_analysis이고, 승인된 운영 저장 실제 보고가 있는 `/Volumes/T5DATA/1.NewsCatalystOS/output/feed_analysis`와 다르다. 이전 읽기전용 조회에서 2026-10-16 개발 기본 보고는 0건, SSD 기존 보고는 43건이었다. 이 차이 때문에 최신 개발 UI에서 실제 사용자가 뉴스가 없다고 오해할 수 있다.

1. 기존 `scripts/open_research_dashboard.py`의 `--reports-root`, `--document-reports-root`, `--evidence-base`, `--notes-root`, `--port`, `--no-browser`로 **운영 원본 읽기전용·메모 별도 폴더·개발 독립 HTTP 포트**의 UI→저장 분석보고→기사검색→테마/기업/후속변화 화면을 연결한다. 운영 상시 8766 서버/설정·운영DB·코드는 손대지 않는다.
2. 기존 설정으로 정상 작동하면 새 스크립트·별도 관리 도구를 만들지 않는다. 실제 입력→사용자 표시 장애가 확인될 때만 최소 수정 후 변경 영향 시험과 Git을 남긴다.
3. 기사·본문 사용권, 원본 SHA·PIT·N/A·Era 읽기 전용, 개인정보/유료AI·공통 5만원 예산·실주문 금지 유지. 기존 push 거절을 우회하지 않는다. 개발 임시 HTTP와 실제 운영 배포/예약·출시 인수를 구분한다.
4. 정상 경로 완료 후 남은 핵심 제품 기능·필수 운영 조건만 진행한다. 새 인적 검수/장기 대기/추가 검증을 새 필수 게이트로 만들지 않는다.

제품/운영/연동 완료는 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md의 원래 사용자 기준으로 판단한다.
