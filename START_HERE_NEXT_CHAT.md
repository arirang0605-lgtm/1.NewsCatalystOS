# START HERE — NewsCatalystOS

기준 2026-10-17T22:23:35+09:00. 사용자 요청 **“연동하자”**에 따라 EraLeader 완료 평가의 읽기전용 연결을 NewsCatalystOS 운영에 반영. 재개: 이 문서 → AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 최신 부분과 Git상태만 확인. 핵심 기능·실사용 우선, 정상 코드 CONTINUE, 새 검수/관리도구·인적승인/기간대기 조건 추가 금지. 코드구현36/36 기록과 독립 운영/양방향 전체인수를 구분한다.

## 현행 운영
- 개발 /Users/shmoon/Documents/ChatGPT/1.NewsCatalystOS/project, branch codex/real-data-path. 사용자 기존 AGENTS/DECISIONS/비전 dirty3 보존.
- 대시보드·5개 RSS runner 배포 SHA **09e1bfbbf43fabd491c372153452c4962b73ed51**, 고정 코드 /Users/shmoon/Library/Application Support/NewsCatalystOS/releases/09e1bfbbf43fabd491c372153452c4962b73ed51. 기존 core/MOTIR 서비스는 이전 정상 버전 유지. 운영 http://127.0.0.1:8766/ (Mac 로컬 전용), 화면에서 기사 기업의 **EraLeader 기업 평가 연결**을 펼친다.
- 현 운영 신규출처 원장 /Users/shmoon/Library/Application Support/NewsCatalystOS/research_workspaces. 개발 output/*_live_dev는 보관본이므로 재수집 실행 금지. 권리/PIT/SHA/기존 비용원장·중복/실주문 금지 유지.
- News 소유 설정 /Users/shmoon/Library/Application Support/NewsCatalystOS/era_daily_connection.json, 평가 수신함 /Users/shmoon/Library/Application Support/NewsCatalystOS/document_analysis/era_daily_assessments. 기존 시간당 com.newscatalystos.research-approved에 optional refresh 연결. 실제 등록직후 launchd exit0/뉴스5출처 성공/평가50개 ALREADY_IMPORTED, 최초수신시각은 보존. Era 장애는 평가만 N/A, 정상뉴스는 계속.

## 실제 연결 증거
EraLeader의 현재 게시 완료 daily snapshot(내용 SHA c1f84378c69d7037902172a809c97655e08f16ced79f86fb6f4fb532ca816a67, 파일 SHA aa310751a5146806aefa5a6bb9b670d7cf2f4480122b294a53c7497f75f974af)을 원본 보고서·browser SHA/기업/날짜·주문금지·사용권 범위 확인 후 News 수신함에 복사. 후보50·연간재무44·종가50 중 현재 뉴스와 **정확 연결1건: SK하이닉스 → DART_CORP:00164779 → 000660**. FY2025 재무, KRX2026-10-16 보관가격/긍정·약화·결측 근거를 원 평가 그대로 표시. 뉴스54조 투자 사건 PLANNED·실수혜미확정 유지. 평가를 새 계산하거나 기존 원본 회사명/테마 DB를 수정하지 않음.
기존 /api/themes 기본 경로가 base9를 원래 ID 그대로 보존하고 source별 추가7테마를 포함해 총16을 전달. Era 기존 decode/validate/match 함수를 실제 운영 API에서 **읽기전용으로 호출해 정상수신·공식ID 일치1** 확인. 별도 context에 완료 daily 행을 전달한 검증이며 **EraLeader 내부의 오래된 WATCH 수신기/영구 저장/자체 UI·스케줄을 변경한 것은 아님**. 회사 자체 재평가나 통합 전체 인수를 선언하지 않음.
직접 영향 **68 PASS/0 FAIL**, 실제 운영 기사/일간/평가 API HTTP200, 새 배포 JS SHA 확인. source first import 2026-10-17T13:04:12.387996+00:00 이전 조회는 N/A. 미국/미식별/복수증권은 N/A. 원문·유료AI·새DART/KRX/SEC 수집0.
증거는 ignored output/era_integration_20261017/ 아래 feature_commit.json·integration_activation.json·operational_integration_proof.json, rollback에 이전 News 설정. Era 프로젝트 원본·DB·Git·예약 쓰기0. Era 담당자가 동시 정상 개발해 HEAD와 상태문서는 바뀌었지만 이번에 읽은 완료 보고서/index 원본 SHA는 그대로; 타 개발을 되돌리지 않는다. Public GitHub push 없음.
다음은 NEXT_TASK.md. 원본 SSD코드·기존 안정서비스·배포 snapshot 직접 덮어쓰기 금지.
