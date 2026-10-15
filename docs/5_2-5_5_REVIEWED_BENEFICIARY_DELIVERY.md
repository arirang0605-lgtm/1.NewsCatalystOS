# 5_2 → 5_5: 검토된 공식 반도체 공급망 관계의 비공개 전달

> 현재 기준은 D-060/D-059이다. 사람 검수 절차와 관련 도구는 삭제했다. 아래 실행 기록은 당시 기록이며 현재 완료 상태는 PROJECT_STATE.md를 따른다.

NewsCatalystOS V1.0의 실제 기능 경로다. EraLeader의 정상 공시 수집기·코드·DB·Git을 변경하거나 DART/SEC/KRX 데이터를 중복 수집하지 않는다. 계약·매출·수혜기업을 자동 확정하지 않는다.

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

## 별도 소비자 프로세스 실행 검증
- 2026-10-14 Mac에서 **명확히 합성임을 표시한 임시 DART 검토 픽스처**만 별도 `/private/tmp`에 만들고, 기존 오프라인 검토→파급 분석→outbox SHA 게시 후 독립 Python 프로세스로 `consume_reviewed_beneficiaries.py`를 직접 실행했다. `CHILD_EXIT=0`, `REVIEW_CANDIDATES=1`, `MACHINE_READABLE_EDGES=1`, `VERIFIED_REAL_BENEFITS=0`. 원본/임시 산출물은 보안된 임시 경로에서 정리되며 공개 Git에 포함되지 않는다.
- 이는 **독립 프로세스의 읽기 전용 파일 계약을 실행**한 증거이며, 실제 EraLeader 프로젝트 또는 후속 자동매매 프로그램이 연동됐다는 주장도 실제 공식 반도체 거래 사실을 검증했다는 주장도 아니다. 관계 실증 0건, 실제 매출 확정 0건, 외부 프로젝트 코드 수정 0건으로 유지한다.
