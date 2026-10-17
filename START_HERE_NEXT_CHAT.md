# START HERE — NewsCatalystOS

## 재개 기준
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md의 **현재** 내용 및 Git HEAD/status만 읽는다. 정상 작동하는 기존 코드 CONTINUE. 사용자 우선: **①승인 뉴스 자동수집 확대 → ②V1 반도체 선별 → ③중요 신규 경제 사건 포착 → ④테마·기업 근거와 화면 출력**. 핵심 기능을 뒤로 미루는 검증·관리/부가 UI 반복 확장 금지. 출처 사용권·PIT·원본 SHA·비밀, AI 월 예산/중복비용/실주문 금지 보존.
개발 워크트리 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). 원본 SSD /Volumes/T5DATA/1.NewsCatalystOS 및 EraLeader 코드·DB·Git/수집기 불변, EraLeader의 검증 공유 데이터만 읽기전용. V1 반도체 1산업. 과거 1_1~6_6 **코드 구현36/36**을 실제 상시운영·출시/연동 완료로 보지 않는다. 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md, docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 사용자 작동 기능 — 2026-10-17T15:53:10+09:00
뉴스 경제 분석 feature SHA **00184a3f8172a745a449bd326e3da5b7922cb320**: 실제 SK하이닉스 PRESS RSS 제목의 `54조 원`(공백 포함) 금액을 정확히 파싱하고 동일 제목의 이미 저장된 `INVESTMENT/PLANNED` 반도체 생산시설 투자 발표를 일간/기사 검색에서 **HIGH_PRIORITY_CANDIDATE**로 노출. 금액은 출처에 보고된 규모이며 실제 집행·수주·매출·수혜를 인증하지 않는다. 큰 투자 계획에 우선순위를 표시해도 AI `ai_eligible=False` 유지하여 자동 유료 분석/주문 호출은 없다. v11 분석 규칙. 자사주 매입·루머·검토 중·금액 모호한 제목은 우선 승격 안 됨.
실제 기저 승인 저장 기사 판본313, 저장 company RSS20을 인터넷 재수집 없이 기존 사설 dev 분석/보고 폴더에 재분석20. 중요 투자 이벤트1, 추가 테마버전0 (기존 company ThemeStore 보존), 새 SHA 보고서. 실제 새 HTTP 127.0.0.1 일간 view: 2026-10-17 기사140, 중요 검토 후보1, 선택 저장 기사 `routing_priority=HIGH_PRIORITY_CANDIDATE`, `reported_plan_only=True`, 경제행동 `INVESTMENT/PLANNED`, 실제 확정 수혜false. 테스트 **97 PASS/0 FAIL**, 원본/개발 source registry·원장·테마 DB 8개 SHA 불변, 웹 임시서버 종료. 최초 dev 공식 SK PRESS 실제 원문 54조 계획 인정은 출처 보고만, 데이터의 실제 유효 날짜/기업 공식 종목 ID는 별도 미검증. 유료AI·외부 뉴스수집0, SSD/공개 GitHub push 없음. 사용자 기존 dirty3 SHA 그대로.

## 다음
NEXT_TASK.md: 이전에 구현·검증한 SK하이닉스 일반 RSS↔PRESS 자동 교대 `--alternate-registry` 개발 수집을 원장의 다음 허용 시각 **2026-10-17 16:11:55 KST 이후에만 1회** 실제 실행. 원장 리셋·시간당 제한 우회 금지. 이전 투자 테마·회사 보존, 새 뉴스/중복/분석과 화면 연결 확인. 출시·운영 예약은 별도.
