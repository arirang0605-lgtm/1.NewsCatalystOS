# 2_6 / 3_6 — 실제 승인 RSS의 독립 인적 정답 검수 준비

NewsCatalystOS V1.0. 기존 1_3→2_1~2_4→3_5 분석 결과와 완료 영수증만 재사용한다. 새로운 RSS/DART/SEC/KRX API 호출, 기사 원문 복제, AI 비용, EraLeader 변경은 없다.

## 2026-10-14 실제 Mac 실행
- 승인된 중기부 및 뉴스와이어 IT의 개인 `acked` 영수증 **6개**를 SHA/SQLite 성공 원장/출처 승인/PIT 및 완료된 1차 triage JSON으로 검증했다. 두 소스에 걸친 공급자+문서 ID+제목 SHA 버전을 결합하여 **실제 서로 다른 제목 39개**를 획득했다.
- `scripts/run_gold_review.py freeze`를 Mac에서 실제 실행, 원본 제목·링크·사건 SHA·기존 분류/중복 후보의 **이후 시각 기준 판정**을 동결했다. T5DATA 개인 `output/gold_review/gold_batch_<SHA>/`의 `predictions.json`, `blind_cases.json`, `human_review_template.json`, `publication.json`을 원자 게시하고, **별도 Mac 내부 디스크** `~/Library/Application Support/NewsCatalystOS/pins/live_gold/gold_batch_<SHA>.pin.json`에 예측/블라인드 검토표 SHA와 현 시점 핀 시각을 고정한다. SHA는 로컬 무결성 증거이며 제3자 공증이 아니다.
- 실제 배치 SHA: `fc78726376397adfcccebe2addd5080b3c006bcc7cc1c3ac4574e60498b3fcb6`. 실제 입력에 붙은 판정은 **2026-10-14 동결 당시** 상태이지 각 과거 보도시점에 알고 있던 동시 예측/역사적 탐지 성능을 의미하지 않는다.
- 맥북 소유자 전용 `~/Library/Application Support/NewsCatalystOS/gold_review_workspace/gold_batch_<SHA>/UNASSIGNED_A/answers.json` 및 `UNASSIGNED_B/answers.json`에 **정답을 전혀 쓰지 않은** 독립 답안지 사본 두 개를 만들었다. 샘플 원문 뉴스나 출력 DB는 GitHub에 올리지 않는다.
- 양 답안지를 그대로 `evaluate`에 통과시키면 **실샘플 39 / 인적 정답 판정 0 / 미결 39 / 목표까지 추가 461**, 중복 precision `N/A`, 중요 사건 recall `N/A`, 독립 정답셋 인증 `false`, 출시 게이트 `false`로 산출된다. 인위적인 합성 정답을 실제 검토로 승격하지 않는다.

## 운영 방법
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
# 실행 전 승인된 RSS 완료 영수증을 읽고 새 날짜/시각의 검증된 스냅샷 생성
PYTHONPATH=src python3 scripts/run_gold_review.py freeze
# 기존 배치 기준, 정답 없는 두 편집용 문서 생성 (자동 재작성/덮어쓰기 금지)
PYTHONPATH=src python3 scripts/run_gold_review.py draft \
  --batch-folder "$PWD/output/gold_review/gold_batch_<SHA>" \
  --expected-sha256 "<SHA>" \
  --pin-file "$HOME/Library/Application Support/NewsCatalystOS/pins/live_gold/gold_batch_<SHA>.pin.json"
# 각 실제 인적 검수 완료 후에만 (아래 문서는 경로 예시)
PYTHONPATH=src python3 scripts/run_gold_review.py evaluate \
  --batch-folder "$PWD/output/gold_review/gold_batch_<SHA>" \
  --expected-sha256 "<SHA>" \
  --pin-file "$HOME/Library/Application Support/NewsCatalystOS/pins/live_gold/gold_batch_<SHA>.pin.json" \
  --review-file "/Mac개인비공개경로/검수자A/answers.json" \
  --review-file "/Mac개인비공개경로/검수자B/answers.json"
