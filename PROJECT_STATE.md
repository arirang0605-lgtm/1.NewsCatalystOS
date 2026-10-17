# PROJECT_STATE — NewsCatalystOS 기능·실자료·출시 분리

기준 2026-10-17T15:53:10+09:00. 기능 SHA `00184a3f8172a745a449bd326e3da5b7922cb320` 개발 로컬. 사용자 승인 범위 V1 반도체 한 산업, 과거 코드 1_1~6_6 **36/36** 기록(제품·실운영 완료 아님). 정상 코드 CONTINUE, 핵심 수집→경제 사건→테마/기업→화면 먼저, 필수 최소 테스트.

## 이번에 새로 해결한 실제 경제 사건 표시 장애
- SK하이닉스 공식 PRESS RSS "용인 Y2·청주 M17에 54조 원 투자 ... AI 시대 메모리 수요 대응" 제목은 이미 경제행동 `INVESTMENT`/phase `PLANNED`(회사 SK하이닉스, 메모리 주제)로 테마1 저장됐지만, 띄어 쓴 `조 원` 금액 파서 누락으로 일간 우선 검토 후보에서 빠져 있었다.
- `MONEY` 및 `_krw`가 띄어 쓴 KRW 단위를 출처 문자 그대로 인식하게 변경. 완료됐던 source-bound 단일 회사 제조시설 `INVESTMENT/PLANNED` 행동 + 명시 금액이 기존 LARGE_KRW 임계값 이상인 경우 **표시 우선순위만 HIGH_PRIORITY_CANDIDATE**. `ai_eligible=False`, `verified_beneficiary=False`, `reported_plan_only=True`, 실제 집행/매출·수혜 미확정. rule_version v11.
- 신규 외부 수집 없이 이미 승인된 회사 RSS20판본을 dev private reports에 재분석(코드0). 일간 조회 2026-10-17 기사140 / 검토1 / 관련 기사 EXACT HTTP200, 투자 계획 유지; 같은 source의 새 테마버전0 (기존 ThemeStore 불변). 관련 **97 PASS/0 FAIL**; 악의적 표현(자사주/검토/금액 복수/막연한 계획) 우선 승격 차단. 운영+dev 등록/원장·테마 8 SHA 불변. 유료 AI/실주문/본문 복제 없음.
- 이 직전 `7bf2c2dd9d427bcce39918c2764ef6213f670228`: 같은 회사 provider ID/1시간 원장으로 SK 뉴스룸 `feed/`↔`category/press/feed/` 완료 ACK 기준 교대 구현, 합성·dry-run 검증. 실제 다음 자동 tick은 아직 미실행, 호출 next_allowed_at=2026-10-17T07:11:55.500573+00:00. 실제 이미 저장된 기사 총313 판본. 운영 SSD/launchd/Public GitHub 미배포.
- 이 개발은 운영 원본이 아닌 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project 내부 개발 환경. 사용자 dirty AGENTS.md/DECISIONS.md/비전3 파일 SHA 불변.

## 다음
NEXT_TASK.md: 원장 허용시간 이후 기존 코드 `run_scheduled_triage.py --alternate-registry` dev single --once, 종료상태/중복 보존/이전 54조 투자 기사 유지 확인. 그 전에는 재시도하지 않고 다른 독립 뉴스 입력 기능 계속. 실사용/실자료·독립 운영·제품 인수 분리.
