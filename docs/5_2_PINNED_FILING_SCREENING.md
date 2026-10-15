# 5_2 — 기존 DART/SEC 수신본의 기업명·공시제목·Form 검토 필터

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

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
