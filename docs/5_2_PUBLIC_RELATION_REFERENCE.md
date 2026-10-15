# 5_2 실제 공개 관계 참고자료 → 기존 반도체 그래프 시범 연결

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

## 자료와 판단 구분

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
