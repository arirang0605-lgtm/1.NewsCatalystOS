# 테마에서 기업 후보 근거로 연결

기존 `ThemeStore`의 불변 시점 판본을 읽어 기업별 포함 이유를 제공한다. 새로운 기사 수집·회사 사전·DB를 만들지 않고 저장된 사건, 회사 식별 매핑, 공급망 근거를 재사용한다. `theme_company_candidates.py`의 결과는 테마 판본 SHA와 연결되며 조회 과정에서 원본 판본이나 테마 점수를 바꾸지 않는다.

## 사용

- 기존 조사 대시보드의 테마 기업 아래 **기업 포함 이유·수혜 경로·불확실성**을 펼친다. 출처와 보도된 행동/단계, 공급자·고객, 계획·상충·제목만 확보된 경우의 한계를 확인한다.
- `GET /api/themes?company_candidates=1&q=기업명`은 `newscatalyst.theme_delivery.v3`의 `ThemeCandidates`와 `CompanyCandidates`를 반환한다. `as_of`, `since`, `activity`는 기존 의미를 유지한다.
- `python3 scripts/search_themes.py --company-candidates --query 기업명 --export-root /비공개/결과폴더`는 SHA로 이름 붙인 읽기 전용 JSON을 저장한다. 기존 `--root`, `--as-of`를 함께 사용할 수 있다.
- 옵션을 생략한 API/CLI와 기존 `build_theme_bundle` 호출은 기존 v1/v2 계약을 유지한다. `read_theme_bundle`은 v3도 읽고 원본 테마에서 기업 결과를 다시 계산해 조작된 파생 결과를 거부한다.

## 정보의 의미

`SOURCE_REPORTED_PARTICIPANT`는 경제 행동 근거에 등장한 기업이다. 실제 계약 이행이나 수혜를 독립 확인한 표시가 아니다. `SOURCE_REPORTED_SUPPLY_RELATION`은 기존 문서·기업·SHA로 연결된 공급 관계이며, `INFERRED_ASSOCIATION`은 추론한 연관이다. 공급 계획은 공급 실현과 구별한다. 같은 기업에 여러 근거 종류가 함께 있을 수 있다.

`business_context.source_topics`는 출처의 제품·사업 주제이고 검증된 사업 구성은 아니다. 공급망 경로가 있으면 단계·상대기업·공급자/고객 역할과 기존 수혜/피해 가설을 전달한다. 없으면 `benefit_path_status=UNKNOWN`이다. 임의의 매출 기여·목표가·총점은 만들지 않는다.

재무/가격 평가는 `NOT_CONNECTED`, 투자 매력은 `NOT_ASSESSED`다. 기존 EraLeader 공시 명부의 회사 매핑 근거는 유지하지만 최신 기업 평가 산출물의 소비는 이번 범위에 포함하지 않았다. 생산자 작업트리·운영 DB·공식 수집기를 변경하거나 실행하지 않는다.

## 검증 범위

합성 시험은 저장→조회→SHA 내보내기→HTTP, 공시 이름 매핑, 당사자/추론 구분, 공급자/고객 영향 차이, 계획, 회사 없는 정책, 중복 보도, 상충/철회, 과거 시점, 파생 결과 조작을 다룬다. 실제 저장 자료의 기업 후보는 기존 보도 근거의 연결 결과이며 신규 투자 유망기업 발굴 성과가 아니다. 실제 수치는 최신 PROJECT_STATE를 따른다.
