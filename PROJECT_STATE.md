# PROJECT_STATE — NewsCatalystOS 현재 기능·실자료·운영 분리

기준 2026-10-17T14:22:52+09:00, 로컬 feature SHA 409bfe45d441eb5a9d8c92be3aa5f8b9ab84a0bf. 과거 1_1~6_6 구현 36/36은 제품/실운영/출시 인수 인증과 별개. V1 반도체 한 산업.

새로 고친 경제 사건 핵심 로직:
1. 실제 SK하이닉스 한국 뉴스룸 PRESS 카테고리 공식 RSS에 생산시설 금액 투자 제목 존재. 직접 조회한 해당 보도 제목에서 이전 ACTIONS는 0건이었고 변경 후 company SK하이닉스, topic 메모리(명시된 수요 대응), action INVESTMENT, phase PLANNED, 실제 집행·수혜 검증 false로 탐지. 운영 공식 보도 원문/본문은 수집하지 않음.
2. 수집 제목의 줄임표 Unicode …가 ...로 정규화되면서 동일 기사 경제 행동과 기업 근거가 문장 단절되던 문제 수정. 자사주·금융투자/불확실 및 아직 실행되지 않은 투자는 실집행으로 승격하지 않음.
3. 합성 승인 RSS 완성 경로(기사 → 저장 제목 분석 → 테마/기업 → 원문 인용 → 임시 HTTP) 정상, 변경 영향 179 PASS/실패0. 아직 새 PRESS 공식 피드를 기존 회사 dev collector로 물리 수집·저장한 실증은 없으므로 분리 보고.
4. 기존 dev 7개 승인 공식 RSS/303 제목판본 유지, 사용자 dirty AGENTS.md/DECISIONS.md/비전 파일3 불변. 운영 SSD·EraLeader·키·원장/예약·유료 AI/본문·공개 GitHub push 변경 없음.

다음: NEXT_TASK.md의 기존 한국 SK newsroom PRESS RSS 소유권/원장/중복 ID 공유 연결, 기존 다음 허용 시각 14:48:15 KST 이후 1회 실제 확인. 비상업용 한정 AMD/Applied 미국 IR은 사용자 승인 없이 유료·상업 목적 수집 금지. 다른 승인 뉴스 4단계 실사용 개발은 계속.
