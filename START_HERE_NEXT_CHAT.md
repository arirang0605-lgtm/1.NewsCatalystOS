# START HERE — 경제 변화 먼저, 같은 출처의 산업·기업 연결 보완

기준 2026-10-18T14:01:56+09:00. 사용자 승인 흐름: **허용 뉴스 → 경제행동 먼저 발견 → 원문 대상·기업·산업 후속연결 → 미분류 포함 관찰 확대**. 산업전용 분석기를 먼저 늘리지 않는다. 반도체 V1/전력기기 선택형 심층해석·기존 Era연결·원본은 보존. Chat+Remote로 이 문서 → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 항목과 Git 상태를 확인하고 CONTINUE.

## 최신 작동
기능·운영 SHA **c1ba5ae6fc0525866374f661c61ed193e27e4c33**. 기존 공통사건 추출/페이지전부 처리(7610f23)를 재사용해, 실제 저장뉴스에서 빠진 **같은 지원행동의 수신자와 목적절**을 후속연결했다. `to a Subsidiary of <Parent> (<Recipient>)`에서 직접 수신자는 자회사명, 모회사는 원문관계로만 표시. `to Enhance ...` 목적절의 명시 산업단어는 기존 분류힌트로 연결한다. 회사명/CHIPS프로그램으로 업종 추정·모회사 수혜확정·신규공식기업ID 생성 없음.
원래 event/theme ID·회사/산업 필드·ThemeStore는 그대로이고, 새 해석은 보고서에 원문 offset/SHA/시각을 붙인 discovery_source_connections로 추가. 같은 해석 재실행은 최초연결시간/보고서SHA 유지, 이전조회에는 새 회사·산업힌트가 나타나지 않는다. 표준 선택export에는 원본과 구분한 추가 문맥/가용시각을 넣는다.

## 실제 운영 근거
2026-10-18 14:00 HTTP 확인: 현재 **382 저장제목 / 26경제행동 / 21관찰주제**, 산업미분류 **14**(이전15), 직접 출처회사명 **16**(이전15). 원문 해석보완2개: Crucible Metals 직접지원 대상·Korea Zinc 원문상 모회사 관계(법적소유/상장/부모수혜 미확정), Powerex 지원목적절 Semiconductor 단어 근거. 새사건0·새테마0이며 부족한 연결만 보완했다. 기존 'SampleQuantum 같은 회사명'만 있는 자료 등은 계속 미분류.
관련 **175 PASS/FAIL0**. 실제 같은 파생 snapshot 재분석 중 ThemeStore byte SHA 불변, source/설정/사용자19파일 unchanged. 운영 research-approved 자동시작exit0·기존수집5성공/새기사0/AI0·발견source성공. 새metadata해석만 추가, 기존 고정재료전달 ALREADY_PUBLISHED. 실제 watcher API/선택export21테마·새JS SHA·과거PIT 확인. Era코드/DB/Git/예약·선정변경0.

## 경로·보존
개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, codex/real-data-path. dashboard/research-approved 코드 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/c1ba5ae6fc0525866374f661c61ed193e27e4c33, core/MOTIR 기존정상서비스 유지. 공통파생 /Users/shmoon/Library/Application Support/NewsCatalystOS/document_analysis/economic_discovery, 기존source /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces. dev output/*_live_dev는 보관본(수집실행금지). UI http://127.0.0.1:8766/ 의 뉴스에서 발견한 경제 변화·관찰 분야, API /api/economic-discovery 및 ?export=1.
증거/rollback: output/discovery_source_context_20261018/real_source_context_proof.json·feature_commit.json·activation.json·operational_source_context_proof.json. 사용자dirty AGENTS/DECISIONS/비전3·원본SSD·비밀·권리/PIT/SHA·비용/무주문 보존. Public GitHub push 없음. 36/36은 기존V1기록, 21주제=21산업완료가 아니다. 다음은 NEXT_TASK.md.
