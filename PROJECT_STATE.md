# PROJECT_STATE — NewsCatalystOS 실사용 운영 전환

기준 2026-10-17T19:47:06+09:00. 기능 SHA d49cc73ff33a54225cc2228245ca259d7cf22a9b. 반도체 V1, 기존 36/36은 과거 코드 작업 구현 기록, 무인운영·출시/연동 인수와 별개.

- 새로 동작: scripts/run_approved_research_feeds_once.py로 MSIT press/policy, Samsung, SK, NIST 공식 승인 출처5를 현재 dev 원장에서 1회 실행(code0, 성공5/실패0, 저장 기사198 분석, 경제행동9 유지, 신규기사0). 하나의 신규 수집기가 아니라 기존 scheduler가 각각 승인 원장/권리/시간당 제한·동일 제공자 교대/중복 제거를 재사용. dry-run/저장자료 replay-only도 실제 OK, Paid AI0, 기사 본문0, ERA API0.
- 첫 출처가 실패/빈 경우 개발 분석 보고서의 부모 폴더가 0755가 돼 정상 후속 출처까지 실패하는 실제 장애를 비공개 분석 폴더 0700 선행 생성으로 해결. 합성 1개 실패 시 정상4개 통과/실패1 기록, 성공 경로 포함 국소 **30 PASS/0 FAIL**.
- 실제 구 NewsCatalystOS 운영 launchd core exit0, MOTIR exit4(공식 기사18 분석 READY, 하나의 중요대상 아닌 과거 semantic UNAVAILABLE). 현재 dev 최신 _analyze_provider를 실제 저장 보고서로 검증: 선택적 불완전만 있는 경우 0, 중요 신규 사건 실제 AI 결함이면 4. **구 운영 코드/예약은 아직 변경하지 않았으므로 active 장애는 해결됐다고 하지 않음**.
- 현 운영 DB 5개를 읽기전용으로 백업하고 별도 owner-only 개발 폴더로 실제 복원, manifest+SHA+integrity 통과, 운영 원본 SHA5 변경 없음. output/operational_recovery_dev_20261017에 보관하며 Public Git 대상 아님. 비공개 launchd 후보 output/research_scheduler_dev 준비(시간당1회, 5개 dev source); 기존 운영 런타임 변경0, 후보 미설치.
- 이전 메인 연구 조회 실제 저장판본372/일간199/중요 후보9 유지(이번 턴 웹 UI 전체 재검증 증거로 대체하지 않음). EraLeader 코드/DB/Git, SSD, 기존 LaunchAgent, GitHub 공개 push, 사용자 dirty3 불변.

## 다음
NEXT_TASK.md: 안전한 운영 배포 인수 및 단 한 번의 출시 통합 회귀 후 기존 MOTIR false exit4 코드 적용/신규 5개 RSS launchd 예약 연결. 사용자 기존 운영 원본과 dirty 파일 임의 변경 금지. Gemini 비용/캐시 및 AI 실제 생성 2026-10-15 증거는 기존 출시 기준에서 재사용; 새로운 단가/외부 검수 게이트 신설 금지.

최신 전체회귀: 219 모듈 240초 제한에서 32% 완료, exit124 시간제한. 진행부분 실패 표시는 없으나 최신 전체회귀 합격 증거는 아직 없음. 운영 LaunchAgent 후보3개는 비공개 개발 폴더에 staged이며 모두 비활성/미설치, 구 MOTIR 실제 exit4 미해결. 사용자 승인 운영 배포 및 전체회귀 완주 후 인수.
