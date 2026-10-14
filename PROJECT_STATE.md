# PROJECT_STATE — NewsCatalystOS 현재 상태

기준일 2026-10-14. 사용자 운영 원칙 AGENTS.md, 과거 기록은 Git에 보존.

## 기능 구현·테스트
- **기존 core/MOTIR 예약 실행→완료 ACK→규칙 분석·기존 캐시→비공개 결과 저장 연결 완료.** 기능 `8342901fae4ef7f7a84baf561d769339f98009ff`, origin/main push·동일 SHA 확인.
- 새 수집기/서비스 없이 `run_scheduled_triage.py`, `run_motir_policy_once.py`가 기존 분석 CLI 함수를 재사용. 파생 root는 core/motir 분리, 기본은 신규 유료AI 없는 규칙 분석. 모델 설정은 기존 캐시 읽기만 허용.
- NOT_DUE·수집 실패에도 이전 완료 자료는 분석하되 원래 실패를 숨기지 않는다. 분석 오류는 성공 ACK/워터마크를 변경하지 않고 replay-only로 재처리한다. 다른 제공자의 손상 triage와 MOTIR Gold 준비 실패가 정상 분석을 막지 않는다.
- 기존 수집 전용 `--skip-analysis`, 무HTTP `--replay-only`, 제공자별 최신최대100·한도초과 표시 지원. 정상 복구 ACK를 건강진단이 오판하던 상태를 바로잡았다. 추가 인수 조건은 없다.
- 변경 영향 **9개 테스트파일 100 PASS/0 FAIL**, compile/diff/Public 검수 PASS. 합성 수집→ACK→분석 성공·저장 실패 복구·캐시 재사용·출처 격리/기존 모드 포함. 전체 회귀나 실제 AI 청구시험은 아님.
- 증거: `logs/scheduled_analysis_regression.log`. 기존 RSS 분석 및 5_5 v1/v2 전달 기능은 보존.

## 실자료 검증
- **20:40 KST** 기존 명령을 replay-only 별도 Python 프로세스로 실행: 중기부23 + 뉴스와이어IT57 + MOTIR10 = **90개 제목 버전**, 결과3파일 저장·SHA 확인, 두 실행기 exit0/exit0. 신규 RSS 요청·유료AI·인적 라벨0.
- 등록부2·운영DB4·기존 LaunchAgent 설정3 총 **9파일 SHA 동일**. 파생 분석결과 외 원본·EraLeader·다른 프로젝트 변경 없음. 제목 수를 독립 경제사건/정답 수로 세지 않는다.
- 실증 로그 `logs/scheduled_analysis_live_check.json`; 결과 `output/feed_analysis/core/reports/`, `output/feed_analysis/motir/reports/` 비공개 보존.

## 운영·출시 인수와 다음 작업
- 기존 1시간 서비스 설정/등록은 유지. 수동 kickstart 확인 요청은 도구 보안 차단으로 실행하지 못했다. 20:41 읽기전용 로그는 이전 정상 tick; **새 코드의 자연 예약 실행은 아직 미관찰**. 같은 명령 재시도·우회 금지, 다음 실제 실행 기록이 생길 때만 확인.
- 관찰 기록 `logs/scheduled_analysis_service_observation.json`. 이 대기는 독립 결과 소비 기능 개발을 막지 않는다.
- 기존 단계 인수 **23/36** 유지(전체 코드 구현률 아님). 원래 500건 평가·정확도/반도체 관계·실AI 비용·실제5거래일·전체 회귀/릴리스는 별도 인수. 새로운 검증 의무를 만들지 않는다.
- 다음은 NEXT_TASK의 RSS 분석 결과→별도 읽기전용 소비. 기존 외부 입력/승인 상태 반복 점검 없이 진행한다.
