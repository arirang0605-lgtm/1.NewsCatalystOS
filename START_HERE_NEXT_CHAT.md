# START HERE — NewsCatalystOS

## 현행 재개 순서·우선순위
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 내용과 Git HEAD/status만 읽는다. 사용자 최우선: 허용 뉴스 자동 수집 확대 → V1 반도체 선별 → 중요한 신규 경제 사건 포착 → 근거 있는 테마·기업 저장/화면. 정상 코드 CONTINUE, 불필요한 검증·관리 기능 확장 금지. 출처권리·SHA/PIT·비밀·AI 월 예산/중복 비용·실주문 금지 보존.
로컬 개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project branch codex/real-data-path. 사용자의 운영 원본 /Volumes/T5DATA/1.NewsCatalystOS, EraLeader 코드/DB/Git 변경 금지. 검증된 EraLeader 데이터는 읽기 전용 공유. 기존 1_1~6_6 구현 36/36은 실제 실사용 운영·출시/연동 완료가 아님. 원래 제품 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 실자료 실행 성공 — 2026-10-17T17:03:18+09:00
NewsCatalystOS 개발 RSS 두 채널 자동 교대의 최초 실제 호출 완료: 2026-10-17 17:00 KST경 기존 원장 다음 허용 시각 16:11:55를 지켜 SK하이닉스 단일 provider_id(skhynix-newsroom-korea)에 --alternate-registry를 지정한 기존 scheduler --once, 자동 선택 primary(일반 뉴스룸), exit0. 저장 RSS 기사10 판본 모두 기확인 GUID, 신규 고유 ID0 / 기존 뉴스20 판본 규칙 재분석 / 메모리 생산 기반 54조 투자 INVESTMENT·PLANNED 후보1·별도 신규 테마0. 원장 다음 허용 2026-10-17T09:00:07.784557+00:00 (18:00:07 KST), 그 이후에만 다른 실제 원격 호출 허용.
다음 출처 선택은 완료 ACK3개 기준 alternate(동일 SK 회사의 공식 보도자료 feed)이고 읽기전용 확인, 별도 호출0. 통합 개발 대시보드 HTTP200: 저장 판본313, 당일 기사140, 높은 중요도 후보1, 투자 계획 원문 기사/테마/직접 당사자 SK하이닉스 1건, 실제 집행·수혜 인증 false, 전날 이전 원본5 및 개발 registry/state/theme 합계9개 SHA 조회 중 불변. 유료AI0/본문 수집0/새 스케줄러0, 임시 HTTP 종료. 국소 기존 테스트10 PASS/실패0, 기능 Git HEAD d7d3e0ea69e0fb7511d3b06b1a8c918999873018, 최신 코드 기능 SHA 00184a3f8172a745a449bd326e3da5b7922cb320, RSS 자동교대 코드 SHA 7bf2c2dd9d427bcce39918c2764ef6213f670228. 운영 SSD/기존 launchd/Public GitHub push 미수행. 사용자 기존 AGENTS/DECISIONS/비전 3 dirty 파일 불변.

## 다음
NEXT_TASK.md — 실제 RSS 기사에서 출처에 직접 명시된 신규 반도체 계약/투자/생산의 뉴스 입력 확보를 계속한다. 신규 회사·공식 출처의 권리 확인 및 기존 수집 파이프라인 재사용 우선, 과거 기사/같은 회사 RSS를 독립 사실로 중복 주장하지 않는다. 자동 교대 다음 fetch 시간 제한 준수, 무인 운영 설치는 별도 단계.
