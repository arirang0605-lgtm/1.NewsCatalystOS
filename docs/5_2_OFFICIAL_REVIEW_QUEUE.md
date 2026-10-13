# 5_2 기존 공시 스냅샷 기반 실제 문서 검토 작업목록

## 무엇이 실제로 동작하는가
- `build_official_review_queue.py`는 **NewsCatalystOS의 기존 비공개 완료 게시본 v2**(`observations.json` + 완료 마커 + 소스 커버리지)를 먼저 SHA/PIT 검증하고, 이를 재사용해 DART/SEC 공시 문서 ID 및 기존 근거 SHA·접수 영수증만 추출한다.
- 코드가 EraLeader의 DART/SEC/KRX 수집기·원본 DB·Git을 변경하거나 API에 재접속하지 않는다. KRX 시세·SEC 회사재무 facts는 자동 제외한다.
- 실제 로컬 v2 게시본 확인 결과: DART 공시 메타 100건, SEC 공시 메타 1,001건, 총 **1,101건**. 이 수는 이미 수신한 **공시 메타 건수**이지 반도체 관련 실제 관계 1,101개가 아니다. 공급관계/반도체 연관성 독립 검수는 현재 0건.
- 각 항목은 `source_id`, `source_document_id`, `source_evidence_id`, `source_receipt_sha256`, `source_available_at`, `source_quality`를 포함하되, `industry_relevance=UNKNOWN_UNSCREENED` / `supply_relation_status=UNREVIEWED` / `verified_real_transaction=false`로 제한한다. 종목명·거래 상대방·계약 내용·실적을 추정하지 않는다.
- `offset`/`limit`으로 안정적인 페이지 나누기를 지원하고, `--document-id`로 실제 검증된 공시 ID 하나만 추출할 수 있다. 정렬은 ID 기준이며 투자 중요도 순위가 아니다.

## Mac 단발 실행 (운영자만)
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/build_official_review_queue.py \
  --publication "/Volumes/T5DATA/1.NewsCatalystOS/output/<기존-완료-게시폴더>" \
  --publication-root "/Volumes/T5DATA/1.NewsCatalystOS/output" \
  --payload-sha256 "<별도-보관한-기존-게시-PAYLOAD-SHA256>" \
  --source-id ALL --limit 1500 \
  --output-root "/Volumes/T5DATA/1.NewsCatalystOS/output"
```
특정 문서만 재검토할 경우 `--source-id dart-disclosures --document-id <기존-DART-ID> --limit 1`처럼 좁힌다. SEC는 `--source-id sec-submissions` 사용.

**실 데이터 스모크 검증 시 주의:** 원 게시 파일에서 *지금* 계산한 SHA를 입력하면 같은 로컬 파일에 대한 일관성 검증일 뿐 과거 공시 공개시각·독립 출처 공증은 아니다. 운영에서는 이전에 독립 보관한 payload pin을 제공해야 한다. 작업목록에 공식 문서 **본문은 저장하지 않는다**.

## 산출물·5_2 인계
- 출력은 `output/official_relation_review_queue_<랜덤 ID>/queue.json` 및 `publication.json`이며, 마커/PIT·SHA 포함, 새 폴더 0700·파일 생성시 0600 요청·원자 게시, 기존 게시 덮어쓰기 금지. 실제 Mac T5DATA 마운트는 파일 권한이 0700으로 표시되었으나 그룹/기타 사용자 권한은 0으로 확인했다. `marker_prepared_at`은 게시 준비시각으로 **실제 이용 가능시각의 공증이 아니다**. 신규 소비자는 SHA 및 최초 완료 읽기 시각을 별도 기록해야 한다.
- 운영자가 `UNKNOWN_UNSCREENED` 항목 중 **실제 반도체 관련 문서**를 공신력 있는 합법적 경로에서 확인해 공식 문서의 정확한 문장과 양사 식별자·독립 SHA/PIT 검토 증거를 비공개 저장하면, 이미 구현된 `scripts/review_supply_relation.py`에 입력한다.
- 공식 문서 본문 없이 `SupplyChainEdge`를 자동 승격하지 않는다. 관계 후보를 얻더라도 `BeneficiaryGraph` 수혜/피해는 가설이며, 실계약 이행·매출·수혜는 추가 검증 전 모두 미확정이다.
- 이번 기능은 **5_2 검토 입력 준비/실 공시 메타 처리**만 해결한다. 공식 본문·사람 검수 실증 및 5_3~5_5 실제 소비/5_6 정답셋 평가가 남아 있어 5_2 완료 판정은 유지 보류한다.
