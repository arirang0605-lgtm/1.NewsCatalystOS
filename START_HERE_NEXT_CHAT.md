# START HERE — NewsCatalystOS 현재 재개점

경로 `/Volumes/T5DATA/1.NewsCatalystOS`. AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 순서와 실제 Git을 확인한다.
RSS 분석 결과의 별도 읽기전용 소비 기능은 코드 SHA `748d705f8045ccaa37be1d368ca1204fc7f42612`에 구현·커밋·origin/main push 완료. 기존 producer/예약 분석 코드는 유지한다.
소비·분석·캐시 관련 재검증 54 PASS/0 FAIL(2026-10-14). 이전 스키마 fixture 결함은 producer 검증을 약화하지 않고 수정했다.
실제 기저장 core80/MOTIR10 제목 분석 결과를 별도 프로세스 2개가 90건 원형 보존·SHA 무변경으로 읽은 증거는 `logs/feed_consumer_live_check.json`.
운영 CLI는 `scripts/consume_feed_analysis.py`, 간단 실행법은 `docs/3_1-4_6_FEED_ANALYSIS_PIPELINE.md`. 비공개 결과 파일과 producer SHA로 선택하며 네트워크/유료AI/DB 쓰기 0.
기존 인수23/36 유지. 실관계 증거·인적 정답·승인 실AI·5실거래일/출시 등은 분리하여 NEXT_TASK.md 참조. 새 자료 없는 대기 항목 반복 점검 금지.
사용자 미커밋 `AGENTS.md`·`DECISIONS.md`·마스터 지침·미추적 그림/파일은 보존하고 임의 stage하지 않는다.
