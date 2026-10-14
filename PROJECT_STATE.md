# PROJECT_STATE — NewsCatalystOS 현재 상태

기준일 2026-10-14. 사용자 개발 원칙은 AGENTS.md. 과거 상태는 Git에 보존.

## 기능 구현·테스트
- **완료 RSS 관측→경제변화 후보/부분 중요도→기존 예산 AI·캐시→결과 파일 연결 완료.** 기능 `7f4daaf146869aa25dc83e426440d0e88d70021a`, origin/main SHA 일치 확인.
- 새 `feed_analysis.py`/`run_feed_analysis.py`가 기존 prior_fact_state/novelty_detection/impact_triage/fact_extraction/AI/비용원장/cache를 연결한다. 기존 수집·ACK·검색·Gold·공급망 v1/v2는 변경 없음.
- 정확 출처 문자열과 후보·AI 미검증 해석 구분. 같은 문서 재발행/캐시 재사용, 금액 정정 버전 분리, 일부 미확인·AI 실패에도 출처 필드 보존. 제목 규칙의 점수/규모는 출력된 스크리닝 가정이지 인수 조건이 아니다.
- T5에서 결과 게시 시 실제 하드링크 errno45를 발견·수정: 짧은 잠금+원자 rename으로 게시, 기존 결과 보존. 별도 두 Python 프로세스는 합성 RSS/가짜 HTTP로 첫 분석1/모의호출1, 재실행 캐시1/모의호출0·동일 결과 SHA.
- 변경 영향 **10개 테스트 파일 103 PASS/0 FAIL**, compile/diff/Public 검사 PASS. 전체 회귀 아님. 로그 `logs/feed_analysis_regression.log`, `logs/feed_analysis_process_smoke.json`.
- 기존 5_5 v1/v2 게시·별도 소비는 `b8dadb9`의 정상 기능을 그대로 보존.

## 실자료 검증
- 20:11 KST 기존 승인 메타데이터 **core80 + motir10 = 90개 제목 버전**, 새 CLI 두 실행 exit0·비공개 결과 SHA 확인. 반도체 용어 정확 일치 필드를 가진 제목은 각1건.
- 이 입력에서 AI 우선순위 조건을 충족한 반도체 신규 후보0. 실제 유료 호출/사람 라벨/새 RSS HTTP0. 90개를 독립 경제사건/인적 정답으로 세지 않는다.
- 등록부2/운영DB4 총6개 원본 SHA 동일. 별도 파생 분석 state/report만 생성. 실제 증거 `logs/feed_analysis_live_check.json`. EraLeader 접근·변경0.
- 실제 모델 사용·요금 승인/정답 평가·허가 원문 실증은 별도다. 같은 미승인 여부를 반복 확인하지 않는다.

## 운영·출시 인수와 다음 작업
- 기존 단계 인수집계 **23/36** 유지. 이번 RSS 전체 처리 연결은 기능 완료이며 전체 제품의 실제 AI/성능 인수가 아니다.
- 원래 500건 인적 평가·정확도·반도체 관계 평가·실AI 비용·실제5거래일·전체 회귀/릴리스는 별도 미완료. 추가 필수 검증 없음.
- 다음: NEXT_TASK의 기존 예약 실행→RSS 분석→결과 저장 연결. 유료AI 미승인 중에도 규칙 분석은 가능하다.
