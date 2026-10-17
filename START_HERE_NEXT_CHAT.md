# START HERE — News 재료 판단 → Era 후보 판단 → 독립 전략

기준 2026-10-18T00:07:53+09:00. 사용자 목적은 docs/ROLE_ALIGNMENT_20261017.md. 기존 정상 코드 CONTINUE, 뉴스 신규/반복/변경과 기업별 조건부 영향 → Era의 독립 전시장 후보 판단 → 개별 전략의 매수·매도·손절 순서. 역방향 재무표·뉴스 소스 수/관리도구 확대가 본 경로를 대신하지 않도록 한다. 이 문서→AGENTS.md→PROJECT_STATE.md→DECISIONS.md→NEXT_TASK.md 최신 부분과 Git 상태만 확인한다.

## 최신 작동 — 기존 정기 뉴스처리에서 고정 재료판본 자동 발행
기능/배포 SHA **168ea012ddcade5555964f1f849edae4200fb261**. 기존 research-approved 시간당 실행의 수집·분석 뒤, 원 ThemeStore/재료 비교/공식 기업식별/표준 v1·v2 bundle을 재사용해 **News 소유 material_outbox**에 불변 발행. 이전 성공 판본이 비교 기준이고, 같은 입력은 ALREADY_PUBLISHED(파일·SHA·게시시각 동일). 자정/조회시간/재무표 가격 갱신만으로 새 재료를 생성하지 않는다. 한 영역이 실패하면 그 영역의 마지막 정상 판본·비교기준을 남기고 정상 영역은 계속 발행한다. 실패·복구/철회·진전·반복/PIT/동시발행 정상·음성 경로 포함.
**기존 /api/themes 기본 URL은 게시 완료판본이 있으면 그 bytes를 그대로 제공한다.** /api/themes?publication=latest 는 같은 불변판본, as_of 과거조회는 당시 게시분만. since/as_of 등 명시 분석조회는 원 경로 유지. 읽기는 출처 워터마크나 게시기준을 변경하지 않음. 발행은 소비자 수신·Era 선정완료가 아니다.
실제 2026-10-18 00:03 KST launchd 자동실행 exit0/뉴스5출처 성공(모두 NOT_DUE, 재수집0), 4저장영역17테마 고정판본 PUBLISHED. API 기본/명시/파일 bytes 일치; 기존 Era reader 실제 읽기17 통과. SK 투자계획은 NO_NEW_MATERIAL/NO_NEW_CATALYST, CAPEX·SUPPLY 조건부경로/반증과 DART00164779 연결 유지. 과거 게시이전 조회404, 실제수혜/시장신규성 미확인.
관련 시험94 PASS/0 FAIL 후 최종 기본API 변경범위48 PASS/0 FAIL(중복 포함, 합산해 진행률로 세지 않음). 개발 실자료 반복발행은 동일SHA ALREADY_PUBLISHED. 새 개발용 원본수집/유료AI0. Era 소스/DB/Git/예약 쓰기0, 그쪽 별도 담당자의 정상 HEAD 갱신을 보존한다.

## 운영 위치
개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path), 사용자 dirty AGENTS/DECISIONS/비전3 보존. dashboard/research-approved 고정코드 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/168ea012ddcade5555964f1f849edae4200fb261; core/MOTIR 기존 정상코드·설정 그대로. 운영 뉴스 원장 /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces, dev output/*_live_dev는 보관본(재수집금지). 전달 폴더 /Users/shmoon/Library/Application Support/NewsCatalystOS/document_analysis/material_outbox; 원 ThemeStore/키/비용/원문 보존. HTTP http://127.0.0.1:8766/.
증거/롤백: ignored output/material_delivery_continuation_20261017/{activation.json,operating_material_publication_proof.json,rollback/}. 실제 게시SHA 4b7cd2adc53cc3a5aaa65aad80e251dd90d6a07e971c58596dea034fbccf35bc. Public GitHub push0. 과거 코드작업36/36은 Era실제선정·독립전략인수 완료가 아니다.
다음은 NEXT_TASK.md.
