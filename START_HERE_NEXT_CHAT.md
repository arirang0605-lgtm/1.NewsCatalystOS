# START HERE — NewsCatalystOS

## 유효 개발 재개 원칙
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 부분만 읽고 Git status. 정상 코드 CONTINUE. 사용자 확정 최우선: 허용 뉴스 자동수집 확대 → V1 반도체 선별 → 중요한 신규 경제 행동 → 근거 있는 테마·기업 저장/사용자 조회. 추가 관리·검증 프레임워크·세부 조회보다 실제 4단계 완성 먼저. 출처권리·SHA/PIT·비밀·AI 월 예산/중복요금·무주문 보호.
현재 로컬 개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path). 운영 원본 SSD /Volumes/T5DATA/1.NewsCatalystOS와 EraLeader 코드/DB/Git 불변, 승인 완료 EraLeader 스냅샷만 읽기전용. V1 산업은 반도체 1개. 1_1~6_6 36/36은 과거 코드 구현 기록, 실제 운영/출시·공동 연동 완료는 별도. 출시 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md, docs/V1_RELEASE_POLICY_2026-10-15.md.

## 마지막 신규 기능 — 2026-10-17T14:22:52+09:00
기능 SHA 409bfe45d441eb5a9d8c92be3aa5f8b9ab84a0bf. SK하이닉스 한국 뉴스룸 공식 PRESS RSS https://news.skhynix.co.kr/category/press/feed/ 의 금액·생산시설 투자 보도 제목에서 기존 경제 규칙이 투자 결정/확정이라는 표현 부재 및 RSS 줄임표 정규화 때문에 사건을 놓치던 문제 해결. 하나의 회사+금액(조/억원)+시설/생산 기반+명시 반도체/메모리 수요 대응만 INVESTMENT/PLANNED(발표된 계획, 미집행/실수혜 미확인)으로 분류. 자사주·금융 투자, 검토·추정·불확실, 시설·기업 없음 등 차단. title … → ... 정규화 후에도 회사 인용 구간/같은 문장을 보존.
합성 승인 기업 RSS → 저장 규칙 보고 → 테마 ThemeStore → 회사 포함 이유 → 정확 원문 구간 → 로컬 HTTP 정상. 변경 영향 179 PASS, 실패0. 실제 공식 PRESS 제목을 함수에 넣어 SK하이닉스/메모리/INVESTMENT/PLANNED 인식 확인했으나 해당 PRESS 기사는 현재 개발 수집원장에 아직 저장되지 않았음. 이전 수집된 7개 출처 303판본은 기존 그대로, 당시 회사 일반 뉴스 제목의 경제 사건0. 개발 로컬 Git만, SSD/예약/기밀·본문·유료AI·GitHub push 불변. 사용자 dirty 파일 3개 보존.

## 다음
NEXT_TASK.md — 기존 한국 SK 뉴스룸 PRESS 카테고리의 해당 경제 뉴스 제목을 같은 회사 provider/원장·GUID dedup 기반으로 실제 한 번 수집·저장해 4단계 경로에 연결. 마지막 skhynix-newsroom-korea next_allowed 2026-10-17T05:48:15.616099+00:00(14:48:15 KST) 이전에는 별도 provider-ID를 통한 재수집 우회/원장 초기화 금지. 미국 AMD/Applied IR 공식 RSS는 일반 이용약관의 사업·상업 이용 제한을 발견해 추가 명시 권한 없이 활성화하지 않는다.
