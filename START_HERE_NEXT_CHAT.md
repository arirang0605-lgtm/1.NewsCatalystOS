# START HERE — NewsCatalystOS

기준 2026-10-17T20:58:49+09:00. **사용자가 2026-10-17 “진행하자”로 승인한 3가지(전체회귀·MOTIR 운영반영·추가5출처 정기실행)를 완료하고 실제 운영을 시작했다.** 원본 보존을 운영 전환 금지로 되돌리지 않는다. 재개 시 이 문서 → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md와 현재 Git 상태만 확인. 기능/실사용 우선, 기존 정상 코드 CONTINUE. 새로운 검수·인적 라벨·5거래일 사전대기나 관리 도구를 추가하지 않는다.

## 실제 운영 위치와 상태
- 개발 저장소: /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. 사용자 기존 AGENTS.md/DECISIONS.md/비전 파일 dirty3 보존.
- 배포된 고정 코드: /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/c56059ab4b9b422fd687f3c8775b1d527fe49052 (파일0400/디렉터리0500). **운영판 수정 금지**; 후속 기능은 개발 저장소에서 변경·필수시험 후 새 버전으로 교체.
- 신규5출처의 운영 데이터: /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces (msit_live_dev/company_live_dev/nist_live_dev). 이 폴더명이 _dev로 끝나도 현재 **운영 원장**이다. 기존 개발 output/*_live_dev는 보관본이므로 수집 실행 금지(동일 출처 이중원장 호출 방지).
- 운영 Mac 대시보드: http://127.0.0.1:8766/ . LaunchAgent com.newscatalystos.dashboard, 자동 시작/종료 시 재시작. 로컬 Mac만 접근, 외부 공개하지 않음.
- MOTIR 기존 라벨 com.newscatalystos.motir를 고정 코드로 교체, 기존 데이터/비용원장/권한 보존. 등록 직후 자동 실행 exit0, 18기사 분석 READY; 이전 중요대상 아닌 선택적 AI1건은 보류 유지. 기존 core com.newscatalystos.triage는 정상 설정 그대로(exit0).
- 새 com.newscatalystos.research-approved: 시간당3600초·RunAtLoad, 기존 5개 승인 RSS 단일 실행기. 등록 직후 실제 자동 실행 성공5/실패0, 기존 경제 후보9 유지/신규기사0/AI0. **자연 1시간 경과 실행 및 24시간 안정성은 후속 관찰**; 시작 시 자동실행과 구별.

## 이번 필수 근거
최종 전체회귀 **7140 PASS / FAIL0 / 875.88초**. 첫 실행의 3실패는 이미 구현된 근거·시각 분리와 이름 없는 서비스 기능의 과거 테스트 기대 불일치였고, 원문 증거/이전 판본 음성경로를 보존해 정합화(코드 변경0); 국소124PASS 후 전체7140PASS 재확인. 배포 SHA c56059ab4b9b422fd687f3c8775b1d527fe49052. 새 snapshot과 검사된 src/scripts/config 바이트 일치.
운영 HTTP: 8개 제공자·5개 저장영역·372판본, 일간199/중요후보9, SK 투자계획→테마→기업→정확 기사근거 READY/수혜미확정. 기존 Gemini 정산86회·71.286원, 미정산2 예약15.1552원 보존·월5만원 이내. 기확보 운영DB5개 백업/분리복원 성공 증거 재사용.
운영 전환 원장: output/release_20261017/activation.json, operational_verification.json, full_regression_final_result.json. 롤백 설정은 같은 폴더 rollback/. AppSupport 데이터 이전에서 원본·보고서·시점·SHA 보존, 복사한 ACK의 저장주소만 이전한 이력은 운영 research_workspaces/MIGRATION_SOURCE_MANIFEST.json. 원본 SSD 코드 235파일 SHA와 정상 core설정/사용자dirty 보존. 공개 GitHub push/실주문/EraLeader 코드·DB·Git 쓰기 없음.

다음: NEXT_TASK.md. 기존 36/36 코드 기록과 독립 운영 개시/장기 안정성 관찰/EraLeader 통합은 각각 구분한다.
