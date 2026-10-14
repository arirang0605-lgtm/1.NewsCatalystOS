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


## 2026-10-14 | 실제 검수자 개별 판정 입력 CLI (NC-HUMAN-REVIEW-ENTRY)

기존 2개 frozen 배치(39건 + 17건)는 수정하지 않고 Mac 개인 `gold_review_workspace`에 마련된 빈 답안지에 **실제 검수자의 직접 판단만** 입력할 수 있게 했다. 원본 뉴스 본문·개인 근거 메모는 Public GitHub에 올리지 않는다. 모든 명령은 맥북 터미널에서 직접 실행해야 하며, AI가 자동으로 yes/no 또는 검토 근거를 작성하는 기능은 없다.

1. 검수자 A가 현재 배치의 블라인드 뉴스 제목·링크·사건 SHA를 확인:
   ```sh
   cd /Volumes/T5DATA/1.NewsCatalystOS
   PYTHONPATH=src python3 scripts/run_gold_review.py review-list \
     --expected-sha256 '<배치의 기존 SHA>' --reviewer-slot UNASSIGNED_A --limit 10
   ```
   이 조회에서 예측값은 숨긴다. 검수자 B는 `UNASSIGNED_B`로 조회하며, 다른 검수자의 라벨을 열어보지 않고 실제 출처를 직접 검토한다.

2. 검수자는 기사 링크와 허용된 공식 근거를 독립 확인한 뒤, 본인 검수 폴더(`.../gold_batch_<SHA>/UNASSIGNED_A/`)에 `evidence_<case_sha256>.txt`를 **직접 작성하고 chmod 600**으로 잠근다. 여기에 출처 링크, 확인한 사실, 증거 위치와 판단 이유를 사람이 작성한다. 원문 유료 기사·키·개인정보를 복사하지 않는다. 이 파일은 외부에 전송하지 않으며 SHA256만 답안지에 기록된다.

3. 사람이 직접 사건 1건을 판정할 때에만 실행:
   ```sh
   PYTHONPATH=src python3 scripts/run_gold_review.py review-one \
     --expected-sha256 '<배치 SHA>' --reviewer-slot UNASSIGNED_A \
     --reviewer-code REVIEWER_A --case-sha256 '<검수할 사건 SHA>' \
     --true-duplicate false --important-event true \
     --evidence-file '<개인 슬롯>/evidence_<사건SHA>.txt' --confirm-human-review
   ```
   `true-duplicate`와 `important-event`는 검수한 사실에 맞춰 각각 true/false를 선택하며 **예시 값이 정답은 아니다**. 검수 종료시각은 시스템이 현재 UTC 시점으로 기록한다. 답안지 업데이트 전에 이전 내용을 Mac 슬롯 내부 `review_history/<case>.before.json`으로 따로 보존하고, 갱신 내용 SHA 영수증을 기록한 후 owner-only 답안지를 원자 교체한다. 이미 완료한 건은 덮어쓰기/수정 불가. 검수자 코드와 슬롯은 하나로 고정한다. 호출에 자동 뉴스 수집·AI 분석은 없다.

4. 실제 검수자 두 명의 입력이 끝나면 `PYTHONPATH=src python3 scripts/run_gold_review.py aggregate`로 전체 합계(진짜 2인 합의/충돌/미입력)를 조회한다. 동일 실제 2인의 독립성은 명령 실행만으로 인증할 수 없다. 검수자 진위와 자료 접근권한은 운영자가 별도 관리하고, 수치 성능/500건/V1 릴리스 게이트는 독립 실증까지 **false**다.

실 Mac에서 `review-list`로 신규 17건 미검수 후보 조회 PASS. 입력 기능은 합성 테스트에서만 판정 1건 및 A/B 분리 기록을 시험했고, 실제 뉴스의 사람이 검수한 정답은 **현재 0건**으로 유지한다.


## 2026-10-14 | 검수자 대화형 터미널 도우미

기존 `review-list`·`review-one`을 재구현하지 않고 연결하는 얇은 터미널 인터페이스:
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/review_news_interactive.py \
  --batch-sha256 "<동결된 배치 SHA>" \
  --slot UNASSIGNED_A --reviewer-code REVIEWER_A
