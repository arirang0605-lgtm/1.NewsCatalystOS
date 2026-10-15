# START HERE — NewsCatalystOS

AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md와 실제 Git 상태를 확인한다. 최신 사용자 지시가 우선한다.

운영: `/Volumes/T5DATA/1.NewsCatalystOS`
작업 체크아웃: `/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project`

목적: 뉴스→경제 사건→초기 테마→기업 수혜 근거→재무·가격·위험을 연결해 투자 검토 가치가 있는 기업 후보를 찾는다. 실제 주문은 범위 밖이다.

최신 구현: 기존 테마 시점 판본→기업 포함 이유/제품·사업 주제/공급 관계/불확실성→대시보드·v3 JSON 연결. 138 PASS. 실제 테마4/기업후보1, 수혜 경로0·재무/가격 미연결. 운영 SSD5개 파일 적용·로컬 대시보드200. 실제 투자 유망기업 발견으로 주장하지 않는다.

다음은 NEXT_TASK의 EraLeader 완료 평가 스냅샷을 선택적으로 읽어 재무·위험 근거를 연결하는 기능이다. 상대 소스/운영 DB/수집기를 수정하지 않고 독립 구현을 이어간다. 사용자 미커밋·원본·비밀·무인 운영·SHA/PIT·공통 예산·실주문 금지를 보존한다.
