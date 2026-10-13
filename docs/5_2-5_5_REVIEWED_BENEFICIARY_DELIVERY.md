# 5_2 → 5_5: 검토된 공식 반도체 공급망 관계의 비공개 전달

NewsCatalystOS V1.0의 실제 기능 경로다. EraLeader의 정상 공시 수집기·코드·DB·Git을 변경하거나 DART/SEC/KRX 데이터를 중복 수집하지 않는다. 계약·매출·수혜기업을 자동 확정하지 않는다.

## 생산 경로
1. 기존 `newscatalyst.observed_official_batch.v2` 완료 게시본과 **미리 별도 보관한 SHA pin**을 재검증한다.
2. 운영자가 권한을 갖고 확인한 **원 공식 제출 문서의 UTF-8 텍스트**, 별도 SHA pin, 검토 JSON, 공급사·고객사 공식 식별자 두 개, 문서 속 직접 관계 문장을 기존 `official_relation_intake.py`에서 검증한다. 같은 원문에서 공식 관계를 찾지 못하거나 파일/검토 증빙이 누락되면 `DATA_UNAVAILABLE`이며 출력하지 않는다.
3. 기존 `semiconductor_profile.py`→`semiconductor_impact.py`→`beneficiary_classification.py`→`beneficiary_graph_contract.py`의 **반도체 단일 산업 파급 경로**를 호출한다. 경제 효과 방향은 기본값 `UNKNOWN`이다. `--direction POSITIVE/NEGATIVE`로 사람이 가설을 선택해도 확정 사실이 아니며, 실제 매출 수혜/거래 이행은 여전히 `false`다.
4. `output/consumer_outbox/reviewed_candidate_<payload SHA>/beneficiary_graph.json`과 `publication.json`을 owner-only 개인 폴더에 **원자적 게시**한다. 다른 프로젝트가 정해지지 않았으므로 EraLeader, CoreAStock, MarketOS 어느 코드에도 자동 기록하지 않는다.

```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/publish_reviewed_beneficiaries.py \
  --publication "/Volumes/T5DATA/1.NewsCatalystOS/output/<완료-v2-게시폴더>" \
  --publication-root "/Volumes/T5DATA/1.NewsCatalystOS/output" \
  --payload-sha256 "<별도-보관-신뢰-SHA>" \
  --review-json "/절대경로/owner-private/review.json" \
  --document-text "/절대경로/허용된-공식원문.txt" \
  --document-sha256 "<별도-보관-원문-SHA>" \
  --trigger PACKAGING_CAPACITY --direction UNKNOWN
```

입력 공식 원문/검토 파일의 읽기 권한은 사용자가 승인한 것에 한정하고, 해당 텍스트는 공개 GitHub·출력 JSON에 복사하지 않는다. 사전 별도 신뢰 PIN을 방금 입력 파일에서 계산해 독립 증거라고 주장하지 않는다. `--trigger`는 `semiconductor_profile.CAUSES`의 7개 원인만 허용한다. 관계 제품 단계가 파급 경로에 부합하지 않으면 `UNKNOWN_RELATIONSHIP`이지 수혜 확정이 아니다.

## 타 프로젝트에서 읽기 전용 소비
- 발행 CLI가 보고한 **payload SHA를 운영자가 별도 경로로 안전하게 전달**한다. 소비자는 기존 게시 본문·완료 마커·파일 SHA·검토된 공식 회사 식별자·PIT 가용 시각을 확인한다. 발행 파일 내용을 변경하거나 오염된 마커의 자기 SHA를 신뢰하지 않는다.
- 후속 프로젝트 연결 대상이 확정되기 전에도 독립 실행 가능한 예시 소비자 `consume_reviewed_beneficiaries.py`가 있다. **파일을 읽을 뿐 자동으로 다른 프로젝트를 변경하지 않는다.** 반환하는 `candidate_edges`에는 공급사·고객사 공식 기업 ID namespace/ID, 제품 단계, 문서 SHA, 검토 SHA, 관계 시각, 관계 종류, 가설적 수혜 분류가 있다. `verified_real_transaction=false`, `verified_real_benefit=false`, `estimated_revenue_krw=null`, `market_action=null`을 유지한다.

```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/consume_reviewed_beneficiaries.py \
  --folder "/Volumes/T5DATA/1.NewsCatalystOS/output/consumer_outbox/reviewed_candidate_<SHA>" \
  --out-root "/Volumes/T5DATA/1.NewsCatalystOS/output/consumer_outbox" \
  --expected-sha256 "<소비자가 별도로 보관한-SHA>"
```

## 인수 및 현재 상태
- 이번 개발은 **합성 공식문서**에 대해 DART/SEC v2 공시 메타→사람 검토→관계 후보→가설적 파급→수혜 후보→SHA outbox→외부 읽기 전용 소비를 시험한다. 정상 경로뿐 아니라 누락 원문/변조/미래시점/타 산업/회사 ID/중복 게시/부당한 수혜 확정을 차단한다.
- **실제 승인된 반도체 공식 공급사–고객사 관계문장/두 공식 기업 식별자의 인적 검수는 아직 0건.** 기존 실 DART 100건+SEC 1,001건은 공시 메타만 있어 실제 원문/관계를 증명하지 못한다. 따라서 실물 outbox 발행/외부 프로젝트 소비 완료를 주장하지 않고 `5_2~5_5` 완료 판정은 유지 보류한다.
- 기존 Mac 뉴스 검색·1시간 launchd·6_5 로컬 DR/5거래일 진행, AI 공급자 실호출/500건 gold/반도체 정확도/6_6 릴리스 판정도 별도 조건이다. 이 기능의 구현은 완료 36단계 수를 임의 늘리지 않는다.

## 별도 소비자 프로세스 실행 검증
- 2026-10-14 Mac에서 **명확히 합성임을 표시한 임시 DART 검토 픽스처**만 별도 `/private/tmp`에 만들고, 기존 오프라인 검토→파급 분석→outbox SHA 게시 후 독립 Python 프로세스로 `consume_reviewed_beneficiaries.py`를 직접 실행했다. `CHILD_EXIT=0`, `REVIEW_CANDIDATES=1`, `MACHINE_READABLE_EDGES=1`, `VERIFIED_REAL_BENEFITS=0`. 원본/임시 산출물은 보안된 임시 경로에서 정리되며 공개 Git에 포함되지 않는다.
- 이는 **독립 프로세스의 읽기 전용 파일 계약을 실행**한 증거이며, 실제 EraLeader 프로젝트 또는 후속 자동매매 프로그램이 연동됐다는 주장도 실제 공식 반도체 거래 사실을 검증했다는 주장도 아니다. 관계 실증 0건, 실제 매출 확정 0건, 외부 프로젝트 코드 수정 0건으로 유지한다.
