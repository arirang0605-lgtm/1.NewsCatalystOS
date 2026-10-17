# START HERE — NewsCatalystOS

## 현재 작업 기준
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 현재 지침과 Git 상태를 확인한다. 기존 코드 CONTINUE·실사용 기능 우선·운영 필수 검증만. 현재 개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path), 원본 SSD /Volumes/T5DATA/1.NewsCatalystOS 수정·배포 금지. EraLeader 검증 완료 스냅샷만 읽기 전용; 타 프로젝트 무관. 반도체 V1 한 산업, 비밀·출처/유료 본문·PIT/비용·실주문 보호. 제품 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md. 1_1~6_6 과거 36/36은 코드 구현 이력이며 운영/출시/실연동 완료로 간주하지 않는다.

## 최신 기능 — 2026-10-17T11:45:04+09:00
NEWS-20261017-EXACT-ARTICLE-COMPANY-QUOTE / 로컬 기능 SHA `388da7ff99119ac584b3fa7c455a72aeb700cfb5`.
기존 검색 기사→같은 RSS provider/event/title SHA→저장 사건/테마의 정확 회사 ID + 근거 SHA→기존 company_evidence 저장 원문/사용권/시점 검사→기사 속 한 기업의 경제 행동 구간만 240자 이하로 펼쳐 보여준다. 선택 기업 외 다른 회사/테마 자료를 섞지 않는다. 허용 본문도 같은 검사, 사용권 철회·과거시각·비일치 자료는 N/A. 별도 공급망은 별도 근거이며 실제 수혜/실거래 인증 아님.
실자료: 저장 NICE평가정보 서비스 출시 RSS 기사 HTTP200/원문 구간 35자 READY, 잘못 선택한 근거 SHA는 N/A·구간 미반환. 합성 허용 MOTIR 본문 기업 구간 정상, 사용권 철회 시 N/A. 관련 테스트 20 PASS/실패0, 브라우저 확장·Python/JS 문법 성공. 원본 5개 상태·출처·테마 파일 SHA 불변. 신규 유료 AI/공식 수집/원본 쓰기0.
로컬 Git만 반영. SSD 기존 서비스·예약·GitHub push 미수행. 사용자 기존 AGENTS/DECISIONS/비전 dirty3 불변.

## 다음
NEXT_TASK.md — 뉴스 검색 결과 화면에서 저장 경제 변화/정책·테마 근거의 유무를 제목 규칙 대 허용 본문으로 구분하여 카드에서 쉽게 발견/필터하도록 연결. 기존 조회 자료만 재사용하고 새 관리·검증 프로그램을 만들지 않는다. 운영/출시 인수는 별개.
