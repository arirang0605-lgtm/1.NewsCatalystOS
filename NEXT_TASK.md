# NEXT_TASK — 기존 운영 백업의 격리 복원·읽기 증거 확인 (OP-05)

## 현재 완료
NEWS-20261017-MOTIR-OPTIONAL-SEMANTIC-RESERVATION / `b23a9acdb1e348b22e0b295bba2ddb70f6d72b73`. MOTIR 예약 exit4의 국소 원인(기존 optional Gemini 의미분석 미정산 이벤트1)을 읽기전용 근거로 확인. 기존 미정산 예약은 유지하여 중복과금 금지, RSS/문서 정규 처리 성공과 optional AI 미완료를 분리하고 비용 사용을 신규 V1 후보로 한정. 신규/변경영향160 PASS. 실저장17항목 격리 replay-only 종료0·보류1·HTTP/유료 AI0·6원본 SHA 불변. 운영 SSD 버전/launchd는 여전히 과거 코드이므로 실제 새 코드 운영 성공 주장은 금지.

## 다음 독립 필수 기능 · OP-05
사용자 승인 없이 운영 배포/push를 강행하지 않고, 독립적으로 진행 가능한 보존·재개 경로의 실자료 정상 입력→격리 복원→읽기 성공을 마친다.
1. 기존 `backup_recovery.backup_sqlite`/`restore_to_new_dir`, `physical_recovery` 및 보관 증거를 필요한 범위만 확인한다. 2026-10-14/15 `restore_checks`/`restore_tests` 등 이전 스냅샷 이력은 존재. 이미 유효한 실제 원본 DB 백업·복원·integrity/read 증거가 충분하면 단순 반복은 하지 않는다.
2. 부족한 경우에 한해 **기존 허용 운영 SQLite DB**를 온라인 읽기 백업하여 다른 비공개 임시 폴더로 복원하고 무결성·필수 테이블 읽기를 한 번 확인한다. 원본 DB·원본 SSD/공개 Git 변경/원본 덮어쓰기·공식 API·유료 AI 요청 금지. 별도 물리 장치/5거래일 대기를 새 출시 조건으로 추가하지 않는다.
3. 백업·복원 완료를 운영 전체 정상화와 혼동하지 않는다. 작업 영향 시험/원본 SHA/Git 상태/백업의 실제 범위만 보고, 필요 없는 코드 변경이나 추가 관리 도구 생성 금지.
4. OP-02 산업부 **자연 예약 tick** 정상화는 실제 SSD 배포된 코드가 바뀐 뒤 증거 확보 대상으로 구분. 기존 구버전 운영 exit4는 그대로 명시. 배포/GitHub push 미승인 시 시도하지 않고 독립 작업은 계속한다.

제품 완료는 docs/PRODUCT_COMPLETION_CRITERIA_20261016.md 원래 기준으로 판정. 코드 36/36은 기능 기록, 출시 인수와 분리.
