# START HERE — NewsCatalystOS 현재 재개점

경로 `/Volumes/T5DATA/1.NewsCatalystOS`. AGENTS.md → PROJECT_STATE.md → DECISIONS.md → NEXT_TASK.md 순서와 실제 Git을 확인한다.
최근 구현: 기존 `search_news.py` 검색 결과와 SHA 고정된 `feed_analysis` 보고서를 출처·사건·제목·triage 증거 기준으로 결합. 새 코드 SHA `43d99ec9361385bfcf677ac60cf8c926f8758bf4`. `--analysis-report-file/--analysis-reports-root/--analysis-expected-sha256` 세 옵션 지정 시 `saved_analysis` 출력. 기존 Gold 맹검·검색은 별도 유지.
변경 영향 **8개 테스트파일 133 PASS/0 FAIL** (2026-10-15). 기존 실제 승인 메타 core/MOTIR 각각 독립 CLI exit0, 분석 연결 2/1건, 보고서 SHA 불변·신규 HTTP/AI 0.
이전 계약 해지 후보 규칙(`12b4066`)·읽기전용 소비(`748d705`)·실 메타90건(2026-10-14)은 보존. AI 실비용 승인 없이 새 호출하지 않음.
기존 인수23/36 유지. NEXT_TASK.md의 5_2 공식 관계 실증은 실제 문서/인적 검토 증거 입수 시 재개하며, 새 증거 없이 같은 차단 점검 반복 금지.
사용자 미커밋 `AGENTS.md`·`DECISIONS.md`·마스터 지침·미추적 그림/파일은 보존하고 임의 stage하지 않는다.