```
- `blind_cases.json`에 원래의 승인된 RSS 제목/출처 링크/사건 SHA·원본 관측시각이 있으며, **중복·광고차단·중요도 예측값은 의도적으로 숨겼다.** `predictions.json`은 사람이 검수하는 동안 수정하지 않는다. `human_review_template.json`을 별도 검수자 두 명에게 각각 복사한다. 검수자는 `reviewer_code`의 `UNASSIGNED_A/B`를 실제 서로 다른 익명 내부 검수 코드로 변경하고, 각 건의 `true_duplicate`/`important_event`를 `true` 또는 `false`로 표시한다. 64자 `review_evidence_sha256`와 리뷰 완료 후 시각 `reviewed_at`(UTC offset 포함)도 검수자가 별도로 제공한다. 빈 입력은 `null` 유지하며 미검수로 집계한다. 서로 다른 코드가 곧 독립 인적 검수의 증명이 되는 것은 아니므로 실제 작업 증거는 별도 유지한다.
- 리뷰 코드가 `UNASSIGNED`인 채로 정답을 입력하면 입력을 차단한다. 리뷰별 SHA/PIT/케이스 문서 동질성, 한 건의 2인 판정 일치·충돌·누락을 기존 `gold_review_intake.py`, `filter_evaluation.py`, `detection_history.py`로 평가한다. 하나의 문서가 중복 ACK에 여러 번 등장해도 동일 제목 버전은 한 사례로 센다. 정답이 없으면 **precision/recall `N/A`**이고 임의의 100% 통과를 반환하지 않는다.

## 인수 조건과 미완료
- 지금 39건은 **실제 수신 뉴스 제목을 기준으로 한 검토 후보**이지 39건의 사람이 검수한 정답이 아니다. 표본이 2개 소스·제목 정보로 편향되어 있으므로 홀드아웃 독립성과 기사 원문 판별력, 반도체 실제 신규사건 성능을 주장할 수 없다.
- 2_6/3_6 인수에는 운영자의 실제 독립 판정 **최소 500건**, 판정 충돌 처리, 유효 분모를 갖춘 precision/recall, 실제 예측 성과 검토 등이 별도로 필요하다. 현재 **인적 gold=0, 461개 이상의 추가 실샘플 필요**, `release_gate_verified=false`. 4단계 실제 AI 공급자 연동, 5_2 실공식 반도체 거래, 6_5 5거래일 및 6_6 최종 배포 역시 미완료. 기존 완료수 **23/36**을 올리지 않는다.


## 2026-10-14 추가 실무 개발 — 기존 검수자료를 보존한 증분 고유 후보 누적
- `scripts/run_gold_review.py progress`: **읽기 전용** 검사. T5DATA의 모든 기존 `gold_batch_<SHA>` 예측·블라인드·원자공표와 Mac 독립 디스크 PIN을 검증한 후, 기존 승인 RSS ACK/SQLite/분석 SHA와 대조해 기존 고정 후보·새 미고정 후보·목표 500건 부족분을 계산한다. 신규 호출·신규 파일 생성/수정·자동 정답 기입 **0**.
- `scripts/run_gold_review.py freeze --new-only`: 기존 배치/검수자의 답안지 **전부 보존**, SHA/PIT 검증된 기존 후보와 중복되지 않는 실제 신규 제목 버전만 새 배치로 별도 원자 게시 후 Mac 독립 로컬 PIN 부여. 과거 배치 중 하나라도 SHA 변조·PIN 누락·상호 중복되면 전체를 fail-closed 중단. 기존 `freeze`의 기본 독립 스냅샷 동작은 유지하되 **향후 누적용에는 반드시 `--new-only`를 사용**한다. 과거에 있던 케이스를 다시 동결해 500개로 부풀리지 않는다.
- 실 Mac 실행: 기존 첫 배치 **39건**, 신규 검증된 뉴스 제목 버전 **17건**, 이번 배치 SHA `f98cd7054b67b1b22abdd4545e23fe0a67282ffd9b0afde0caa922a9de438b26`, 누적 서로 다른 후보 **56건**, 500까지 **444건 부족**. 실제 검수자 인적 답변은 기존/신규 모두 0, 정답 검증률 N/A 및 출시는 false. 이번 배치 신규 검토 답안지 `UNASSIGNED_A/B` 2개를 Mac 비공개 폴더에 생성했으나 **둘 다 정답 없는 빈 파일**이다. 두 답안지를 `evaluate` 호출해 신규 17건 모두 미검수/정확도 null 확인.
- 다음 체크 명령:
  ```sh
  cd /Volumes/T5DATA/1.NewsCatalystOS
  PYTHONPATH=src python3 scripts/run_gold_review.py progress
  # 신규 미동결 후보가 있을 때만, 과거 pinned batch/답안지는 건드리지 않고 별도 배치 생성
  PYTHONPATH=src python3 scripts/run_gold_review.py freeze --new-only
  ```
- 이번 56건은 **실제 승인 RSS 고유 검수 후보**, 독립 검수 완료 56건/투자재료 검증 56건이 아니다. 새로운 동결시각은 해당 시점의 판단이며 과거 예측 성능을 주장하지 않는다. 사용자 승인 별도 2인 실제 검토·500건 확보/소스 다양성·문서 실제 근거가 아직 필요. 더 많은 합성 검증으로 2_6·3_6 단계를 완료 처리하지 않는다. 5_2 실제 공식 반도체 계약·AI 실비용·6_5 5거래일·6_6 출시 조건도 그대로 미완료, **23/36** 유지.


## 2026-10-14 | 전체 배치의 실제 2인 검수 결과 통합 평가

- `PYTHONPATH=src python3 scripts/run_gold_review.py aggregate` — Mac과 T5DATA의 **모든 기존 PIN 고정 배치**를 읽기 전용 조회하고, 동일한 배치 ID 하위 두 검수 파일(`UNASSIGNED_A/answers.json` 및 `UNASSIGNED_B/answers.json`)을 개별 검증한 뒤 전체 합계를 산출한다. 새 RSS GET/AI 호출/원본·답안지 수정은 하지 않는다.
- 각 배치마다 SHA/PIT·완료 공표/블라인드 검수표와 두 검수자 답안지를 기존 `evaluate_live_gold_reviews`로 검증한다. 한 배치라도 중복 사례/독립 MAC PIN 누락/답안지 삭제·오류면 전체 집계를 중단한다. 실제 사람이 합의한 건수만 정확도에 반영하고 불일치/미검수는 별도 집계한다.
- 중복 precision은 **전체 배치 true_positive / (전체 true_positive + false_positive)**, 중요 사건 recall은 **전체 탐지 중요 건수 / 전체 실제 중요 건수**이다. 배치별 퍼센트의 단순평균은 사용하지 않는다. 평가 입력이 0이면 해당 비율은 `null`을 표시한다.
- 실제 Mac에서 기존 39건 + 17건의 두 배치·사용자가 작성한 두 쌍의 빈 검수 양식을 합산해 **표본 56, 2인 합의 0, 미검수 56, precision/recall N/A, 목표 500까지 후보 444건/인적 합의 500건 부족** 결과 확인. 이 결과는 실측 정답을 생성하거나 과거 시점의 실시간 예측 성능을 증명하지 않는다.
- `mathematical_threshold_met_on_supplied_labels`이 향후 true가 되더라도 검수자 독립성, 실제 사건 원문 근거·소스 다양성·검증된 과거 예측 성과를 자동 인증하지 않으며, `reviewer_independence_certified=false`, `source_diversity_certified=false`, `prospective_live_accuracy_certified=false`, `release_gate_verified=false`는 별도 최종 인수까지 유지한다. 2_6·3_6을 합성 라벨 테스트로 완료 처리하지 않는다.
