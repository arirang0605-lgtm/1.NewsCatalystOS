# PROJECT_STATE — NewsCatalystOS 기능·실자료·운영 현재

기준 2026-10-17T12:47:15+09:00, 로컬 기능 Git `78376452d46ebcaf941621faa51ac668853e777d`, 기존 1_1~6_6 코드36/36 구현 이력(출시 완료는 별도). 사용자 방향: 뉴스 승인 범위 확대, V1 반도체 자동 선별→경제 행동→테마·기업 저장/조회, 운영 필수 최소 테스트.

## 새 실사용 조회 기능
- 독립 승인 수집 MSIT(과기정통부) 개발 폴더 `output/msit_live_dev`을 `--msit-source-root`로 기존 개발 대시보드 검색·일간 기록에 읽기 전용 결합. 원본 3출처(core156 판본, motir17 판본), 신규 정책 RSS 1출처50판본 = 실제 총223판본. 다른 새 RSS press 채널은 아직 실패 상태이며 완성으로 계산하지 않음.
- 저장 기사 제목 '반도체' 통합검색 4건(기존3/신규1), 신규 MSIT 정책 기사50 일간·정확 판본 분석 READY, 저장 경제 변화0·기업 수혜 미확정. 판본/보고 root 별개, 독립 provider와 SourceShare/PIT 검증, 관리자 화면/새 도구 없음.
- 합성 다중 출처2건(하나는 명시 계약)에서 저장 원문과 승인 게시물 정확 일치→두 기사 통합검색/일간2→계약 사건·미확인 상태 출력, 과거 시점=N/A 확인. 변경 영향 **17 PASS/실패0**, 원본·개발 registry/SQL/ThemeStore 7파일 SHA불변, 유료 AI/중복 수집/본문 저장0.
- 전 턴 `e6967a2da6235ce6e4cc2e3f07b8efd2f0d27ec5`: MSIT 94와 65 새 approved metadata RSS, 1MiB bounded/no redirect/default 10sec. MSIT R&D 50 저장 실운영이 아닌 dev 성공; press 50은 독립 HTTP 정상 파싱됐으나 최초 6초 예약 수집 실패, 마지막 next_allowed_at=2026-10-17T04:02:15+00:00로 기존 원장 보존. 수정 후 자연 실제 press 호출 검증 미실시.
- 현행 SSD launchd/운영 자동화/DB/기존 대시보드 미배포, GitHub push 없음. 사용자 AGENTS.md/DECISIONS.md/비전 파일 dirty3 SHA 불변. 합성 및 개발 저장뉴스 화면 증거를 실제 정규 운영 완료로 부르지 않는다.

## 다음
NEXT_TASK.md: press 출처가 원장상 허용되면 dev-private `run_scheduled_triage.py --once` 1회, 기존 10초 한계 유지, 상태를 정확하게 기록. 기사50 반도체 후보6 기준/분석 실물 저장, 허위 실제 거래·수혜 생성 금지. 운영 SSD 미승인 배포·권한변경 금지.
