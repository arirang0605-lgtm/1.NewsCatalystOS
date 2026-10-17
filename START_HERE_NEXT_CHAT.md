# START HERE — NewsCatalystOS

## 현재 개발 기준
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 현재 내용과 git status/HEAD만 확인한다. 사용자 확정: **정상 코드 CONTINUE, 기능 구현 우선, 실제 변경 영향·필수 안전만 테스트**. 핵심 ① 승인 뉴스 수집 확대 → ② V1 반도체 선별 → ③ 신규 중요 경제 변화 → ④ 테마·회사 근거 있는 자동 연결 및 사용자 조회. 검증도구·관리/세부화면 반복 확대 금지.
개발 워크트리 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. 운영 원본 /Volumes/T5DATA/1.NewsCatalystOS는 미배포/불변. EraLeader 코드·DB·Git 수정 및 중복 수집 금지, 검증된 스냅샷 읽기 전용 공유만. 출처권리·SHA/PIT·비밀·기존 유료AI 예산·무주문 보존. 과거 1_1~6_6 코드 36/36 기록은 출시·실운영/공동 인수 완료가 아니다. 완료 조건 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 신규 동작 — 2026-10-17T12:47:15+09:00
NEWS-20261017-FEDERATED-NEW-SOURCES-IN-DASHBOARD / 기능 개발 SHA `78376452d46ebcaf941621faa51ac668853e777d`.
기존 CLI `scripts/open_research_dashboard.py`에 읽기 전용 `--msit-source-root` 선택 추가. 기존 core+motir 스냅샷/보고서와 개발 MSIT 추가 수집 source와 보고서를 이름공간('msit')만 분리하여 검색·같은 일간 화면·정확 기사 저장경제변화 결과에 함께 표시. 파일 합치기/수집 반복/원본DB 쓰기 없음, PIT/SHA/원본 인증·권리 재활용. 불완전한 MSIT press 수집 상태는 coverage_complete=false와 missing_approved_provider_ids 1로 표시.
실자료 CLI HTTP 테스트: 기존 승인 저장 core156 + motir17 판본, MSIT R&D 50판본 = 전체223개. '반도체' 통합검색 4건(기존3 + 신규1); MSIT 실제 당일 일간 기사50(기존 그 날짜 기사0); MSIT 정확 뉴스 판본 상세 `saved_title_analysis.status=READY`/경제 행동0/N/A 수혜. HTTP200. 개발/원본 설정·상태·테마DB 7 SHA 무변경, 임시 HTTP 종료. 합성 독립 두 RSS 출처→2회사 중복 없는 날짜 집계/검색/정확 기사 경제행동 계약/과거 차단 정상. 변경 영향17 PASS, 실패0. 별도 수집/유료AI·본문0. 기능 commit `78376452d46ebcaf941621faa51ac668853e777d`; 운영 SSD/GitHub Public push 미수행. 사용자 dirty3 보존.
개발 실행 예: --reports-root /Volumes/T5DATA/1.NewsCatalystOS/output/feed_analysis --evidence-base "~/Library/Application Support/NewsCatalystOS" --document-reports-root "~/Library/Application Support/NewsCatalystOS/document_analysis" --msit-source-root /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project/output/msit_live_dev --notes-root 사설임시폴더 --port 0 --no-browser. 사용자 셸에서 ~가 인용될 때 경로 확장 주의.

## 다음
NEXT_TASK.md: MSIT press 최초 dev scheduler 실패 후 1시간 출처 호출 예약 제한(2026-10-17 **13:02:15 KST 이후**)을 지킨 뒤 실제 10초 타임아웃 변경 버전으로 한 번 수집하고 반도체 후보→저장 분석→테마/기업 N/A→새 통합 화면 경로까지 확인. 현재 시각이 그 전이면 유료AI·외부 source 재수집 반복 금지, 독립 핵심 기능 진행. 개발 서버 코드 미배포/운영 승인 분리.
