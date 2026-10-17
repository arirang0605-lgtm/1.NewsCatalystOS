# PROJECT_STATE — NewsCatalystOS 최신 재개 상태

기준 2026-10-17T09:17:39+09:00 / 작업트리 codex/real-data-path. 기존 36/36은 과거 **핵심 코드 구현** 기록이며 운영·실자료 인수/두 프로젝트 연동은 미완료 구분 유지. 적용 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md.

## 최근 작동 기능
- 작업 NEWS-20261017-MOTIR-RSS-DOCUMENT-EVIDENCE, 기능 SHA `26b8360daa1cd28fe5886106c8dfe13e4a2f221f`. 승인 완료 산업부 RSS의 정확 provider/event/title SHA·URL·RSS가용시각으로 기존 문서 바인딩을 확인하고, archive/receipt/document SHA·현 시점 사용권·저장 본문 보고서·서로 독립된 본문 가용시각·테마 사건 ID/근거 SHA가 모두 연결될 때만 허용 본문 정책 사건을 GET /api/news-evidence + 기존 검색 상세 화면에 표시한다.
- 공식 본문 경로는 RSS 제목 분석과 분리. 반도체 정책 사건만 표시, 원문 전문 비공개, 동명/주제 유사로 회사·매출·수혜를 추측하지 않는다. 중복 본문 재분석은 동일 이벤트 1건으로 노출, 철회/과거/PIT 경계 유지, 부재·권리철회는 항목별 N/A.
- 테스트: 신규 `tests/test_motir_saved_document_evidence.py` 4 PASS + 수정 기존 검색 브라우저 3 PASS = **7 PASS**, 영향 기존 `test_saved_article_evidence.py`, `test_motir_article_binding.py`, `test_motir_document_analysis.py` 합계 **23 PASS**. 총 30 PASS, 실패0; JS·Python 구문 및 Git diff 검사 성공.
- 저장 실자료: 산업부 '반도체 메가프로젝트 전담국 출범' HTTP200, 공식 본문 정책 `POLICY_CHANGE` 1테마 **READY**, 직접 기업0·실수혜 미확인. '반도체 설계 청년 인재' HTTP200/명시 경제 변화 없음 `N/A`. 비교한 6개 원본 설정·SQLite·바인딩 파일 SHA 불변; 신규 API/수집/유료AI 호출0.
- 구현·로컬 합성/실자료 읽기 증거는 확인했으나 **운영 SSD/상시 서버 배포와 GitHub push 미수행**, 실제 예약 운영 증거와 출시 인수 별개. 사용자 기존 dirty3 불변·EraLeader/운영 원본 무변경.

## 다음
NEXT_TASK.md: 검색 결과의 정확 기사/테마 사건에 해당하는 기존 ThemeChanges 후속·정정 이력을 기간 기준으로 바로 읽는 UI 경로. 원자료 새 조인·관리 시스템 추가/전체 회귀 반복 대신 사용자 입력→기존 저장 변화→조회 기능을 우선한다.
