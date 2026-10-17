# START HERE — NewsCatalystOS

기준 2026-10-17T19:47:06+09:00, 현재 개발 기능 SHA d49cc73ff33a54225cc2228245ca259d7cf22a9b, branch codex/real-data-path.
재개는 Git status와 START_HERE_NEXT_CHAT.md → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 부분만. 사용자 최우선은 **반도체 실사용 완성**: 기존 정상 코드 CONTINUE, 승인 뉴스 수집·분류·중요 경제 변화·테마/기업/화면 기능을 무인 실행·복구·출시로 연결한다. 추가 연구 뉴스 소스나 검증/관리 도구 확대보다 실제 실행 장애를 먼저 해결한다.
실행 개발 위치 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project. 운영 SSD /Volumes/T5DATA/1.NewsCatalystOS, 기존 LaunchAgent 두 개, EraLeader 코드/DB/Git, 공개 GitHub는 변경하지 않는다. EraLeader 데이터는 이미 검증된 스냅샷만 읽기 전용. 출처권리/PIT/SHA·비밀·Gemini 기존 예산/중복방지·실주문 안전 유지. 기존 1_1~6_6 코드 구현 36/36은 실제 정기운영/출시·연동 인수와 다르다. 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 및 docs/V1_RELEASE_POLICY_2026-10-15.md.

## 최신 성공: 운영 자동 처리 경로
- 기능 d49cc73ff33a54225cc2228245ca259d7cf22a9b: scripts/run_approved_research_feeds_once.py 한 번으로 기존 MSIT 2, Samsung/SK 2, NIST 1 **승인 RSS 5개 실행**. 공식 수집기/개별 호출원장/동일기관 교대/ACK·PIT·ThemeStore는 그대로. 실제 --once 5/5 코드0, 저장 메타데이터198건 분석·기존 경제 후보9/고유 새 기사0, 유료AI·본문·EraLeader API0. --replay-only 실제198건 재분석(HTTP0), --dry-run5 출처 정상. 한 출처 오류 시 다른 정상 4개 진행, 전체 exit4로 부분 실패 유지.
- 실제 운영 장애 하나 수정: 빈 첫 source가 비공개 분석 루트를 0755로 잘못 생성하여 건강한 다음 source를 차단하던 경로를 scripts/run_feed_analysis.py에서 0700 선행 생성. 집중 변경영향 테스트 **30 PASS/0 FAIL**.
- 실제 구 SSD 운영 launchd 2개: triage 최근 exit0, MOTIR 최근 exit4. 산업부 18건 뉴스/규칙 분석은 READY인데 오래된 비대상 기사1건의 선택적 semantic AI가 UNAVAILABLE여서 구 버전에서 전체 실패. dev 현재 _analyze_provider에 실제 운영 저장 보고서 읽기전용으로 재현 시 이 불완전만 있으면 exit0, 중요 AI 실패는 exit4 유지. **운영 SSD 버전 교체 전이므로 MOTIR live exit4는 미해결**.
- 운영 DB5개(수집2·중복 인덱스2·테마1)를 기존 백업/복원 함수로 각각 owner-only 개발 폴더 output/operational_recovery_dev_20261017 에 snapshot/독립 restore+SHA/SQLite integrity 성공. 운영 원본 5 SHA 불변. 신규 5RSS hourly launchd private plist 후보 output/research_scheduler_dev/com.newscatalystos.research-approved.plist (0600) 준비, 미설치/미활성화.
- 기능 Git은 로컬만, 사용자 미커밋 AGENTS/DECISIONS/비전3파일 불변.

다음: NEXT_TASK.md. 신규 기술뉴스 확대보다 구 운영버전↔dev 코드 인수·산업부 의미없는 optional AI 경보 해결과 5 RSS 예약 활성화/운영 안전 배포를 최우선으로, 배포 전 실제 전체 회귀 1회. 원본 SSD/기존 예약 임의 덮어쓰기 금지.

출시 전체 회귀 상태: 2026-10-17 219개 테스트 모듈을 한 번 시도했으나 240초 상한에서 32% 진행한 뒤 exit124. 부분 실패 표시 없었지만 전체 통과는 미확인. 재시도는 배포 인수 작업 창에 충분한 시간·자원을 확보한 경우에만. 비공개 로그 output/research_scheduler_dev/release_regression_20261017.log.
