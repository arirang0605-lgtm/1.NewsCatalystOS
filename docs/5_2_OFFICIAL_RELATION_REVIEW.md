# 5_2 공식 문서 기반 관계 근거 자동 검사

D-060에 따라 사람 검수와 검수자 코드를 삭제했다. `OfficialRelationReview`라는 기존 타입명과 `--review-json` 옵션명은 호환 가능한 호출 이름으로 유지하지만 입력 내용은 자동 추출한 근거이다.

- 입력 스키마: `newscatalyst.official_relation_intake.v2`. 최상위 필드는 `schema`, `review`, `supplier`, `customer`.
- `review`는 원본 문서 ID·출처 SHA·본문 SHA·입수/검사 시각·양사명·본문에 실제 존재하는 관계 문장·반도체 공정을 담는다. `reviewer_code`는 삭제했다. `reviewed_at`은 자동 검사 시각이다.
- 기존 완료 공시 스냅샷과 본문 SHA, 회사 식별자, 문장 일치, 부정문, 시점을 자동 검사한다. 근거 없는 관계를 통과시키지 않는다.
- `scripts/review_supply_relation.py`의 기존 출처·문서 인자를 사용한다. 결과는 보도된 관계 후보이며 계약 이행·실매출을 인증하지 않는다.
- 원문·운영 DB는 비공개로 보관하고 EraLeader는 읽기 전용이다. 실제 본문 확보와 자동 처리 연결 진행은 PROJECT_STATE/NEXT_TASK를 따른다.
