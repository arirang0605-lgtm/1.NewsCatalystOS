# START HERE — NewsCatalystOS

## 현행 재개 순서와 사용자 최우선 약속
AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 부분만 보고 Git status 확인. 기존 정상 코드 **CONTINUE**, 새 관리/검증·부가기능 확장보다 실제 **공식·허용 뉴스 수집 확대 → V1 반도체 선별 → 중요한 신규 경제 행동 → 근거 있는 테마·기업 자동 연결과 사용자 조회** 완성을 우선한다. 테스트는 변경 영향과 PIT·출처권리·비밀/중복 과금·무주문 등 필수 안전만.
개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project (codex/real-data-path), 분리된 승인 뉴스 개발 상태 output/msit_live_dev (gitignore). 원본 운영 SSD /Volumes/T5DATA/1.NewsCatalystOS·EraLeader 코드/DB/Git/예약은 변경하지 않는다. EraLeader의 이미 검증된 데이터만 읽기전용 공유. V1 산업은 반도체 1개. 기존 1_1~6_6 **코드 구현 36/36**은 제품·실운영/출시/연동 완료가 아니다. 완료 조건은 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md.

## 마지막 신규 작동 결과 — 2026-10-17T13:13:52+09:00
- 공식 과기정통부 press `msit-official-press` 최초 6초 실패의 개발 전용 호출 허용 2026-10-17 13:02:15 KST 경과 후, **1회** 기존 scheduler --once로 수집 성공(exit0): 50개 제목 신규 저장 / V1 반도체 키워드 후보6 / 규칙 분석50 / 경제 변화 확정0 / 테마·기업 실제 신규0 / 수집 유료AI0 / 본문저장0. private source 성공 watermark 2026-10-17T04:02:47.848138+00:00. 다음 호출 2026-10-17T05:02:40.712164+00:00 이후만 허용.
- 과기정통부 연구개발 정책 RSS 50건(반도체 후보1)과 합쳐 dev 추가 출처2개가 모두 실제 50건씩 수집·저장 완료. 기존3출처(core156/motir17) 포함 총 **273개 저장 판본**, '반도체' 검색 **10건**(기존3 + 과기정통부 press6/policy1), 2026-10-17 일간 저장100. 검색/일간/정확 판본 조회 HTTP200·3개 수집 영역 커버리지 완전.
- **신규 기능 로컬 SHA `17c889ecbe13d571039542899d4cf3f5bfcd4467`**: MSIT 원본 저장 ThemeStore는 기존 테마DB와 물리/논리적으로 분리. 신규 출처에서 실제 경제 행동이 발견될 경우 같은 MSIT 출처의 정확 판본→경제 테마→기업 포함 이유/원문 제목 구간만 기사 상세와 별도 테마 카드에서 조회; 기존 테마와 동일 이름·ID라도 자동 병합/수혜 승격 금지. 합성 정상 경로/잘못된 출처 조회 거부 + HTTP/브라우저 변경 영향 **21 PASS**, 실패0. 실제 추가 출처 정책/보도자료는 경제 행동0이므로 테마0·수혜 미확정 그대로.
- 승인 registry/수집 state/ThemeStore 원본·개발 파일 7개 SHA 미변경(read-only 조회시), 기존 운영 원본 파일5개 수집 중 변경 없음. 별도 임시 HTTP 종료, SSD 배포·유료 AI·기사 본문 수집·공개 GitHub push 없음. 사용자 기존 dirty AGENTS.md/DECISIONS.md/비전3파일 불변.

## 다음
NEXT_TASK.md: 기존 collector를 그대로 재활용해 추가로 이용조건 확인 가능한 공식 RSS 뉴스 출처를 실제 입력으로 확대하고, 반도체 중요한 경제 행동 기사에서 4단계 경로가 실제 작동하도록 한다. 신규 출처의 허가·최신성 부족은 그 출처에서만 N/A; 다른 독립 개발 지속. 정규 운영/출시 인수는 별도.
