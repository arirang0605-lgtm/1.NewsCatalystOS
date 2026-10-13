# 5_2 — 기존 DART/SEC 수신본의 기업명·공시제목·Form 검토 필터

2026-10-14. 기존 5_2 `official_review_queue`에 **선택적** 수신원본 메타 조회를 추가한 것이다. DART/SEC/KRX API를 다시 호출하거나 EraLeader 코드·DB·Git에 쓰지 않는다.

## 실제 데이터 신뢰 경계
- 입력 A: `output/<기존 완료-v2 게시폴더>/observations.json` + 완료 마커, **별도 보관된 payload SHA pin**. 기존 `published_observations.py`→`operational_observations.py`로 검증한다.
- 입력 B: EraLeader가 **이미 완료한 최초 DART/SEC raw first-capture**와 `official_api_pit_research.json`. **Mac 내부 독립 디스크**의 기존 `official_api_pit_research.pin.json`을 `pin_anchor.verify_with_local_anchor`가 확인한다. 각 first receipt/raw SHA 및 DART 14자리 공시번호·SEC accession ID 집합을 다시 검증하고, v2의 해당 문서 ID·소스별 원문 SHA·receipt SHA와 **정확히 일치**할 때만 기업명/보고서 제목/Form 필터를 허용한다.
- DART: `rcept_no` 기준 `corp_name`, `corp_code`, `stock_code`, `report_nm` 추출. SEC: 해당 수집본의 `name`/CIK/`tickers`와 각 accession별 `form`, `primaryDocDescription` 추출. 모두 **공식 API 응답에 기재된 메타데이터**이며 기업 신원 독립 공증·공시 본문/공개시각 증명이 아니다.
- `--issuer-contains`, `--title-contains`는 제공자 표기의 대소문자 무시 리터럴 부분일치, `--filing-form`은 SEC 제출 Form 등 정확한 유형을 선택한다. 이 **검색 필터는 종목 투자우선 순위나 공급망 실거래 순위가 아니다.**

## 실행 예
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/build_official_review_queue.py \
  --publication "/Volumes/T5DATA/1.NewsCatalystOS/output/<기존-완료-v2-게시폴더>" \
  --publication-root "/Volumes/T5DATA/1.NewsCatalystOS/output" \
  --payload-sha256 "<사전에 별도 보관한 v2 payload SHA>" \
  --with-pinned-issuer-context \
  --era-root "/Volumes/T5DATA/eraleader" \
  --era-report "/Volumes/T5DATA/eraleader/output/official_api_integrated_20261012/official_api_pit_research.json" \
  --independent-anchor "$HOME/Library/Application Support/NewsCatalystOS/pins/official_api_pit_research.pin.json" \
  --source-id sec-submissions --filing-form 10-Q --limit 100
```
- 위 조건을 `--source-id dart-disclosures --title-contains 계약`으로 바꾸면 DART 검토 후보를 좁힐 수 있다. **절대** SHA 없이 요청하거나 현재 raw 파일을 읽고 즉시 SHA를 계산해 독립적인 과거 공시 발행 증거라고 주장하지 않는다.
- 기존 옵션만 사용하면 **이전 v1 스키마 그대로 문서 ID·receipt만 포함한 큐**가 생성된다. 신뢰된 원본 메타가 결합된 검토 큐는 확장 **v2 스키마**로 명시한다. `--with-pinned-issuer-context`가 없는 상태에서는 회사명/보고서/Form 검색 옵션을 거부한다.
- 출력 `output/official_relation_review_queue_<id>/queue.json`의 `issuer_name_observed`, `issuer_namespace_observed`, `issuer_code_observed`, `filing_heading_observed`, `filing_type_observed` 등은 **원문에 적힌 출처의 보고 메타**다. `issuer_authority_attested=false`, `official_document_text_available=false`, `industry_relevance=UNKNOWN_UNSCREENED`, `supply_relation_status=UNREVIEWED`, `verified_real_transaction=false`. `semiconductor_keyword_hint_only`도 후보 검색 힌트일 뿐 공정·계약 인과관계의 증명이 아니다.

## 2026-10-14 Mac 실제 검증
- 이미 존재한 DART 첫 페이지 **100건**, SEC 단일 회사의 최근 제출 **1,001건** = 합계 **1,101건**, 기저 raw SHA와 완료 v2 문서 ID를 로컬에서 결합했다. SEC 수집본의 응답 보고 기업명은 **Apple Inc.**이며 10-Q 유형은 **33건**, 별도 private 큐 발행 성공.
- DART `--title-contains 계약` 1건의 원문 제목은 **주식 양수도 계약** 유형으로, 반도체 고객·공급계약이 아니다. 유효 공급관계 0건. **키워드 1건을 공급계약 1건으로 잘못 승격하지 않는 구조**가 유지됐다.
- 별도 출력은 NewsCatalystOS private `output/`에만 있으며 GitHub Public 미포함. 이 시험에서 사용자가 즉시 확인한 v2 파일의 SHA는 **같은 파일의 로컬 일관성 확인일 뿐 독립 보관 SHA 검증이 아님**; EraLeader 연구 참고본은 별도 Mac local TOFU anchor로 확인한 것으로 제3자 공식 공개시각 공증은 아니다.
- 5_2 실제 공식 문서 본문과 사람 검토 공급사/고객사 공식 ID가 준비되기 전에는 기존 `scripts/review_supply_relation.py` 및 `scripts/publish_reviewed_beneficiaries.py` 실증 완료로 선언하지 않는다. 합성/메타 검색 기능 추가만으로 **전체 36개 작업 완료 수는 올리지 않는다**.
