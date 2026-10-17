# START HERE — NewsCatalystOS

## 현재 유효 개발 원칙
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 내용과 Git status 확인. 기존 정상 코드 CONTINUE·실사용 기능 우선. **승인 뉴스 수집 확대 → V1 반도체 선별 → 중요한 신규 경제 변화 발견 → 근거 있는 테마·기업 저장/조회**를 먼저 완성. 추가 관리·검증 도구/세부 UI 확장 금지, 변경 영향만 필요한 범위 시험. 출처권리·PIT/원본 SHA·비밀/AI 예산·중복비용·실주문 금지 보존.
개발: /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). 운영 원본 SSD /Volumes/T5DATA/1.NewsCatalystOS·EraLeader 코드/DB/Git·기존 예약에 쓰지 않는다. EraLeader 검증 스냅샷만 읽기 전용. 사용자는 1_1~6_6 **36/36 코드 구현 기록**과 실제 실자료·상시 운영/출시·타 시스템 연동을 구분한다. 완료 조건 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md, docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 기능·증거 — 2026-10-17T15:27:46+09:00
- 자동 교대 핵심 기능 SHA **7bf2c2dd9d427bcce39918c2764ef6213f670228**: `scripts/run_scheduled_triage.py --alternate-registry <동일 회사 승인 보도자료 RSS 설정>`를 추가. 기본 삼성/SK 회사 registry를 보존한 채 **SK하이닉스 동일 provider_id**에 대해 일반 뉴스룸 `https://news.skhynix.co.kr/feed/` ↔ 보도자료 `https://news.skhynix.co.kr/category/press/feed/`을 기존 완료 ACK 수 기준으로 다음 실행마다 자동 선택. 별도 수집기·DB·요금/호출 한도 없음, 실패/미완료 건은 성공으로 세지 않음. 지원 대상은 단일 공급자·같은 기관 도메인/권리/메타데이터 저장 범위·시간당 호출한도 검증. 기존 SK회사 원장과 중복 제거·근거 SHA/PIT 그대로 재사용.
- 기존 로컬 feature SHA e25e3ce57740c14d128c076f9823fd2574d26f90에서 보도자료 RSS를 같은 SK하이닉스 provider_id로 **실제 신규 10기사** 수집·규칙 경제변화1·테마1·회사1·정확 원문 제목 구간까지 성공: 투자 규모 54조원, SK하이닉스 메모리 생산 시설, `INVESTMENT/PLANNED`, 실제 집행·수익·수혜 인증하지 않음. 총 저장 기사 판본 313개(기존303+보도자료 신규10). 개발 사설 상태 `output/company_live_dev`, 원본/기업 공식 본문 미저장, 유료 AI0, ERA 코드·DB·수집 없음.
- 변경영향 **44 PASS/0 FAIL**. 합성 주수집→교대→주수집 순서/동일 GUID 단일 ID/호출 제한·취소권리 방어 정상. 실제 완료 ACK로 다음 경로 `primary`를 읽기 전용으로 선택했으며 `--dry-run` 종료코드0/HTTP0/AI0, 개발 관련 5 SHA 불변. 기존 작업트리 사용자 dirty3 SHA 미변경. 운영 SSD/기존 launchd/GitHub Public push 미반영.

## 다음
NEXT_TASK.md — 다음 허용 시각 이후 한 번 `--alternate-registry`를 포함한 실제 scheduler 개발 원장 tick에서 일반 RSS가 자동 선택되고 이전 보도자료 경제 사건이 그대로 보존되는지 확인. 허용 시각 전에는 원장 리셋·무단 재수집 금지; 다른 독립 승인 뉴스 핵심 개발 진행. 매일 실제 운영 배포·자동 예약은 별도 승인/실증.
