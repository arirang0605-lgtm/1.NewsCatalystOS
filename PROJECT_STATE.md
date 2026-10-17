# PROJECT_STATE — NewsCatalystOS 최신 기능/실자료/운영 구분

기준 2026-10-17T10:35:59+09:00. V1 반도체 한 산업, 과거 1_1~6_6 코드 구현 36/36(출시 인수 아님). 완료 기준 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md.

## 최신 기능·해소한 개발 장애
- `b23a9acdb1e348b22e0b295bba2ddb70f6d72b73`: 산업부 예약 작업이 국소 옵션 의미분석 실패를 전체 RSS 수집·저장 실패로 잘못 판정해 종료4 반환하던 문제의 개발 코드 수정. 실제 비공개 저장분석 17항목 중 캐시15·AI 미정산 예약1·미실행1 확인; 예약 기록은 비용 원장에서 2개 미정산 포함 (이벤트3개 과거 요청 판본 중), 임의 비용 정산/키 변경/재호출 없이 보존. 미정산 이전 호출은 새 `AI_PREVIOUS_CALL_UNSETTLED`로 명시하며 기존 저장 캐시/일반 뉴스 사실은 유지. 예약 메타의 국소 AI 미완료를 개별 status+requested_ai_complete=false로 남기고 기존 완료 RSS 입력·분석은 exit0 가능; 중요한 ai_eligible 신규 사건 오류·파일/DB 오류는 여전히 exit4. 예약 유료 의미분석 라우팅은 24시간 이내 V1 반도체 제목 + 기존 triage 검토 후보만 선택(신규 출시 게이트가 아닌 비용 절감 설정). 명시 사용자 단일 기사 분석 예외 유지.
- 변경영향 시험: 160 PASS, 실패0(신규 예약상태/격리/정상 신규 AI fixture 3 포함). JS/CLI 변경 영향 없음. 실제 미정산 article의 기존 비용원장·AI캐시·보고서 3개 SHA 불변, AI HTTP/신규 유료 호출0.
- 실제 저장 MOTIR 승인 RSS 17건 로컬 replay-only: 이전 운영 ai_cache 읽기전용 백업을 별도 임시폴더로 복사, private 새 분석 root에 저장·보고서 SHA 확인. status MOTIR_SECTOR_SOURCE_ANALYSIS_READY / exit0, semantic_deferred=1·incomplete=1, paid_adapter_attempts=0, 외부 수집0, 실코어 입력→보고 정상. 6개 원본 설정·state·비용·캐시·테마DB SHA 불변, 임시 사본 정리.
- 이전 개발 대시보드 실자료(2026-10-16 43 뉴스/8 테마/5 기업후보, RSS 검색173, MOTIR 정책 기사/기간변화)는 정상. 이 턴에 무관한 화면/원본/예약 코드를 재작업하지 않음.
- **실운영 별도**: 현재 launchd com.newscatalystos.motir의 배포된 SSD 코드는 구버전, 최근 exit4를 새 코드의 자연 예약실행 성공으로 대체하지 않는다. 운영 배포/재시작·GitHub push 모두 미수행. 사용자 기존 dirty3 불변, EraLeader/MarketOS·API·SSD 원본 무변경.

## 다음
NEXT_TASK.md: 현재 개발-운영 배포 경계는 그대로 보존. 다른 독립 필수 OP-05 복원 읽기를 이미 있는 정상 스냅샷/백업·코드로 1회 실자료 확인하되 기존 유효 증거가 충분하면 반복 안 함. 인적 검수·새 장비/5거래일 선행 필수화 금지.
