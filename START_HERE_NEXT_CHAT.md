# START HERE — 뉴스 경제 변화 먼저 → 산업·기업 연결 → 관찰 확대

기준 2026-10-18T13:16:02+09:00. 사용자 최신 요청: **산업을 먼저 정해 분석기를 추가하는 대신, 허용된 뉴스에서 경제 행동을 먼저 발견하고 산업·기업은 그 뒤 연결한다.** 기존 반도체/전력기기 분석은 심층 해석 기능으로 보존한다. Chat + Remote Desktop Commander로 CONTINUE. 이 문서 → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 항목과 Git 상태만 읽는다. 과거 V1 완료를 다시 미완료로 만들거나 인적검수·관찰기간·관리도구를 새 필수조건으로 추가하지 않는다.

## 현행 완료 기능
공통 경로 bc9e06c의 구현/운영을 재개하여 이어갔다. 기존 run_feed_analysis.py --discover-economy는 산업 선택 없이 공통 경제 행동·원문 대상/회사 → 선택적 산업 단어 힌트 → 미분류 포함 관찰후보를 저장한다. 산업 사전을 전부 제거해도 같은 사건이 남는 시험이 있다. 모르는 업종/제품/당사자는 해당 필드만 미분류/미확보로 남기며, 회사이름으로 업종을 추정하지 않는다. 원문·발행시각/PIT·미확인·무수혜인증은 보존한다.
최신 기능·운영 SHA **7610f2357a4b02d98b7d360953106ba08093173c**: 최근100개 제한 뒤에 오래된 승인 저장제목이 계속 남던 입력 공백을 해결. 기존100개 보고서 단위를 유지하고 같은 관측시각으로 후속 페이지를 처리한다. 원문/수집원장·승인범위·API호출한도 변경 없이 저장분을 끝까지 분석. 페이지 실패는 해당 source만 미처리로 남기고 다른source 계속.

## 실제 근거
2026-10-18 13:13 운영 확인: 기존 승인 제공자8개/현재 저장 제목 **378개**, 경제행동 **26건**, 관찰주제 **21개**, 산업 미분류 **15개**, 출처명시 회사명 **15개**. 원문 단어 힌트는 반도체/핵심광물이며 나머지는 미분류 관찰이다. 21개를 21산업 검증 완료라고 계산하지 않는다. 기존340제목/25사건에서 누락됐던38제목과 관찰사건1을 추가한 것이며, 과거 뉴스를 오늘 발생한 호재로 바꾸지 않음.
관련 고유181개 시험 성공(180개 기존 성공+누락 test import1건 수정/재검증), 직전178개 공통발견 성공은 별도 이전근거. 실제 launchd research-approved 자동시작exit0/기존수집5성공·추가수집0/AI0, discovery8provider 성공·남은페이지0. 현재 HTTP200·JS고정배포 bytes·표준관찰출력21테마 검증. 원본/설정20파일 replay 전후SHA동일, 사용자dirty3·Era코드/DB/Git/예약 쓰기0.

## 운영·경계
개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). dashboard/research-approved 고정코드 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/7610f2357a4b02d98b7d360953106ba08093173c; core/MOTIR 기존정상서비스 그대로. 공통관찰 파생자료 /Users/shmoon/Library/Application Support/NewsCatalystOS/document_analysis/economic_discovery, 기존 운영뉴스원장 /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces. dev output/*_live_dev는 보관본이므로 재수집하지 않는다. 사용화면 http://127.0.0.1:8766/ 의 **뉴스에서 발견한 경제 변화·관찰 분야**, API /api/economic-discovery, 표준 선택출력 ?export=1.
새 발견후보를 기존 반도체 검증공급망·Era 점수에 자동 가산하지 않는다. Era 기존 재료선정 연결은 완료된 별도기능으로 유지, 새 광역후보 관찰은 심층검증/전체시장·기사본문 분석/자동추가출처 사용허가와 다르다. 다음은 NEXT_TASK.md. Public GitHub push 없음, 기존36/36은 V1기록으로만 유지.
