# PROJECT_STATE — NewsCatalystOS 최신 상태

기준 2026-10-17T11:25:03+09:00. 개발 브랜치 codex/real-data-path / 기능 SHA `148acfa56939fe36a752b2d2c57d9ba1b0fb8ec5`; 기존 36/36 기능 코드 구현 기록 유지, 독립 운영/실자료/공동 인수는 별도. 사용자 우선순위 실사용 기능 개발, 변경 영향 최소 시험. V1 반도체.

## 작동 기능·증거
- 정확 RSS 기사 및 이미 허용된 공식 본문에서 매칭된 이벤트·테마만 읽어 회사의 직접 출처 당사자 지위/포함 이유/기사 출처·시각, 이미 저장된 공식 식별 매핑의 ID·SHA 여부와 같은 사건에 별도 출처로 결속된 공급자·고객의 관계 맥락을 새 `article_company_context` 응답으로 노출. 기존 ThemeStore/standard_delivery.CompanyCandidates 재사용, 직접/별도 관계 분리, 원문 제목·회사 이름만으로 신규 기업·수혜/매출 추론 금지. 과거/PIT 및 철회 시점은 사건 버전에 따름.
- 집중 테스트 `tests/test_news_article_company_context.py` 등 변경 영향 **17 PASS / 실패0**, JS 구문/Git diff 검사 완료. 합성: 같은 기사 직접 당사자1~2, 고정 DART ID는 해당 원문 매핑만, 다른 출처 공급자/고객, 정책 무기업 N/A, 과거 시점 거부. 실제 2기사 임시 로컬 HTTP: NICE평가정보 서비스 출시 직접 기업1·포함 이유1/공식 ID 미확인(비반도체 사례); 반도체 메가프로젝트 전담국 공식 본문 POLICY_CHANGE와 회사0 N/A. 원본 설정·상태DB·테마DB5 SHA 불변. 운영 원본·타 프로젝트·API 수집·유료AI·GitHub 변경 없음.
- 최신 사용자 검색→규칙 제목 분석→정확 테마/회사/공급망→기간별 후속 변화 보기까지 기존 UI로 조회 가능. 반도체 V1 실제 기업 수혜 입증은 아직 없음; 이를 비반도체 사용성 증거로 대체하지 않는다.
- 로컬 코드만 커밋 `148acfa56939fe36a752b2d2c57d9ba1b0fb8ec5`; 운영 SSD·상시 8766/launchd는 구버전, 배포/자연 tick 성공 증거 별도. 사용자 dirty3 보존.

## 다음
NEXT_TASK.md의 **동일 기사·기업 경제 변화 원문 근거 문장 열람** 기능. 기존 /api/company-evidence의 테마 전체 근거를 해당 선택 기사 source URL/event/ref SHA와 연결해 다른 출처 문장을 잘못 보여주지 않도록 함. 실제 자료 없는 부분 N/A. 별도 출시 운영 확인은 명시 완료조건에서만 시행.
