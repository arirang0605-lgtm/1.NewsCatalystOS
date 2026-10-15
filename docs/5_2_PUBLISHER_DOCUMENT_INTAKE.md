# 5_2 기업 IR·정부 본문 근거 입력

D-060에 따라 사람 검수·검수자 코드·`HUMAN_OPERATOR` 요구를 삭제했다.

- 입력 스키마: `newscatalyst.publisher_relation_intake.v2`.
- 최상위 필드: `schema`, `relation_kind`, `review`, `supplier`, `customer`. `review_origin`과 `reviewer_code`는 사용하지 않는다.
- 기존 허가 아카이브·출처 등록부·본문 SHA·회사 식별자·본문 일치 문장·시점은 자동 검사한다. `reviewed_at`은 자동 검사 시각이다.
- `relation_kind`는 `REPORTED_DIRECT_TRANSACTION` 또는 `ANNOUNCED_SUPPLY_PLAN`. 계획과 실제 이행·매출을 구분한다.
- `scripts/review_supply_relation.py --input-kind publisher`와 `scripts/publish_reviewed_beneficiaries.py`의 기존 아카이브·등록부·`--review-json` 인자를 사용한다. JSON은 자동 추출한 관계 근거이며 사람 입력을 요구하지 않는다.
- `scripts/consume_reviewed_beneficiaries.py`의 기존 게시물 읽기 경로는 유지한다. 이미 저장한 그래프와 원본은 다시 쓰지 않는다.
