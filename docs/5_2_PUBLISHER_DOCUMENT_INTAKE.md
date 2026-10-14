# 5_2 기업 IR·정부 원문 입력 — 공시와 별도 출처 유형

## 이번에 해결한 입력 제약

기존 `read_official_relation_intake`는 DART/SEC 완료 관측 배치에 속한 공시만 받았다.
기업 발표를 확인하고도 이를 다른 SEC 공시의 본문으로 바꾸어 입력하면 출처가 틀린다.
기존 공식 입력은 그대로 두고, `official_relation_intake.py`에
`read_publisher_relation_intake`를 추가했다. 기존 원본 아카이브·관계 문장 검토·기업
바인딩·공급망·파급·수혜분류 코드를 재사용한다. 별도 수집기나 평가 프레임워크는 없다.

## 입력과 재사용 경계

1. 기존 `evidence_archive.archive_evidence`로 보관된 `LICENSED_SOURCE_BYTES` 버전이 필요하다.
   이번 입력기는 저장·다운로드·등록을 하지 않으며 이미 있는 아카이브를 읽는다.
2. 기존 출처 등록부의 `COMPANY_IR` 또는 `GOVERNMENT_POLICY` 제공자가 문서 최초
   관측 시점과 현재 모두 승인 상태여야 한다. 기존 전체 원문 보관 정책인
   `WRITTEN_LICENSE` + `allow_full_text_storage=true`를 유지한다.
   공개 사이트라는 이유만으로 이 설정을 생성하거나 허가로 바꾸지 않는다.
3. 운영자가 독립적으로 보관한 문서 SHA와 아카이브 영수증 SHA를 함께 받는다.
   아카이브의 제공자·문서 ID·버전과 리뷰의 제공자·문서 ID·증빙 ID가 일치해야 한다.
4. 사람이 실제 작성한 검수 입력만 사용한다. 입력 스키마는
   `newscatalyst.publisher_relation_intake.v1`, `review_origin=HUMAN_OPERATOR`이다.
   기존 `OfficialRelationReview`/`CompanyBinding` 필드 구조를 재사용하며
   `schema/review_origin/relation_kind/review/supplier/customer`가 최상위 필드다.
   검수 코드 문자열 자체는 사람의 신원·독립성 인증이 아니다.
5. 첫 소비 완료시각 이후로만 사용할 수 있다. 정정 자료는 기존 아카이브의
   새 버전과 `supersedes_version_id`를 사용하고 이전 문서·리뷰는 보존한다.

아카이브 버전은 RSS나 SEC 수신 영수증으로 변환하지 않고 `ArchivedEvidence`로
직접 연결한다. 기업 식별자도 문서 제공기관에 억지로 맞추지 않으며 실제 검토된
각 기업의 SEC_CIK/DART_CORP/KRX_STOCK 네임스페이스를 보존한다.

## 공급계획과 거래관계 구분

`relation_kind`는 검수자가 근거를 확인해 명시한다.
- `REPORTED_DIRECT_TRANSACTION`: 문서에 보고된 직접 공급관계. 실제 계약 이행·출하를 인증하지 않는다.
- `ANNOUNCED_SUPPLY_PLAN`: 앞으로의 공급계획. 영향 방향을 POSITIVE로 지정해도
  `ANNOUNCED_SUPPLY_PLAN_UNVERIFIED`로 분류하고 실현 매출은 null로 유지한다.

자동으로 문장을 읽고 참/거짓이나 관계 상태를 결정하는 AI 기능을 추가한 것이 아니다.
기존 단순 테마 관계와 두 회사 이름의 동시 등장만으로 검수 완료를 주장할 수 없다.

## CLI

기존 명령의 기본 `--input-kind official` 및 공식 공시 입력은 유지된다.
허가·검수된 비공개 아카이브가 실제 준비된 경우 다음 형태를 사용한다.
아래 값은 자리표시자이며 운영 입력이나 허가를 자동 생성하는 명령이 아니다.

```sh
PYTHONPATH=src python3 scripts/review_supply_relation.py \
  --input-kind publisher \
  --registry /absolute/private/providers.json \
  --archive-root /absolute/private/document_archive \
  --archive-version <retained-archive-version> \
  --archive-receipt-sha256 <retained-receipt-sha256> \
  --document-sha256 <retained-document-sha256> \
  --review-json /absolute/private/human_relation_review.json
```

publisher 모드에 `--publication` 등의 공시 입력을 섞으면 거절한다.
출력에는 원문이나 인간 답안 대신 관계 종류·증빙 SHA·사용가능시각만 포함한다.

## 그래프 호환성과 남은 작업

기업 발표 출처와 계획 관계를 담은 그래프는 `newscatalyst.beneficiary_graph.v2`로
구분한다. 기존 공식 문서 그래프는 v1 그대로이며, v1 전용 게시·소비자는 v2를
정상적으로 거절한다. **v2 외부 게시·소비 연결은 다음 5_5 작업**이다.
문서가 검토됐다는 상태와 실제 수혜/매출 인증은 다르며 모두 false/null을 유지한다.

## 2026-10-14 확인 결과

변경 영향 12개 테스트 파일 **158 PASS / 0 FAIL**. 회사 IR/정부 입력, 계획·거래 구분,
정정 버전 보존, 출처별 식별자, 권한 만료·미검수·잘못된 원문/핀 거절,
PIT 및 기존 공식 경로의 하위호환을 검증했다. 테스트 허가·인적 답안은 모두 합성이다.
별도 Python 프로세스의 합성 publisher CLI도 exit0, 계획 관계/실거래 확정0이었다.

실제 Mac에 등록된 기존 제공자 3개 중 위 전체 원문 보관 조건을 충족하는 출처는 0개다.
실제 원문 아카이브 입력·사람 검수 추가·새 출처 등록·AI/공식API 호출은 0이며,
기존 등록부2/운영DB4/관계 참고·PIN2 총 8개 파일 SHA는 전후 동일했다.
기존 실제 관계 참고자료는 그대로 보존했고 정식 입력으로 승격하지 않았다.

사용조건 조사 근거: https://www.apple.com/legal/internet-services/terms/site.html
(2026-10-14 확인). 제한된 정보 이용조건과 자동 접근·복제 제한을 확인했으며,
웹페이지 조회를 운영 원문 수집 허가로 간주하지 않았다. 이 검토는 법적 허가서가 아니다.

**전체 완료 23/36 유지.** 원문 사용권한·실제 검수·외부 소비·정답 평가·실 AI·
5거래일 운영은 코드의 합성 시험만으로 완료하지 않는다.
