# 5_6 — 반도체 관계 후보의 독립 사례 평가 기능

기존 비공개 5_5 outbox를 **별도 보관한 payload SHA**로 읽고, 사람이 독립 검토한 사례 라벨과 결합해 정밀도·재현율·정확도·오탐·누락을 계산한다. 이 기능은 정답을 만들거나 수혜·실매출을 확정하지 않는다. 실자료 라벨 0건인 현재는 출시 인수 증거가 없다.

## 입력→출력
- `--manifest`: 소유자 전용(0600) JSON, `{"schema":"newscatalyst.semiconductor_evaluation_pins.v1","pins":[{"folder":"/absolute/private/outbox/reviewed_candidate_<SHA>","out_root":"/absolute/private/outbox","expected_sha256":"<별도 보관한 64자리 SHA>","graph_version":"v1"}]}`. 기업발표 v2는 `graph_version:"v2"`를 명시한다.
- `--labels`: 소유자 전용(0600) JSON, `{"schema":"newscatalyst.semiconductor_case_labels.v1","cases":[...]}`. 각 사례는 `event_sha256, document_sha256, supplier_namespace, supplier_id, customer_namespace, customer_id, product_stage, source_available_at, truth, reviewed_at, review_proof_sha256`를 포함한다. `truth`는 `BENEFICIARY`, `NOT_BENEFICIARY`, `UNRESOLVED` 중 하나다. 실제 검토자가 별도로 보관한 문서/검토 SHA와 시각을 입력한다.
- 동일 사건·문서·두 회사·제품 단계의 사례를 하나로 결합한다. 게시본이 없는 검토된 수혜 사례는 누락, 근거가 없는 수혜 후보는 오탐, 미확정 라벨과 라벨 없는 후보는 분모 밖 보류로 분리한다. 출력에는 사례 해시와 지표만 포함하며 회사명·원문은 출력하지 않는다.

```sh
PYTHONPATH=src python3 scripts/evaluate_semiconductor_cases.py \
  --manifest /absolute/private/pins.json --labels /absolute/private/labels.json
```

현재 5_6 코드 경로의 합성 입력 시험만 완료. `precision_target_on_supplied_labels`는 제공된 라벨에서 산술 목표를 만족한다는 뜻이고 `independent_real_case_gate_verified=false`는 실제 독립 라벨·대표 표본·출시 인수가 별도라는 뜻이다. 5_2 공식 관계 실증과 실제 5_6 사례 평가는 자료가 생길 때 진행한다.
