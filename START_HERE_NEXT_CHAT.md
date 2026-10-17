# START HERE — NewsCatalystOS

## 최신 재개 순서와 사용자 약속
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 현재 내용 및 Git status만 확인. 기존 정상 코드 CONTINUE, 개발은 ①승인 뉴스 자동 수집 확대 → ②V1 반도체 선별 → ③중요 경제 변화 판별 → ④근거 있는 테마·관련 기업의 저장/화면 출력 순서. 추가 검증·관리도구/세부 UI 확장으로 기능 구현을 늦추지 않는다. 출처권리·PIT·키·AI 예산/중복 과금·실주문 금지 유지.
개발 워크트리 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. 운영 SSD /Volumes/T5DATA/1.NewsCatalystOS와 EraLeader 코드·DB·Git은 불변, 검증된 EraLeader 공유 스냅샷은 읽기전용. 1_1~6_6 36/36은 기존 코드 구현 기록이지 제품 운영·출시/실연동 완료는 아님. 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md, docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 동작 — 2026-10-17T13:55:12+09:00
로컬 feature SHA 926031a995955635f3320ecfc1ec1805b9e9df25. 삼성전자 한국 뉴스룸 RSS(20건)와 SK하이닉스 한국 뉴스룸 RSS(10건)를 기존 승인 수집·ACK/중복제거·규칙 경제 변화 분석·저장 경로로 1회씩 실행, 전부 exit0. private dev source output/company_live_dev, 공개 metadata-only 권한 config/semiconductor_company_rss_metadata_registry.json. 삼성 제작 콘텐츠 이용안내와 SK 뉴스룸 이용가이드의 제3자 콘텐츠/저작권 제한을 감안해 RSS 제목·ID·URL만, 본문/이미지 없음. AI0, 기존 운영 DB/SSD/키/원본 변경0.
기존 core156/motir17/MSIT100/기업30 = 총 승인 저장 RSS 303 판본, 실제 4개 독립 워크스페이스에서 검색·일간 화면·회사 뉴스 상세 HTTP200. 하이닉스 검색 기업 기사6, 신규 회사기사30, 2026-10-17 일간130, source coverage complete. 신규 회사 제목의 반도체 후보 SK10/삼성0, 명시 경제 행동0 → 테마/실수혜0 정상 N/A. 별도 source 등록 예시: --msit-source-root /절대/msit_root --additional-source-root company=/절대/company_root. 기존 MSIT 옵션 호환·출처 독립 theme/기업 구분 보존. 기존 원본+개발 registry/수집 state 9 파일 SHA 읽기 후 미변경. 격리 임시 HTTP 종료. 변경 영향 42 PASS/실패0. GitHub 공개 push 및 운영 launchd 배포 미실시, 사용자 dirty3 보존.

## 다음
NEXT_TASK.md: 실제 반도체 계약·수주·설비투자·양산 제목을 다루는 공식 기업 보도자료/IR RSS를 추가 발굴하고, 사용권·형식 확인한 source부터 기존 collector로 수집→경제 사건→테마/기업→화면까지 실자료 정상 경로를 완성한다. 당장 명시 행동 없는 제목을 AI/추론으로 확정 계약·수혜로 가공하지 않는다.