```

실제 검수자 A는 자기 슬롯만 사용하고 B는 `UNASSIGNED_B` 및 다른 본인 코드로 별도 실행한다. 프로그램은 검수가 필요한 첫 번째 뉴스의 기존 허가 RSS 제목·링크·사건 SHA만 표시하고, **직접 출처 확인 여부**, **기존 사건의 중복 여부**, **경제적으로 중요한 신규 사건인지 여부**, **직접 작성한 확인근거 및 최종 확정**을 순서대로 질문한다. 코드에 정답이나 기본 yes/no가 없고 모델 예측도 공개하지 않는다. 거절/중단/잘못된 입력이면 답안지를 수정하지 않는다.

검수자가 직접 입력한 한 줄 근거만 Mac 개인 `evidence_<사건SHA>.txt`(0600)에 새로 저장하고, 기존 `record_review_once`로 과거 답안지 SHA 이력/원자 업데이트/중복 작성 금지를 처리한다. 한 번 호출하면 최대 한 사건만 처리하며 허용되지 않은 유료 기사 원문, API 키, 개인정보를 메모에 붙여넣지 않는다. **실제 독립 2인 검수와 원본 근거의 유효성은 운영자가 별도 확인해야 하며** 프로그램 입력만으로 실제 인적 독립성/accuracy/V1 출시를 인증하지 않는다. 사람 입력을 가정한 단위 테스트는 실제 사례의 라벨 1건으로 계산하지 않는다.

2026-10-14 오후 승인 RSS 추가 관측분 **9개 고유 제목 버전**이 기존 56개와 겹치지 않아 새 비공개 골드 묶음 SHA `fedd0b65882d2f99969c506db00e2e668c5548e6faf049e390d09d0dac05a4f7`로 동결됐다. Mac 별도 SHA PIN과 두 빈 검수자 답안지 생성 확인, 총 **65 후보**, 신규 정답 0건, 목표 500까지 **435건 부족**. 실제 인적 검수자는 아직 참여하지 않았다. 새 거래일·공식 반도체 계약 관계·실 AI 유료 호출이 완료된 것이 아니다.


### 승인 출처별 후보 구성을 반드시 확인

`run_gold_review.py progress`는 현재 승인 RSS를 중복 제거한 출처별 숫자(`by_current_approved_provider`), 다음 동결 대상 출처별 수(`new_unfrozen_by_provider`), 반도체 제목 키워드 **인적 검토 힌트** 수만 함께 표시한다. 실제 Mac 개인 원장의 2026-10-14 조회 결과는 중기부 RSS 23건, 뉴스와이어 IT RSS 42건, 총 고유 후보 65건, 새 미동결 0건, 반도체 관련 키워드 검토 힌트 1건이었다. **키워드 힌트 1건은 공식 공급계약·경제적 신규 사건의 검증 성공 1건을 뜻하지 않는다.** 두 출처의 편중된 제목만으로 반도체 공급망 성능 95%를 주장하지 않는다. 신규 출처는 사전 사용권한 승인이 없는 한 활성화하지 않는다.


## 2026-10-14 | 검수 제출 중단 시 원본·SHA 이력 복구

이미 사용 중인 `review-one` 및 대화형 검수는 원래의 원자적 답안 교체 직전에 이전 답안지(`<case>.before.json`)와 기존 로컬 영수증을 따로 남겼다. 맥북 절전·SSD 분리 등으로 교체가 중단되면 다음 검수를 진행할 수 없었다. 이를 해결하기 위해 **제출 직전의 완성 답안 문서(`<case>.proposed.json`)도 현재 Mac 개인 `review_history` 아래 0600으로 불변 보관**한다.

실제 검수자 본인이 판정하고 승인했던 그 케이스만 안전하게 복구할 때:
```sh
cd /Volumes/T5DATA/1.NewsCatalystOS
PYTHONPATH=src python3 scripts/run_gold_review.py review-recover \
  --expected-sha256 "<기존 gold_batch SHA>" \
  --reviewer-slot UNASSIGNED_A \
  --case-sha256 "<복구할 이전 사람 확정 사건 SHA>"
