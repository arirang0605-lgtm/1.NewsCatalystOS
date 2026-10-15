# 저장 테마 기업의 공식 식별 연결

기존 뉴스 후보의 원래 이름을 보존하면서 `feed_company_identity.load_directory`와 `article_company_identity.resolve_names`의 정확한 이름 판정을 재사용한다. 유사도·부분 이름·약칭 추측은 사용하지 않는다. 새 공식 API 수집이나 EraLeader 소스 실행은 없다.

## 입력과 저장

`python3 scripts/resolve_theme_companies.py`는 기존 비공개 `company_identity.json`의 고정 공시 명부를 읽어 `document_analysis/theme_company_identity`에 식별 영수증을 생성한다. `--theme-root`, `--identity-config`, `--output-root`로 분리된 경로를 사용할 수 있다. 디렉터리는 소유자 전용이며 테마 DB는 읽기 전용이다. 명부에 없는 후보도 그 상태를 기록한다.

예약 `run_feed_analysis.py`도 저장 테마 처리 후 같은 경로를 호출한다. 표준 운영 경로에서는 기존 설정을 사용하고, 사용자 지정 분석 경로에서는 명시된 설정만 사용한다. 설정/명부 오류는 식별만 UNAVAILABLE로 남기고 뉴스 처리는 계속한다. 스케줄러 요약에는 이름·원문 대신 식별 상태와 생성/캐시 수만 전달한다.

영수증은 후보 ID, 테마 판본 SHA, 원래 이름, 명부 SHA, resolver 버전으로 구분한다. 정확한 코드가 있는 경우 공시 문서 ID·출처 영수증/원본 SHA·확보시각·근거 SHA를 포함한다. 동일 입력 재실행은 최초 결정시각을 유지한다. 새로운 명부나 테마 판본은 새 영수증이 된다. `decision_at` 이전 조회에는 새 식별 결과가 나타나지 않는다.

## 조회

`GET /api/company-research?q=DART_CORP:12345678` 또는 `scripts/search_themes.py --with-financials --query DART_CORP:12345678`로 공식 코드 검색이 가능하다. 예시 번호는 합성값이다. CLI의 `--identity-root`는 기본적으로 평가 캐시 옆 `theme_company_identity`다.

`identity_context.status`는 MATCHED, NOT_IN_SNAPSHOT, AMBIGUOUS, NOT_RESOLVED_AS_OF, ALREADY_IDENTIFIED를 구분한다. MATCHED일 때만 `resolved_entity_id`를 추가하고 기존 `entity_id`는 그대로 둔다. 서명 없는 로컬 SHA는 무결성 검사이며 독립 기관 인증이 아니다. 손상된 선택적 영수증은 건너뛰고 후보를 유지한다.

재무 평가 연결은 기존 `era_company_assessment`의 코드·기간·통화·가용시각 조건을 그대로 적용한다. 식별 성공이어도 평가 목록에 없을 수 있다. 대시보드는 식별 근거와 재무 관측을 함께 보여 준다. 이 기능은 실제 거래·수혜·매출 기여·현재 가격 매력을 확정하지 않는다.

기존 테마 사건 수·판본·기본 v1/v2/v3 출력은 변경하지 않는다. 식별 결과는 company_research 파생 조회에만 더한다. 실제 검증에서는 명부 밖 후보의 미확인 경로가 확인됐으며, 긍정 재무 연결은 합성 시험으로 확인했다.
