# NEXT_TASK — 뉴스 검색 결과 → 기존 경제 변화·테마·기업 근거 연결

## 기준
최신 완료: NEWS-20261017-DASHBOARD-FEDERATED-NEWS-SEARCH / 73d6afb412d07f5bc4d6d286b793aa4778a85c1b. 전체 저장 뉴스 검색 입력→기존 SHA 승인 워크스페이스 검색(core/motir)→HTTP/UI 제목·원문 링크로 전달. 새 집중3+인접15 PASS, 실제173판본 중 '반도체' 3제목 표시, 외부 호출0. 원문·운영 DB/설정 보존. 개발 로컬만 반영, 운영 배포와 실제 투자 수혜 검증은 별개.

## 다음 단일 미완료 사용자 기능
기존 로컬 대시보드 '전체 저장 뉴스 검색' 결과에서 **선택된 정확한 (provider_id, event_id, title_sha256) 기사 판본**의 기존 저장 경제변화/테마/직접 관련 기업·출처로 이동하거나, 근거가 아직 없으면 명시적인 N/A를 보여준다 (NC-02/03/04/06의 조회 연결).
입력: 검색 결과 정확 원문 출처와 보관 SHA/가용시각 → 처리: 기존 저장 FeedAnalysis/ThemeStore의 경제 사건/기업 식별 증거 조회 및 동일 판본 확인 → 출력: 기사 검색 결과 옆 사건/테마/기업 맥락(검증/미확인 구분).
- 기존 search_completed_workspaces, ThemeStore, research_dashboard 및 회사 증거 조회 경로를 재사용. 별도 수집/검색/비교 엔진·임의 공식기업ID·뉴스 본문 저장 금지.
- 같은 이름/기사 유사도만으로 다른 기업·테마 연결하지 않는다. 사건/수혜·계약은 source-reported 또는 inferred로 구별하고 독립 확인을 가장하지 않는다.
- 최초 source_available_at·분석/테마 decision_at과 현재 질의시각을 지키고, 정정/철회·복수판본·출처 누락은 정확히 분리한다. 원문 SHA/버전 불일치 시 fail-closed/N/A.
- 실제 저장 입력에 기존 ThemeStore 근거가 있으면 링크를 확인하는 정상 경로가 있어야 한다. 근거 없는 자료는 해당 항목만 N/A. 같은 증거의 기존 테스트 재반복 금지.
- 로컬 코드+변경영향 집중시험→로컬 Git→상태 MD. 운영 원본/사용자 dirty3/PIT·비밀·기존 월 예산·Era 읽기전용 및 GitHub push 거절 경계 유지.

완료 판정: docs/PRODUCT_COMPLETION_CRITERIA_20261016.md. 기존 코드36/36은 별도 운영·실자료·연동 제품 인수를 대신하지 않는다.
