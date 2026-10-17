# PROJECT_STATE — NewsCatalystOS 최신 기능·실자료·운영 상태

2026-10-17T11:45:04+09:00 / 기능 SHA `388da7ff99119ac584b3fa7c455a72aeb700cfb5` (개발 로컬). 과거 세부 코드 36/36 구현 기록 유지; 제품 실사용 운영·출시/실연동 인수는 별도. V1 반도체 산업 한정, 기능 구현 우선·필수 최소 시험.

## 이번에 새로 작동하는 사용자 기능
- 뉴스 검색 → 정확 RSS/허용 본문 판본 → 기업이 연관된 테마/경제 행동과 포함 이유 → **기존 인가된 원문 속 해당 기업의 경제 행동 구간만 클릭 확장**. `/api/news-evidence`의 선택적 `excerpt_theme_id/ excerpt_entity_id/ excerpt_claim_event_id/ excerpt_evidence_sha256`는 기존 정확 기사 (provider/event/title SHA)에 결속되어 다른 기사·기업·원문 판본을 읽지 못함. 저장 `company_evidence`의 원문/권리·시점·근거 무결성 검사 재사용. 최대 240자 구간, 긴 경우 잘림 표시, 실거래·매출/수혜 인증 없음.
- 집중 테스트 **20 PASS / 실패0**. 합성 RSS 2기업 동일 제목에서 기업별 경제 구간 분리, HTTP 정확 사건/근거 선택·변조 거부, 합성 MOTIR 허용 본문 인용과 권리 철회 차단, JS 확장 시 1회 로드·텍스트 안전. 실제 저장 NICE평가정보 서비스 출시 기사 원문 구간 35자 HTTP200 READY, 잘못된 근거 SHA N/A. 비반도체 기능 통과를 V1 반도체 직접 수혜 실증으로 대체하지 않음.
- 출처 registry/state와 ThemeStore 원본 5파일 SHA 불변, 신규 네트워크 수집·유료AI·DB/기밀 변경0. 운영 SSD·기존 8766/launchd 미배포, GitHub push 미시도. 사용자 AGENTS.md/DECISIONS.md/비전 dirty3 보존.

## 다음
NEXT_TASK.md — 현재 뉴스 검색결과는 키워드/후보 힌트만 표시하므로 사용자가 실제 저장 경제 사건 존재 여부를 알기 위해 각각 상세 열어야 한다. 동일 저장 source SHA/PIT로 제목 경제 변화와 허용 본문 정책 근거를 분리한 **검색 카드의 근거 구분·필터**를 기능으로 우선 구현. 새로운 AI/데이터 수집 없이 입력→저장결과→화면 경로만 완성. 제품/운영 기준은 기존 완료 정의만 사용.