```

복구는 Mac PIN 고정 GoldBatch·원래 답안지·완성 예정 답안지의 두 SHA와 영수증, 실제 검수자 코드/검수 시각(PIT), 검토 근거 메모의 SHA까지 검사한다. **원래 답안지 상태와 정확히 동일하거나 이미 목표 완성 상태일 때만** 실행할 수 있다. 다른 사례 변경·검토자 변경·영수증 누락·근거 변경·기존 답안지 변경을 감지하면 거절한다. 이미 적용한 리뷰를 다시 입력하거나 새로운 라벨을 생성하지 않고, 이전 인간 확인시각으로 보존한다. 근거의 신뢰성·두 사람의 독립성은 별도 실운영 검증 필요하다.

이 기능은 새 사람을 가장하거나 라벨을 생성하지 않으며 새로운 DART/SEC/KRX/RSS/AI 호출도 하지 않는다. 현재 실제 뉴스 65건의 사람 검수 정답은 여전히 0건이다. 기존 사용자 파일과 EraLeader 데이터·코드는 변경하지 않았다.


## 2026-10-14 | 실제 500건 후보의 자동 증분 동결·검수양식 생성 (독립 RSS 서비스 보존)

- `scripts/run_gold_capture_once.py`는 **이미 수집·분석 완료된** 1_3→3_5 승인된 RSS ACK만 SHA/PIT로 검증한다. 별도 Mac `gold_capture.lock`의 배타 잠금을 잡고 `gold_freeze_progress`에 진짜 신규 제목 버전이 있을 때만 기존 `freeze_real_gold_review_cases(incremental_only=True)`를 호출한다. 새로운 T5DATA private 배치·Mac **다른 물리 디스크** PIN을 만들며, 검수자 A/B의 **비어 있는** 작업공간도 기존 `prepare_blank_human_review_sheets`를 재사용해 마련한다. 새 후보가 없으면 아무 배치도 추가하지 않는다.
- SSD PIN이 생성된 후 절전/오류로 빈 검수 공간 생성에 실패해도 다음 실행에서 **기존 PIN을 다시 검증하고 해당 검수 공간이 전혀 없는 경우에만** 빈 시트를 생성한다. 기존 인간 검수자가 일부라도 입력한 답안지·손상된 작업공간은 절대 초기화/덮어쓰기하지 않으며 오류로 중단한다. 한 번에 두 프로그램이 돌면 배타 잠금으로 후행 작업은 취소된다. 자동 인간 정답/AI 호출/기사 원문 저장/공식 API 중복 수집 기능은 없다.
- Mac에 기존 `com.newscatalystos.triage`와 **별개의 사용자 launchd** `com.newscatalystos.gold`를 **2026-10-14** 등록했다. 새로운 작업도 3,600초마다 실행하되 기존 RSS 작업 코드는 수정하지 않았다. `create_gold_agent.py --write`는 처음 설치할 때만 새 owner-only plist·개인 로그를 만들며 재설치 시 무단 덮어쓰기 금지. 소스 제한은 기존 승인 **중기부 보도자료 + 뉴스와이어 IT RSS 두 종**으로 고정한다. PIN/답안·로그/DB는 모두 개인 Mac·T5DATA에만 있고 GitHub 공개 대상이 아니다.
- 실제 Mac 첫 수집 구간에는 추가 뉴스 제목 버전 **5개**를 별도 고정하여 누적 **70건(4개 pinned 배치; 중기부 23, 뉴스와이어 IT 47)**이 됐다. 정상 no-new 반복 실행은 추가 0, 빈 검수 공간 0, total70/remaining430/사람정답0/AI0/추가 RSS HTTP0을 반환했다. `launchctl kickstart gui/$(id -u)/com.newscatalystos.gold` 이후 실제 launchd `runs=1,last exit code=0`, stderr 0바이트, 개인 stdout의 같은 결과를 검증했다. 기존 triage `runs=9,last exit code=0`. 실제 완료 영수증20건이지만 모두 **10월14일 하루**, 거래소 실운영 5일 인수는 여전히 false.
- 확인/중지: `PYTHONPATH=src python3 scripts/run_gold_capture_once.py`는 네트워크 사용 없이 즉시 한번 실행. `launchctl print gui/$(id -u)/com.newscatalystos.gold` 및 Mac `~/Library/Application Support/NewsCatalystOS/logs/gold_stdout.log`로 최근 상태 확인. 필요한 경우 `launchctl bootout gui/$(id -u)/com.newscatalystos.gold`로 **금 후보 자동 동결만 중지**할 수 있다(기존 RSS 수집은 유지). 자동 실행이 필요 없으면 plist는 사용자 승인하에 별도 보관·정리하며 자동 삭제하지 않는다.
- **운영 범위**: 승인된 RSS 제목 버전 및 자동 동결 시각의 2~3단계 모델/룰 상태. 이는 **인간 독립 골드 라벨 70건, 공식 반도체 거래 70건, 과거 보도 시점 동시 예측 70건을 인증하지 않는다.** 500 후보까지 430건, 인간 2명 확인 골드 0건, 정확도/재현율 N/A, V1.0 출시 false. 새 뉴스는 1시간 서비스의 실제 동결시각 이후 사용 가능하며 과거 공개시각으로 소급하지 않는다.


## 2026-10-14 | 반도체 V1.0 검증표본 편중 감시 (실데이터)

- 새 읽기전용 `PYTHONPATH=src python3 scripts/run_gold_review.py scope-audit`는 **전체 기동작 PIN 고정 배치**의 Mac 독립 SHA와 T5DATA 예측·블라인드 문서, 검수자 A/B 답안지를 다시 검증한 후 **출처별·성격별·반도체 키워드 힌트별 실제 표본 구성만** 집계한다. 검사 결과 JSON에 기사 제목, 링크, 키, 인간 메모, 모델의 사전 예측은 출력하지 않는다. 새 RSS/DART/SEC/KRX/AI 호출·답안 쓰기·공개 업로드 모두 0.
- **실제 Mac 결과(2026-10-14):** SHA 동결 4배치 / 고유 RSS 제목버전 **70건**, 중기부 공식기관 **23건**, 뉴스와이어 IT 배포 보도자료 **47건**. 반도체 제목에 기설정 키워드가 포함된 **검토 힌트 1건(1.4%)**, 다른 69건. 원본 RSS 첫 로컬 이용가능 날짜는 UTC 10월13~14일, 동결 PIN 날짜는 UTC 10월14일. 독립 사람 2명 동의 **0건**, 500개까지 고유 후보 추가 **430건**, 두 사람 합의 정답 추가 **500건**. `precision/recall` 인증 및 sector 적합도 인증 모두 false.
- 보도자료가 다른 배포 경로를 통해 전송되어도 독립 취재기사로 간주하지 않는다. 정부 보도자료와 배포 보도자료로 편중된 표본 500건을 단순히 채우는 방식은 반도체 산업 성능의 독립 검증으로 충분하지 않다. `SEMICONDUCTOR_KEYWORD_COVERAGE_NOT_REPRESENTATIVE`, `PRESS_RELEASES_ARE_NOT_INDEPENDENT_JOURNALISM`, `TWO_HUMAN_GOLD_LABELS_INCOMPLETE` 등을 **검토 경고**로 표시한다. 키워드가 없다고 관련성이 확실히 없다는 것도 아니므로 제목 힌트를 골드 정답으로 취급하거나 자동 제외하지 않는다.
- 다음에는 실제 허가된 반도체 기업 IR·정부 산업 정책·검증된 독립 취재 자료 등 **새 자료원 권한/라이선스를 먼저 확인**하고 추가 데이터를 확보해야 한다. 기존 EraLeader DART·SEC·KRX의 기게시 스냅샷은 계속 읽기전용이며 NewsCatalystOS의 중복 공식 수집기 신설 금지. V1.0 2_6/3_6 **실측 완료 판정은 보류**한다.
