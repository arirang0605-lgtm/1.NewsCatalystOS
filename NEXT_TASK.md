# NEXT_TASK — MSIT press 실제 뉴스 신규 자동수집 1회 → 반도체 선별·경제변화·테마/기업·통합 화면 (NC-01/02/03/06)

## 이미 구현/실행 완료
`78376452d46ebcaf941621faa51ac668853e777d`: MSIT dev 별도 승인 RSS를 기존 core/MOTIR과 동일 대시보드에 읽기 전용 연합. 실제 현재 저장 입력 core156/motir17/msit R&D50 = 223 원본 판본. 일간 당일 신규50, '반도체' 통합검색4(신규1), 기사 선택/저장 제목 경제 행동 분석 READY, 실제 경제변화0·기업/실거래 수혜미확정. 집중17 PASS. 원본7 SHA 유지. 신규 press RSS 수집은 아직 미확인.

## 다음 실사용 작업 — 이 대기 조건에만 적용
개발 측 새 출처 `msit-official-press`의 지난 1회 수집은 이전 default HTTP 6초에서 실패했고, 다음 이용 시각은 기존 개발 전용 호출 원장 **2026-10-17 13:02:15 KST 이후**. 다음 사용자 턴에서 현재 시각이 그 전이라면 원장 리셋/추가 HTTP 수집을 시도하지 말고 독립 핵심 기능 개발을 계속한다.
1. 허용 이후 `/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project/output/msit_live_dev`의 기존 사설 registry/state/ACK를 그대로 두고 (삭제·reset 금지), `scripts/run_scheduled_triage.py --once --provider-id msit-official-press`로 **1회만** 수집·triage·규칙 경제 행동/테마·보고 저장 실행. `--analysis-root`는 기존 `output/msit_live_dev/feed_analysis/core`을 재사용. `--analysis-theme-root`는 기존 분리 `output/msit_live_dev/document_analysis/theme_history`. 모델/AI 유료 실행 비허용. 본문 HTML/첨부 미저장.
2. 코어 HTTP 성공 시 실제 press50 기사와 반도체 키워드 6후보의 저장 여부, 새 경제변화/관련 회사가 실제 없으면 N/A, 출력 SHA/PIT와 당일 통합 뉴스검색·보도자료 구분 결과를 확인. 실패 시 이유 한정 기록 후 독립 개발 지속(같은 1시간내 무의미한 HTTP 재시도 금지).
3. 사용자 핵심 4단계 ①뉴스 확대→②반도체→③중요 경제행동→④테마/관련기업을 정상 입력에서 끝까지 작동하게 하는 장애만 수정. 새 검증/관리 도구·다른 산업 심층 검증으로 대체하지 않는다. 세부 코드36/36 기록은 제품 독립 운영/출시 인수가 아니다.
4. 승인 설정·기존 운영 SSD·EraLeader 코드/DB/Git, 유료 기사 원문/비밀/API/주문/무단 GitHub push 변경 금지. 기능·실자료·출시 인수는 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 기준으로 분리.

진행 우선순위: 사용자 약속대로 **새로 자동 들어오는 뉴스의 실제 처리 및 사용자 조회** 먼저.
