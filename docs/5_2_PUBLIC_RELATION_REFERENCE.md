# 5_2 실제 공개 관계 참고자료 → 기존 반도체 그래프 시범 연결

## 목적과 범위

기존 공식 공시 메타에는 공급사·고객사 관계 본문이 없었다. 해당 메타에 다른
기업 발표를 같은 공시처럼 연결하거나, ChatGPT의 자료 확인을 사람 검수로
입력해서는 안 된다. `public_relation_reference.py`는 실제 확인한 **짧은 출처 인용과
회사 식별자 참고자료**를 기존 5_2~5_5 코드에 시범 입력하는 오프라인 어댑터다.
새 평가 프레임워크, 수집기, 사람 정답 생성기 또는 공식 인수의 우회 경로가 아니다.

## 기존 코드 재사용

`CompanyBinding` / `FeedObservation`의 가벼운 출처 주장 타입을 메모리에서만 사용해
`observed_supply_edge` → `propagate_semiconductor_claim` →
`classify_semiconductor_beneficiary` → `build_beneficiary_graph`를 호출한다.
가상 RSS 영수증이나 공식 API 캡처를 만들지 않으며 등록부·수집DB·Gold·검수답안에
삽입하지 않는다. 원래 `official_relation_intake.py`와 공식 관계 게시/소비 코드는
변경하지 않는다. 시범 결과는 공식 outbox의 기존 검증에서 거절된다.

## 자료와 판단 구분

- `ASSISTANT_SOURCE_RESEARCH_NOT_HUMAN_REVIEW`: 보조자의 출처 조사 메모이며,
  독립 사람 검수·500건 정답·정확도 측정에 포함하지 않는다.
- `SHORT_CITATION_ONLY_NOT_COLLECTION_PERMISSION`: 짧은 인용·출처 링크만 보관한다.
  사이트 자동수집·기사 전체 저장·외부 재배포의 허가를 받은 것으로 간주하지 않는다.
  이 도구는 네트워크 호출이나 새 제공자 활성화 기능을 갖지 않는다.
- 최초 기록시각, 별도 물리 디스크의 로컬 SHA PIN 시각, 이번 소비 완료시각을
  구분한다. 출처의 과거 날짜는 날짜 그대로 표시하고 `published_at`은 null이다.
  과거 관계를 오늘의 신규 계약·새로운 경제사건으로 승격하지 않는다.
- SHA는 **짧은 참고기록 전체의 로컬 무결성**을 확인한다. 기사 원문 전체의 SHA,
  외부 인증 또는 실제 발행시각 증거가 아니다. SEC 식별자 링크와 짧은
  회사명/CIK 인용 역시 본문에서의 계약관계 검증과 구분한다.
- 방향은 UNKNOWN 고정, 실매출·현재 출하·수혜확정은 false/null이다.
  `eligible_for_delivery=false`, `official_review_gate_satisfied=false`를 유지한다.

## 실행

실제 사례 및 SHA PIN은 개인 전용 디렉터리에만 저장한다. 아래 경로는 자리표시자다.

```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/inspect_public_relation_reference.py \
  --reference-file /absolute/private/ssd/relation_reference_<SHA>.json \
  --pin-file /absolute/private/mac/relation_reference_<SHA>.pin.json
```

출력은 출처 URL·회사 식별자·반도체 공정·근거 SHA·그래프 **미리보기**다.
짧은 출처 인용문 자체는 출력에 복제하지 않는다. 입력은 수정하지 않으며,
검증 실패 시 원문·개인 경로를 노출하지 않고 종료코드 4를 반환한다.

## 2026-10-14 실사용 확인

실제 기업 공식 발표의 19단어 관계 인용 1건과 SEC 공식 회사 식별자 참고 2건을
개인 SSD에 저장하고, Mac 내부에 별도 로컬 SHA PIN을 보관했다. 별도 Python
프로세스가 기존 반도체 그래프 코드로 관계 후보 1건을 처리해 종료코드 0을 반환했다.
시범 분류는 `EFFECT_DIRECTION_UNKNOWN`, 공식 인수·외부 전달은 false다.
등록부 2개·운영 DB 4개·참고자료/PIN 2개의 SHA가 조회 전후 동일했다.
실제 회사명, 인용, 운영 자료 및 시범 결과는 Public Git에 포함하지 않았다.

변경 영향 8개 테스트 파일 **87 passed / 0 failed**. 합성 테스트에는
기존 공식 게시 경로의 시범 입력 거절, 미래시각·변조·다른 CIK/회사/산업,
원문 추가·가짜 사람검수·수집 허가 승격 차단, 원본불변을 포함한다.

실제 공식 문서 참고자료가 생긴 것은 진전이지만, 승인된 원문 사용·정식 관계 검토와
실제 후속 소비 인수를 대체하지 않는다. V1.0 인수 완료 수는 **23/36**이다.
다음 작업은 확보한 관계의 적법한 운영 입력 경로 및 실제 검수를 기존 공식
인수 조건에 맞게 연결하는 것이다. 참고자료가 없다고 같은 검색·검수 도구를
다시 만들거나 사람이 작성한 것으로 라벨을 자동 입력하지 않는다.
