# START HERE — NewsCatalystOS

## 현재 개발 기준
사용자 지시대로 기존 코드 CONTINUE, V1 반도체 1산업만 확인한다. 최신 AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md를 필요한 범위만 읽는다.
제품 완료 판정: docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md. 종전 1_1~6_6 36/36 기능 구현 기록은 유지하되 제품 운영·실자료·연동 인수 완료로 취급하지 않는다.
개발 코드: /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). SSD 운영 원본 /Volumes/T5DATA/1.NewsCatalystOS는 수정·배포하지 않는다.

## 최신 기능 — 2026-10-17T09:17:39+09:00
NEWS-20261017-MOTIR-RSS-DOCUMENT-EVIDENCE / 로컬 기능 SHA `26b8360daa1cd28fe5886106c8dfe13e4a2f221f`.
산업부 공식 RSS 기사 정확 provider/event/title SHA → 기존 승인 본문 바인딩(별도 archive/document SHA) → 저장된 본문 분석 → ThemeStore의 반도체 정책 사건·테마를 검색 상세 HTTP/화면으로 연결. 현재 문서 사용권·원문 SHA·본문 분석 시각·테마 기록 시각을 확인하고 원본·유료 본문·거래/수혜 확정은 표시하지 않는다. 정확 바인딩 없는 기사/경제 변화 없는 공식 본문은 N/A.
집중7 PASS(새 4 + 수정 화면3), 기존 영향23 PASS, 실패0. 실제 산업부 '반도체 메가프로젝트 전담국(局) 출범' 기사: HTTP200/정확 본문→POLICY_CHANGE 1테마 READY, 기업 당사자 0. '반도체 설계 청년 인재' 기사: HTTP200/본문 경제변화 N/A. 원본 설정·수집상태·테마·본문바인딩 6파일 SHA 불변.
기능은 **개발 로컬만** 확인, 운영 SSD/기존 8766 서버 미배포·공개 GitHub push 미수행. 사용자 dirty AGENTS.md·DECISIONS.md·CODEX_PRODUCT_VISION_AND_NEXT_WORK_20261015.md는 불변.

## 다음
NEXT_TASK.md — 검색 결과에서 확인된 정책 사건의 기존 후속·정정·기간 변화 기록을 직접 볼 수 있도록 연결(NC-05/06). 기존 ThemeStore/ThemeChanges 사용, 빈 변화·자료결측은 N/A. 추가 수집·유료AI·공식회사 추론/실주문·EraLeader 수정 금지.
