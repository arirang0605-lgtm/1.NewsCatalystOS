# START HERE — NewsCatalystOS

## 현재 작업 기준
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 현재 지침과 Git 상태를 확인한다. 기존 코드 CONTINUE·실사용 기능 우선·운영 필수 검증만. 현재 개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path), 원본 SSD /Volumes/T5DATA/1.NewsCatalystOS 수정·배포 금지. EraLeader 검증 완료 스냅샷만 읽기 전용; 타 프로젝트 무관. 반도체 V1 한 산업, 비밀·출처/유료 본문·PIT/비용·실주문 보호. 제품 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md. 1_1~6_6 과거 36/36은 코드 구현 이력이며 운영/출시/실연동 완료로 간주하지 않는다.

## 최신 기능 — 2026-10-17T11:45:04+09:00
NEWS-20261017-EXACT-ARTICLE-COMPANY-QUOTE / 로컬 기능 SHA `388da7ff99119ac584b3fa7c455a72aeb700cfb5`.
기존 검색 기사→같은 RSS provider/event/title SHA→저장 사건/테마의 정확 회사 ID + 근거 SHA→기존 company_evidence 저장 원문/사용권/시점 검사→기사 속 한 기업의 경제 행동 구간만 240자 이하로 펼쳐 보여준다. 선택 기업 외 다른 회사/테마 자료를 섞지 않는다. 허용 본문도 같은 검사, 사용권 철회·과거시각·비일치 자료는 N/A. 별도 공급망은 별도 근거이며 실제 수혜/실거래 인증 아님.
실자료: 저장 NICE평가정보 서비스 출시 RSS 기사 HTTP200/원문 구간 35자 READY, 잘못 선택한 근거 SHA는 N/A·구간 미반환. 합성 허용 MOTIR 본문 기업 구간 정상, 사용권 철회 시 N/A. 관련 테스트 20 PASS/실패0, 브라우저 확장·Python/JS 문법 성공. 원본 5개 상태·출처·테마 파일 SHA 불변. 신규 유료 AI/공식 수집/원본 쓰기0.
로컬 Git만 반영. SSD 기존 서비스·예약·GitHub push 미수행. 사용자 기존 AGENTS/DECISIONS/비전 dirty3 불변.

## 최상위 사용자 약속 — 2026-10-17
**기존 정상 기능을 그대로 활용하고 필수 안전장치만 유지한다. 추가 검증도구·세부 관리 기능보다 허용 뉴스 수집 범위 확대와 핵심 자동 처리의 실사용 완성을 우선한다.**
핵심 제품 흐름은 ① 사용권 있는 뉴스 자동수집 → ② V1 반도체 관련 기사 선별 → ③ 새로운 중요한 경제 변화 판별 → ④ 저장 테마·관련 기업의 근거 있는 연결/출력. 기존 뉴스 상세/회사 근거 조회 코드는 보존하되 신규 조회·관리 기능 확장은 이 4단계 실사용 흐름 뒤로 미룬다.
기능 구현 및 실제 입력→분석→저장→화면 경로에 장애가 있을 때만 국소 수정·변경 영향 시험. 키/권리/원본·PIT/중복비용·무주문 안전은 유지. 외부 뉴스 전체 무제한 수집을 뜻하지 않으며 허용·검증 가능한 출처부터 추가한다.

## 다음
NEXT_TASK.md의 실제 뉴스 수집 범위 확대와 저장 경제변화·테마·기업 자동 연결을 먼저 구현. 운영·출시/공동 인수는 구별. SSD 운영 원본/타 프로젝트 변경 금지.
