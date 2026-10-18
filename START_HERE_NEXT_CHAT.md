# START HERE — 뉴스 테마 후보·관련 사업 분야 종합 운영

기준 2026-10-18 15:39 KST. 사용자 승인: **KRX 등 산업분류 없이 뉴스에서 유망 테마 후보를 발견하고 관련 산업을 정리하는 개발 진행**. 기존 원문 비교만 다음 작업으로 반복하지 않는다. 이 문서 → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md와 Git 상태를 확인한다.

## 실제 현재 동작
기능/dashboard 배포 **35b039c4139a36727a91407cde9205864de6cc6c**. 기존 검증된 경제행동 보고서·ThemeStore·경제경로를 재사용해 공통 원문 사업대상의 뉴스를 종합한다. 대시보드 **주목할 테마 후보·관련 산업**, /api/economic-discovery의 theme_outlook, ?export=1의 discovery_theme_outlook으로 주목 이유·관련 사업/행동/원문 기업·조건부 기회/반증·비교기간 변화가 연결된다. 산업표·회사명 별칭·새 AI/수집 없이 실행한다.
실자료 383개 제목 판본 / 기존45주제·50출처관측 유지. **Silicon Carbide Semiconductors — Bosch·I-Pulse**의 지원 발표를 복수기업 조사 후보1개로 연결, 초기 관찰37개. 복수 기업의 서로 다른 행동까지 갖춘 우선조사 후보는0개. CHIPS R&D Award만 같다는 이유로6개 회사를 유망산업으로 묶지 않는다. 관련188PASS/0FAIL. source·파생파일726개 SHA 불변. 실제15:39 HTTP200·JS SHA·45테마 선택export/확장41 확인.

## 경로·운영 경계
DEV=/Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch=codex/real-data-path. BASE=~/Library/Application Support/NewsCatalystOS. dashboard만 BASE/releases/35b039c4139a36727a91407cde9205864de6cc6c. research-approved는 기존4fd8c755d3c4/시간당예약, core/MOTIR 설정과 Era코드·DB·Git·순위 보존. 기존 /api/themes 고정 게시bytes 불변. UI http://127.0.0.1:8766/.
증거·rollback은 output/theme_outlook_20261018/{targeted_tests.json,real_data_proof.json,activation.json,operating_screen.png}. 상세 docs/THEME_OUTLOOK_20261018.md. 사용자dirty AGENTS/DECISIONS/비전3 보존, Public GitHub push0.

현재는 **공통 원문 사업대상 기반 조사 후보의 첫 버전**이다. 주가·수익성/독립사건/공통 수요 인과관계·전체 산업의 공급망을 확정하지 않는다. V1 36/36은 기존 범위 기록이며 이번 가설38개를38산업 완료로 계산하지 않는다. 다음 NEXT_TASK.md.
